import calendar
from collections import Counter
from datetime import timedelta

from reading_goals import _parse_ts, average_days_to_finish, validate_year

MAX_TZ_OFFSET = 840

def validate_month(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 12:
        raise ValueError("Month must be a whole number from 1 to 12.")
    return value

def validate_tz_offset(value):
    if isinstance(value, bool) or not isinstance(value, int) or abs(value) > MAX_TZ_OFFSET:
        raise ValueError("tz_offset must be a whole number of minutes between -840 and 840.")
    return value

def _local_finish(item, tz_offset_minutes):
    parsed = _parse_ts(item.get("finished_at"))
    if parsed is None or parsed.tzinfo is None:
        return None
    return parsed - timedelta(minutes=tz_offset_minutes)

def finished_in_month(item, year, month, tz_offset_minutes=0):
    local = _local_finish(item, tz_offset_minutes)
    return local is not None and local.year == year and local.month == month

def previous_month(year, month):
    validate_month(month)
    return (year - 1, 12) if month == 1 else (year, month - 1)

def month_counts(items, tz_offset_minutes=0):
    counts = Counter()
    for item in items:
        local = _local_finish(item, tz_offset_minutes)
        if local is not None:
            counts[(local.year, local.month)] += 1
    return [{"year": y, "month": m, "count": c} for (y, m), c in sorted(counts.items(), reverse=True)]

def first_month(rows, tz_offset_minutes=0):
    best = None
    for row in rows:
        for field in ("added_at", "started_at", "finished_at"):
            parsed = _parse_ts(row.get(field))
            if parsed is None or parsed.tzinfo is None:
                continue
            local = parsed - timedelta(minutes=tz_offset_minutes)
            key = (local.year, local.month)
            if best is None or key < best:
                best = key
    return best

def month_range(first, selected, current):
    start = min(first, selected) if first else selected
    end = max(current, selected)
    return {"from": {"year": start[0], "month": start[1]}, "to": {"year": end[0], "month": end[1]}}

def genre_mix(items, top=5):
    counts = Counter()
    for item in items:
        for tag in set(t for t in (item.get("genre_tags") or []) if isinstance(t, str)):
            counts[tag] += 1
    total = sum(counts.values())
    if total == 0:
        return []
    ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    slices = [{"genre": g, "count": c} for g, c in ranked[:top]]
    rest = sum(c for _, c in ranked[top:])
    if rest:
        slices.append({"genre": "Other", "count": rest})
    for s in slices:
        s["percent"] = round(s["count"] * 100 / total)
    return slices

def goal_progress(goal, finished_items, year, month, tz_offset_minutes=0):
    if isinstance(goal, bool) or not isinstance(goal, int) or goal < 1:
        return None
    count = 0
    for item in finished_items:
        local = _local_finish(item, tz_offset_minutes)
        if local is not None and local.year == year and local.month <= month:
            count += 1
    return {"year": year, "goal": goal, "finished": count, "percent": min(100, round(count * 100 / goal))}

def summarize_month(items, year, month, tz_offset_minutes=0, top_genres=3, max_books=4, max_covers=30):
    validate_year(year)
    validate_month(month)
    validate_tz_offset(tz_offset_minutes)

    in_month = []
    for item in items:
        local = _local_finish(item, tz_offset_minutes)
        if local is not None and local.year == year and local.month == month:
            in_month.append((local, item))
    in_month.sort(key=lambda pair: (pair[1].get("title") or "").casefold())
    in_month.sort(key=lambda pair: pair[0], reverse=True)
    ordered = [item for _, item in in_month]

    genres = Counter()
    for item in ordered:
        for tag in set(t for t in (item.get("genre_tags") or []) if isinstance(t, str)):
            genres[tag] += 1
    top = sorted(genres.items(), key=lambda pair: (-pair[1], pair[0]))[:top_genres]

    return {
        "year": year,
        "month": month,
        "label": f"{calendar.month_name[month]} {year}",
        "finished": len(ordered),
        "top_genres": [{"genre": g, "count": c} for g, c in top],
        "time_to_finish": average_days_to_finish(ordered),
        "books": [
            {"title": i.get("title"), "author": i.get("author"),
             "cover_url": i.get("cover_url"), "finished_at": i.get("finished_at"),
             "genre": next((t for t in (i.get("genre_tags") or []) if isinstance(t, str)), None),
             "liked": i.get("vote") == 1}
            for i in ordered[:max_books]
        ],
        "genre_mix": genre_mix(ordered),
        "covers": [
            {"title": i.get("title"), "author": i.get('author'), "cover_url": i.get("cover_url")}
            for i in ordered[:max_covers]
        ],
    }