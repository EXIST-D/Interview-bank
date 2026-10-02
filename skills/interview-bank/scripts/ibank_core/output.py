"""Bounded CLI output. Agents read stdout into their context, so every result has a byte budget.

A result that does not fit is saved whole under bank/cache/outputs/ and stdout receives the
largest list trimmed to the budget plus a `_page` block saying how to read the rest. Canonical
data and task packets on disk are never trimmed.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_BUDGET = 32768
# Constant reference blocks repeated in every classification task; the full task file keeps them.
REFERENCE_KEYS = ("taxonomy", "company_profile_fields", "companies")


def budget():
    """Byte budget for one stdout result; INTERVIEW_BANK_MAX_OUTPUT overrides (minimum 4096)."""
    try:
        return max(4096, int(os.environ.get("INTERVIEW_BANK_MAX_OUTPUT", DEFAULT_BUDGET)))
    except ValueError:
        return DEFAULT_BUDGET


def encode(value, pretty=False):
    if pretty:
        return json.dumps(value, ensure_ascii=False, indent=2)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def size(value):
    return len(encode(value).encode("utf-8"))


def save_full(bank, command, result):
    """Keep the untrimmed result where the agent can page through it; None when there is no bank."""
    if bank is None or not (Path(bank) / "manifest.json").is_file():
        return None
    from .storage import atomic_write, bank_file
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = bank_file(Path(bank), f"cache/outputs/{command}-{stamp}-{os.getpid()}.json")
    atomic_write(target, encode(result) + "\n")
    return str(target)


def fit(command, result, bank=None, limit=None):
    """Return `result` unchanged when it fits, otherwise a trimmed copy with a `_page` block."""
    limit = limit or budget()
    if not isinstance(result, dict) or size(result) <= limit:
        return result
    trimmed = dict(result)
    omitted = [key for key in REFERENCE_KEYS if key in trimmed]
    for key in omitted:
        del trimmed[key]
    lists = [key for key, value in trimmed.items() if isinstance(value, list) and value]
    field = max(lists, key=lambda key: size(trimmed[key]), default=None)
    page = {"field": field, "returned": 0, "total": len(trimmed[field]) if field else 0, "next_offset": 0,
            "omitted_keys": omitted, "full_output": save_full(bank, command, result), "budget_bytes": limit}
    if field:
        items, low, high = trimmed[field], 0, len(trimmed[field])
        # Largest prefix that fits, leaving room for the page block itself.
        while low < high:
            middle = (low + high + 1) // 2
            if size({**trimmed, field: items[:middle], "_page": page}) <= limit:
                low = middle
            else:
                high = middle - 1
        trimmed[field] = items[:low]
        # A result that is already a page (search, run-show --offset) continues from its own offset.
        start = result.get("offset") if type(result.get("offset")) is int else 0
        following = start + low if low < len(items) else result.get("next_offset", start + low)
        page.update(returned=low, next_offset=following)
        if "next_offset" in result:
            trimmed["next_offset"] = following
    is_task = str(result.get("id", "")).startswith("run_") and field == "items"
    page["hint"] = (f"Read the remaining items with: run-show --run {result['id']} --offset {page['next_offset']} --limit 20"
                    if is_task else "Narrow the query (--limit/--offset or filters) or read full_output")
    trimmed["_page"] = page
    return trimmed
