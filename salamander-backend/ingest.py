import os
import re
import time
import requests
import html
import json
import math
import unicodedata
from collections import Counter
from names import flip_name
from langdetect import detect, LangDetectException
from sentence_transformers import SentenceTransformer
from supabase_client import supabase

GENRE_KEYWORD_MAP = {
    "fantasy": "fantasy",
    "science fiction": "science fiction",
    "sci-fi": "science fiction",
    "mystery": "mystery",
    "thriller": "thriller",
    "suspense": "thriller",
    "true crime": "true crime",
    "crime fiction": "crime fiction",
    "crime": "crime fiction",
    "romance": "romance",
    "horror": "horror",
    "historical fiction": "historical fiction",
    "literary fiction": "literary fiction",
    "autobiography": "autobiography",
    "biography": "biography",
    "biographies": "biography",
    "memoir": "memoir",
    "young adult": "young adult",
    "juvenile fiction": "childrens",
    "juvenile": "childrens",
    "middle grade": "childrens",
    "children": "childrens",
    "poetry": "poetry",
    "short stories": "short stories",
    "graphic novel": "graphic novel",
    "comic": "graphic novel",
    "self-help": "self help",
    "self help": "self help",
    "art history": "art",
    "fine art": "art",
    "art criticism": "art",
    "painting": "art",
    "photography": "art",
    "history": "history",
    "social science": "social science",
    "sociology": "social science",
    "anthropology": "social science",
    "political science": "politics",
    "science": "science",
    "philosophy": "philosophy",
    "religion": "religion",
    "business": "business",
    "economics": "business",
    "humor": "humor",
    "comedy": "humor",
    "cooking": "cooking",
    "travel": "travel",
    "psychology": "psychology",
    "politics": "politics",
    "sports": "sports",
    "adventure": "adventure",
    "nonfiction": "nonfiction",
    "fiction": "fiction",
}

MIN_SUPPORT = 2
SMALL_SUBJECT_LIST = 8
NOISY_GENRES = {"art", "history", "science", "religion", "fiction", "nonfiction", "politics",
                "philosophy", "psychology", "business", "sports", "travel", "humor",
                "social science", "self help", "adventure", "historical fiction", "literary fiction",
                "autobiography"}
FICTION_HEADING_MAP = {"historical": "historical fiction", "literary": "literary fiction"}
IGNORED_SUBJECT = re.compile(r"history and criticism|criticism and interpretation|early works to|reading level|large type")
NON_ART_CONTEXT = re.compile(r"militar|martial|performing art|\bin art\b|art museum")
CLASSICS_SUBJECTS = {"classics", "classic literature", "classic fiction", "literary classics"}
STRICT_GENRES = {"classics", "short stories"}
NO_RESCUE = STRICT_GENRES | {"adventure"}

HEADERS = {"User-Agent": "Salamander-Capstone-Project/1.0 (jcwilliams14@student.fullsail.edu)"}
ISBNDB_HEADERS = {"Authorization": os.environ["ISBNDB_API_KEY"]}
MIN_DESCRIPTION_LENGTH = 50
DUPLICATE_MIN_SIMILARITY = 0.4

embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

def is_placeholder(title, author):
    t = (title or "").strip().lower()
    a = (author or "").lower()
    return bool(re.match(r"untitled\b", t)) or "to be revealed" in a or "to be confirmed" in a

def generate_embedding(text):
    if not text:
        return None
    vector = embedding_model.encode(text)
    return vector.tolist()

def build_embedding_text(title, description):
    if description:
        return f"{title}. {description}" if title else description
    return title

def clean_description(text):
    if not text:
        return None
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text if len(text) > 20 else None

def is_english(text):
    if not text:
        return False
    try:
        return detect(text) == 'en'
    except LangDetectException:
        return False

def _match_piece(cleaned):
    if re.search(r"biography\s*autobiography", cleaned):
        return "biography"
    if cleaned in CLASSICS_SUBJECTS:
        return "classics"
    for keyword, canonical in GENRE_KEYWORD_MAP.items():
        if keyword in cleaned:
            return canonical
    if re.search(r"\bart\b", cleaned) and not NON_ART_CONTEXT.search(cleaned):
        return "art"
    return None

def genre_support(raw_tags):
    support = Counter()
    for tag in raw_tags or []:
        if not tag:
            continue
        fiction_heading = tag.strip().lower().startswith("fiction")
        matches = set()
        for piece in re.split(r"[,/]", tag):
            cleaned = re.sub(r"[^a-z\s-]", "", piece.lower()).strip()
            if not cleaned or IGNORED_SUBJECT.search(cleaned):
                continue
            genre = _match_piece(cleaned)
            if not genre and fiction_heading:
                genre = FICTION_HEADING_MAP.get(cleaned)
            if genre:
                matches.add(genre)
        if len(matches) >= 3:
            continue
        for genre in matches:
            support[genre] += 1
    return support

def genre_threshold(genre, subject_count):
    if genre in STRICT_GENRES and subject_count >= SMALL_SUBJECT_LIST:
        return MIN_SUPPORT
    if subject_count < SMALL_SUBJECT_LIST or genre not in NOISY_GENRES:
        return 1
    return MIN_SUPPORT

