import os
import secrets
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import date, datetime, timezone
from collections import Counter
from collaborative import recommend_with_strategy
from recommend import (zero_history_recommend, build_genre_centroids, 
                        get_current_bestsellers_with_covers, 
                        no_preference_fallback, 
                        personalized_recommend, invalidate_user_centroids,
                        diversity_suggestions, genre_seed_recommend)
from search import (search_catalog, browse_catalog, attach_user_state,
                    filter_catalog, list_genres)
from catalog_request import find_external_matches, add_requested_book, RequestLimitError
from reading_goals import (validate_goal, validate_year, compute_pace, finished_count_for_year,
                            next_started_at, average_days_to_finish)
from reading_dates import apply_date_edit
from library import sort_library
from monthly_summary import (summarize_month, finished_in_month, previous_month, month_counts,
                                first_month, month_range, goal_progress, validate_month, validate_tz_offset)
from supabase_client import supabase

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in ["http://localhost:5173", os.environ.get("FRONTEND_ORIGIN")] if o],
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
    existing_rows = (supabase.table("reading_status").select("status, started_at, finished_at")
                        .eq("user_id", request.user_id).eq("book_id", request.book_id)
                        .execute().data)
    existing = existing_rows[0] if existing_rows else {}
    row = {
        "user_id": request.user_id,
        "book_id": request.book_id,
        "status": request.status,
        "updated_at": now,
        "finished_at": None,
        "started_at": next_started_at(existing.get("status"), existing.get("started_at"),
                                        request.status, now),
    }
    if request.status == "finished":
        row["finished_at"] = existing.get("finished_at") or now
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

@app.get("/recent-finished/{user_id}")
def recent_finished(user_id: str, limit: int = 3):
    limit = max(1, min(limit, 12))
    rows = (supabase.table("reading_status")
            .select("book_id, finished_at")
            .eq("user_id", user_id)
            .eq("status", "finished")
            .not_.is_("finished_at", "null")
            .order("finished_at", desc=True)
            .limit(limit)
            .execute()
            .data
    )
    if not rows:
        return {"books": []}
    ids = [r["book_id"] for r in rows]
    books = supabase.table("books").select("id, title, author, cover_url").in_("id", ids).execute().data
    by_id = {b["id"]: b for b in books}
    return {
        "books": [
            {**by_id[r["book_id"]], "finished_at": r["finished_at"]}
            for r in rows
            if r["book_id"] in by_id
        ]
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

class ReadingDatesRequest(BaseModel):
    user_id: str
    book_id: str
    started_on: str | None = None
    finished_on: str | None = None
    today: str | None = None

@app.post("/reading-dates")
def edit_reading_dates(request: ReadingDatesRequest):
    sent = getattr(request, "model_fields_set", getattr(request, "__fields_set__", set()))
    edit = {k: getattr(request, k) for k in ("started_on", "finished_on") if k in sent}
    try:
        day = date.fromisoformat(request.today) if request.today else datetime.now(timezone.utc).date()
    except ValueError:
        raise HTTPException(status_code=400, detail="today must be a date like 2026-10-31.")
    rows = (supabase.table("reading_status").select("status, started_at, finished_at")
                .eq("user_id", request.user_id).eq("book_id", request.book_id).execute().data)
    if not rows:
        raise HTTPException(status_code=404, detail="That book isn't in your reading log.")
    row = rows[0]
    try:
        changes = apply_date_edit(row["status"], row.get("started_at"), row.get("finished_at"), edit, day)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if changes:
        (supabase.table("reading_status").update(changes)
            .eq("user_id", request.user_id).eq("book_id", request.book_id).execute())
    return {"started_at": changes.get("started_at", row.get("started_at")),
            "finished_at": changes.get("finished_at", row.get("finished_at"))}

@app.get("/reading-log/{user_id}")
def reading_log(user_id: str):
    rows = (supabase.table("reading_status").select("book_id, started_at, finished_at")
                .eq("user_id", user_id).eq("status", "finished")
                .order("finished_at", desc=True).execute().data)
    by_id = {}
    ids = [r["book_id"] for r in rows]
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        for b in supabase.table("books").select("id, title, author, cover_url").in_("id", chunk).execute().data:
            by_id[b["id"]] = b
    return {"books": [
        {**by_id[r["book_id"]], "started_at": r["started_at"], "finished_at": r["finished_at"]}
        for r in rows if r["book_id"] in by_id
    ]}

@app.get("/library/{user_id}")
def library(user_id: str, sort: str = "status"):
    rows = (supabase.table("reading_status").select("book_id, status, added_at")
                .eq("user_id", user_id).execute().data)
    by_id = {}
    ids = [r["book_id"] for r in rows]
    for i in range(0, len(ids), 100):
        chunk = ids[i: i + 100]
        for b in supabase.table("books").select("id, title, author, cover_url").in_("id", chunk).execute().data:
            by_id[b["id"]] = b
    items = [{**by_id[r["book_id"]], "status": r["status"], "added_at": r["added_at"]}
                for r in rows if r["book_id"] in by_id]
    try:
        ordered = sort_library(items, sort)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"sort": sort, "total": len(ordered), "books": ordered}

