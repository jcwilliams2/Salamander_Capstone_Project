from reading_goals import _parse_ts

STATUS_ORDER = ["reading", "want_to_read", "finished", "dnf"]
SORTS = ("status", "year_newest", "year_oldest")

def _added_time(item):
    parsed = _parse_ts(item.get("added_at"))
    return parsed.timestamp() if parsed else None

def _title_key(item):
    return (item.get("title") or "").casefold()

def _status_rank(item):
    status = item.get("status")
    return STATUS_ORDER.index(status) if status in STATUS_ORDER else len(STATUS_ORDER)

def sort_library(items, sort="status"):
    if sort not in SORTS:
        raise ValueError("sort must be one of: status, year_newest, year_oldest.")

    def key(item):
        t = _added_time(item)
        undated = t is None
        if sort == "status":
            return (_status_rank(item), undated, -(t or 0), _title_key(item))
        if sort == "year_newest":
            return (undated, -(t or 0), _title_key(item))
        return (undated, t or 0, _title_key(item))
    
    return sorted(items, key=key)