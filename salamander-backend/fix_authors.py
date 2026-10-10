import sys
from supabase_client import supabase
from names import fix_stored_author

APPLY = "--apply" in sys.argv

rows, start = [], 0
while True:
    batch = supabase.table("books").select("id, author").order("id").range(start, start + 999).execute().data
    rows += batch
    if len(batch) < 1000:
        break
    start += 1000

changes = [(r["id"], r["author"], fix_stored_author(r["author"])) for r in rows if r["author"] and fix_stored_author(r["author"]) != r["author"]]

for _, old, new in changes:
    print(f"{old!r} -> {new!r}")
print(f"\n{len(changes)} of {len(rows)} authors would change")

if APPLY:
    for book_id, _, new in changes:
        supabase.table("books").update({"author": new}).eq("id", book_id).execute()
    print("Applied.")
else:
    print("Dry run. Re-run with --apply to write.")