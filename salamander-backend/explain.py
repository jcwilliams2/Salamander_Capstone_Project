import json
import time
from collections import Counter
import numpy as np

FIT_BANDS = [(90, "a strong match"), (70, "a good match"), (40, "a moderate match")]
FIT_FLOOR = "a looser match"

CACHE_SECONDS = 600
_catalog_cache = {"at": 0.0, "matrix": None}

ANCHOR_FLOOR = 0.35
STRONG_ANCHOR = 0.45
CENTROID_STATUSES = {"finished", "reading", "dnf"}

def _vector(emb):
    if emb is None:
        return None
    if isinstance(emb, str):
        emb = json.loads(emb)
    vec = np.asarray(emb, dtype=float)
    if vec.size == 0 or not np.linalg.norm(vec):
        return None
    return vec

def _cosine(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def _is_negative(book, vote):
    return vote == -1 or (book.get("status") == "dnf" and vote != 1)

def _is_positive(book, vote):
    return not _is_negative(book, vote) and (book.get("status") == "finished" or vote == 1)

def positive_anchors(user_books, feedback):
    anchors = []
    for book in user_books:
        vote = feedback.get(book["id"], 0)
        if not _is_positive(book, vote):
            continue
        vec = _vector(book.get("embedding"))
        if vec is not None:
            anchors.append((book, vec, vote))
    return anchors

def closest_anchor(target_id, target_vec, anchors):
    best = None
    for book, vec, vote in anchors:
        if book["id"] == target_id:
            continue
        sim = _cosine(target_vec, vec)
        if best is None or sim > best[1]:
            best = (book, sim, vote)
    return best

def catalog_similarities(centroid, loader, now=None):
    now = time.time() if now is None else now
    if _catalog_cache["matrix"] is None or now - _catalog_cache["at"] > CACHE_SECONDS:
        vecs = [v for v in (_vector(r.get("embedding")) for r in loader()) if v is not None]
        if not vecs:
            return None
        matrix = np.vstack(vecs)
        _catalog_cache["matrix"] = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
        _catalog_cache["at"] = now
    unit = np.asarray(centroid, dtype=float)
    unit = unit / np.linalg.norm(unit)
    return _catalog_cache["matrix"] @ unit

def fit_percentile(sim, catalog_sims):
    if catalog_sims is None or len(catalog_sims) == 0:
        return None
    return int(round(100 * float(np.mean(np.asarray(catalog_sims) <= sim))))

def fit_label(percentile):
    if percentile is None:
        return None
    for floor, label in FIT_BANDS:
        if percentile >= floor:
            return label
    return FIT_FLOOR

def genre_profile(user_books, feedback):
    enjoyed, unfavored = Counter(), Counter()
    for book in user_books:
        vote = feedback.get(book["id"], 0)
        tags = {str(t).strip().casefold() for t in (book.get("genre_tags") or []) if t}
        if _is_positive(book, vote):
            enjoyed.update(tags)
        elif _is_negative(book, vote):
            unfavored.update(tags)
    return enjoyed, unfavored

def genre_reasons(tags, enjoyed, unfavored, limit=2):
    shared, new, caution = [], [], []
    for tag in tags or []:
        key = str(tag).strip().casefold()
        up, down = enjoyed.get(key, 0), unfavored.get(key, 0)
        if up > down:
            shared.append(tag)
        elif down > up:
            caution.append(tag)
        elif up == 0 and down == 0:
            new.append(tag)
    return shared[:limit], new[:limit], caution[:limit]

def _join(items):
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} and {items[-1]}"

def _fit_sentence(label, scope, lead, soft=False):
    text = f"{label} for {scope}"
    if label == FIT_FLOOR:
        text += "" if soft else ", so it may be outside your usual reading"
    return f"Overall, {text}." if lead else f"{text[0].upper()}{text[1:]}."

def own_state(target_id, user_books, feedback):
    status = next((b.get("status") for b in user_books if b["id"] == target_id), None)
    vote = feedback.get(target_id, 0)
    if status is None and vote == 0:
        return None
    return {"status": status, "vote": vote}

