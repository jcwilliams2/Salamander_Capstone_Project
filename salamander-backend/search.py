import re
from supabase_client import supabase
from postgrest.exceptions import APIError
from collections import Counter

MIN_QUERY_LENGTH = 2
MAX_TOKENS = 5

def search_catalog(q, limit=20):
    cleaned = re.sub(r'[,()%*\\_"]', " ", q or "")
    tokens = [t.lower() for t in cleaned.split() if t][:MAX_TOKENS]
    if not tokens or len(max(tokens, key=len)) < MIN_QUERY_LENGTH:
        return []

    anchor = max(tokens, key=len)
    rows = (
        supabase.table("books")
        .select("id, title, author, cover_url")
        .or_(f"title.ilike.%{anchor}%,author.ilike.%{anchor}%")
        .limit(200)
        .execute()
        .data
    )

    matches = []
    for row in rows:
        haystack = f"{row['title'] or ''} {row['author'] or ''}".lower()
        if all(t in haystack for t in tokens):
            matches.append(row)

    phrase = " ".join(tokens)

    def rank(row):
        title = (row["title"] or "").lower()
        if title == phrase:
            return (0, title)
        if title.startswith(phrase):
            return (1, title)
        return (2, title)

    matches.sort(key=rank)
    return matches[:limit]

def _fetch_all(build_query, batch=1000):
    rows, start = [], 0
    while True:
        chunk = build_query().range(start, start + batch - 1).execute().data
        rows.extend(chunk)
        if len(chunk) < batch:
            return rows
        start += batch

def normalize_genres(genres):
    if isinstance(genres, str):
        genres = genres.split(",")
    return sorted({g.strip().lower() for g in (genres or []) if g and g.strip()})

def _search_tokens(q):
    cleaned = re.sub(r'[,()%*\\_"]', " ", q or "")
    tokens = [t.lower() for t in cleaned.split() if t][:MAX_TOKENS]
    if not tokens or len(max(tokens, key=len)) < MIN_QUERY_LENGTH:
        return []
    return tokens

def order_results(rows, wanted, tokens):
    wanted = set(wanted)
    phrase = " ".join(tokens)
    for r in rows:
        have = {t.lower() for t in (r.get("genre_tags") or [])}
        r["matched_genres"] = sorted(wanted & have)

    def rank(r):
        title = (r.get("title") or "").lower()
        if not tokens:
            text_rank = 0
        elif title == phrase:
            text_rank = 0
        elif title.startswith(phrase):
            text_rank = 1
        else:
            text_rank = 2
        return (-len(r["matched_genres"]), text_rank, title)
    return sorted(rows, key=rank)

def filter_catalog(q, genres, page=1, page_size=24):
    wanted = normalize_genres(genres)
    if not wanted:
        return [], 0
    tokens = _search_tokens(q)

    def build():
        query = supabase.table("books").select("id, title, author, cover_url, genre_tags").overlaps("genre_tags", wanted)
        if tokens:
            anchor = max(tokens, key=len)
            query = query.or_(f"title.ilike.%{anchor}%,author.ilike.%{anchor}%")
        return query.order("id")
    
    rows = _fetch_all(build)
    if tokens:
        rows = [
            r for r in rows
            if all(t in f"{r['title'] or ''} {r['author'] or ''}".lower() for t in tokens)
        ]
    rows = order_results(rows, wanted, tokens)
    start = (max(page, 1) - 1) * page_size
    return rows[start:start + page_size], len(rows)

def list_genres():
    rows = _fetch_all(lambda: supabase.table("books").select("id, genre_tags").order("id"))
    counts = Counter(g.lower() for r in rows for g in (r.get("genre_tags") or []))
    return [{"genre": g, "count": c} for g, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]

def attach_user_state(results, user_id):
    if not user_id or not results:
        return results
    ids = [r["id"] for r in results]
    statuses = supabase.table("reading_status").select("book_id, status").eq("user_id", user_id).in_("book_id", ids).execute().data
    votes = supabase.table("feedback").select("book_id, vote").eq("user_id", user_id).in_("book_id", ids).execute().data
    status_by_id = {r["book_id"]: r["status"] for r in statuses}
    vote_by_id = {r["book_id"]: r["vote"] for r in votes}
    for r in results:
        r["status"] = status_by_id.get(r["id"], "")
        r["vote"] = vote_by_id.get(r["id"], 0)
    return results

def browse_catalog(page=1, page_size=24):
    page = max(page, 1)
    start = (page - 1) * page_size
    try:
        resp = (
            supabase.table("books")
            .select("id, title, author, cover_url", count="exact")
            .order("title")
            .order("id")
            .range(start, start + page_size - 1)
            .execute()
        )
    except APIError:
        return [], 0
    return resp.data, resp.count or 0

if __name__ == "__main__":
    print("T41")
    results = []

    def check(label, ok):
        print(f" {label}: {'OK' if ok else 'FAIL'}")
        results.append(bool(ok))

    rows = [
        {"id": 1, "title": "B", "genre_tags": ["mystery", "fantasy"]},
        {"id": 2, "title": "A", "genre_tags": ["fantasy"]},
        {"id": 3, "title": "C", "genre_tags": ["fantasy", "mystery"]},
    ]
    ordered = order_results(rows, ["fantasy", "mystery"], [])
    check("both-genre books rank first, whatever the tag order", [r["id"] for r in ordered] == [1, 3, 2])

    both, both_total = filter_catalog("", ["fantasy", "mystery"], 1, 60)
    check("every result has at least one selected genre", bool(both) and all(r["matched_genres"] for r in both))
    counts = [len(r["matched_genres"]) for r in both]
    check("match count never increases down the list", counts == sorted(counts, reverse=True))
    toki, _ = filter_catalog("tolkien", ["fantasy"], 1, 60)
    check("filter combines with text search", bool(toki) and all("tolkien" in (r["author"] or "").lower() for r in toki))
    sf, _ = filter_catalog("", ["Science Fiction"], 1, 60)
    check("multi-word, mixed-case genre works", bool(sf))
    check("unknown genre returns nothing", filter_catalog("", ["zzzz"], 1, 60) == ([], 0))
    check("no genres returns nothing", filter_catalog("dune", [], 1, 60) == ([], 0))
    genres = list_genres()
    check("genre list has counts", bool(genres) and all({"genre", "count"} <= set(g) for g in genres))
    print(f" fantasy+mystery: {both_total} books; {sum(1 for c in counts if c == 2)} match both")

    failures = results.count(False)
    print(f"\n{'PASS' if failures == 0 else 'FAIL'}: {failures} mismatches")