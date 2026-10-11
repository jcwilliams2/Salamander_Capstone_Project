import numpy as np
import json
import os
import requests
from collections import Counter
from datetime import date, datetime, timezone
from supabase_client import supabase

_nyt_cache = {"data": None, "next_publish_date": None}

GENRE_ADJACENCY = {
    "fantasy": {"science fiction", "historical fiction", "young adult", "mystery", "horror", "graphic novel"},
    "science fiction": {"fantasy", "mystery", "thriller"},
    "mystery": {"thriller", "crime fiction", "horror", "literary fiction"},
    "thriller": {"mystery", "crime fiction", "horror"},
    "romance": {"literary fiction", "young adult", "historical fiction"},
    "horror": {"fantasy", "mystery", "thriller"},
    "historical fiction": {"literary fiction", "biography", "fantasy", "romance"},
    "literary fiction": {"historical fiction", "memoir", "romance", 'mystery'},
    "biography": {"memoir", "literary fiction", "psychology"},
    "memoir": {"biography", "literary fiction", "psychology"},
    "young adult": {"fantasy", "romance", "science fiction"},
    "childrens": {"young adult", "fantasy"},
    "poetry": {"literary fiction", "memoir"},
    "graphic novel": {"fantasy", "science fiction", "humor"},
    "self help": {"psychology", "business"},
    "history": {"biography", "politics"},
    "science": {"science fiction", "history"},
    "philosophy": {"psychology", "religion"},
    "religion": {"philosophy", "history"},
    "business": {"self help", "psychology"},
    "true crime": {"crime fiction", "mystery"},
    "crime fiction": {"mystery", "thriller", "true crime"},
    "humor": {"graphic novel", "literary fiction"},
    "cooking": {"travel"},
    "travel": {"memoir", "cooking"},
    "psychology": {"self help", "memoir", "philosophy"},
    "politics": {"history", "philosophy"},
    "sports": {"biography"},
    "nonfiction": set(),
    "fiction": set(),
}

GENRE_DISPLAY = {"childrens": "children's", "self help": "self-help"}

STATUS_BASE_WEIGHT = {
    "finished": 1.0,
    "reading": 0.6,
    "dnf": 0.3,
    "want_to_read": 0.4,
}

VOTE_MULTIPLIER = {1: 1.6, 0: 1.0, -1: 0.4}

DIVERSITY_STATUSES = {"finished", "dnf"}

def get_current_bestsellers_with_covers(list_name="combined-print-and-e-book-fiction"):
    today = date.today()

    if _nyt_cache["data"] and _nyt_cache["next_publish_date"] and today < _nyt_cache["next_publish_date"]:
        return _nyt_cache["data"]

    resp = requests.get(
        f"https://api.nytimes.com/svc/books/v3/lists/current/{list_name}.json",
        params={"api-key": os.environ["NYT_API_KEY"]},
    )
    if resp.status_code != 200:
        print(f" NYT fetch failed: {resp.status_code}")
        return _nyt_cache["data"] or []

    payload = resp.json().get("results", {})
    books = payload.get("books", [])
    results = [{
        "title": b.get("title"),
        "author": b.get("author"),
        "isbn": b.get("primary_isbn13"),
        "cover_url": b.get("book_image"),
        "explanation": "Current New York Times bestseller",
    } for b in books]

    next_date_str = payload.get("next_published_date")
    try:
        next_date = datetime.strptime(next_date_str, "%Y-%m-%d").date() if next_date_str else None
    except ValueError:
        next_date = None

    _nyt_cache["data"] = results
    _nyt_cache["next_publish_date"] = next_date
    return results

def get_adjacent_genres(user_genre_tags):
    adjacent = set()
    for genre in user_genre_tags:
        adjacent.update(GENRE_ADJACENCY.get(genre, set()))
    return adjacent

def get_coldstart_path(user_books):
    n = len(user_books)
    if n == 0:
        return "zero_history"
    elif n <= 3:
        return "sparse_history"
    else:
        return "broader_history"

