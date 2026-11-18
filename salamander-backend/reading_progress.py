def _whole(value, name):
    if isinstance(value, bool):
        raise ValueError(f"The {name} must be a whole number.")
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError(f"The {name} must be a whole number.")
        value = int(value)
    if not isinstance(value, int):
        raise ValueError(f"The {name} must be a whole number.")
    return value

def validate_progress(percent, page, page_count):
    if percent is None and page is None:
        raise ValueError("Send a percent or a page number.")
    if percent is not None and page is not None:
        raise ValueError("Send either a percent or a page number, not both.")
    if page is not None:
        if not page_count:
            raise ValueError("This book has no page count yet, so enter a percent instead.")
        page = _whole(page, "page")
        if not 0 <= page <= page_count:
            raise ValueError(f"The page must be between 0 and {page_count}.")
        return page * 100 // page_count, page
    percent = _whole(percent, "percent")
    if not 0 <= percent <= 100:
        raise ValueError("The percent must be between 0 and 100.")
    return percent, None

def progress_after_status_change(old_status, new_status, percent, page):
    if new_status == "finished":
        return 100, None
    if new_status == "want_to_read":
        return None, None
    if old_status == "finished":
        return None, None
    return percent, page