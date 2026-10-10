import re
from supabase_client import supabase
from postgrest.exceptions import APIError

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
    print("T39")
    results = []

    def check(label, ok):
        print(f" {label}: {'OK' if ok else 'FAIL'}")
        results.append(bool(ok))

    def has(q, fragment):
        return any(fragment.lower() in r["title"].lower() for r in search_catalog(q))

    dune = search_catalog("dune")
    check("exact title ranks first", bool(dune) and dune[0]["title"].lower() == "dune")
    check("partial title ('wizard of earth')", has("wizard of earth", "Wizard of Earthsea"))
    check("partial author ('rothfuss')", has("rothfuss", "Name of the Wind"))
    check("author in either name order ('toni morrison' finds Beloved)", has("toni morrison", "Beloved"))
    check("case-insensitive ('HOBBIT')", has("HOBBIT", "Hobbit"))
    check("words split across title and author ('hobbit tolkien')", has("hobbit tolkien", "Hobbit"))
    check("no match returns an empty list", search_catalog("zzzzqx") == [])
    check("one-character query returns an empty list", search_catalog("a") == [])
    check("punctuation can't break the query ('dune, (frank)%')", has("dune, (frank)%", "Dune"))

    sample = search_catalog("beloved")
    check("results have id/title/author/cover_url and no embedding",
        bool(sample) and all({"id", "title", "author", "cover_url"} <= set(r) and "embedding" not in r for r in sample))
    print(f" 'beloved' returned {len(sample)} row(s)")

    page1, total = browse_catalog(1, 24)
    page2, _ = browse_catalog(2, 24)
    check("browse returns a full first page", len(page1) == 24 and total >= 24)
    check("pages don't overlap", not ({r["id"] for r in page1} & {r["id"] for r in page2}))
    check("page past the end returns empty", browse_catalog(10_000, 24) == ([], 0))

    failures = results.count(False)
    print(f"\n{'PASS' if failures == 0 else 'FAIL'}: {failures} mismatches")