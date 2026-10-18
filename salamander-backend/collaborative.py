import time
import numpy as np

from recommend import (
    supabase,
    get_book_weight,
    get_rejected_books,
    filter_similar_to_rejected,
    get_catalog_with_embeddings,
    get_user_books_with_feedback,
    get_user_centroids,
    get_books_by_status,
    query_similar_books,
    explore_rerank,
    explain_recommendation,
    cosine_distance,
    _to_vector,
    personalized_recommend,
)

USE_SYNTHETIC_PEERS = True
SYNTHETIC_PEER_COUNT = 200
SYNTHETIC_SEED = 7
MODEL_TTL_SECONDS = 600
ALPHA_MAX = 0.5
ALPHA_RAMP_BOOKS = 20
MIN_BOOKS_FOR_CF = 3
SHRINKAGE = 2.0

_model_cache = {"model": None, "built_at": 0.0}

def cf_preference(status, vote):
    if status == "want_to_read" or status == "dnf" or vote == -1:
        return 0.0
    return float(get_book_weight(status, vote))

def build_matrix(profiles, item_ids):
    index = {b: i for i, b in enumerate(item_ids)}
    m = np.zeros((len(profiles), len(item_ids)))
    for u, user in enumerate(profiles):
        for book_id, pref in profiles[user].items():
            if pref > 0 and book_id in index:
                m[u, index[book_id]] = pref
    return m, index

def item_similarity(matrix, shrinkage=SHRINKAGE):
    norms = np.linalg.norm(matrix, axis=0)
    safe = np.where(norms == 0, 1.0, norms)
    sim = (matrix.T @ matrix) / np.outer(safe, safe)
    present = (matrix > 0).astype(float)
    co = present.T @ present
    sim = sim * (co / (co + shrinkage))
    np.fill_diagonal(sim, 0.0)
    sim[norms == 0, :] = 0.0
    sim[:, norms == 0] = 0.0
    return sim

def build_cf_model(profiles, item_ids):
    matrix, index = build_matrix(profiles, item_ids)
    return {"sim": item_similarity(matrix), "index": index, "ids": list(item_ids), "n_users": matrix.shape[0]}

def rank_cf(pref_by_book, model, exclude_ids=(), n=10):
    index, sim, ids = model["index"], model["sim"], model["ids"]
    liked = [(index[b], p) for b, p in pref_by_book.items() if p > 0 and b in index]
    if not liked:
        return []
    cols = np.array([i for i, _ in liked])
    prefs = np.array([p for _, p in liked])
    block = sim[:, cols]
    den = np.abs(block).sum(axis=1)
    num = block @ prefs
    scores = np.divide(num, den, out=np.zeros_like(num), where=den > 0)
    best_liked = cols[np.argmax(block, axis=1)]
    skip = {index[b] for b in exclude_ids if b in index}
    out = []
    for i in np.argsort(-scores, kind="stable"):
        if den[i] <= 0 or i in skip:
            continue
        out.append((ids[i], float(scores[i]), ids[best_liked[i]]))
        if len(out) == n:
            break
    return out

def generate_synthetic_peers(catalog, n_users=SYNTHETIC_PEER_COUNT, seed=SYNTHETIC_SEED):
    rng = np.random.default_rng(seed)
    books = sorted(catalog, key=lambda b: b["id"])
    if not books:
        return {}
    ids = [b["id"] for b in books]
    pop = 1.0 / (rng.permutation(len(ids)) + 1.0) ** 0.8
    genre_pool = {}
    for i, b in enumerate(books):
        for g in b.get("genre_tags") or []:
            genre_pool.setdefault(g, []).append(i)
    genres = sorted(g for g, members in genre_pool.items() if len(members) >= 5)
    statuses = ["finished", "reading", "dnf", "want_to_read"]
    status_p = [0.70, 0.05, 0.10, 0.15]
    peers = {}
    for u in range(n_users):
        home = list(rng.choice(genres, size=min(len(genres), int(rng.integers(1, 3))), replace=False)) if genres else []
        home_idx = sorted({i for g in home for i in genre_pool[g]})
        n_books = int(rng.integers(6, 21))
        chosen, guard = set(), 0
        while len(chosen) < min(n_books, len(ids)) and guard < 500:
            guard += 1
            pool = home_idx if (home_idx and rng.random() < 0.75) else range(len(ids))
            pool = np.array(list(pool))
            chosen.add(int(rng.choice(pool, p=pop[pool] / pop[pool].sum())))
        log = {}
        for i in sorted(chosen):
            status = str(rng.choice(statuses, p=status_p))
            if status == "finished":
                vote = int(rng.choice([1, 0, -1], p=[0.50, 0.40, 0.10]))
            elif status == "dnf":
                vote = int(rng.choice([0, -1], p=[0.6, 0.4]))
            else:
                vote = 0
            log[ids[i]] = (status, vote)
        peers[f"synthetic-{u:04d}"] = log
    return peers

def to_preferences(log):
    return {b: cf_preference(s, v) for b, (s, v) in log.items()}

def _fetch_all(table, columns):
    rows, start = [], 0
    while True:
        batch = supabase.table(table).select(columns).order("user_id").range(start, start + 999).execute().data
        rows += batch
        if len(batch) < 1000:
            return rows
        start += 1000

