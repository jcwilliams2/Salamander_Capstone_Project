import numpy as np
import json
import os
import requests
from datetime import date, datetime
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

STATUS_BASE_WEIGHT = {
    "finished": 1.0,
    "reading": 0.6,
    "dnf": 0.3,
    "want_to_read": 0.4,
}

VOTE_MULTIPLIER = {1: 1.6, 0: 1.0, -1: 0.4}

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

def query_similar_books(query_vector, exclude_ids=None, limit=10):
    result = supabase.rpc('match_books', {
        'query_embedding': query_vector,
        'match_count': limit,
        'exclude_ids': exclude_ids or []
    }).execute()
    return result.data

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

def find_diversity_gaps(user_books, all_books_with_embeddings, n=5, min_percentile=40, max_percentile=75):
    if len(user_books) < 3:
        return []

    centroid = diversity_centroid(user_books)
    user_ids = set(b['id'] for b in user_books)

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

if __name__=="__main__":
    print("T27")
    failures = 0

    rejected = supabase.table("books").select("id, title, embedding").eq("isbn", "9780547928227").execute().data
    candidates = query_similar_books(_to_vector(rejected[0]["embedding"]).tolist(), limit=20)

    kept = filter_similar_to_rejected(candidates, rejected)
    kept_ids = {b["id"] for b in kept}
    print(f" {len(candidates)} candidates -> {len(kept)} kept, {len(candidates) - len(kept)} removed")

    for b in candidates:
        was_removed = b["id"] not in kept_ids
        should_remove = b["id"] not in kept_ids
        should_remove = b["similarity"] >= 0.40
        ok = was_removed == should_remove
        if was_removed:
            print(f" removed: {b["title"]} (similarity {b["similarity"]:.3f}) {'OK' if ok else 'FAIL'}")
        failures += 0 if ok else 1

    nontrivial = 0 < len(kept) < len(candidates)
    print(f" test results in some kept and some removed: {nontrivial}")
    failures += 0 if nontrivial else 1

    unchanged = filter_similar_to_rejected(candidates, []) == candidates
    print(f" no rejected books -> candidates unchanged: {unchanged}")
    failures += 0 if unchanged else 1

    print(f"\n{'PASS' if failures == 0 else 'FAIL'}: {failures} mismatches")