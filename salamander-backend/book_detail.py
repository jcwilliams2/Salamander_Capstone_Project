BOOK_COLUMNS = "id, title, author, cover_url, description, genre_tags, isbn"

def _clean_text(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None

def _clean_tags(tags):
    if not isinstance(tags, list):
        return []
    seen, out = set(), []
    for tag in tags:
        tag = _clean_text(tag)
        if tag and tag.casefold() not in seen:
            seen.add(tag.casefold())
            out.append(tag)
    return out

def shape_book(row):
    book = {"id": row["id"], "title": _clean_text(row.get("title")) or "Untitled"}
    for key, source in (("author", "author"), ("cover_url", "cover_url"),
                        ("synopsis", "description"), ("isbn", "isbn")):
        value = _clean_text(row.get(source))
        if value:
            book[key] = value
    tags = _clean_tags(row.get("genre_tags"))
    if tags:
        book["genre_tags"] = tags
    return book

def attach_reader_state(book, status_row, vote_row):
    book["status"] = (status_row or {}).get("status") or ""
    book["vote"] = (vote_row or {}).get("vote") or 0
    return book