def exact_genres(raw_tags):
    out = set()
    for raw in raw_tags:
        whole = (raw or "").lower().strip()
        if whole.startswith("fiction"):
            out.add("fiction")
        for label in (whole, whole.split("/")[0].strip()):
            g = GENRE_KEYWORD_MAP.get(label)
            if g and label.replace("-", " ") == g:
                out.add(g)
    return out

def normalize_genre_tags(raw_tags):
    if not raw_tags:
        return []
    support = genre_support(raw_tags)
    n = len(raw_tags)
    exact = exact_genres(raw_tags)
    kept = [g for g, c in support.items()
            if c >= genre_threshold(g, n) or (g in exact and g not in NO_RESCUE)]
    if not kept and support:
        top = max(support.values())
        kept = sorted(g for g, c in support.items()
                        if c == top and g not in NO_RESCUE)[:3]
    return sorted(kept)

def fetch_isbndb_metadata(isbn):
    resp = requests.get(
        f"https://api2.isbndb.com/book/{isbn}",
        headers=ISBNDB_HEADERS,
        timeout=10
    )
    time.sleep(0.5)

    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        print(f" ISBNdb unexpected status {resp.status_code} for {isbn}")
        return None
    
    try:
        payload = resp.json()
    except requests.exceptions.JSONDecodeError:
        print(f" Invalid JSON from ISBNdb for {isbn}")
        return None

    book = payload.get("book")
    if not book:
        return None

    return {
        "title": book.get("title"),
        "author": ", ".join(flip_name(a) for a in book.get("authors", [])) if book.get("authors") else None,
        "isbn": isbn,
        "description": book.get("synopsis") or book.get("excerpt"),
        "genre_tags": book.get("subjects"),
        "cover_url": book.get("image"),
    }

def fetch_google_books_metadata(isbn):
    params = {"q": f"isbn:{isbn}"}
    key = os.environ.get("GOOGLE_BOOKS_API_KEY")
    if key:
        params["key"] = key
    resp = requests.get(
        f"https://www.googleapis.com/books/v1/volumes", 
        params=params,
        timeout=10
    )
    time.sleep(0.5)

    if resp.status_code != 200:
        print(f" Google Books unexpected status {resp.status_code} for {isbn}")
        return None

    try:
        payload = resp.json()
    except requests.exceptions.JSONDecodeError:
        print(f" Invalid JSON from Google Books for {isbn}")
        return None

    items = payload.get("items")
    if not items:
        return None

    volume_info = items[0].get("volumeInfo",  {})
    authors = volume_info.get("authors")

    return {
        "title": volume_info.get("title"),
        "author": ", ".join(flip_name(a) for a in authors) if authors else None,
        "isbn": isbn,
        "description": volume_info.get("description"),
        "genre_tags": volume_info.get("categories"),
        "cover_url": volume_info.get("imageLinks", {}).get("thumbnail"),
    }

def safe_get_json(url, retries=3):
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
        except requests.exceptions.RequestException:
            print(f" Connection error on attempt {attempt + 1}/{retries} for {url}")
            time.sleep(2 * (attempt + 1))
            continue

        time.sleep(0.5)
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            print(f" Unexpected status {resp.status_code} for {url}")
            return None
        try:
            return resp.json()
        except requests.exceptions.JSONDecodeError:
            print(f" Invalid JSON for {url}. Raw: {resp.text[:200]}")
            return None
    print(f" Giving up on {url} after {retries} attempts")
    return None

def get_details(work_key):
    work_data = safe_get_json(f"https://openlibrary.org{work_key}.json")
    if not work_data:
        return None, None
    description = work_data.get("description")
    if isinstance(description, dict):
        description = description.get("value")
    subjects = work_data.get("subjects")
    return description, subjects

def get_author(author_key):
    author_data = safe_get_json(f"https://openlibrary.org{author_key}.json")
    if not author_data:
        return None
    return author_data.get("name")

def fetch_open_library_metadata(isbn):
    edition = safe_get_json(f"https://openlibrary.org/isbn/{isbn}.json")
    if not edition:
        return None

    description, genre_tags = None, None
    works = edition.get("works")
    if works:
        description, genre_tags = get_details(works[0]["key"])

    author_names = []
    for a in edition.get("authors", []):
        name = get_author(a["key"])
        if name:
            author_names.append(flip_name(name))

    cover_ids = edition.get("covers")
    cover_url = f"https://covers.openlibrary.org/b/id/{cover_ids[0]}-M.jpg" if cover_ids else None

    return {
        "title": edition.get("title"),
        "author": ", ".join(author_names) if author_names else None,
        "isbn": isbn,
        "description": description,
        "genre_tags": genre_tags,
        "cover_url": cover_url
    }

