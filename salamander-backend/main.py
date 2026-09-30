from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from recommend import zero_history_recommend, build_genre_centroids
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
    return {"success": True}

class DeleteStatusRequest(BaseModel):
    user_id: str
    book_id: str

@app.delete("/reading-status")
def delete_reading_status(request: DeleteStatusRequest):
    supabase.table("reading_status").delete().eq("user_id", request.user_id).eq("book_id", request.book_id).execute()
    return {"success": True}