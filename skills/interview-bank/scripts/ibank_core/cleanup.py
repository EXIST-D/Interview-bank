"""Reclaim runs/ space without losing history.

Snapshot runs written before 1.12 (format 1) store a full before-image plus the full staged tables;
newer runs store a change set. Once a run is committed and can no longer be undone, either is dead
weight: compaction removes it and keeps run.json (audit), commit.json and report.md. Expired task
packets, spilled outputs and the retired SQLite cache are deleted. Intakes and unknown directories
are never touched: media intakes hold the only full transcripts.
"""
import shutil
from datetime import datetime, timedelta, timezone

from .ids import utc_now
from .schema import TABLES, require
from .storage import atomic_write, bank_file, dumps, fingerprint, open_bank, read_json
from .timestamps import parse_timestamp

SNAPSHOT_FILES = (*(f"{table}.jsonl" for table in TABLES), "before.json", "state.json", "changes.jsonl",
                  "config_before.json", "config_after.json")


def _tree_bytes(path):
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.exists() else 0


def _created(path, meta):
    try:
        return parse_timestamp(meta["created_at"])
    except (KeyError, TypeError, ValueError):
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _inventory(bank):
    entries = []
    for path in sorted(bank_file(bank, "runs").glob("run_*")):
        if not path.is_dir():
            continue
        for kind, name in (("stage", "run.json"), ("task", "task.json"), ("intake", "intake.json")):
            if (path / name).is_file():
                meta = read_json(path / name)
                break
        else:
            kind, meta = "unknown", {}
        entries.append({"id": path.name, "path": path, "kind": kind, "meta": meta, "created": _created(path, meta)})
    return entries


def plan(bank, current, keep_days=30, keep_last=20, now=None):
    """Decide what may be compacted or deleted; every kept stage records why."""
    require(type(keep_days) is int and keep_days >= 0 and type(keep_last) is int and keep_last >= 0,
            "keep-days and keep-last must be non-negative integers")
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=keep_days)
    entries = _inventory(bank)
    by_id = {e["id"]: e for e in entries}
    reasons = {}

    def keep(run_id, reason):
        reasons.setdefault(run_id, reason)

    digest = fingerprint(current)
    for entry in entries:
        meta = entry["meta"]
        if entry["kind"] == "stage" and meta.get("status") == "staged":
            keep(entry["id"], "pending stage")
        if entry["kind"] == "stage" and meta.get("status") == "committed" and (entry["path"] / "commit.json").is_file():
            if read_json(entry["path"] / "commit.json").get("after_digest") == digest:
                keep(entry["id"], "latest undo point")
                for predecessor in meta.get("supersedes", []):
                    keep(predecessor, "import restored by undoing the latest merge")
        if entry["created"] > cutoff:
            keep(entry["id"], f"younger than {keep_days} days")
    for kind in ("stage", "task"):
        newest = sorted((e for e in entries if e["kind"] == kind), key=lambda e: e["created"], reverse=True)[:keep_last]
        for entry in newest:
            keep(entry["id"], f"newest {keep_last} {kind}s")

    compact, delete = [], []
    for entry in entries:
        if entry["id"] in reasons or entry["kind"] in ("intake", "unknown"):
            continue
        if entry["kind"] == "stage":
            files = [entry["path"] / name for name in SNAPSHOT_FILES if (entry["path"] / name).is_file()]
            if files:
                compact.append({"run_id": entry["id"], "status": entry["meta"].get("status"),
                                "operation": entry["meta"].get("operation", "ingest"),
                                "bytes": sum(f.stat().st_size for f in files), "files": [f.name for f in files]})
        elif entry["kind"] == "task":
            delete.append({"run_id": entry["id"], "operation": entry["meta"].get("operation"), "bytes": _tree_bytes(entry["path"])})
    outputs = bank_file(bank, "cache/outputs")
    stale_outputs = [p for p in outputs.glob("*.json") if datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc) < cutoff] if outputs.is_dir() else []
    legacy = bank_file(bank, "cache/bank.sqlite")
    legacy_bytes = legacy.stat().st_size if legacy.is_file() else 0
    kept = {}
    for run_id, reason in reasons.items():
        if run_id in by_id:
            kept[reason] = kept.get(reason, 0) + 1
    return {"compact": compact, "delete_tasks": delete, "stale_outputs": [str(p) for p in stale_outputs],
            "legacy_index_bytes": legacy_bytes,
            "kept": kept, "never_touched": {"intakes": sum(e["kind"] == "intake" for e in entries),
                                            "unknown": sum(e["kind"] == "unknown" for e in entries)},
            "reclaim_bytes": sum(i["bytes"] for i in compact) + sum(i["bytes"] for i in delete)
                             + sum(p.stat().st_size for p in stale_outputs) + legacy_bytes}


def gc(bank, apply=False, keep_days=30, keep_last=20):
    """Dry-run by default; with apply, act under the bank lock and log what was removed."""
    with open_bank(bank) as (_, _, current):
        before = _tree_bytes(bank_file(bank, "runs"))
        result = plan(bank, current, keep_days, keep_last)
        result.update(mode="applied" if apply else "dry-run", runs_bytes_before=before,
                      policy={"keep_days": keep_days, "keep_last": keep_last})
        if not apply:
            result["hint"] = "Nothing was changed. Show this summary to the user and rerun with --apply after they agree."
            return result
        for item in result["compact"]:
            for name in item["files"]:
                bank_file(bank, f"runs/{item['run_id']}/{name}").unlink()
        for item in result["delete_tasks"]:
            shutil.rmtree(bank_file(bank, f"runs/{item['run_id']}"))
        for path in result["stale_outputs"]:
            bank_file(bank, "cache/outputs/" + path.replace("\\", "/").rsplit("/", 1)[-1]).unlink()
        if result["legacy_index_bytes"]:
            bank_file(bank, "cache/bank.sqlite").unlink()
        result["runs_bytes_after"] = _tree_bytes(bank_file(bank, "runs"))
        log = bank_file(bank, f"logs/gc-{utc_now().replace(':', '').replace('+', 'Z')}.json")
        atomic_write(log, dumps(result) + "\n")
        result["log"] = str(log)
        return result
