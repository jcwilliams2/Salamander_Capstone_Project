import re
from page_counts import clean_page_count

KINDS = ("page_count",)
MAX_NOTE = 300
MAX_OPEN_FLAGS = 20

def validate_flag(kind, suggested_pages, note):
    if kind not in KINDS:
        raise ValueError("That kind of report isn't supported.")
    pages = None
    if suggested_pages is not None:
        pages = clean_page_count(suggested_pages)
        if pages is None:
            raise ValueError("Enter a page count between 10 and 5000, or leave it blank.")
    cleaned = re.sub(r"\s+", " ", note or "").strip() or None
    if cleaned and len(cleaned) > MAX_NOTE:
        raise ValueError(f"Keep the note under {MAX_NOTE} characters.")
    return kind, pages, cleaned