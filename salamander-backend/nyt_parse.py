import re
from datetime import date

ISBN13 = re.compile(r"\d{13}")

def clean_isbn13(value):
    digits = re.sub(r"[\s-]", "", str(value or ""))
    return digits if ISBN13.fullmatch(digits) else None

def split_authors(author):
    text = re.sub(r"\s+", " ", author or "").strip()
    if not text:
        return []
    parts = re.split(r",\s*|\s+and\s+|\s*&\s*|\s+with\s+", text)
    return [p.strip() for p in parts if p.strip()]

def _clean_int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None

def parse_list_response(payload, list_name):
    results = (payload or {}).get("results") or {}
    try:
        published = date.fromisoformat(results.get("published_date") or "")
    except ValueError:
        raise ValueError("The NYT response has no usable published date.")
    books, seen = [], set()
    for b in results.get("books") or []:
        rank = b.get("rank")
        if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1 or rank in seen:
            continue
        seen.add(rank)
        books.append({
            "rank": rank,
            "isbn": clean_isbn13(b.get("primary_isbn13")),
            "title": re.sub(r"\s+", " ", b.get("title") or "").strip() or None,
            "author": re.sub(r"\s+", " ", b.get("author") or "").strip() or None,
            "weeks_on_list": _clean_int(b.get("weeks_on_list")),
        })
    if not books:
        raise ValueError("The NYT response has no books.")
    books.sort(key=lambda b: b["rank"])
    return {"list_name": list_name, "published_date": published.isoformat(), "books": books}