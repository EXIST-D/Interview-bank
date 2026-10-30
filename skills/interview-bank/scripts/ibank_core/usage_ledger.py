"""Usage and cost of the Web reader's model calls and searches: per job and per Beijing day.

One ledger per bank is shared by the screenshot import and the mock interview, so the daily budget covers both."""
import threading
from datetime import datetime, timedelta

from . import ai
from .storage import atomic_write, dumps, read_json

USAGE_DAYS = 120


def add_usage(total, entries, prices):
    """Fold recorded calls into a usage summary; cost counts only calls with a configured price."""
    total = dict(total or {"calls": 0, "input": 0, "cached": 0, "output": 0, "searches": 0, "cost": 0.0, "unpriced": 0})
    for entry in entries:
        if entry["kind"] == "search":
            total["searches"] += 1
        else:
            total["calls"] += 1
            total["input"] += entry["hit"] + entry["miss"]
            total["cached"] += entry["hit"]
            total["output"] += entry["output"]
        price = ai.cost(entry, prices)
        if price is None:
            total["unpriced"] += 1
        else:
            total["cost"] = round(total["cost"] + price, 6)
    return total


class Ledger:
    """cache/web-intake/usage.json: per Beijing day, so totals line up with DeepSeek's bill; kept for USAGE_DAYS days."""

    def __init__(self, root, config):
        self.path = root / "usage.json"
        self.prices = config.get("prices", {})
        self.budget = config["limits"]["daily_budget"]
        self.lock = threading.Lock()

    def days(self):
        return (read_json(self.path) if self.path.is_file() else {"schema_version": 1, "days": {}})["days"]

    def add(self, entries):
        with self.lock:
            days = self.days()
            for entry in entries:
                day = datetime.fromisoformat(entry["at"]).astimezone(ai.BEIJING).date().isoformat()
                days[day] = add_usage(days.get(day), [entry], self.prices)
            days = {day: days[day] for day in sorted(days)[-USAGE_DAYS:]}
            atomic_write(self.path, dumps({"schema_version": 1, "days": days}) + "\n")

    def view(self):
        days = self.days()
        today = datetime.now(ai.BEIJING).date()
        recent = [days[d] for d in days if d >= (today - timedelta(days=29)).isoformat()]
        month = None
        for day in recent:
            month = {k: round((month or {}).get(k, 0) + v, 6) for k, v in day.items()}
        return {"today": days.get(today.isoformat()), "last_30_days": month, "priced": bool(self.prices),
                "daily_budget": self.budget or None}

    def over_budget(self):
        today = self.days().get(datetime.now(ai.BEIJING).date().isoformat())
        return bool(self.budget and today and today["cost"] >= self.budget)
