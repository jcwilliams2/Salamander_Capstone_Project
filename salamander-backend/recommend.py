import numpy as np
import json
from supabase_client import supabase

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

if __name__=="__main__":
    centroids = build_genre_centroids()
    print(f"Built centroids for {len(centroids)} genres: {list(centroids.keys())}")

    recommendations = zero_history_recommend(selected_genres=["fantasy"], genre_centroids=centroids)
    print("\n--- Test 1: Genre selection ('fantasy') ---")
    for book in recommendations:
        print(f" {book['title']} by {book.get('author', 'Unknown')}")

    print("\n--- Test 2: Seed books (Hobbit, Name of the Wind, Circe) ---")
    seed_books = supabase.table("books").select("id, title, embedding").in_(
        "isbn", ["9780547928227", "9780756404741", "9780316556347"]
    ).execute().data
    recommendations = zero_history_recommend(seed_books=seed_books, genre_centroids=centroids)
    for book in recommendations:
        print(f" {book['title']} by {book.get('author', 'Unknown')}")

    print("\n--- Test 3: No selection at all (fallback) ---")
    recommendations = zero_history_recommend(genre_centroids=centroids)
    for book in recommendations:
        print(f" {book['title']} by {book.get('author', 'Unknown')}")