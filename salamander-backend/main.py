from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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
    result = supabase.table("reading_status").upsert({
        "user_id": request.user_id,
        "book_id": request.book_id,
        "status": request.status,
    }, on_conflict="user_id,book_id").execute()
    invalidate_user_centroids(request.user_id)
    return {"success": True}

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