@app.get("/monthly-summary/{user_id}")
def monthly_summary(user_id: str, today: str | None = None, tz_offset: int = 0,
                    year: int | None = None, month: int | None = None):
    try:
        day = date.fromisoformat(today) if today else datetime.now(timezone.utc).date()
        validate_year(day.year)
    except ValueError:
        raise HTTPException(status_code=400, detail="today must be a date like 2026-11-03.")
    try:
        validate_tz_offset(tz_offset)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if (year is None) != (month is None):
        raise HTTPException(status_code=400, detail="Send both your year and month, or neither.")
    try:
        if year is None:
            year, month = previous_month(day.year, day.month)
        validate_year(year)
        validate_month(month)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if (year, month) > (day.year, day.month):
        raise HTTPException(status_code=400, detail="That month hasn't happened yet.")

    rows = (supabase.table("reading_status").select("book_id, status, started_at, finished_at, added_at")
            .eq("user_id", user_id).execute().data)
    finished = [r for r in rows if r["status"] == "finished"]
    in_month = [r for r in finished if finished_in_month(r, year, month, tz_offset)]
    by_id = {}
    votes = {}
    ids = [r["book_id"] for r in in_month]
    for i in range(0, len(ids), 100):
        chunk = ids[i: i + 100]
        for b in supabase.table("books").select("id, title, author, cover_url, genre_tags").in_("id", chunk).execute().data:
            by_id[b["id"]] = b
        for v in supabase.table("feedback").select("book_id, vote").eq("user_id", user_id).in_("book_id", chunk).execute().data:
            votes[v["book_id"]] = v["vote"]
    items = [{**by_id[r["book_id"]], **r, "vote": votes.get(r["book_id"])} for r in in_month if r["book_id"] in by_id]
    
    goal_rows = (supabase.table("reading_goals").select("goal")
                    .eq("user_id", user_id).eq("year", year).execute().data)
    goal = goal_rows[0]["goal"] if goal_rows else None

    result = summarize_month(items, year, month, tz_offset)
    result["months"] = month_counts(finished, tz_offset)
    result["range"] = month_range(first_month(rows, tz_offset), (year, month), (day.year, day.month))
    result["goal_progress"] = goal_progress(goal, finished, year, month, tz_offset)
    return result

@app.get("/user-onboarding-status/{user_id}")
def check_onboarding_status(user_id: str):
    result = supabase.table("profiles").select("onboarding_completed").eq("id", user_id).execute()
    if not result.data:
        return {"onboarding_completed": False}
    return {"onboarding_completed": result.data[0].get("onboarding_completed", False)}

class CompleteOnboardingRequest(BaseModel):
    user_id: str
    selected_genres: list[str] | None = None

@app.post("/complete-onboarding")
def mark_onboarding_complete(request: CompleteOnboardingRequest):
    update = {"onboarding_completed": True}
    if request.selected_genres is not None:
        update["onboarding_genres"] = request.selected_genres
    result = supabase.table("profiles").update(update).eq("id", request.user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="No profile found for this user")
    return {"success": True}

class ThemeRequest(BaseModel):
    user_id: str
    theme: str

THEME_ID = re.compile(r"[a-z][A-Za-z0-9]{1,30}")

