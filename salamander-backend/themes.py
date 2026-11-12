import re
import numpy as np

THRESHOLD = 0.3
MAX_CANDIDATES = 80

STOPWORDS = frozenset(
    "a an the and or but of in on at to for from with by as is are was were be been being it its this that "
    "these those he she they his her their him them who whom which what when where while after before into "
    "over under about against between through during without within not no nor so than too very can will just "
    "one two also has have had do does did all any each more most other some such only own same "
    "you your yours we our us my me i if then there here next many several every another until because "
    "could would should might must may near deep using used eleven twelve three four five six seven eight nine ten "
    "up down out off how why while whose itself himself herself themselves myself yourself ourselves "
    "behind beyond gone toward towards upon among along across around".split()
)

GENERIC = frozenset(
    "novel novels book books story stories tale author authors bestselling bestseller bestsellers times york new "
    "winner award awards awardwinning acclaimed prize review reviews edition series volume read reader readers "
    "first classic masterpiece debut brilliant powerful gripping compelling international internationally "
    "national page pages chapter chapters bibliographic record records reprint reprints reproduction "
    "facsimile novelist writer writers young old little great good big small large literary fiction nonfiction narrative everyday impactful alive "
    "ebook ebooks kindle audiobook paperback hardcover isbn publisher copyright "
    "bookstore bookstores bookshop bookshops greatest best finest worst racist".split()
)

VERBS = frozenset(
    "includes include including tells tell starts start follow follows following offers offer offering destroys destroy "
    "died dies die named name names takes take makes make becomes become finds find brings bring begins begin "
    "learns learn discovers discover examines examine provides provide explains explain traces trace presents present "
    "features feature contains contain introduces introduce reveals reveal uncovers uncover explores explore shows show "
    "sees see goes go comes come gets get gives give keeps keep leaves leave lives live looks look needs need "
    "turns turn wants want works work tries try asks ask believes believe falls fall help help holds hold "
    "knows know leads lead meets meet moves move plays play puts put runs run says say tells thinks think "
    "tracks uses use sued sues sue marries marry wrest leaving leaves gone achieve evade tames written "
    "cause causes caused causing writes write writing wrote".split()
)

ADJECTIVE_ENDINGS = ("ial", "ical", "ous", "ive", "ful", "less", "ible", "able", "ish", "ic")
ADJECTIVE_NOUNS = frozenset({"music", "magic", "logic", "politic", "physics", "ethics", "critic", "comic", "epic", "mystic",
                                "classic", "tactic", "traffic", "republic", "panic", "arctic", "antarctic", "fabric", "rhetoric",
                                "romantic", "fantastic", "mathematic", "genetic", "graphic", "organic", "plastic", "article"})
LY_NOUNS = frozenset({"family", "italy", "ally", "lily", "belly", "jelly", "bully", "assembly", "anomaly", "rally"})
_SENTENCE_SPLIT = re.compile(r"[.,!?;:—–()\"\n]+")
_WORD = re.compile(r"[a-z][a-z'\-]*")

def _proper_names(text):
    names = set()
    capitalized, lowercase = {}, set()
    for sentence in _SENTENCE_SPLIT.split(text or ""):
        tokens = re.findall(r"[A-Za-z][A-Za-z'\-]*", sentence)
        for position, token in enumerate(tokens):
            key = token.lower().strip("'-")
            if token[0].isupper() and not token.isupper():
                capitalized[key] = capitalized.get(key, 0) + 1
                if position > 0:
                    names.add(key)
            elif token.islower():
                lowercase.add(key)
    names |= {w for w, n in capitalized.items() if n>= 2 and w not in lowercase}
    return names

def looks_english(text, minimum=0.12):
    words = re.findall(r"[a-z']+", (text or "").lower())
    if len(words) < 8:
        return False
    return sum(1 for w in words if w in STOPWORDS) / len(words) >= minimum

