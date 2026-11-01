import re
from datetime import date, datetime
from math import floor

MAX_GOAL = 1000
MIN_YEAR = 2000
MAX_YEAR = 2100

def validate_year(value):
    if isinstance(value, bool) or not isinstance(value, int) or not MIN_YEAR <= value <= MAX_YEAR:
        raise ValueError(f"Year must be a whole number from {MIN_YEAR} to {MAX_YEAR}.")
    return value

def validate_goal(value):
    if value is None:
        return None
    message = "Enter a whole number of 1 or more, or leave it blank for no goal."
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(message)
    if not 1 <= value <= MAX_GOAL:
        raise ValueError(message)
    return value

def compute_pace(goal, finished, today):
    goal = validate_goal(goal)
    if goal is None:
        return None
    if isinstance(finished, bool) or not isinstance(finished, int) or finished < 0:
        raise ValueError("finished must be a whole number, 0 or more.")
    if not isinstance(today, date):
        raise ValueError("today must be a date.")

    month = today.month
    expected = (goal * month) / 12
    difference = finished - expected
    amount = floor(abs(difference) + 0.5)

    if finished >= goal:
        status, amount = "complete", 0
    elif amount == 0:
        status = "on_track"
    elif difference > 0:
        status = "ahead"
    else:
        status = "behind"

    return {
        "goal": goal,
        "month": month,
        "finished": finished,
        "expected": round(expected, 1),
        "status": status,
        "amount": amount,
    }

def finished_count_for_year(finished_at_values, year):
    count = 0
    for value in finished_at_values:
        if not value:
            continue
        text = re.sub(r"\.(\d+)", lambda m: "." + (m.group(1) + "000000")[:6], str(value).replace("Z", "+00:00"))
        try:
            moment = datetime.fromisoformat(text)
        except ValueError:
            continue
        if moment.year == year:
            count += 1
    return count

def _parse_ts(value):
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        text = re.sub(r"\.(\d+)", lambda m: "." + m.group(1).ljust(6, "0")[:6], text)
        return datetime.fromisoformat(text)
    except ValueError:
        return None

def next_started_at(old_status, old_started_at, new_status, now):
    if new_status == "reading":
        if old_status == "reading":
            return old_started_at
        return now
    if new_status == "finished":
        if old_status in ("reading", "finished"):
            return old_started_at
        return None
    return None

def average_days_to_finish(rows):
    durations = []
    for row in rows:
        start = _parse_ts(row.get("started_at"))
        end = _parse_ts(row.get("finished_at"))
        if start is None or end is None:
            continue
        if (start.tzinfo is None) != (end.tzinfo is None):
            continue
        seconds = (end - start).total_seconds()
        if seconds < 0:
            continue
        durations.append(seconds / 86400)
    if not durations:
        return {"average_days": None, "books_counted": 0}
    return {"average_days": round(sum(durations) / len(durations), 1),
            "books_counted": len(durations)}