@app.get("/user-settings/{user_id}")
def get_user_settings(user_id: str):
    rows = supabase.table("profiles").select("theme").eq("id", user_id).execute().data
    return {"theme": rows[0]["theme"] if rows else "light"}

@app.post("/user-settings/theme")
def set_theme(request: ThemeRequest):
    if not THEME_ID.fullmatch(request.theme):
        raise HTTPException(status_code=400, detail="Invalid theme name.")
    result = supabase.table("profiles").update({"theme": request.theme}).eq("id", request.user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="No profile found for this user")
    return {"theme": request.theme}

class GoalRequest(BaseModel):
    user_id: str
    year: int
    goal: int | None = None

@app.get("/reading-goal/{user_id}")
def get_reading_goal(user_id: str, year: int | None = None):
    try:
        year = validate_year(year) if year is not None else datetime.now(timezone.utc).year
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    rows = (supabase.table("reading_goals").select("goal")
                .eq("user_id", user_id).eq("year", year).execute().data)
    return {"year": year, "goal": rows[0]["goal"] if rows else None}

@app.post("/reading-goal")
def set_reading_goal(request: GoalRequest):
    try:
        year = validate_year(request.year)
        goal = validate_goal(request.goal)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not supabase.table("profiles").select("id").eq("id", request.user_id).execute().data:
        raise HTTPException(status_code=404, detail="No profile found for this user")
    if goal is None:
        supabase.table("reading_goals").delete().eq("user_id", request.user_id).eq("year", year).execute()
    else:
        supabase.table("reading_goals").upsert(
            {"user_id": request.user_id, "year": year, "goal": goal,
             "updated_at": datetime.now(timezone.utc).isoformat()},
            on_conflict="user_id,year",
        ).execute()
    return {"year": year, "goal": goal}

@app.get("/reading-pace/{user_id}")
def reading_pace(user_id: str, today: str | None = None):
    try:
        day = date.fromisoformat(today) if today else datetime.now(timezone.utc).date()
        validate_year(day.year)
    except ValueError:
        raise HTTPException(status_code=400, detail="today must be a date like 2026-10-30.")
    goal_rows = (supabase.table("reading_goals").select("goal")
                    .eq("user_id", user_id).eq("year", day.year).execute().data)
    goal = goal_rows[0]["goal"] if goal_rows else None
    finished_rows = (supabase.table("reading_status").select("started_at, finished_at")
                        .eq("user_id", user_id).eq("status", "finished").execute().data)
    finished = finished_count_for_year([r["finished_at"] for r in finished_rows], day.year)
    return {"year": day.year, "goal": goal, "finished": finished,
            "pace": compute_pace(goal, finished, day),
            "time_to_finish": average_days_to_finish(finished_rows)}

STUDY_AUTO_EXPLORE = 0.35
STUDY_PILOT = os.environ.get("STUDY_PILOT") == "1"

def get_study_arm(user_id):
    rows = supabase.table("participant_assignments").select("arm").eq("user_id", user_id).execute().data
    return rows[0]["arm"] if rows else None

def choose_arm():
    if STUDY_PILOT:
        arms = [r["arm"] for r in supabase.table("participant_assignments").select("arm").execute().data]
        return "A" if arms.count("A") <= arms.count("B") else "B"
    return secrets.choice(["A", "B"])

@app.get("/study/arm/{user_id}")
def study_arm(user_id: str):
    arm = get_study_arm(user_id)
    if not arm:
        supabase.table("participant_assignments").upsert(
            {"user_id": user_id, "arm": choose_arm()},
            on_conflict="user_id",
            ignore_duplicates=True,
        ).execute()
        arm = get_study_arm(user_id)
    return {"arm": arm, "explore": STUDY_AUTO_EXPLORE}

def genre_seed_feed(user_id, n, explore):
    rows = supabase.table("profiles").select("onboarding_genres").eq("id", user_id).execute().data
    genres = (rows[0].get("onboarding_genres") if rows else None) or []
    if not genres:
        return None
    logged = [r["book_id"] for r in supabase.table("reading_status").select("book_id").eq("user_id", user_id).execute().data]
    return genre_seed_recommend(genres, genre_centroids, n=n, explore=explore, exclude_ids=logged)

