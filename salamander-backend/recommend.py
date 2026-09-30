import numpy as np
import json
from supabase_client import supabase

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

def explain_recommendation(book, user_books=None, selected_genres=None):
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

    if selected_genres:
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
            return popularity_baseline_recommend(n)
        genre_vector = np.array(vectors, dtype=float).mean(axis=0).tolist()
        recs = query_similar_books(genre_vector, limit=n)
        for book in recs:
            book['explanation'] = explain_recommendation(book, selected_genres=selected_genres)
            book.pop('embedding', None)
        return recs
    else:
        return popularity_baseline_recommend(n)

def popularity_baseline_recommend(n=10):
    result = supabase.table("books").select("id, title, author").order("created_at").limit(n).execute()
    return result.data

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

if __name__=="__main__":
#    def fetch(isbns):
#        return supabase.table("books").select("id, title, embedding").in_("isbn", isbns).execute().data
#    
#    fantasy_profile = fetch([
#        "9780547928227", "9780756404741", "9780316556347", "9780441478125",
#        "9780441172719", "9780547773742", "9780553293357"
#    ])
#    mystery_profile = fetch([
#        "9780394758282", "9780307588371", "9781250301697", "9780307949486",
#        "9780062073563"
#    ])
#    memoir_profile = fetch([
#        "9780399590504", "9781451648539", "9780345350688", "9780807014295"
#    ])
#    selfhelp_profile = fetch([
#        "9780735211292", "9781982137274", "9780374533557", "9780804139298"
#    ])

#    profiles = [fantasy_profile, mystery_profile, memoir_profile, selfhelp_profile]

#    recommender_hit_rate = evaluate_recommender(profiles, k=1)
#    baseline_hit_rate = evaluate_popularity_baseline(profiles, k=1)

#    print(f"Content-based recommender hit rate: {recommender_hit_rate:.4f}")
#    print(f"Popularity baseline hit rate: {baseline_hit_rate:.4f}")
#    print(f"\nDoes recommender outperform baseline? {recommender_hit_rate > baseline_hit_rate}")

    hobbit = supabase.table("books").select("id, embedding").eq("isbn", "9780547928227").execute()
    similar = query_similar_books(hobbit.data[0]["embedding"], exclude_ids=[hobbit.data[0]["id"]])
    print("--- Hobbit similarity check (larger catalog) ---")
    for book in similar:
        print(f" {book["title"]} by {book["author"]} — similarity: {book["similarity"]:.3f}")