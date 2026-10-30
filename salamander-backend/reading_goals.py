from datetime import date
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