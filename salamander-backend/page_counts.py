import re

MIN_PAGES = 10
MAX_PAGES = 5000

def clean_page_count(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        match = re.search(r"\d+", value.replace(",", ""))
        if not match:
            return None
        value = match.group()
    try:
        pages = int(float(value))
    except (TypeError, ValueError, OverflowError):
        return None
    return pages if MIN_PAGES <= pages <= MAX_PAGES else None

def open_library_pages(edition):
    if not isinstance(edition, dict):
        return None
    return clean_page_count(edition.get("number_of_pages")) or clean_page_count(edition.get("pagination"))