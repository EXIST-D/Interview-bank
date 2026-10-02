"""Composite commands: the usual sequences in one call, still built from the audited primitives.

Every step keeps its own validation and its own stage. A composite command commits only when the stage it
produced has no review items; otherwise it stops at the staged run and says what needs a decision, exactly
as the two-step flow would. curate, config and undo stay two-step on purpose: a person should see them first.
"""
from __future__ import annotations

from typing import Optional

from .dedupe import candidate_task, stage_decisions
from .ingestion import intake_images, save_extraction, stage_extraction
from .runs import commit_run, run_path
from .schema import require
from .storage import read_json

PREVIEW = 5


def intake_summary(payload: dict) -> dict:
    """What the host needs to start reading: counts, the first few view paths and the next command."""
    items = payload.get("items", [])
    return {"intake_id": payload["id"], "operation": payload["operation"], "sources": len(items),
            "duplicates_skipped": len(payload.get("duplicates", [])),
            "first": [{"source_id": i["source"]["id"], "view_path": i.get("view_path"), "type": i["source"]["type"],
                       **({"segments": len(i["segments"])} if "segments" in i else {})} for i in items[:PREVIEW]],
            "next": (f"Read every source (run-show --run {payload['id']} --offset 0 --limit 20 lists them), then "
                     f"ingest submit --intake {payload['id']} --extraction <file>") if items else "Nothing new to read."}


def ingest_images(bank, paths, **options) -> dict:
    return intake_summary(intake_images(bank, paths, **options))


def ingest_media(bank, paths, **options) -> dict:
    from .media import intake_media
    summary = intake_media(bank, paths, **options)
    return intake_summary(read_json(run_path(bank, summary["id"]) / "intake.json"))


def _dedupe_summary(task: dict) -> dict:
    items = task["items"]
    with_candidates = [i for i in items if i["matches"]]
    return {"task_id": task["id"], "incoming": len(items), "with_candidates": len(with_candidates),
            "exact_matches": sum(any(m["exact"] for m in i["matches"]) for i in items),
            # Every incoming question needs a decision, so all are listed (the output budget pages long lists).
            "items": [{"question_id": i["incoming"]["id"], "canonical": i["incoming"]["canonical"],
                       "candidates": [{"id": m["question"]["id"], "canonical": m["question"]["canonical"], "score": m["score"],
                                       "exact": m["exact"]} for m in i["matches"][:3]]} for i in items]}


def ingest_submit(bank, intake_id: str, extraction: dict) -> dict:
    """extract-save + stage --from-intake + dedupe-candidates --run."""
    saved = save_extraction(bank, intake_id, extraction)
    if saved["remaining_source_ids"]:
        return {"status": "extraction_incomplete", "saved": saved["saved"], "total": saved["total"],
                "remaining_source_ids": saved["remaining_source_ids"][:20],
                "next": f"Read the remaining sources and call ingest submit --intake {intake_id} again with their results."}
    staged = stage_extraction(bank, intake_id, read_json(run_path(bank, intake_id) / "extraction.json"))
    if staged["review"]:
        return {"status": "review_required", "stage_run": staged["run_id"], "review": staged["review"],
                "next": "Fix the flagged candidates (evidence, pii_reviewed, reviewed) and submit the corrected extraction."}
    task = candidate_task(bank, staged["run_id"])
    return {"status": "dedupe_pending", "stage_run": staged["run_id"], "counts": staged["counts"],
            "summary": staged.get("summary", {}), "dedupe": _dedupe_summary(task),
            "next": (f"Judge every incoming question (run-show --run {task['id']} pages the full task), then "
                     f"ingest finalize --task {task['id']} --decisions <file>; with no candidates, --decisions may be omitted.")}


def ingest_finalize(bank, task_id: str, decisions: Optional[dict] = None, workflow_name: Optional[str] = None) -> dict:
    """dedupe (host decisions, or exact-only) + commit, then optionally a research workflow over this intake."""
    staged = stage_decisions(bank, decisions, None if decisions else task_id)
    if staged["review"]:
        return {"status": "review_required", "committed": False, "stage_run": staged["run_id"], "review": staged["review"],
                "next": "Resolve each review item (or let the user decide in the Web reader), then finalize again."}
    receipt = commit_run(bank, staged["run_id"])
    result = {"status": "committed", "committed": True, "run_id": staged["run_id"], "counts": receipt["counts"],
              "total_counts": receipt["total_counts"], "dedupe": receipt["summary"].get("dedupe", {})}
    if workflow_name:
        from .workflows import workflow
        flow = workflow(bank, "create", {"name": workflow_name, "from_run": staged["run_id"]})
        require(not flow.get("review"), "Workflow stage needs review")
        commit_run(bank, flow["run_id"])
        result["workflow_id"] = flow["summary"]["workflow_id"]
        result["next"] = f"workflow next --id {result['workflow_id']} returns the first research batch."
    else:
        result["next"] = "research (or workflow create --from_run) for answers, then export."
    return result


def commit_unless_review(bank, staged: dict) -> dict:
    """The --commit flag: commit a clean stage, otherwise return it unchanged."""
    if "run_id" not in staged or staged.get("review"):
        return {**staged, "committed": False}
    receipt = commit_run(bank, staged["run_id"])
    return {**staged, "committed": True, "status": "committed", "receipt": {"counts": receipt["counts"], "summary": receipt["summary"]}}
