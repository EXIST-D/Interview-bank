"""Inspectable, version-bound cognitive task packets for any host Agent."""
from .ids import new_run_id, utc_now
from .catalog import CATALOG
from .runs import run_path
from .schema import TAXONOMY, require
from .storage import atomic_write, dumps, fingerprint, open_bank, read_json


def write_task(bank, operation, current, config, items, **extra):
    task = {"schema_version": 1, "id": new_run_id(), "operation": operation, "created_at": utc_now(),
            "base_digest": fingerprint(current), "config_digest": fingerprint(config), "items": items, **extra}
    atomic_write(run_path(bank, task["id"]) / "task.json", dumps(task) + "\n")
    return task


def read_task(bank, task_id, operation, current, config):
    task = read_json(run_path(bank, task_id) / "task.json")
    require(task["operation"] == operation, "Wrong task type")
    require(task["base_digest"] == fingerprint(current), "Task is stale: bank changed; generate a new task")
    require(task["config_digest"] == fingerprint(config), "Task is stale: configuration changed")
    return task


def classification_task(bank, question_ids=None):
    with open_bank(bank) as (_, config, current):
        questions = [q for q in current["questions"] if q["status"] == "active" and (not question_ids or q["id"] in question_ids)]
        if question_ids:
            require({q["id"] for q in questions} == set(question_ids), "Unknown/merged question ID")
        require(bool(questions), "No questions selected")
        return write_task(bank, "classification", current, config,
            [{"question": q, "occurrences": [o for o in current["occurrences"] if o["question_id"] == q["id"]]} for q in questions],
            taxonomy=TAXONOMY, taxonomy_extensions=config.get("taxonomy_extensions", {}), companies=current["companies"],
            catalog_version=CATALOG["catalog_version"], catalog_command="taxonomy --dimension <dimension> --query <keywords> --json",
            company_profile_fields={field: CATALOG[field] for field in ("company_type", "ownership", "business_models")},
            instruction="Infer specific semantic labels from each question and its original occurrences; use multiple labels only for actual core concepts. Prefer leaf labels; parent queries include descendants. Normalize Chinese and technology aliases using the taxonomy catalog. Do not infer company/industry/ownership/round/date without evidence; company profiles require profile_evidence. Classify occurrence roles separately from intrinsic question role suitability. Return every selected question, a reason and confidence; leave uncertain labels empty/unknown.")