def attach_covers(books):
    missing = [b["id"] for b in books if "cover_url" not in b]
    if not missing:
        return books
    rows = supabase.table("books").select("id, cover_url").in_("id", missing).execute().data
    by_id = {r["id"]: r["cover_url"] for r in rows}
    for b in books:
        b.setdefault("cover_url", by_id.get(b["id"]))
    return books

def query_similar_books(query_vector, exclude_ids=None, limit=10):
    result = supabase.rpc('match_books', {
        'query_embedding': query_vector,
        'match_count': limit,
        'exclude_ids': exclude_ids or []
    }).execute()
    return attach_covers(result.data)

def explain_recommendation(book, user_books=None, selected_genres=None, genre_centroids=None):
    if user_books:
        similarities = []
        for b in user_books:
            b_emb = b['embedding']
            if isinstance(b_emb, str):
                b_emb = json.loads(b_emb)
            rec_emb = book.get('embedding')
            if isinstance(rec_emb, str):
                rec_emb = json.loads(rec_emb)
            if rec_emb is not None:
                sim = np.dot(b_emb, rec_emb) / (np.linalg.norm(b_emb) * np.linalg.norm(rec_emb))
                similarities.append((b, sim))
        if similarities:
            closest = max(similarities, key=lambda x: x[1])
            return f"Recommended because of similarity to '{closest[0]['title']}'"

    if selected_genres and genre_centroids:
        book_emb = book.get('embedding')
        if isinstance(book_emb, str):
            book_emb = json.loads(book_emb)
        if book_emb is not None:
            best_genre, best_sim = None, -1
            for g in selected_genres:
                centroid = genre_centroids.get(g)
                if centroid is None:
                    continue
                sim = np.dot(book_emb, centroid) / (np.linalg.norm(book_emb) * np.linalg.norm(centroid))
                if sim > best_sim:
                    best_sim = sim
                    best_genre = g
            if best_genre:
                return f"Recommended based on your interest in {best_genre}"
        return f"Recommended based on your interest in {selected_genres[0]}"

    return "Recommended based on popularity"

def sparse_history_recommend(user_books, n=10):
    parsed_embeddings = []
    for b in user_books:
        emb = b['embedding']
        if isinstance(emb, str):
            emb = json.loads(emb)
        parsed_embeddings.append(emb)

    embeddings = np.array(parsed_embeddings, dtype=float)
    user_vector = embeddings.mean(axis=0).tolist()
    exclude_ids = [b['id'] for b in user_books]
    candidates = query_similar_books(user_vector, exclude_ids=exclude_ids, limit=(n * 2))
    return candidates[:n]

def zero_history_recommend(selected_genres=None, seed_books=None, genre_centroids=None, n=10):
    if seed_books:
        recs = sparse_history_recommend(seed_books, n)
        for book in recs:
            book['explanation'] = explain_recommendation(book, user_books=seed_books)
            book.pop('embedding', None)
        return recs
    elif selected_genres and genre_centroids:
        vectors = [genre_centroids[g] for g in selected_genres if g in genre_centroids]
        if not vectors:
            return no_preference_fallback(n)
        genre_vector = np.array(vectors, dtype=float).mean(axis=0).tolist()
        recs = query_similar_books(genre_vector, limit=n)
        for book in recs:
            book['explanation'] = explain_recommendation(book, selected_genres=selected_genres, genre_centroids=genre_centroids)
            book.pop('embedding', None)
        return recs
    else:
        return no_preference_fallback(n)

def popularity_baseline_recommend(n=10):
    result = supabase.table("books").select("id, title, author").order("created_at").limit(n).execute()
    return result.data

def no_preference_fallback(n=10):
    bestsellers = get_current_bestsellers_with_covers()
    if bestsellers:
        return bestsellers[:n]
    return popularity_baseline_recommend(n)

