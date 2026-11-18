from datetime import date, datetime, timezone
from supabase_client import supabase

ROW_FIELDS = ("rank", "isbn", "title", "author", "weeks_on_list", "book_id")
FALLBACK_LISTS = ["combined-print-and-e-book-fiction", "combined-print-and-e-book-nonfiction"]
MAX_AGE_DAYS = 21
FALLBACK_EXPLANATION = "Current New York Times bestseller"

def latest_published(list_name):
    rows = (supabase.table("bestseller_rankings").select("published_date")
                .eq("list_name", list_name).order("published_date", desc=True)
                .limit(1).execute().data)
    return rows[0]["published_date"] if rows else None

def write_rankings(lst):
    name, published = lst["list_name"], lst["published_date"]
    latest = latest_published(name)
    if latest and published < latest:
        return {"status": "skipped_older", "rows": 0}
    now = datetime.now(timezone.utc).isoformat()
    rows = [{"list_name": name, "published_date": published, "fetched_at": now,
                **{k: b.get(k) for k in ROW_FIELDS}} for b in lst["books"]]
    supabase.table("bestseller_rankings").upsert(rows, on_conflict="list_name,published_date,rank").execute()
    last_rank = max(r["rank"] for r in rows)
    (supabase.table("bestseller_rankings").delete().eq("list_name", name).eq("published_date", published)
        .gt("rank", last_rank).execute())
    supabase.table("bestseller_rankings").delete().eq("list_name", name).lt("published_date", published).execute()
    return {"status": "refreshed" if latest == published else "new_week", "rows": len(rows)}

def is_fresh(published_date, today, max_age_days=MAX_AGE_DAYS):
    try:
        published = date.fromisoformat(published_date)
    except (TypeError, ValueError):
        return False
    return (today - published).days <= max_age_days

def merge_rankings(per_list, exclude_ids=None, n=10):
    if n <= 0:
        return []
    order = []
    for list_index, rows in enumerate(per_list):
        for r in rows:
            if r.get("book_id"):
                order.append((r["rank"], list_index, r["book_id"]))
    order.sort()
    skip, seen, out = set(exclude_ids or ()), set(), []
    for _, _, book_id in order:
        if book_id in skip or book_id in seen:
            continue
        seen.add(book_id)
        out.append(book_id)
        if len(out) >= n:
            break
    return out

def cached_bestsellers(n=10, exclude_ids=None, lists=FALLBACK_LISTS, today=None):
    today = today or date.today()
    per_list = []
    for name in lists:
        latest = latest_published(name)
        if not latest or not is_fresh(latest, today):
            continue
        rows = (supabase.table("bestseller_rankings").select("rank, book_id").eq("list_name", name)
                    .eq("published_date", latest).order("rank").execute().data)
        per_list.append(rows)
    ids = merge_rankings(per_list, exclude_ids, n)
    if not ids:
        return []
    books = supabase.table("books").select("id, title, author, isbn, cover_url").in_("id", ids).execute().data
    by_id = {b["id"]: b for b in books}
    return [{**by_id[i], "explanation": FALLBACK_EXPLANATION} for i in ids if i in by_id]