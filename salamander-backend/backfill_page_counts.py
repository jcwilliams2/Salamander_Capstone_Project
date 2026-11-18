import argparse
from collections import Counter

from ingest import fetch_page_count
from supabase_client import supabase

PAGE = 1000

def books_missing_pages():
    rows, start = [], 0
    while True:
        batch = (supabase.table("books").select("id, isbn, title").is_("page_count", "null")
                    .order("id").range(start, start + PAGE - 1).execute().data)
        rows += batch
        if len(batch) < PAGE:
            break
        start += PAGE
    return [r for r in rows if r.get("isbn")]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="only try this many books")
    parser.add_argument("--dry-run", action="store_true", help="look pages up but do not save them")
    args = parser.parse_args()

    todo = books_missing_pages()
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(todo)} books to try")

    found, missing = Counter(), []
    for i, book in enumerate(todo, 1):
        try:
            pages, source = fetch_page_count(book["isbn"])
        except Exception as e:
            print(f" Error on {book['isbn']}: {e}")
            missing.append(book["title"])
            continue
        if pages:
            if not args.dry_run:
                supabase.table("books").update({"page_count": pages}).eq("id", book["id"]).execute()
            found[source] += 1
            print(f" [{i}/{len(todo)}] {book['title']}: {pages} pages ({source})")
        else:
            missing.append(book["title"])
            print(f" [{i}/{len(todo)}] {book['title']}: no page count found")

    print(f"\nFilled {sum(found.values())} of {len(todo)} ({dict(found)}).")
    if missing:
        print(f"No page count for {len(missing)}: {missing[:25]}{' ...' if len(missing) > 25 else ''}")
    if args.dry_run:
        print("(dry run: nothing was saved)")

if __name__ == "__main__":
    main()