def build_genre_centroids():
    all_books = supabase.table("books").select("genre_tags, embedding").execute().data

    genre_embeddings = {}
    for book in all_books:
        tags = book.get("genre_tags")
        emb = book.get("embedding")
        if not tags or not emb:
            continue
        if isinstance(emb, str):
            emb = json.loads(emb)
        for tag in tags:
            genre_embeddings.setdefault(tag, []).append(emb)

    centroids = {}
    for genre, embeddings in genre_embeddings.items():
        arr = np.array(embeddings, dtype=float)
        centroids[genre] = arr.mean(axis=0).tolist()

    return centroids

def diversity_centroid(user_books):
    parsed_embeddings = []

    for b in user_books:
        emb = b['embedding']
        if isinstance(emb, str):
            emb = json.loads(emb)
        parsed_embeddings.append(emb)

    embeddings = np.array(parsed_embeddings, dtype=float)
    return embeddings.mean(axis=0)

def cosine_distance(a, b):
    a, b = np.array(a), np.array(b)
    return (1 - (np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))))

def diversity_score(user_books):
    if len(user_books) < 3:
        return None
    centroid = diversity_centroid(user_books)
    distances = []
    for b in user_books:
        emb = b['embedding']
        if isinstance(emb, str):
            emb = json.loads(emb)
        distances.append(cosine_distance(emb, centroid))
    return float(np.mean(distances))

def find_diversity_gaps(user_books, all_books_with_embeddings, n=5, min_percentile=40, max_percentile=75, exclude_ids=None):
    if len(user_books) < 3:
        return []

    centroid = diversity_centroid(user_books)
    user_ids = set(b['id'] for b in user_books) | set(exclude_ids or [])

    user_genres = set()
    for b in user_books:
        tags = b.get('genre_tags')
        if tags:
            user_genres.update(tags)
    adjacent_genres = get_adjacent_genres(user_genres)

    candidates = []
    for book in all_books_with_embeddings:
        if book['id'] in user_ids:
            continue

        book_genres = set(book.get('genre_tags') or [])
        if not book_genres & adjacent_genres:
            continue

        emb = book['embedding']
        if isinstance(emb, str):
            emb = json.loads(emb)
        dist = cosine_distance(emb, centroid)
        candidates.append((book, dist))

    if not candidates:
        return []
    
    distances_only = [d for _, d in candidates]
    min_dist = np.percentile(distances_only, min_percentile)
    max_dist = np.percentile(distances_only, max_percentile)
    mid_dist = (min_dist + max_dist) /2

    in_range = [(b, d) for b, d in candidates if min_dist <= d <= max_dist]
    in_range.sort(key=lambda x: abs(x[1] - mid_dist))

    results = []
    for book, dist in in_range:
        if len(results) >= n:
            break
        book['distance'] = dist
        results.append(book)

    return results

def evaluate_recommender(user_profiles, k=1, n=10):
    hits, total = 0, 0
    for profile in user_profiles:
        if len(profile) <= k:
            continue
        held_out = profile[-k:]
        visible = profile[:-k]
        recs = sparse_history_recommend(visible, n=n)
        rec_ids = set(r['id'] for r in recs)
        held_out_ids = set(b['id'] for b in held_out)
        hits += len(rec_ids & held_out_ids)
        total += len(held_out_ids)
    return hits / total if total else None

def evaluate_popularity_baseline(user_profiles, k=1, n=10):
    hits, total = 0, 0
    for profile in user_profiles:
        if len(profile) <= k:
            continue
        held_out = profile[-k:]
        recs = popularity_baseline_recommend(n=n)
        rec_ids = set(r['id'] for r in recs)
        held_out_ids = set(b['id'] for b in held_out)
        hits += len(rec_ids & held_out_ids)
        total += len(held_out_ids)
    return hits / total if total else None

def get_book_weight(status, vote):
    base = STATUS_BASE_WEIGHT.get(status, 0.5)
    if status == "want_to_read":
        return base
    return base * VOTE_MULTIPLIER.get(vote, 1.0)

