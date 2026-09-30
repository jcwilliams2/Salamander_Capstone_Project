import os
import time
import requests
from supabase_client import supabase
from ingest import get_book_metadata, insert_book, HEADERS

NYT_API_KEY = os.environ["NYT_API_KEY"]

OPEN_LIBRARY_SUBJECTS = [
    "fantasy", "mystery", "poetry", "cooking", "true_crime",
    "science_fiction", "biography", "graphic_novels", "self_help", "travel",
    "horror", "romance", "young_adult", "history", "philosophy", "humor",
    "psychology", "art", "crime_fiction", "classic_literature",
]

NYT_LISTS = [
    "hardcover-fiction", "hardcover-nonfiction", "young-adult-hardcover",
    "graphic-books-and-manga", "advice-how-to-and-miscellaneous",
    "mass-market-monthly", "series-books", "combined-print-and-e-book-fiction",
]

def get_existing_isbns():
    result = supabase.table("books").select("isbn").execute()
    return set(row["isbn"] for row in result.data if row.get("isbn"))

def discover_isbns_by_subject(subject, limit=10):
    resp = requests.get(
        f"https://openlibrary.org/subjects/{subject}.json?limit={limit}",
        headers=HEADERS,
    )
    time.sleep(0.5)
    if resp.status_code != 200:
        print(f" Subject '{subject}' lookup failed: {resp.status_code}")
        return []

    works = resp.json().get("works", [])
    isbns = []
    for work in works:
        edition_key = work.get("cover_edition_key")
        if not edition_key:
            continue
        edition_resp = requests.get(
            f"https://openlibrary.org/books/{edition_key}.json", headers=HEADERS
        )
        time.sleep(0.5)
        if edition_resp.status_code != 200:
            continue
        edition_data = edition_resp.json()
        isbn_13 = edition_data.get("isbn_13")
        isbn_10 = edition_data.get("isbn_10")
        if isbn_13:
            isbns.append(isbn_13[0])
        elif isbn_10:
            isbns.append(isbn_10[0])
    return isbns

def discover_nyt_bestsellers(list_name):
    resp = requests.get(
        f"https://api.nytimes.com/svc/books/v3/lists/current/{list_name}.json",
        params={"api-key": NYT_API_KEY},
    )
    time.sleep(12)
    if resp.status_code != 200:
        print(f" NYT list '{list_name}' lookup failed: {resp.status_code}")
        return []

    books = resp.json().get("results", {}).get("books", [])
    return [b["primary_isbn13"] for b in books if b.get("primary_isbn13")]

def build_discovery_list(per_subject_limit=8):
    existing = get_existing_isbns()
    discovered = set()

    print("--- Discovering via Open Library subjects ---")
    for subject in OPEN_LIBRARY_SUBJECTS:
        isbns = discover_isbns_by_subject(subject, limit=per_subject_limit)
        new_ones = [i for i in isbns if i not in existing and i not in discovered]
        print(f" {subject}: found {len(isbns)}, {len(new_ones)} new")
        discovered.update(new_ones)

    print("\n--- Discovering via NYT Bestsellers ---")
    for list_name in NYT_LISTS:
        isbns = discover_nyt_bestsellers(list_name)
        new_ones = [i for i in isbns if i not in existing and i not in discovered]
        print(f" {list_name}: found {len(isbns)}, {len(new_ones)} new")
        discovered.update(new_ones)

    return list(discovered)

def ingest_discovered_books(isbn_list):
    successes, failures = 0, []
    for isbn in isbn_list:
        book_data = get_book_metadata(isbn)
        if book_data:
            insert_book(book_data)
            successes += 1
        else:
            failures.append(isbn)
    print(f"\nIngested {successes}/{len(isbn_list)}. Failed: {failures}")

if __name__ == "__main__":
    new_isbns = build_discovery_list(per_subject_limit=10)
    print(f"\nTotal new, deduplicated ISBNs discovered: {len(new_isbns)}")
    ingest_discovered_books(new_isbns)