def get_book_metadata(isbn):
    ol_data = fetch_open_library_metadata(isbn)
    if ol_data and ol_data.get("description"):
        primary, source_tier = ol_data, "open_library"
    else:
        print(f" Falling back to ISBNdb for {isbn}")
        isbndb_data = fetch_isbndb_metadata(isbn)
        if isbndb_data and isbndb_data.get("description"):
            primary, source_tier = isbndb_data, "isbndb"
        else:
            print(f" Falling back to Google Books for {isbn}")
            gb_data = fetch_google_books_metadata(isbn)
            if gb_data:
                primary = gb_data
                source_tier = "google_books" if gb_data.get("description") else "google_books_no_description"
            elif isbndb_data:
                primary, source_tier = isbndb_data, "isbndb_no_description"
            else:
                return None

    raw_subjects = primary.get("genre_tags")
    author = primary.get("author")

    print(f" {isbn}: primary={source_tier}, has_genre_tags={bool(raw_subjects)}, has_author={bool(author)}")

    alt_fetchers = {
        "open_library": fetch_open_library_metadata,
        "isbndb": fetch_isbndb_metadata,
        "google_books": fetch_google_books_metadata,
    }
    for name, fetcher in alt_fetchers.items():
        if raw_subjects and author and primary.get("cover_url"):
            break
        if name in source_tier:
            continue
        alt = fetcher(isbn)
        if not alt:
            continue
        if not raw_subjects and alt.get("genre_tags"):
            raw_subjects = alt.get("genre_tags")
            print(f" Backfilled genre_tags for {isbn} from {name}")
        if not author and alt.get("author"):
            author = alt.get("author")
            print(f" Backfilled author for {isbn} from {name}")
        if not primary.get("cover_url") and alt.get("cover_url"):
            primary["cover_url"] = alt.get("cover_url")
            print(f" Backfilled cover_url for {isbn} from {name}")

    primary["source_tier"] = source_tier
    primary["author"] = author
    if is_placeholder(primary.get("title"), author):
        print(f" Skipping placeholder: {primary.get('title')} / {author}")
        return None
    primary["raw_subjects"] = raw_subjects
    primary["genre_tags"] = normalize_genre_tags(raw_subjects)

    cleaned_description = clean_description(primary.get("description"))
    if not cleaned_description or len(cleaned_description) < MIN_DESCRIPTION_LENGTH:
        print(f" Skipping {isbn}: no usable description ({primary.get('title')})")
        return None
    primary["description"] = cleaned_description
    primary["is_english"] = is_english(cleaned_description)
    if not primary["is_english"]:
        print(f" Skipping {isbn}: description not English ({primary.get('title')})")
        return None

    embedding_text = build_embedding_text(primary.get("title"), cleaned_description)
    primary["embedding"] = generate_embedding(embedding_text)

    return primary

def _author_key(author):
    first = (author or "").split(",")[0]
    return re.sub(r"[^a-z]", "", first.lower())

def _escape_like(text):
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

def _fold_name(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(c)).lower()

def _author_names(author):
    names = []
    for part in (author or "").split(","):
        tokens = re.sub(r"[^a-z\s]", "", re.sub(r"[.\-]", " ", _fold_name(part))).split()
        if tokens:
            names.append((tokens[0] if len(tokens) > 1 else "", tokens[-1]))
    return names

def _given_compatible(a, b):
    if not a or not b or a == b:
        return True
    return (len(a) == 1 and b.startswith(a)) or (len(b) == 1 and a.startswith(b))

def authors_overlap(author_a, author_b):
    for ga, sa in _author_names(author_a):
        for gb, sb in _author_names(author_b):
            if sa == sb and _given_compatible(ga, gb):
                return True

    return False

def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0

def _as_vector(value):
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    return value if isinstance(value, list) and value else None

def is_duplicate_work(title, author, embedding=None):
    if not _author_names(author):
        return False
    rows = supabase.table("books").select("id, author, embedding").ilike("title", _escape_like(title.strip())).execute().data
    for r in rows:
        if not authors_overlap(author, r.get("author")):
            continue
        stored = _as_vector(r.get("embedding"))
        if embedding is None or stored is None:
            return True
        if _cosine(embedding, stored) >= DUPLICATE_MIN_SIMILARITY:
            return True
    return False

def insert_book(book_data):
    if not book_data or not book_data.get("title"):
        return None
    if is_duplicate_work(book_data["title"], book_data.get("author"), book_data.get("embedding")):
        print(f" Skipping duplicate edition: {book_data['title']} ({book_data.get('author')})")
        return "duplicate"
    try:
        result = supabase.table("books").insert(book_data).execute()
        return result
    except Exception as e:
        if "duplicate key" in str(e):
            print(f" {book_data.get('isbn')} already exists, skipping")
            return "duplicate"
        raise

def ingest_isbn_list(isbn_list):
    successes, failures = 0, []
    for isbn in isbn_list:
        try:
            book_data = get_book_metadata(isbn)
            if book_data:
                result = insert_book(book_data)
                if result == "duplicate":
                    print(f" {isbn} already in catalog")
                successes += 1
            else:
                failures.append(isbn)
        except Exception as e:
            print(f" Unexpected error on {isbn}: {e}")
            failures.append(isbn)
    print(f"Ingested {successes}/{len(isbn_list)}. Failed: {failures}")

if __name__ == "__main__":
    print("Nothing to see here.")