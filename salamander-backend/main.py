from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timezone
from collections import Counter
from recommend import (zero_history_recommend, build_genre_centroids, 
                        get_current_bestsellers_with_covers, 
                        no_preference_fallback, 
                        personalized_recommend, invalidate_user_centroids,
                        diversity_suggestions)
from search import search_catalog, browse_catalog, attach_user_state
from supabase_client import supabase

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# precompute centroids once at startup
genre_centroids = build_genre_centroids()

class OnboardingRequest(BaseModel):
    selected_genres: list[str] | None = None
    seed_book_ids: list[str] | None = None

@app.post("/recommendations/onboarding")
def get_onboarding_recommendations(request: OnboardingRequest):
    seed_books = None
    if request.seed_book_ids:
        result = supabase.table("books").select("id, title, embedding").in_("id", request.seed_book_ids).execute()
        seed_books = result.data

    recommendations = zero_history_recommend(
        selected_genres=request.selected_genres,
        seed_books=seed_books,
        genre_centroids=genre_centroids,
        n=10
    )
    return {"recommendations": recommendations}

@app.get("/recommendations/returning-no-history")
def get_returning_user_feed():
    return {"recommendations": get_current_bestsellers_with_covers()}

class FeedbackRequest(BaseModel):
    user_id: str
    book_id: str
    vote: int

@app.post("/feedback")
def record_feedback(request: FeedbackRequest):
    result = supabase.table("feedback").upsert({
        "user_id": request.user_id,
        "book_id": request.book_id,
        "vote": request.vote,
    }, on_conflict="user_id,book_id").execute()
    invalidate_user_centroids(request.user_id)
    return {"success": True}

class ReadingStatusRequest(BaseModel):
    user_id: str
    book_id: str
    status: str

@app.post("/reading-status")
def update_reading_status(request: ReadingStatusRequest):
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "user_id": request.user_id,
        "book_id": request.book_id,
        "status": request.status,
        "updated_at": now,
        "finished_at": None,
    }
    if request.status == "finished":
        existing = (supabase.table("reading_status").select("finished_at")
                    .eq("user_id", request.user_id).eq("book_id", request.book_id)
                    .execute().data)
        row["finished_at"] = (existing[0].get("finished_at") if existing else None) or now
    supabase.table("reading_status").upsert(row, on_conflict="user_id,book_id").execute()
    invalidate_user_centroids(request.user_id)
    return {"success": True}

@app.get("/reading-stats/{user_id}")
def reading_stats(user_id: str):
    rows = supabase.table("reading_status").select("book_id, status, finished_at").eq("user_id", user_id).execute().data
    status_counts = Counter(r["status"] for r in rows)

    votes = supabase.table("feedback").select("vote").eq("user_id", user_id).execute().data
    vote_counts = Counter(v["vote"] for v in votes)

    history_ids = [r["book_id"] for r in rows if r["status"] in ("finished", "reading", "dnf")]
    genre_counts = Counter()
    for i in range(0, len(history_ids), 100):
        chunk = history_ids[i:i + 100]
        books = supabase.table("books").select("genre_tags").in_("id", chunk).execute().data
        for b in books:
            for g in b.get("genre_tags") or []:
                genre_counts[g] += 1

    finished_at = sorted(
        r["finished_at"] for r in rows
        if r["status"] == "finished" and r.get("finished_at")
    )
    
    return {
        "status_counts": {s: status_counts.get(s, 0) for s in ("finished", "reading", "dnf", "want_to_read")},
        "vote_counts": {"up": vote_counts.get(1, 0), "down": vote_counts.get(-1, 0)},
        "genres": [{"genre": g, "count": c} for g, c in genre_counts.most_common(8)],
        "finished_at": finished_at,
    }

@app.get("/want-to-read/{user_id}")
def want_to_read_list(user_id: str):
    rows = (supabase.table("reading_status").select("book_id, updated_at")
            .eq("user_id", user_id).eq("status", "want_to_read")
            .order("updated_at", desc=True).execute().data)
    if not rows:
        return {"results": []}
    ids = [r["book_id"] for r in rows]
    books = (supabase.table("books").select("id, title, author, cover_url, genre_tags")
            .in_("id", ids).execute().data)
    by_id = {b["id"]: b for b in books}
    ordered = [by_id[i] for i in ids if i in by_id]
    return {"results": attach_user_state(ordered, user_id)}

class DeleteStatusRequest(BaseModel):
    user_id: str
    book_id: str

@app.delete("/reading-status")
def delete_reading_status(request: DeleteStatusRequest):
    supabase.table("reading_status").delete().eq("user_id", request.user_id).eq("book_id", request.book_id).execute()
    invalidate_user_centroids(request.user_id)
    return {"success": True}

@app.get("/user-onboarding-status/{user_id}")
def check_onboarding_status(user_id: str):
    result = supabase.table("profiles").select("onboarding_completed").eq("id", user_id).execute()
    if not result.data:
        return {"onboarding_completed": False}
    return {"onboarding_completed": result.data[0].get("onboarding_completed", False)}

class CompleteOnboardingRequest(BaseModel):
    user_id: str

@app.post("/complete-onboarding")
def mark_onboarding_complete(request: CompleteOnboardingRequest):
    result = supabase.table("profiles").update({"onboarding_completed": True}).eq("id", request.user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="No profile found for this user")
    return {"success": True}

@app.get("/recommendations/personalized/{user_id}")
def get_personalized_feed(user_id: str, explore: float = 0.0):
    recs = personalized_recommend(user_id, n=12, explore=explore)
    if not recs:
        recs = no_preference_fallback(15)
    return {"recommendations": recs}

@app.get("/recommendations/diversity/{user_id}")
def get_diversity_feed(user_id: str):
    return {"suggestions": diversity_suggestions(user_id, n=6)}

@app.get("/catalog/search")
def catalog_search(q: str = "", user_id: str | None = None):
    return {"results": attach_user_state(search_catalog(q), user_id)}

@app.get("/catalog/browse")
def catalog_browse(page: int = 1, page_size: int = 24, user_id: str | None = None):
    page_size = min(max(page_size, 1), 60)
    books, total = browse_catalog(page, page_size)
    return {"results": attach_user_state(books, user_id), "page": max(page, 1), "total": total}