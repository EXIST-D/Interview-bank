"""Validated staging, durable commits and provenance-preserving undo."""
import hashlib
import re

from .errors import ValidationError, ReviewRequired
from .catalog import normalize_labels
from .ids import new_company_id, new_occurrence_id, new_question_id, new_run_id, new_source_id, utc_now
from .normalize import normalize_company_alias, normalize_question_text, normalize_technology
from .schema import TABLES, require, validate_data, validate_run
from .storage import (atomic_write, bank_file, dumps, empty_data, fingerprint, jsonl_text,
                      open_bank, read_json, read_jsonl, transaction)


def run_path(bank, run_id):
    require(isinstance(run_id, str) and re.fullmatch(r"run_[a-zA-Z0-9_-]+", run_id), "Invalid run ID")
    return bank_file(bank, f"runs/{run_id}")


def combined(current, addition):
    result = {table: current[table] + addition[table] for table in TABLES}
    if "_state" in current:
        import copy
        result["_state"] = copy.deepcopy(current["_state"])
    return result


def stage_bundle(bank, bundle, run_id=None):
    require(isinstance(bundle, dict) and type(bundle.get("schema_version")) is int and bundle["schema_version"] == 1, "bundle: schema_version 1 required")
    require(set(bundle) <= {"schema_version", *TABLES}, "bundle: unknown table")
    addition = {table: bundle.get(table, []) for table in TABLES}
    for table in TABLES:
        require(isinstance(addition[table], list), f"bundle.{table}: expected list")
    with open_bank(bank) as (_, config, current):
        validate_data(combined(current, addition), config)
        return _write_stage(bank, addition, run_id)


def _write_stage(bank, addition, run_id=None, duplicate_sources=0, metadata=None):
    run_id = run_id or new_run_id()
    path = run_path(bank, run_id)
    require(not path.exists(), f"Run already exists: {run_id}; use a new run ID")
    path.mkdir(parents=True)
    for table in TABLES:
        atomic_write(bank_file(bank, f"runs/{run_id}/{table}.jsonl"), jsonl_text(addition[table]))
    if "_state" in addition:
        atomic_write(path / "state.json", dumps(addition["_state"]) + "\n")
    run = {"schema_version": 1, "id": run_id, "status": "staged", "created_at": utc_now(),
           "digest": fingerprint(addition), "duplicate_sources": duplicate_sources}
    run.update(metadata or {})
    validate_run(run)
    # Metadata is last: an interrupted stage cannot be mistaken for a ready run.
    atomic_write(path / "run.json", dumps(run) + "\n")
    return {"run_id": run_id, "status": "staged", "counts": {t: len(addition[t]) for t in TABLES},
            "duplicate_sources": duplicate_sources, "review": run.get("review", []),
            "summary": run.get("summary", {})}


def stage_text(bank, input_path, *, run_id=None, company=None, roles=(), domains=(),
               technologies=(), round_name="unknown", interview_type="unknown", event_date=None,
               question_type="concept", difficulty="unknown", retention=None):
    """One nonblank line is one already selected question, not arbitrary prose."""
    raw = input_path.read_bytes()
    try:
        lines = [line for line in raw.decode("utf-8-sig").splitlines() if line.strip()]
    except UnicodeError as exc:
        raise ValidationError("Text input must be UTF-8") from exc
    require(bool(lines), "Text input has no questions")
    digest = hashlib.sha256(raw).hexdigest()
    roles, domains = normalize_labels("role_tracks", roles), normalize_labels("domains", domains)
    with open_bank(bank) as (_, config, current):
        addition = empty_data()
        if any(s["sha256"] == digest for s in current["sources"]):
            return _write_stage(bank, addition, run_id, duplicate_sources=1)
        retention = retention or config["source_retention"]
        require(retention in ("reference", "none"), "Selected-text adapter supports reference/none retention; image intake also supports copy")
        company_id = None
        if company:
            key = normalize_company_alias(company)
            matches = [c for c in current["companies"] if key in {normalize_company_alias(a) for a in [c["name"], *c["aliases"]]}]
            if matches:
                company_id = matches[0]["id"]
            else:
                company_id = new_company_id()
                addition["companies"].append({"schema_version": 1, "id": company_id, "name": company.strip(), "aliases": [], "industries": []})
        now, source_id = utc_now(), new_source_id()
        addition["sources"].append({"schema_version": 1, "id": source_id, "type": "text",
                                    "path": str(input_path.resolve()) if retention == "reference" else None,
                                    "sha256": digest, "platform": None, "source_url": None,
                                    "source_date": None, "imported_at": now, "retention": retention})
        for sequence, original in enumerate(lines, 1):
            qid = new_question_id()
            canonical = original.strip()
            addition["questions"].append({"schema_version": 1, "id": qid, "canonical": canonical,
                "normalized": normalize_question_text(canonical), "language": config["language"],
                "question_type": question_type, "role_tracks": list(roles), "domains": list(domains),
                "technologies": list(dict.fromkeys(normalize_technology(t) for t in technologies)),
                "difficulty": difficulty, "status": "active", "merged_into": None,
                "created_at": now, "updated_at": now})
            addition["occurrences"].append({"schema_version": 1, "id": new_occurrence_id(), "question_id": qid,
                "source_id": source_id, "original_text": original, "company_id": company_id,
                "role_tracks": list(roles), "interview_type": interview_type, "round": round_name,
                "event_date": event_date, "sequence": sequence, "parent_occurrence_id": None,
                "extraction_confidence": 1.0, "classification_confidence": 1.0 if roles or domains or technologies else 0.0,
                "created_at": now})
        validate_data(combined(current, addition), config)
        return _write_stage(bank, addition, run_id)


