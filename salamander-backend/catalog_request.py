import re
import sys
import time
import threading
import requests
import unicodedata

from ingest import HEADERS, ISBNDB_HEADERS, get_book_metadata, insert_book, is_duplicate_work, authors_overlap
from names import flip_name
from search import _search_tokens
from supabase_client import supabase

MAX_REQUESTS_PER_HOUR = 5
LOOKUP_CACHE_SECONDS = 3600
LOOKUP_CACHE_MAX = 200
CANDIDATES_PER_SOURCE = 8
MAX_CANDIDATES = 5

_lookup_cache = {}
_requests_by_user = {}
_ingest_lock = threading.Lock()

class RequestLimitError(Exception):
    pass

def clean_isbn(value):
    digits = re.sub(r"[\s-]", "", value or "")
    if re.fullmatch(r"\d{13}", digits) or re.fullmatch(r"\d{9}[\dXx]", digits):
        return digits.upper()
    return None

def to_isbn13(isbn):
    if len(isbn) == 13:
        return isbn
    core = "978" + isbn[:9]
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(core))
    return core + str((10 - total % 10) % 10)

def _fold(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(c)).lower()

def _matches(tokens, title, author):
    haystack = _fold(f"{title or ''} {author or ''}")
    return all(_fold(t) in haystack for t in tokens)

def _isbn_in_catalog(isbn):
    return bool(supabase.table("books").select("id").eq("isbn", isbn).limit(1).execute().data)

