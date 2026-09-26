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