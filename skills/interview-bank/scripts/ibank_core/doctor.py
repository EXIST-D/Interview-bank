import platform
import sqlite3
from pathlib import Path

from .index import fts5_available, index_status
from .storage import bank_file, open_bank, read_json


def doctor(bank):
    with open_bank(bank) as (manifest, _, data):
        missing = []
        for source in data["sources"]:
            if source["retention"] != "none" and source["path"]:
                path = Path(source["path"])
                if not path.is_absolute():
                    path = bank / path
                if not path.is_file():
                    missing.append(source["id"])
        incomplete, pending, reviews, media_intakes = [], [], [], []
        runs = bank_file(bank, "runs")
        if runs.exists():
            for path in runs.iterdir():
                if not path.is_dir():
                    continue
                if (path / "run.json").is_file():
                    run = read_json(path / "run.json")
                    if run.get("status") == "staged":
                        pending.append(path.name)
                        if run.get("review"):
                            reviews.append({"run_id": path.name, "items": run["review"]})
                elif (path / "intake.json").is_file():
                    intake = read_json(path / "intake.json")
                    if intake.get("operation") == "media-intake" and not intake.get("completed_at") and intake.get("items"):
                        media_intakes.append({"intake_id": path.name, "sources": len(intake["items"]),
                                             "needs_transcript": sum("segments" not in item for item in intake["items"])})
                elif not (path / "task.json").is_file():
                    incomplete.append(path.name)
        return {"bank": str(bank), "python": platform.python_version(), "schema_version": manifest["schema_version"],
                "sqlite": sqlite3.sqlite_version, "fts5_available": fts5_available(), "index": index_status(bank, data),
                "lock": "acquired (free before this command)", "counts": {t: len(v) for t, v in data.items() if t != '_state'},
                "state_counts": {k:len(v) for k,v in data.get('_state',{}).items() if k != 'version'},
                "missing_source_files": missing, "incomplete_runs": incomplete, "pending_runs": pending, "review_required": reviews,
                "media_intakes": media_intakes}