def commit_run(bank, run_id):
    with open_bank(bank) as (manifest, config, current):
        path = run_path(bank, run_id)
        run = read_json(bank_file(bank, f"runs/{run_id}/run.json"))
        validate_run(run)
        require(run["id"] == run_id, "Run ID mismatch")
        if run["status"] == "committed":
            return {**read_json(bank_file(bank, f"runs/{run_id}/commit.json")), "already_committed": True}
        require(run["status"] == "staged", f"Run is {run['status']} and cannot commit")
        addition = {table: read_jsonl(bank_file(bank, f"runs/{run_id}/{table}.jsonl")) for table in TABLES}
        if (path / "state.json").exists():
            addition["_state"] = read_json(path / "state.json")
        require(fingerprint(addition) == run["digest"], "Staged files changed; create a new staging run")
        if run.get("review"):
            raise ReviewRequired(f"Run {run_id} has unresolved review items; inspect run-show and stage corrected input")
        if run.get("intake_id"):
            intake = read_json(run_path(bank, run["intake_id"]) / "intake.json")
            if intake.get("operation") == "media-intake":
                require(not intake.get("completed_at") and intake["digest"] == fingerprint(intake["items"]), "Media intake changed before commit")
                staged_sources = {s["id"]: s for s in addition["sources"]}
                for item in intake["items"]:
                    staged_source = staged_sources.get(item["source"]["id"])
                    if staged_source:
                        require(staged_source.get("transcription") == item["source"].get("transcription"), "Transcript changed before commit; restage")
            for item in intake["items"]:
                view = item.get("view_path")
                if view:
                    from pathlib import Path
                    from .media import file_hash
                    require(file_hash(view) == item["source"]["sha256"], "Source changed before commit; intake again")
        if run.get("mode") == "snapshot":
            require(fingerprint(read_json(path / "before.json")) == run["base_digest"], "Missing/changed recovery snapshot; restage")
            require(fingerprint(current) == run["base_digest"], "Bank changed since staging; regenerate this operation from current data")
            require(fingerprint(config) == run["config_digest"], "Bank configuration changed; restage")
            final = addition
        else:
            final = combined(current, addition)
        target_config = config
        if run.get("new_config_digest"):
            target_config = read_json(path / "config_after.json")
            require(fingerprint(target_config) == run["new_config_digest"], "Staged config changed")
        from .state import enforce_policies
        enforce_policies(current, final, run.get("operation", "ingest"))
        validate_data(final, target_config)
        committed_at = utc_now()
        result = {"schema_version": 1, "run_id": run_id, "committed_at": committed_at,
                  "counts": {t: len(final[t]) - len(current[t]) for t in TABLES},
                  "total_counts": {t: len(final[t]) for t in TABLES},
                  "duplicate_sources": run.get("duplicate_sources", 0), "summary": run.get("summary", {}),
                  "after_digest": fingerprint(final), "after_config_digest": fingerprint(target_config)}
        files = {f"data/{table}.jsonl": jsonl_text(final[table]) for table in TABLES}
        if "_state" in final:
            files["data/state.json"] = dumps(final["_state"]) + "\n"
        manifest["last_updated_at"] = committed_at
        run["status"] = "committed"
        files["manifest.json"] = dumps(manifest) + "\n"
        if run.get("new_config_digest"):
            files["config.json"] = dumps(target_config) + "\n"
        files[f"runs/{run_id}/run.json"] = dumps(run) + "\n"
        files[f"runs/{run_id}/commit.json"] = dumps(result) + "\n"
        for previous_id in run.get("supersedes", []):
            previous = read_json(run_path(bank, previous_id) / "run.json")
            require(previous["status"] == "staged", "Previous stage is no longer available; regenerate")
            previous.update(status="superseded", superseded_by=run_id)
            files[f"runs/{previous_id}/run.json"] = dumps(previous) + "\n"
        files[f"runs/{run_id}/report.md"] = (f"# Interview Bank — {run.get('operation', 'ingest')}\n\nRun: {run_id}\n\n"
            + "\n".join(f"- {table}: {result['counts'][table]:+d} (total {len(final[table])})" for table in TABLES)
            + f"\n- Duplicate sources skipped: {result['duplicate_sources']}\n\n## Summary\n\n"
            + dumps(run.get("summary", {})) + "\n\n## Audit\n\n```json\n" + dumps(run.get("audit", [])) + "\n```\n")
        if run.get("intake_id"):
            intake_path = bank_file(bank, f"runs/{run['intake_id']}/intake.json")
            intake = read_json(intake_path)
            if intake.get("operation") == "media-intake":
                intake["completed_at"] = committed_at
            for item in intake["items"]:
                if item["source"]["retention"] == "none":
                    item.pop("view_path", None)
                    item.pop("original_path", None)
            files[f"runs/{run['intake_id']}/intake.json"] = dumps(intake) + "\n"
        transaction(bank, files)
        return result


