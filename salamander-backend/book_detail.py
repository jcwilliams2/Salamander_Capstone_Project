import json
import numpy as np

BOOK_COLUMNS = "id, title, author, cover_url, description, genre_tags, isbn, raw_subjects, embedding"

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

def tag_affinity(embedding, tags, centroids):
    if isinstance(embedding, str):
        embedding = json.loads(embedding)
    if embedding is None or not centroids:
        return {}
    vec = np.asarray(embedding, dtype=float)
    norm = np.linalg.norm(vec)
    if norm == 0:
        return {}
    out = {}
    for tag in tags:
        centroid = centroids.get(tag)
        if centroid is None:
            continue
        c = np.asarray(centroid, dtype=float)
        cnorm = np.linalg.norm(c)
        if cnorm:
            out[tag] = float(vec @ c / (norm * cnorm))
    return out

def rank_tags(tags, support=None, affinity=None):
    support = support or {}
    affinity = affinity or {}
    return sorted(tags, key=lambda t: (-support.get(t, 0), -affinity.get(t, 0.0), t.casefold()))

def shape_book(row, support=None, affinity=None):
    book = {"id": row["id"], "title": _clean_text(row.get("title")) or "Untitled"}
    for key, source in (("author", "author"), ("cover_url", "cover_url"),
                        ("synopsis", "description"), ("isbn", "isbn")):
        value = _clean_text(row.get(source))
        if value:
            book[key] = value
    tags = _clean_tags(row.get("genre_tags"))
    if tags:
        book["genre_tags"] = rank_tags(tags, support, affinity)
    return book

def attach_reader_state(book, status_row, vote_row):
    book["status"] = (status_row or {}).get("status") or ""
    book["vote"] = (vote_row or {}).get("vote") or 0
    return book