STUDY_MIN_RATED = 10
SURVEY_ITEM_IDS = ["r1", "r2", "r3", "n1", "n2", "n3", "d1", "d2", "d3", "d4", "s1", "s2", "s3", "attn"]

def count_rated(user_id):
    votes = {r["book_id"] for r in supabase.table("feedback").select("book_id").eq("user_id", user_id).execute().data}
    statuses = {r["book_id"] for r in supabase.table("reading_status").select("book_id").eq("user_id", user_id).execute().data}
    return len(votes | statuses)

@app.get("/study/progress/{user_id}")
def study_progress(user_id: str):
    done = bool(supabase.table("survey_responses").select("user_id").eq("user_id", user_id).execute().data)
    return {"rated": count_rated(user_id), "required": STUDY_MIN_RATED, "survey_done": done}

class SurveyRequest(BaseModel):
    user_id: str
    answers: dict[str, int]

@app.post("/study/survey")
def submit_survey(request: SurveyRequest):
    assigned = supabase.table("participant_assignments").select("assigned_at").eq("user_id", request.user_id).execute().data
    if not assigned:
        raise HTTPException(status_code=403, detail="Not a study participant.")
    if set(request.answers) != set(SURVEY_ITEM_IDS) or any(not 1 <= v <= 5 for v in request.answers.values()):
        raise HTTPException(status_code=400, detail="Please answer every question.")
    if supabase.table("survey_responses").select("user_id").eq("user_id", request.user_id).execute().data:
        raise HTTPException(status_code=409, detail="Your survey has already been submitted.")

    started = datetime.fromisoformat(assigned[0]["assigned_at"].replace("Z", "+00:00"))
    seconds = int((datetime.now(timezone.utc) - started).total_seconds())
    try:
        supabase.table("survey_responses").insert({
            "user_id": request.user_id,
            "answers": request.answers,
            "attention_passed": request.answers["attn"] == 4,
            "rated_count": count_rated(request.user_id),
            "session_seconds": seconds,
        }).execute()
    except Exception:
        raise HTTPException(status_code=409, detail="Your survey has already been submitted.")
    return {"success": True}

@app.get("/recommendations/personalized/{user_id}")
def get_personalized_feed(user_id: str, explore: float = 0.0, strategy: str = "hybrid"):
    if get_study_arm(user_id) == "A":
        explore = STUDY_AUTO_EXPLORE
    recs = recommend_with_strategy(user_id, n=12, explore=explore, strategy=strategy)
    if not recs:
        recs = genre_seed_feed(user_id, n=12, explore=explore)
    if not recs:
        recs = no_preference_fallback(15)
    return {"recommendations": recs}

@app.get("/recommendations/diversity/{user_id}")
def get_diversity_feed(user_id: str):
    return {"suggestions": diversity_suggestions(user_id, n=8)}

@app.get("/catalog/search")
def catalog_search(q: str = "", user_id: str | None = None):
    return {"results": attach_user_state(search_catalog(q), user_id)}

@app.get("/catalog/browse")
def catalog_browse(page: int = 1, page_size: int = 24, user_id: str | None = None):
    page_size = min(max(page_size, 1), 60)
    books, total = browse_catalog(page, page_size)
    return {"results": attach_user_state(books, user_id), "page": max(page, 1), "total": total}

@app.get("/catalog/filter")
def catalog_filter(genres: str, q: str = "", page: int = 1, page_size: int = 24, user_id: str | None = None):
    page, page_size = max(page, 1), min(max(page_size, 1), 60)
    books, total = filter_catalog(q, genres, page, page_size)
    return {"results": attach_user_state(books, user_id), "page": page, "total": total}

@app.get("/catalog/genres")
def catalog_genres():
    return {"genres": list_genres()}

@app.get("/catalog/lookup")
def catalog_lookup(q: str):
    matches = find_external_matches(q)
    return {"candidates": matches, "candidate": matches[0] if matches else None}

class CatalogRequest(BaseModel):
    user_id: str
    isbn: str

@app.post("/catalog/request")
def request_catalog_book(request: CatalogRequest):
    try:
        return add_requested_book(request.user_id, request.isbn)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RequestLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))