"""Composite commands: the usual sequences in one call, still built from the audited primitives.

Every step keeps its own validation and its own stage. A composite command commits only when the stage it
produced has no review items; otherwise it stops at the staged run and says what needs a decision, exactly
as the two-step flow would. curate, config and undo stay two-step on purpose: a person should see them first.
"""
from __future__ import annotations

from typing import Optional

from .dedupe import candidate_task, stage_decisions, task_summary
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


def ingest_submit(bank, intake_id: str, extraction: dict, top_k: Optional[int] = None) -> dict:
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
    task = candidate_task(bank, staged["run_id"], top_k)
    summary = task_summary(bank, task)
    return {"status": "dedupe_pending", "stage_run": staged["run_id"], "counts": staged["counts"],
            "summary": staged.get("summary", {}), "dedupe": summary,
            "next": (f"Read the review sheet ({summary['review_sheet']}): it groups the incoming questions by topic with "
                     f"their candidates and the bank's questions of the same topic. Then ingest finalize --task {task['id']} "
                     "--decisions <file> (refs such as n3/e7 are accepted; default_action KEEP_DISTINCT covers unlisted "
                     "questions; --defer-review commits the rest when the user must decide some merges).")}


def ingest_finalize(bank, task_id: str, decisions: Optional[dict] = None, workflow_name: Optional[str] = None,
                    defer_review: bool = False) -> dict:
    """dedupe (host decisions, or exact-only) + commit, then optionally a research workflow over this intake.

    defer_review commits everything that is decided and leaves the REVIEW items to the person (Web reader, then
    dedupe --resolve); without it a single REVIEW item stops the whole intake at the staged run."""
    staged = stage_decisions(bank, decisions, task_id, defer_review=defer_review)
    if staged["review"]:
        return {"status": "review_required", "committed": False, "stage_run": staged["run_id"], "review": staged["review"],
                "next": ("Resolve each review item, or finalize again with --defer-review to commit the rest and let the user "
                         "decide these in the Web reader.")}
    receipt = commit_run(bank, staged["run_id"])
    result = {"status": "committed", "committed": True, "run_id": staged["run_id"], "counts": receipt["counts"],
              "total_counts": receipt["total_counts"], "dedupe": receipt["summary"].get("dedupe", {})}
    if staged.get("deferred_review"):
        result["deferred_review"] = len(staged["deferred_review"])
        result["user_decision"] = (f"{len(staged['deferred_review'])} possible merges wait for the user in the Web reader "
                                   f"(合并裁决); after they decide, dedupe --resolve {staged['run_id']} stages the result.")
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