def compute_weights(user_books, feedback_by_book_id):
    weights = {}
    for book in user_books:
        vote = feedback_by_book_id.get(book["id"], 0)
        status = book.get("status", "reading")
        weights[book["id"]] = get_book_weight(status, vote)
    return weights

def is_degenerate_weighting(weights, min_books=3, threshold=0.15):
    return len(weights) >= min_books and float(np.std(list(weights.values()))) < threshold

def compute_final_weights(user_books, feedback_by_book_id):
    weights = compute_weights(user_books, feedback_by_book_id)
    if is_degenerate_weighting(weights):
        return {
            book["id"]: (1.2 if book.get("status") == "finished" else 0.5)
            for book in user_books
        }
    return weights

def get_user_books_with_feedback(user_id):
    status_rows = supabase.table("reading_status").select("book_id, status").eq("user_id", user_id).execute().data
    feedback_rows = supabase.table("feedback").select("book_id, vote").eq("user_id", user_id).execute().data

    feedback_by_book_id = {row["book_id"]: row["vote"] for row in feedback_rows}
    book_ids = [row["book_id"] for row in status_rows]
    if not book_ids:
        return [], {}

    books = supabase.table("books").select("id, title, embedding, genre_tags").in_("id", book_ids).execute().data
    status_by_book_id = {row["book_id"]: row["status"] for row in status_rows}
    for book in books:
        book["status"] = status_by_book_id.get(book["id"], "reading")
    return books, feedback_by_book_id

def _to_vector(emb):
    if isinstance(emb, str):
        emb = json.loads(emb)
    return np.array(emb, dtype=float)

def get_rejected_books(user_id):
    dnf_rows = supabase.table("reading_status").select("book_id").eq("user_id", user_id).eq("status", "dnf").execute().data
    down_rows = supabase.table("feedback").select("book_id").eq("user_id", user_id).eq("vote", -1).execute().data
    ids = list({r["book_id"] for r in dnf_rows} | {r["book_id"] for r in down_rows})
    if not ids:
        return []
    return supabase.table("books").select("id, title, embedding").in_("id", ids).execute().data

def filter_similar_to_rejected(candidates, rejected_books, threshold=0.40):
    if not rejected_books:
        return candidates
    rejected_vecs = [_to_vector(b["embedding"]) for b in rejected_books]
    rejected_ids = {b["id"] for b in rejected_books}
    kept = []
    for book in candidates:
        if book["id"] in rejected_ids:
            continue
        vec = _to_vector(book["embedding"])
        if any(1 - cosine_distance(vec, rv) >= threshold for rv in rejected_vecs):
            continue
        kept.append(book)
    return kept

def user_diversity_centroid_from_books(user_books):
    eligible = [b for b in user_books if b.get("status") in DIVERSITY_STATUSES]
    if not eligible:
        return None
    return diversity_centroid(eligible)

def get_user_diversity_centroid(user_id):
    user_books, _ = get_user_books_with_feedback(user_id)
    return user_diversity_centroid_from_books(user_books)

def compute_user_centroids(user_books, feedback):
    rec_books = [b for b in user_books if b.get("status") != "want_to_read"]
    rec = None
    if rec_books:
        weights = compute_final_weights(rec_books, feedback)
        vecs = np.array([_to_vector(b["embedding"]) for b in rec_books])
        w = np.array([weights[b["id"]] for b in rec_books])
        rec = np.average(vecs, axis=0, weights=w)
    div = user_diversity_centroid_from_books(user_books)
    return rec, div

