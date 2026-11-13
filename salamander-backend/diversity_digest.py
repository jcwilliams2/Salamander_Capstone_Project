from datetime import datetime, timedelta, timezone

FREQUENCIES = {
    "weekly": ("Weekly", 7),
    "biweekly": ("Every 2 weeks", 14),
    "monthly": ("Monthly", 30),
    "bimonthly": ("Every 2 months", 60),
    "quarterly": ("Every 3 months", 90),
}
DEFAULT_FREQUENCY = "biweekly"
DIGEST_DAYS = FREQUENCIES[DEFAULT_FREQUENCY][1]
DIGEST_PICKS = 3
TREND_TOLERANCE = 0.02

HEADLINES = {
    "first": "Here's a first look at the variety in your reading.",
    "up": "Your reading variety is a little higher than in your last digest.",
    "down": "Your reading variety is a little lower than in your last digest.",
    "steady": "Your reading variety is about the same as in your last digest.",
}

def _parse(stamp):
    if isinstance(stamp, datetime):
        parsed = stamp
    else:
        try:
            parsed = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

def frequency_options():
    return [{"value": v, "label": label, "days": days} for v, (label, days) in FREQUENCIES.items()]

def validate_frequency(value):
    if value not in FREQUENCIES:
        raise ValueError("Choose weekly, biweekly, monthly, every 2 months or every 3 months.")
    return value

def days_for(frequency):
    return FREQUENCIES.get(frequency, FREQUENCIES[DEFAULT_FREQUENCY])[1]

def digest_due(latest_created_at, now=None, days=DIGEST_DAYS):
    if latest_created_at is None:
        return True
    created = _parse(latest_created_at)
    if created is None:
        return True
    now = now or datetime.now(timezone.utc)
    return now - created >= timedelta(days=days)

def trend_label(score, previous_score, tolerance=TREND_TOLERANCE):
    if previous_score is None:
        return "first"
    change = score - previous_score
    if change > tolerance:
        return "up"
    if change < -tolerance:
        return "down"
    return "steady"

def shape_pick(book):
    pick = {"id": book.get("id"), "title": book.get("title") or ""}
    for field in ("author", "cover_url", "explanation"):
        if book.get(field):
            pick[field] = book[field]
    return pick

def build_findings(score, previous_score, picks, books_considered, limit=DIGEST_PICKS):
    trend = trend_label(score, previous_score)
    return {
        "score": round(float(score), 3),
        "score_percent": round(float(score) * 100),
        "previous_score": None if previous_score is None else round(float(previous_score), 3),
        "trend": trend,
        "headline": HEADLINES[trend],
        "books_considered": int(books_considered),
        "picks": [shape_pick(p) for p in (picks or []) if p.get("id")][:limit],
    }

def unseen_digest(row):
    if not row or row.get("seen_at"):
        return None
    findings = row.get("findings") or {}
    return {"id": row["id"], "created_at": row.get("created_at"), **findings}