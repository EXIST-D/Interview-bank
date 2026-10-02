"""Retired SQLite projection.

Queries filter the canonical data that open_bank has already loaded and validated; the old
cache/bank.sqlite was read back in full on every query and never used for SQL filtering.
`rebuild-index` remains as a deprecated command that removes the leftover cache file.
"""
from .storage import bank_file, open_bank

LEGACY_CACHE = "cache/bank.sqlite"


def rebuild_index(bank):
    """Deprecated no-op kept for scripts written against older versions."""
    with open_bank(bank):
        cache = bank_file(bank, LEGACY_CACHE)
        removed = cache.is_file()
        if removed:
            cache.unlink()
        return {"index": "not_used", "deprecated": True, "legacy_cache_removed": removed,
                "hint": "Queries read the canonical JSONL directly; rebuild-index is no longer needed and will be removed."}
