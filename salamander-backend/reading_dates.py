import re
from datetime import date
from reading_goals import _parse_ts

MIN_YEAR = 2000
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
_FORMAT_HELP = "Enter a date like 2026-10-31."

def parse_day(value, label):
    if not isinstance(value, str) or not _DAY.fullmatch(value):
        raise ValueError(f"{label}: {_FORMAT_HELP}")
    try:
        day = date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{label}: that isn't a real date. {_FORMAT_HELP}")
    if day.year < MIN_YEAR:
        raise ValueError(f"{label}: the year must be {MIN_YEAR} or later.")
    return day

def day_to_timestamp(day):
    return f"{day.isoformat()}T12:00:00+00:00"

def _day_of(timestamp):
    parsed = _parse_ts(timestamp)
    return parsed.date() if parsed else None

def apply_date_edit(status, existing_started, existing_finished, edit, today):
    changes = {}
    started_day = _day_of(existing_started)
    finished_day = _day_of(existing_finished)

    if "started_on" in edit:
        if status not in ("reading", "finished"):
            raise ValueError("A start date can only be set on a book you're reading or have finished.")
        if edit["started_on"] is None:
            started_day = None
            changes["started_at"] = None
        else:
            started_day = parse_day(edit["started_on"], "Start date")
            if started_day > today:
                raise ValueError("Start date can't be in the future.")
            changes["started_at"] = day_to_timestamp(started_day)

    if "finished_on" in edit:
        if status != "finished":
            raise ValueError("A finish date can only be set on a book marked Finished.")
        if edit["finished_on"] is None:
            raise ValueError("A finished book needs a finish date.")
        finished_day = parse_day(edit["finished_on"], "Finish date")
        if finished_day > today:
            raise ValueError("Finish date can't be in the future.")
        changes["finished_at"] = day_to_timestamp(finished_day)

    if changes and started_day and finished_day and finished_day < started_day:
        raise ValueError("The finish date can't be before the start date.")
    return changes