def verdict_sentence(own):
    status, vote = own["status"], own["vote"]
    thumbs = {1: "gave it a thumbs up", -1: "gave it a thumbs down"}.get(vote)
    lead = {"finished": "You finished this", "dnf": "You stopped reading this", "reading": "You're reading this now"}.get(status)
    if lead:
        return f"{lead} and {thumbs}." if thumbs else f"{lead}."
    if status == "want_to_read":
        return f"It's on your Want to Read list, and you {thumbs}." if thumbs else "It's on your Want to Read list."
    if thumbs:
        return f"You {thumbs.replace('gave it', 'gave this')}."
    return None

def _safely(fn, * args):
    try:
        return [t for t in (fn(*args) or []) if t]
    except Exception:
        return []

def explain_book(target, user_books, feedback, rec_centroid, catalog_sims, tags=None, themes_for=None, contrast_for=None):
    result = {"book_id": target["id"], "explanation": "", "similar_to": None, "fit": None, "percentile": None,
                "shared_genres": [], "new_genres": [], "unfavored_genres": [], "own": None,
                "themes": [], "contrast_themes": [], "anchor_score": None}
    vec = _vector(target.get("embedding"))
    if vec is None:
        result["explanation"] = "We can't compare this book to your taste yet, because it doesn't have enough description data."
        return result

    own = own_state(target["id"], user_books, feedback)
    verdict = verdict_sentence(own) if own else None
    result["own"] = own if verdict else None
    in_centroid = bool(verdict) and own["status"] in CENTROID_STATUSES

    anchor = closest_anchor(target["id"], vec, positive_anchors(user_books, feedback))
    if anchor is not None and anchor[1] < ANCHOR_FLOOR:
        anchor = None
    if rec_centroid is not None and not in_centroid:
        centroid = _vector(rec_centroid)
        if centroid is not None:
            result["percentile"] = fit_percentile(_cosine(vec, centroid), catalog_sims)
            result["fit"] = fit_label(result["percentile"])

    strong_anchor = anchor is not None and anchor[1] >= STRONG_ANCHOR
    contrast = []
    if result["fit"] == FIT_FLOOR and contrast_for and not strong_anchor:
        contrast = _safely(contrast_for)
    result["contrast_themes"] = contrast

    others = [b for b in user_books if b["id"] != target["id"]]
    enjoyed, unfavored = genre_profile(others, feedback)
    shared, new, caution = genre_reasons(tags, enjoyed, unfavored) if (enjoyed or unfavored) else ([], [], [])
    if verdict:
        new = []
    result["shared_genres"], result["new_genres"], result["unfavored_genres"] = shared, new, caution

    genre_parts = []
    if shared:
        genre_parts.append(f"It shares genres you've enjoyed: {_join(shared)}.")
    elif new:
        genre_parts.append(f"This is new territory for you: {_join(new)}.")
    if caution:
        genre_parts.append(f"Heads up: you've downvoted or stopped books tagged {_join(caution)}.")

    contrast_part = []
    if contrast:
        lead_in = "But it" if shared else "It"
        contrast_part = [f"{lead_in} leans on {_join(contrast)}, which is further from your usual reading."]

    parts = [verdict] if verdict else []
    if anchor:
        book, sim, vote = anchor
        verb = "liked" if vote == 1 else "finished"
        result["anchor_score"] = round(float(sim), 2)
        themes = _safely(themes_for, book["id"]) if themes_for else []
        result["themes"] = themes
        if result["fit"] == FIT_FLOOR and not strong_anchor:
            lead = f"The closest book you've {verb} is '{book['title']}'"
        else:
            lead = f"Similar to '{book['title']}', which you {verb}"
        parts.append(f"{lead}, and both touch on {_join(themes)}." if themes else f"{lead}.")
        result["similar_to"] = {"id": book["id"], "title": book["title"]}
        parts += genre_parts + contrast_part
        if result["fit"]:
            scope = "your reading as a whole" if (strong_anchor and result["fit"] == FIT_FLOOR) else "your current taste"
            parts.append(_fit_sentence(result["fit"], scope, lead=True, soft=strong_anchor or bool(contrast)))
    elif result["fit"]:
        parts += genre_parts + contrast_part
        parts.append(_fit_sentence(result["fit"], "your reading so far", lead=bool(parts), soft=bool(contrast)))
    elif verdict:
        parts += genre_parts
    else:
        shown = [t for t in (tags or []) if t][:3]
        if shown:
            parts.append(f"Tagged {', '.join(shown)}.")
        parts.append("Finish or rate a few books and we'll be able to compare it to your taste.")
    result["explanation"] = " ".join(parts)
    return result