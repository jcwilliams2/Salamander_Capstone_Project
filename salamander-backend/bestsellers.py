import os
import time
import requests
from nyt_parse import parse_list_response, split_authors
from supabase_client import supabase

NYT_LISTS = ["combined-print-and-e-book-fiction", "combined-print-and-e-book-nonfiction", 
                "young-adult-hardcover", "graphic-books-and-manga"]
NYT_PAUSE_SECONDS = 12

def fetch_list(list_name, get=requests.get):
    resp = get(
        f"https://api.nytimes.com/svc/books/v3/lists/current/{list_name}.json",
        params={"api-key": os.environ["NYT_API_KEY"]},
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"NYT returned status {resp.status_code} for {list_name}")
    return parse_list_response(resp.json(), list_name)

def fetch_all_lists(lists=NYT_LISTS, fetch=fetch_list, pause=NYT_PAUSE_SECONDS):
    out = []
    for i, name in enumerate(lists):
        if i:
            time.sleep(pause)
        out.append(fetch(name))
    return out

def find_book_id(isbn, title, author):
    from ingest import _escape_like, authors_overlap
    if isbn:
        rows = supabase.table("books").select("id").eq("isbn", isbn).execute().data
        if rows:
            return rows[0]["id"]
    if not title:
        return None
    wanted = ", ".join(split_authors(author))
    if not wanted:
        return None
    rows = supabase.table("books").select("id, author").ilike("title", _escape_like(title.strip())).execute().data
    for r in rows:
        if authors_overlap(wanted, r.get("author")):
            return r["id"]
    return None

def ingest_bestsellers(lists, get_metadata=None, insert=None, find=find_book_id):
    if get_metadata is None or insert is None:
        from ingest import get_book_metadata, insert_book
        get_metadata = get_metadata or get_book_metadata
        insert = insert or insert_book
    summary = {"already_in_catalog": 0, "added": 0, "no_metadata": 0, "errors": 0}
    resolved = []
    for lst in lists:
        rows = []
        for book in lst["books"]:
            book_id = None
            try:
                book_id = find(book["isbn"], book["title"], book["author"])
                if book_id:
                    summary["already_in_catalog"] += 1
                elif book["isbn"]:
                    data = get_metadata(book["isbn"])
                    if not data:
                        summary["no_metadata"] += 1
                    else:
                        insert(data)
                        book_id = find(book["isbn"], book["title"], book["author"])
                        if book_id:
                            summary["added"] += 1
                        else:
                            summary["no_metadata"] += 1
            except Exception as e:
                print(f" Could not ingest {book.get('title')}: {e}")
                summary["errors"] += 1
                book_id = None
            rows.append({**book, "book_id": book_id})
        resolved.append({"list_name": lst["list_name"], "published_date": lst["published_date"], "books": rows})
    return {"summary": summary, "lists": resolved}