def stage_snapshot(bank, current, final, config, *, operation, audit=(), review=(), summary=None, intake_id=None, supersedes=(), next_config=None):
    """Caller holds open_bank lock; retain an immutable before-image for undo."""
    from .state import enforce_policies
    enforce_policies(current, final, operation)
    validate_data(final, next_config or config)
    metadata = {"mode": "snapshot", "operation": operation, "base_digest": fingerprint(current),
                "config_digest": fingerprint(config), "audit": list(audit), "review": list(review), "summary": summary or {}, "supersedes": list(supersedes)}
    if intake_id:
        metadata["intake_id"] = intake_id
    if next_config is not None:
        metadata["new_config_digest"] = fingerprint(next_config)
    result = _write_stage(bank, final, metadata=metadata)
    atomic_write(run_path(bank, result["run_id"]) / "before.json", dumps(current) + "\n")
    if next_config is not None:
        atomic_write(run_path(bank, result["run_id"]) / "config_before.json", dumps(config) + "\n")
        atomic_write(run_path(bank, result["run_id"]) / "config_after.json", dumps(next_config) + "\n")
    return result


def show_run(bank, run_id=None):
    with open_bank(bank):
        if run_id:
            path = run_path(bank, run_id)
            if (path / "intake.json").exists():
                return read_json(path / "intake.json")
            if (path / "task.json").exists():
                return read_json(path / "task.json")
            run = read_json(path / "run.json")
            validate_run(run)
            return run
        return {"runs": [p.name for p in sorted(bank_file(bank, "runs").glob("run_*")) if p.is_dir()]}


def undo_run(bank, run_id):
    with open_bank(bank) as (_, config, current):
        path = run_path(bank, run_id)
        run = read_json(path / "run.json")
        require(run.get("mode") == "snapshot" and run["status"] == "committed", "Only committed snapshot operations support undo")
        receipt = read_json(path / "commit.json")
        require(receipt["after_digest"] == fingerprint(current), "Later changes exist; undo them first to avoid overwriting data")
        require(receipt.get("after_config_digest", fingerprint(config)) == fingerprint(config), "Later configuration changes exist; undo them first")
        before = read_json(path / "before.json")
        require(fingerprint(before) == run["base_digest"], "Undo snapshot changed")
        undo_scope = "full_snapshot"
        if {q["id"] for q in current["questions"]} != {q["id"] for q in before["questions"]} and run.get("operation") == "dedupe":
            predecessors = run.get("supersedes", [])
            require(len(predecessors) == 1, "Missing original import stage for merge undo")
            original_path = run_path(bank, predecessors[0])
            original = read_json(original_path / "run.json")
            imported = {t: read_jsonl(original_path / f"{t}.jsonl") for t in TABLES}
            if (original_path / "state.json").exists():
                imported["_state"] = read_json(original_path / "state.json")
            require(fingerprint(imported) == original["digest"], "Original import stage changed")
            # Undo merging without deleting imported source/question history.
            before = imported if original.get("mode") == "snapshot" else combined(before, imported)
            undo_scope = "dedupe_only_preserve_import"
        require({q["id"] for q in current["questions"]} == {q["id"] for q in before["questions"]},
                "Undo cannot physically remove imported questions; use curation or a subsequent merge correction")
        previous_config = read_json(path / "config_before.json") if run.get("new_config_digest") else None
        if previous_config is not None:
            require(fingerprint(previous_config) == run["config_digest"], "Undo config snapshot changed")
        return stage_snapshot(bank, current, before, config, operation="undo", audit=[{"undo_run": run_id, "scope": undo_scope}],
                              summary={"undo_scope": undo_scope}, next_config=previous_config)


def abandon_run(bank, run_id):
    with open_bank(bank):
        path = run_path(bank, run_id) / "run.json"
        run = read_json(path)
        validate_run(run)
        require(run["status"] in ("staged", "abandoned"), "Only uncommitted stages can be abandoned")
        run["status"] = "abandoned"
        atomic_write(path, dumps(run) + "\n")
        return {"run_id": run_id, "status": "abandoned", "canonical_changed": False}
