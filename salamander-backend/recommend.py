import numpy as np
from supabase_client import supabase

def get_coldstart_path(user_books):
    n = len(user_books)
    if n == 0:
        return "zero_history"
    elif n <= 3:
        return "sparse_history"
    else:
        return "broader_history"

def sparse_history_recommend(user_books, n=10):
    embeddings = np.array([b['embedding'] for b in user_books])
    user_vector = embeddings.mean(axis=0)
    exclude_ids = [b['id'] for b in user_books]
    candidates = query_similar_books(user_vector, exclude_ids=exclude_ids, limit=(n * 2))
    return candidates[:n]

def query_similar_books(query_vector, exclude_ids=None, limit=10):
    result = supabase.rpc('match_books', {
        'query_embedding': query_vector,
        'match_count': limit,
        'exclude_ids': exclude_ids or []
    }).execute()
    return result.data

if __name__=="__main__":
    test_books = supabase.table("books").select("id, title, embedding").in_(
        "isbn", ["9780547928227", "9780756404741", "9780316556347"]
        ).execute().data
    
    print("Simulating a user who has read:")
    for b in test_books:
        print(f" - {b['title']}")

    recommendations = sparse_history_recommend(test_books)
    print("\nRecommend:")
    for book in recommendations:
        print(f" {book['title']} by {book['author']} — similarity: {book['similarity']:.3f}")