def get_user_centroids(user_id):
    rows = supabase.table("user_centroids").select("recommendation_centroid, diversity_centroid").eq("user_id", user_id).execute().data
    if rows:
        r, d = rows[0]["recommendation_centroid"], rows[0]["diversity_centroid"]
        return (None if r is None else _to_vector(r)), (None if d is None else _to_vector(d)), True

    user_books, feedback = get_user_books_with_feedback(user_id)
    rec, div = compute_user_centroids(user_books, feedback)
    supabase.table("user_centroids").upsert({
        "user_id": user_id,
        "recommendation_centroid": None if rec is None else rec.tolist(),
        "diversity_centroid": None if div is None else div.tolist(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, on_conflict="user_id").execute()
    return rec, div, False

def invalidate_user_centroids(user_id):
    supabase.table("user_centroids").delete().eq("user_id", user_id).execute()

def get_books_by_status(user_id, statuses):
    rows = supabase.table("reading_status").select("book_id").eq("user_id", user_id).in_("status", list(statuses)).execute().data
    if not rows:
        return []
    ids = [r["book_id"] for r in rows]
    return supabase.table("books").select("id, title, embedding").in_("id", ids).execute().data

def explore_rerank(candidates, rec, div, n, explore):
    explore = min(max(float(explore), 0.0), 1.0)
    if explore == 0 or len(candidates) <= n:
        return candidates[:n]

    anchor = div if div is not None else rec
    vecs = {b["id"]: _to_vector(b["embedding"]) for b in candidates}
    rel = {i: 1 - cosine_distance(v, rec) for i, v in vecs.items()}
    novelty = {i: cosine_distance(v, anchor) for i, v in vecs.items()}

    remaining, chosen = list(candidates), []
    while remaining and len(chosen) < n:
        def score(b):
            redundancy = max((1 - cosine_distance(vecs[b["id"]], vecs[c["id"]]) for c in chosen), default=0.0)
            return (1 - explore) * rel[b["id"]] + explore * (novelty[b["id"]] - redundancy)
        best = max(remaining, key=score)
        chosen.append(best)
        remaining.remove(best)
    return chosen

def intra_list_distance(vectors):
    d = [cosine_distance(vectors[i], vectors[j])
        for i in range(len(vectors)) for j in range(i + 1, len(vectors))]
    return float(np.mean(d)) if d else 0.0

def personalized_recommend(user_id, n=10, explore=0.0):
    rec, div, _cached = get_user_centroids(user_id)
    if rec is None:
        return None
    
    logged = supabase.table("reading_status").select("book_id").eq("user_id", user_id).execute().data
    exclude_ids = [r["book_id"] for r in logged]

    pool = (n * 6) if explore and explore > 0 else (n * 3)
    candidates = query_similar_books(rec.tolist(), exclude_ids=exclude_ids, limit=pool)
    candidates = filter_similar_to_rejected(candidates, get_rejected_books(user_id))
    candidates = explore_rerank(candidates, rec, div, n, explore)

    finished = get_books_by_status(user_id, {"finished"})
    for book in candidates:
        book["explanation"] = (
            explain_recommendation(book, user_books=finished)
            if finished else "Recommended based on your reading history"
        )
        book.pop("embedding", None)
    return candidates

def get_catalog_with_embeddings():
    rows, start = [], 0
    while True:
        batch = supabase.table("books").select("id, title, author, cover_url, genre_tags, embedding").order("id").range(start, start + 999).execute().data
        rows += batch
        if len(batch) < 1000:
            return rows
        start += 1000

def explain_diversity_suggestion(book, user_books):
    def show(g):
        return GENRE_DISPLAY.get(g, g)

    counts = Counter(g for b in user_books for g in (b.get("genre_tags") or []))
    for g in book.get("genre_tags") or []:
        for u, _ in counts.most_common():
            if u != g and (u in GENRE_ADJACENCY.get(g, set()) or g in GENRE_ADJACENCY.get(u, set())):
                article = "an" if show(g)[0] in "aeiou" else "a"
                return f"Something to explore: {article} {show(g)} pick that pairs well with the {show(u)} titles you've been reading."
    return "Something to explore: a change of pace that pairs well with your library."

def diversity_suggestions(user_id, n=5):
    user_books, _ = get_user_books_with_feedback(user_id)
    eligible = [b for b in user_books if b.get("status") in DIVERSITY_STATUSES]
    if len(eligible) < 3:
        return []
    picks = find_diversity_gaps(eligible, get_catalog_with_embeddings(),
                n=(n * 3), exclude_ids=[b["id"] for b in user_books],
                )
    picks = filter_similar_to_rejected(picks, get_rejected_books(user_id))[:n]
    for book in picks:
        book["explanation"] = explain_diversity_suggestion(book, eligible)
        book.pop("embedding", None)
        book.pop("distance", None)
    return picks

if __name__=="__main__":
    import uuid
    print("T36")
    results = []

    def check(label, ok):
        print(f" {label}: {'OK' if ok else 'FAIL'}")
        results.append(bool(ok))

    def get(isbn):
        return supabase.table("books").select("id, title, embedding").eq("isbn", isbn).execute().data[0]

    hobbit, notw, circe = get("9780547928227"), get("9780756404741"), get("9780316556347")

    tag = uuid.uuid4().hex[:8]
    uid = supabase.auth.admin.create_user({
        "email": f"t36-{tag}@example.com",
        "password": f"Tmp-{tag}-pass1",
        "email_confirm": True,
        "user_metadata": {"username": f"t36_{tag}"},
    }).user.id

    try:
        def log_status(book, status):
            supabase.table("reading_status").upsert({"user_id": uid, "book_id": book["id"], "status": status}, on_conflict="user_id,book_id").execute()

        for b in (hobbit, notw, circe):
            log_status(b, "finished")

        rec, div, _ = get_user_centroids(uid)

        def embs(books):
            ids = [b["id"] for b in books]
            rows = supabase.table("books").select("id, embedding").in_("id", ids).execute().data
            by = {r["id"]: _to_vector(r["embedding"]) for r in rows}
            return [by[i] for i in ids]

        levels = (0, 0.35, 0.7, 1.0)
        picks = {w: personalized_recommend(uid, n=6, explore=w) for w in levels}
        ild = {w: intra_list_distance(embs(picks[w])) for w in levels}
        rel = {w: float(np.mean([1 - cosine_distance(v, rec) for v in embs(picks[w])])) for w in levels}
        far = {w: float(np.mean([cosine_distance(v, div) for v in embs(picks[w])])) for w in levels}

        own = {b["id"] for b in (hobbit, notw, circe)}
        check("every level returns 6 picks, none already logged, none with a raw embedding", 
                all(len(p) == 6 and not ({x["id"] for x in p} & own) and all("embedding" not in x and x.get("explanation") for x in p)
                for p in picks.values()))
        check("explore=0 matches the original behaviour exactly", 
                [x["id"] for x in picks[0]] == [x["id"] for x in personalized_recommend(uid, n=6)])
        check("out-of-range values are clamped (5 -> 1, -1 -> 0)",
                [x["id"] for x in personalized_recommend(uid, n=6, explore=5)] == [x["id"] for x in picks[1.0]]
                and [x["id"] for x in personalized_recommend(uid, n=6, explore=-1)] == [x["id"] for x in picks[0]])
        check("intra-list distance rises with exploration (0.7 and 1.0 vs 0)", ild[0.7] > ild[0] and ild[1.0] > ild[0])
        check("picks sit farther from the diversity centroid as exploration rises", far[1.0] > far[0])
        check("closeness to the user's taste falls as exploration rises (this represents the real trade-off)", rel[0] > rel[1.0])

        for w in levels:
            print(f" explore={w}: ILD={ild[w]:.3f}  relevance={rel[w]:.3f}  distance-from-center={far[w]:.3f}")
        print(" familiar:", [x["title"] for x in picks[0]])
        print(" adventurous:", [x["title"] for x in picks[0.7]])

    finally:
        supabase.table("feedback").delete().eq("user_id", uid).execute()
        supabase.table("reading_status").delete().eq("user_id", uid).execute()
        supabase.auth.admin.delete_user(uid)
        print(" (temporary test user removed)")

    failures = results.count(False)
    print(f"\n{'PASS' if failures == 0 else 'FAIL'}: {failures} mismatches")