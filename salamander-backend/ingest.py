import os
import re
import time
import requests
import html
from supabase import create_client
from dotenv import load_dotenv
from langdetect import detect, LangDetectException
from sentence_transformers import SentenceTransformer

load_dotenv()

GENRE_KEYWORD_MAP = {
    "fantasy": "fantasy",
    "science fiction": "science fiction",
    "sci-fi": "science fiction",
    "mystery": "mystery",
    "thriller": "thriller",
    "suspense": "thriller",
    "crime fiction": "crime fiction",
    "crime": "crime fiction",
    "romance": "romance",
    "horror": "horror",
    "historical fiction": "historical fiction",
    "literary fiction": "literary fiction",
    "biography": "biography",
    "autobiography": "autobiography",
    "memoir": "memoir",
    "young adult": "young adult",
    "juvenile fiction": "childrens",
    "juvenile": "childrens",
    "middle grade": "childrens",
    "children": "childrens",
    "poetry": "poetry",
    "graphic novel": "graphic novel",
    "comic": "graphic novel",
    "self-help": "self help",
    "self help": "self help",
    "history": "history",
    "science": "science",
    "philosophy": "philosophy",
    "religion": "religion",
    "business": "business",
    "economics": "business",
    "true crime": "true crime",
    "humor": "humor",
    "comedy": "humor",
    "cooking": "cooking",
    "travel": "travel",
    "psychology": "psychology",
    "politics": "politics",
    "sports": "sports",
    "nonfiction": "nonfiction",
    "fiction": "fiction",
}

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"]
)

HEADERS = {"User-Agent": "Salamander-Capstone-Project/1.0 (jcwilliams14@student.fullsail.edu)"}
ISBNDB_HEADERS = {"Authorization": os.environ["ISBNDB_API_KEY"]}

embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

def generate_embedding(text):
    if not text:
        return None
    vector = embedding_model.encode(text)
    return vector.tolist()

def build_embedding_text(title, description):
    if description:
        return f"{title}. {description}" if title else description
    return title

def backfill_missing_embeddings():
    result = supabase.table("books").select("id, title, description").is_("embedding", "null").execute()
    print(f"Found {len(result.data)} books missing embeddings.")
    for row in result.data:
        embedding_text = build_embedding_text(row["title"], row["description"])
        embedding = generate_embedding(embedding_text)
        if embedding:
            supabase.table("books").update({"embedding": embedding}).eq("id", row["id"]).execute()
            print(f" Backfilled embedding for book id {row['id']}")

def query_similar_books(query_vector, exclude_ids=None, limit=10):
    result = supabase.rpc('match_books', {
        'query_embedding': query_vector,
        'match_count': limit,
        'exclude_ids': exclude_ids or []
    }).execute()
    return result.data

def clean_description(text):
    if not text:
        return None
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text if len(text) > 20 else None

def reclean_existing_descriptions():
    result = supabase.table("books").select("id, description").execute()
    updated = 0
    for row in result.data:
        cleaned = clean_description(row["description"])
        if cleaned != row["description"]:
            supabase.table("books").update({"description": cleaned}).eq("id", row["id"]).execute()
            print(f" Re-cleaned book id {row['id']}")
            updated += 1
    print(f"Re-cleaned {updated}/{len(result.data)} books.")

def is_english(text):
    if not text:
        return False
    try:
        return detect(text) == 'en'
    except LangDetectException:
        return False

def normalize_genre_tags(raw_tags):
    if not raw_tags:
        return []
    normalized = set()
    for tag in raw_tags:
        if not tag:
            continue
        tag_matches = set()
        for piece in re.split(r"[,/]", tag):
            cleaned = re.sub(r"[^a-z\s-]", "", piece.lower()).strip()
            if not cleaned:
                continue
            for keyword, canonical in GENRE_KEYWORD_MAP.items():
                if keyword in cleaned:
                    tag_matches.add(canonical)
                    break
        if len(tag_matches) >= 3:
            continue
        normalized.update(tag_matches)
    return sorted(normalized)

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
        "author": ", ".join(book.get("authors", [])) if book.get("authors") else None,
        "isbn": isbn,
        "description": book.get("synopsis") or book.get("excerpt"),
        "genre_tags": book.get("subjects"),
    }

def fetch_google_books_metadata(isbn):
    resp = requests.get(
        f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}", 
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
        "author": ", ".join(authors) if authors else None,
        "isbn": isbn,
        "description": volume_info.get("description"),
        "genre_tags": volume_info.get("categories"),
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
            author_names.append(name)

    return {
        "title": edition.get("title"),
        "author": ", ".join(author_names) if author_names else None,
        "isbn": isbn,
        "description": description,
        "genre_tags": genre_tags,
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
        if raw_subjects and author:
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

    primary["source_tier"] = source_tier
    primary["author"] = author
    primary["raw_subjects"] = raw_subjects
    primary["genre_tags"] = normalize_genre_tags(raw_subjects)

    cleaned_description = clean_description(primary.get("description"))
    primary["description"] = cleaned_description
    primary["is_english"] = is_english(cleaned_description) if clean_description else None

    embedding_text = build_embedding_text(primary.get("title"), cleaned_description)
    primary["embedding"] = generate_embedding(embedding_text)

    return primary



def insert_book(book_data):
    if not book_data or not book_data.get("title"):
        return None
    try:
        result = supabase.table("books").insert(book_data).execute()
        return result
    except Exception as e:
        if "duplicate key" in str(e):
            print(f" {book_data.gt('isbn')} already exists, skipping")
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
    hobbit = supabase.table("books").select("id, embedding").eq("isbn", "9780547928227").execute()
    similar = query_similar_books(hobbit.data[0]["embedding"], exclude_ids=[hobbit.data[0]["id"]])
    for book in similar:
        print(f"{book['title']} by {book['author']} — similarity: {book['similarity']:.3f}")