def _search_open_library(q):
    try:
        resp = requests.get(
            "https://openlibrary.org/search.json",
            params={"q": q, "limit": CANDIDATES_PER_SOURCE, "fields": "title,author_name,isbn,cover_i"},
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code != 200:
            return []
        docs = resp.json().get("docs", [])
    except (requests.exceptions.RequestException, ValueError):
        return []

    out = []
    for d in docs:
        isbns = [i for i in (clean_isbn(x) for x in d.get("isbn", [])) if i]
        if not isbns:
            continue
        isbn = next((i for i in isbns if len(i) == 13), None) or to_isbn13(isbns[0])
        cover = f"https://covers.openlibrary.org/b/id/{d['cover_i']}-M.jpg" if d.get("cover_i") else None
        out.append({
            "title": d.get("title"),
            "author": ", ".join(d.get("author_name", [])[:2]) or None,
            "isbn": isbn,
            "cover_url": cover,
            "source": "open_library",
        })
    return out

def _search_isbndb(q):
    try:
        resp = requests.get(
            f"https://api2.isbndb.com/books/{requests.utils.quote(q)}",
            params={"page": 1, "pageSize": CANDIDATES_PER_SOURCE},
            headers=ISBNDB_HEADERS,
            timeout=10,
        )
        if resp.status_code != 200:
            return []
        books = resp.json().get("books", [])
    except (requests.exceptions.RequestException, ValueError):
        return []

    out = []
    for b in books:
        isbn = clean_isbn(b.get("isbn13") or b.get("isbn"))
        if not isbn:
            continue
        authors = b.get("authors") or []
        out.append({
            "title": b.get("title"),
            "author": ", ".join(flip_name(a) for a in authors) or None,
            "isbn": to_isbn13(isbn),
            "cover_url": b.get("image"),
            "source": "isbndb",
        })
    return out

def _search_google_books(q):
    import os
    params = {"q": q, "maxResults": CANDIDATES_PER_SOURCE, "printType": "books"}
    key = os.environ.get("GOOGLE_BOOKS_API_KEY")
    if key:
        params["key"] = key
    try:
        resp = requests.get("https://www.googleapis.com/books/v1/volumes", params=params, timeout=10)
        if resp.status_code != 200:
            return []
        items = resp.json().get("items", [])
    except (requests.exceptions.RequestException, ValueError):
        return []

    out = []
    for item in items:
        info = item.get("volumeInfo", {})
        ids = {i.get("type"): i.get("identifier") for i in info.get("industryIdentifiers", [])}
        isbn = clean_isbn(ids.get("ISBN_13") or ids.get("ISBN_10"))
        if not isbn:
            continue
        authors = info.get("authors") or []
        out.append({
            "title": info.get("title"),
            "author": ", ".join(flip_name(a) for a in authors) or None,
            "isbn": to_isbn13(isbn),
            "cover_url": info.get("imageLinks", {}).get("thumbnail"),
            "source": "google_books",
        })
    return out

def _same_work(a, b):
    if _fold(a["title"]).strip() != _fold(b["title"]).strip():
        return False
    if not a.get("author") or not b.get("author"):
        return True
    return authors_overlap(a["author"], b["author"])

def find_external_matches(q):
    tokens = _search_tokens(q)
    if not tokens:
        return []
    phrase = " ".join(tokens)

    cached = _lookup_cache.get(phrase)
    if cached and cached[0] > time.time():
        return cached[1]

    found = []
    for search in (_search_open_library, _search_isbndb, _search_google_books):
        for c in search(phrase):
            if not c.get("title") or not _matches(tokens, c["title"], c["author"]):
                continue
            if any(_same_work(c, f) for f in found):
                continue
            if _isbn_in_catalog(c["isbn"]) or is_duplicate_work(c["title"], c["author"]):
                continue
            found.append(c)
            if len(found) >= MAX_CANDIDATES:
                break
        if len(found) >= MAX_CANDIDATES:
            break

    if len(_lookup_cache) >= LOOKUP_CACHE_MAX:
        _lookup_cache.clear()
    _lookup_cache[phrase] = (time.time() + LOOKUP_CACHE_SECONDS, found)
    return found

def find_external_match(q):
    matches = find_external_matches(q)
    return matches[0] if matches else None

def _check_rate_limit(user_id):
    now = time.time()
    recent = [t for t in _requests_by_user.get(user_id, []) if now - t < 3600]
    if len(recent) >= MAX_REQUESTS_PER_HOUR:
        _requests_by_user[user_id] = recent
        raise RequestLimitError("You've reached the hourly limit for adding books. Please try again later.")
    recent.append(now)
    _requests_by_user[user_id] = recent

def add_requested_book(user_id, isbn):
    clean = clean_isbn(isbn)
    if not user_id:
        raise ValueError("A valid user is required.")
    if not clean:
        raise ValueError("That doesn't look like a valid ISBN. Enter 10 or 13 digits.")
    isbn13 = to_isbn13(clean)

    existing = supabase.table("books").select("id, title, author").eq("isbn", isbn13).limit(1).execute().data
    if existing:
        return {"status": "exists", "book": existing[0]}

    _check_rate_limit(user_id)
    with _ingest_lock:
        book = get_book_metadata(isbn13)
        if not book:
            return {"status": "unavailable",
                    "message": "We couldn't find enough information (an English description is required) to add this book."}
        result = insert_book(book)

    if result == "duplicate":
        return {"status": "exists", "book": {"title": book["title"]}}
    row = (result.data or [{}])[0]
    return {"status": "added", "book": {"id": row.get("id"), "title": book["title"], "author": book.get("author")}}

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--add"]
    if args:
        found = find_external_match(" ".join(args))
        print("candidate:", found)
        if found and "--add" in sys.argv:
            print(add_requested_book("cli-test", found["isbn"]))
        sys.exit(0)
    
    print("T58/T59")
    results = []

    def check(label, ok):
        print(f" {label}: {'OK' if ok else 'FAIL'}")
        results.append(bool(ok))

    check("ISBN-10 converts to ISBN-13", to_isbn13("0306406152") == "9780306406157")
    check("hyphenated ISBN-13 is cleaned", clean_isbn("978-0-306-40615-7") == "9780306406157")
    check("bad ISBN is rejected", clean_isbn("123") is None and clean_isbn("abc") is None)
    check("all query words must appear", _matches(["dune", "herbert"], "Dune", "Frank Herbert")
            and not _matches(["dune", "tolkien"], "Dune", "Frank Herbert"))
    check("empty or one-letter query finds nothing", find_external_match("") is None and find_external_match("a") is None)

    _requests_by_user.pop("limit-test", None)
    try:
        for _ in range(MAX_REQUESTS_PER_HOUR):
            _check_rate_limit("limit-test")
        limited = False
        try:
            _check_rate_limit("limit-test")
        except RequestLimitError:
            limited = True
        check("hourly limit blocks the next request", limited)
    finally:
        _requests_by_user.pop("limit-test", None)

    try:
        add_requested_book("u", "xyz")
        raised = False
    except ValueError:
        raised = True
    check("invalid ISBN raises before any work", raised)

    check("nonsense title has no external match", find_external_match("zzzzqxqx wwwvvv") is None)
    
    row = supabase.table("books").select("isbn, title, author").limit(1).execute().data[0]
    check("a catalog book is recognized by ISBN", _isbn_in_catalog(row["isbn"]))
    check("a catalog book is recognized by title and author", is_duplicate_work(row["title"], row["author"]))

    check("same title, different authors are different works",
            not _same_work({"title": "Echo", "author": "Francesca Haig"}, {"title": "echo", "author": "Pam Muñoz Ryan"}))
    check("same work with an extra co-author is one work",
            _same_work({"title": "Dune", "author": "Frank Herbert"}, {"title": "Dune", "author": "Frank Herbert, Brian Herbert"}))
    check("same surname and initial but different first names are different authors",
            not authors_overlap("John Smith", "Jane Smith"))
    check("an initial matches a full first name", authors_overlap("J. K. Rowling", "Joanne Rowling"))
    check("accents are folded in author names", authors_overlap("José Saramago", "Jose Saramago"))

    try:
        add_requested_book("u", "123")
        msg = ""
    except ValueError as e:
        msg = str(e)
    check("invalid ISBN gives a readable message", "ISBN" in msg)

    failures = results.count(False)
    print(f"\n{'PASS' if failures == 0 else 'FAIL'}: {failures} mismatches")