def candidate_phrases(text, avoid=(), max_candidates=MAX_CANDIDATES):
    avoid = {w.casefold() for w in avoid} | _proper_names(text)
    stems = {w[:5] for w in avoid if len(w) >= 6}
    counts = {}
    for sentence in _SENTENCE_SPLIT.split((text or "").lower()):
        raw = _WORD.findall(sentence)
        words = [w.strip("'-") for w in raw]
        for n in (1, 2):
            for i in range(len(words) - n + 1):
                if any("'" in w for w in raw[i: i + n]):
                    continue
                gram = words[i: i + n]
                if any(w in STOPWORDS for w in gram):
                    continue
                if any(w in GENERIC or w in VERBS or w in avoid for w in gram):
                    continue
                if any(len(w) >= 6 and w[:5] in stems for w in gram):
                    continue
                if any(len(w) > 4 and w.endswith("ed") for w in gram):
                    continue
                if n == 1 and len(gram[0]) < 4:
                    continue
                if any(w.endswith("ly") and w not in LY_NOUNS for w in gram):
                    continue
                if n > 1 and gram[-1].endswith("ing"):
                    continue
                if n > 1 and gram[-1].endswith(ADJECTIVE_ENDINGS):
                    continue
                if n == 1 and gram[0].endswith(ADJECTIVE_ENDINGS) and gram[0] not in ADJECTIVE_NOUNS:
                    continue
                if any(len(w) < 3 for w in gram):
                    continue
                phrase = " ".join(gram)
                counts[phrase] = counts.get(phrase, 0) + 1
    ordered = sorted(counts, key=lambda p: (-counts[p], -len(p), p))
    return ordered[:max_candidates]

def _unit(matrix):
    matrix = np.asarray(matrix, dtype=float)
    norms = np.linalg.norm(matrix, axis=-1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms

def _overlaps(phrase, chosen):
    return any(phrase in c or c in phrase for c in chosen)

def _pick(phrases, scores, vecs, limit, lam=0.7):
    chosen, chosen_idx = [], []
    remaining = list(range(len(phrases)))
    while remaining and len(chosen) < limit:
        best, best_val = None, None
        for i in remaining:
            if _overlaps(phrases[i], chosen):
                continue
            redundancy = max((float(vecs[i] @ vecs[j]) for j in chosen_idx), default=0.0)
            value = lam * scores[i] - (1 - lam) * redundancy
            if best_val is None or value > best_val:
                best, best_val = i, value
        if best is None:
            break
        chosen.append(phrases[best])
        chosen_idx.append(best)
        remaining.remove(best)
    return chosen

def shared_themes(text_a, text_b, embed, limit=2, avoid=(), min_score=THRESHOLD):
    if not text_a or not text_b or len(text_a) < 40 or len(text_b) < 40:
        return []
    if not (looks_english(text_a) and looks_english(text_b)):
        return []
    avoid = set(avoid) | _proper_names(text_a) | _proper_names(text_b) | _proper_names(f"{text_a}\n{text_b}")
    phrases = list(dict.fromkeys(candidate_phrases(text_a, avoid) + candidate_phrases(text_b, avoid)))
    if not phrases:
        return []
    vecs = _unit(embed([text_a, text_b] + phrases))
    doc_a, doc_b, pvecs = vecs[0], vecs[1], vecs[2:]
    scores = np.minimum(pvecs @ doc_a, pvecs @ doc_b)
    keep = [i for i in range(len(phrases)) if scores[i] >= min_score]
    if not keep:
        return []
    return _pick([phrases[i] for i in keep], [scores[i] for i in keep], pvecs[keep], limit)

def contrast_themes(text, centroid, embed, limit=2, avoid=(), min_score=THRESHOLD):
    if not text or len(text) < 40 or centroid is None or not looks_english(text):
        return []
    phrases = candidate_phrases(text, avoid)
    if not phrases:
        return []
    vecs = _unit(embed([text] + phrases))
    doc, pvecs = vecs[0], vecs[1:]
    cent = _unit(np.asarray(centroid, dtype=float))
    in_book = pvecs @ doc
    scores = in_book - pvecs @ cent
    keep = [i for i in range(len(phrases)) if in_book[i] >= min_score]
    if not keep:
        return []
    return _pick([phrases[i] for i in keep], [scores[i] for i in keep], pvecs[keep], limit)