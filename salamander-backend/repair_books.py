import re
import sys
import os
import time
import requests
from supabase_client import supabase
from ingest import clean_description, is_english, build_embedding_text, generate_embedding, HEADERS
from recommend import build_genre_centroids, _to_vector, cosine_distance

APPLY = "--apply" in sys.argv
MIN_DESC = 50
TAG_THRESHOLD =  0.40
GENERIC_TAGS = {"fiction", "nonfiction"}

google_down = False

class RateLimited(Exception):
    pass

def fetch_all_books(columns):
    rows, start = [], 0
    while True:
        batch = supabase.table("books").select(columns).order("id").range(start, start + 999).execute().data
        rows.extend(batch)
        if len(batch) < 1000:
            return rows
        start += 1000

def clean_title_for_search(title):
    t = re.sub(r"\(.*?\)", "", title)
    return t.split(":")[0].strip()

def _norm(text):
    return re.sub(r"[^a-z0-9 ]", "", (text or "").lower()).strip()

def google_query(q, tries=3):
    params = {"q": q, "maxResults": 5}
    key = os.environ.get("GOOGLE_BOOKS_API_KEY")
    if key:
        params["key"] = key
    for attempt in range(tries):
        resp = requests.get("https://www.googleapis.com/books/v1/volumes", params=params, timeout=10)
        if resp.status_code in (429, 500, 502, 503):
            wait = 3 * 2 ** attempt
            print(f"  HTTP {resp.status_code}, waiting {wait}s", flush=True)
            time.sleep(wait)
            continue
        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code}: {resp.text[:120]}", flush=True)
            return []
        return resp.json().get("items") or []
    raise RateLimited(q)

def matches_book(volume_info, title, author):
    want_title = _norm(clean_title_for_search(title))
    got_title = _norm(volume_info.get("title"))
    if not want_title or not (want_title in got_title or got_title in want_title):
        return False
    if not author:
        return True
    first = re.split(r",| and ", author)[0]
    tokens = _norm(first).split()
    if not tokens:
        return True
    got_authors = _norm(" ".join(volume_info.get("authors") or []))
    return tokens[-1] in got_authors

def google_description(isbn, title=None, author=None):
    for item in google_query(f"isbn:{isbn}")[:3]:
        desc = clean_description(item.get("volumeInfo", {}).get("description"))
        if desc and len(desc) >= MIN_DESC:
            return desc
    if title:
        q = f'intitle:"{clean_title_for_search(title)}"'
        if author:
            q += f' inauthor:"{re.split(",| and ", author)[0].strip()}"'
        for item in google_query(q):
            info = item.get("volumeInfo", {})
            if not matches_book(info, title, author):
                continue
            desc = clean_description(info.get("description"))
            if desc and len(desc) >= MIN_DESC:
                return desc
    return None

def openlibrary_description(title, author):
    params = {"title": clean_title_for_search(title), "limit": 5}
    if author:
        params["author"] = re.split(",| and ", author)[0].strip()
    try:
        resp = requests.get("https://openlibrary.org/search.json", params=params, headers=HEADERS, timeout=15)
        time.sleep(0.5)
        if resp.status_code != 200:
            return None
        for doc in resp.json().get("docs", []):
            info = {"title": doc.get("title"), "authors": doc.get("author_name")}
            if not matches_book(info, title, author):
                continue
            work = requests.get(f"https://openlibrary.org{doc['key']}.json", headers=HEADERS, timeout=15)
            time.sleep(0.5)
            if work.status_code != 200:
                continue
            raw = work.json().get("description")
            if isinstance(raw, dict):
                raw = raw.get("value")
            desc = clean_description(raw)
            if desc and len(desc) >= MIN_DESC:
                return desc
    except requests.RequestException as e:
        print(f"  Open Library error: {e}", flush=True)
    return None

def fetch_description(isbn, title, author):
    global google_down
    if not google_down:
        try:
            desc = google_description(isbn, title, author)
            if desc:
                return desc
        except RateLimited:
            google_down = True
            print("  Google Books unavailable; using Open Library for the rest of this run", flush=True)
    return openlibrary_description(title, author)

def repair_descriptions():
    print(f"--- Repairing descriptions that are thin or nonexistent ---")
    targets = [b for b in fetch_all_books("id, title, author, isbn, description")
                if len((b.get("description") or "").strip()) < MIN_DESC and b.get("isbn")]
    print(f"{len(targets)} books to check", flush=True)
    fixed, foreign, unresolved, limited = 0, [], [], 0
    for i, b in enumerate(targets, 1):
        print(f" [{i}/{len(targets)}] {b['title'][:60]}", flush=True)
        try:
            desc = fetch_description(b["isbn"], b["title"], b.get("author"))
            limited = 0
        except RateLimited:
            limited += 1
            unresolved.append(b["title"])
            if limited >= 3:
                print("Rate limited 3 times in a row. Stopping; try again later and check GOOGLE_BOOKS_API_KEY.")
                break
            continue
        time.sleep(1)
        if not desc:
            unresolved.append(b["title"])
            continue
        if not is_english(desc):
            foreign.append(b["title"])
            continue
        print(f" fix: {b['title']} ({len(desc)} chars)")
        if APPLY:
            supabase.table("books").update({
                "description": desc,
                "is_english": True,
                "embedding": generate_embedding(build_embedding_text(b["title"], desc)),
            }).eq("id", b["id"]).execute()
        fixed += 1
    print(f"Fixed {fixed}. Non-English (review): {foreign}")
    print(f"Still no description (review/delete): {unresolved}")

def retag_untagged():
    print("\n--- Tagging untagged books by nearest genre centroid ---")
    centroids = {g: _to_vector(v) for g, v in build_genre_centroids().items() if g not in GENERIC_TAGS}
    for b in fetch_all_books("id, title, genre_tags, embedding"):
        if b.get("genre_tags") or not b.get("embedding"):
            continue
        vec = _to_vector(b["embedding"])
        ranked = sorted(((1 - cosine_distance(vec, c), g) for g, c in centroids.items()), reverse=True)
        sim, tag = ranked[0]
        shown = ", ".join(f"{g} {s:.2f}" for s, g in ranked[:3])
        print(f" {b['title'][:55]:55} -> {tag if sim >= TAG_THRESHOLD else '(skip)'}  [{shown}]")
        if APPLY and sim >= TAG_THRESHOLD:
            supabase.table("books").update({
                "genre_tags": [tag],
                }).eq("id", b["id"]).execute()

if __name__ == "__main__":
    print("APPLYING" if APPLY else "DRY RUN (add --apply to write changes)")
    repair_descriptions()
    #retag_untagged()