import calendar
from datetime import date, datetime, timedelta, timezone

from .schema import partial_date, require


def interval(value):
    partial_date(value, "date")
    if value is None:
        return None
    if len(value) == 4:
        return date(int(value), 1, 1), date(int(value), 12, 31)
    if len(value) == 7:
        year, month = map(int, value.split("-"))
        return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    parsed = date.fromisoformat(value)
    return parsed, parsed


def today(as_of=None):
    if as_of:
        partial_date(as_of, "as_of")
        require(len(as_of) == 10, "as_of requires YYYY-MM-DD")
        return date.fromisoformat(as_of)
    return datetime.now(timezone.utc).date()


def bounds(date_from=None, date_to=None, recent_days=None, as_of=None):
    if as_of is not None:
        today(as_of)
    start = interval(date_from)[0] if date_from else None
    end = interval(date_to)[1] if date_to else None
    if recent_days is not None:
        require(type(recent_days) is int and recent_days > 0, "recent_days must be positive")
        reference = today(as_of)
        start = max(start or date.min, reference - timedelta(days=recent_days - 1))
        end = min(end or date.max, reference)
    require(not start or not end or start <= end, "date_from must not exceed date_to")
    return start, end


def effective_answer(answer, as_of=None, stale_days=180):
    if not answer:
        return "missing"
    if answer["status"] == "stale":
        return "stale"
    timestamp = answer["verified_at"] or answer["created_at"]
    checked = datetime.fromisoformat(timestamp).date()
    return "stale" if (today(as_of) - checked).days > stale_days else answer["status"]