def load_real_profiles():
    votes = {(r["user_id"], r["book_id"]): r["vote"] for r in _fetch_all("feedback", "user_id, book_id, vote")}
    logs = {}
    for r in _fetch_all("reading_status", "user_id, book_id, status"):
        logs.setdefault(r["user_id"], {})[r["book_id"]] = (r["status"], votes.get((r["user_id"], r["book_id"]), 0))
    return logs

def get_cf_model(force=False):
    fresh = _model_cache["model"] is not None and time.time() - _model_cache["built_at"] < MODEL_TTL_SECONDS
    if fresh and not force:
        return _model_cache["model"]
    catalog = get_catalog_with_embeddings()
    logs = load_real_profiles()
    if USE_SYNTHETIC_PEERS:
        logs.update(generate_synthetic_peers(catalog))
    profiles = {u: to_preferences(log) for u, log in logs.items()}
    model = build_cf_model(profiles, [b["id"] for b in catalog])
    model["books"] = {b["id"]: b for b in catalog}
    _model_cache.update(model=model, built_at=time.time())
    return model

def collaborative_recommend(user_id, n=10, model=None):
    model = model or get_cf_model()
    user_books, feedback = get_user_books_with_feedback(user_id)
    prefs = {b["id"]: cf_preference(b.get("status"), feedback.get(b["id"], 0)) for b in user_books}
    if not any(p > 0 for p in prefs.values()):
        return None
    logged = {b["id"] for b in user_books}
    pool = rank_cf(prefs, model, exclude_ids=logged, n=n * 3)
    titles = {b["id"]: b["title"] for b in user_books}
    candidates = []
    for book_id, score, because in pool:
        book = dict(model["books"][book_id])
        book["cf_score"] = score
        book["explanation"] = f"Readers who liked '{titles.get(because, 'a book in your library')}' also liked this"
        candidates.append(book)
    candidates = filter_similar_to_rejected(candidates, get_rejected_books(user_id))[:n]
    for book in candidates:
        book.pop("embedding", None)
    return candidates

def blend_alpha(n_liked):
    if n_liked < MIN_BOOKS_FOR_CF:
        return 0.0
    return float(min(ALPHA_MAX, ALPHA_MAX * (n_liked - MIN_BOOKS_FOR_CF + 1) / ALPHA_RAMP_BOOKS))

def minmax(scores):
    if not scores:
        return {}
    lo, hi = min(scores.values()), max(scores.values())
    if hi - lo < 1e-12:
        return {k: 1.0 for k in scores}
    return {k: (v - lo) / (hi - lo) for k, v in scores.items()}

def blend_scores(content, cf, alpha):
    c, f = minmax(content), minmax(cf)
    rows = [(i, (1 - alpha) * c.get(i, 0.0) + alpha * f.get(i, 0.0), c.get(i, 0.0), f.get(i, 0.0))
            for i in set(c) | set(f)]
    rows.sort(key=lambda r: (-r[1], str(r[0])))
    return rows

def hybrid_recommend(user_id, n=10, explore=0.0, model=None):
    rec, div, _cached = get_user_centroids(user_id)
    if rec is None:
        return None

    user_books, feedback = get_user_books_with_feedback(user_id)
    prefs = {b["id"]: cf_preference(b.get("status"), feedback.get(b["id"], 0)) for b in user_books}
    alpha = blend_alpha(sum(1 for p in prefs.values() if p > 0))
    if alpha == 0.0:
        return personalized_recommend(user_id, n=n, explore=explore)

    logged = {b["id"] for b in user_books}
    pool = n * 6

    content_books = {b["id"]: b for b in query_similar_books(rec.tolist(), exclude_ids=list(logged), limit=pool)}

    model = model or get_cf_model()
    ranked = rank_cf(prefs, model, exclude_ids=logged, n=len(model["ids"]))
    cf_all = {i: s for i, s, _ in ranked}
    because = {i: why for i, _, why in ranked}

    candidate_ids = set(content_books) | {i for i, _, _ in ranked[:pool]}
    books = {i: dict(model["books"][i]) for i in candidate_ids if i in model["books"]}
    for i, b in content_books.items():
        books[i] = b

    content = {i: 1 - cosine_distance(_to_vector(b["embedding"]), rec) for i, b in books.items()}
    cf = {i: cf_all.get(i, 0.0) for i in books}

    titles = {b["id"]: b["title"] for b in user_books}
    finished = get_books_by_status(user_id, {"finished"})
    candidates = []
    for i, score, c_n, f_n in blend_scores(content, cf, alpha):
        book = books[i]
        book["hybrid_score"] = score
        if alpha * f_n > (1 - alpha) * c_n and i in because:
            book["explanation"] = f"Readers who liked '{titles.get(because[i], 'a book in your library')}' also liked this"
        else:
            book["explanation"] = (explain_recommendation(book, user_books=finished)
                                    if finished else "Recommended based on your reading history")
        candidates.append(book)

    candidates = filter_similar_to_rejected(candidates, get_rejected_books(user_id))
    candidates = explore_rerank(candidates, rec, div, n, explore)
    for book in candidates:
        book.pop("embedding", None)
    return candidates

def recommend_with_strategy(user_id, n=10, explore=0.0, strategy="hybrid"):
    if strategy == "content":
        return personalized_recommend(user_id, n=n, explore=explore)
    if strategy == "collaborative":
        return collaborative_recommend(user_id, n=n)
    return hybrid_recommend(user_id, n=n, explore=explore)