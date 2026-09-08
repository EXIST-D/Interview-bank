import copy

from .ids import utc_now
from .catalog import PROFILE_FIELDS, normalize_label, normalize_labels
from .ingestion import privacy_check, resolve_company
from .normalize import normalize_question_text, normalize_technology
from .runs import stage_snapshot
from .schema import require, string, confidence, strings
from .storage import dumps, open_bank
from .tasks import read_task

EDITABLE = {
    "questions": {"canonical", "language", "question_type", "role_tracks", "domains", "technologies", "difficulty", "report_exclusion"},
    "occurrences": {"company_id", "role_tracks", "interview_type", "round", "event_date", "classification_confidence"},
    "companies": {"name", "aliases", "industries", *PROFILE_FIELDS},
    "sources": {"platform", "source_url", "source_date"},
}


def apply_changes(data, changes, config):
    require(isinstance(changes, list) and bool(changes), "changes must be a nonempty array")
    audit = []
    for change in changes:
        require(isinstance(change, dict), "Change must be object")
        table, key, values = change.get("table"), change.get("id"), change.get("set")
        require(isinstance(table, str) and table in EDITABLE, "Table cannot be edited")
        require(isinstance(values, dict) and bool(values), "set must be nonempty object")
        require(set(values) <= EDITABLE[table], "Attempt to modify immutable identity, provenance or merge fields")
        if table == "companies" and any(field in values for field in ("company_type", "ownership", "business_models")):
            string(values.get("profile_evidence"), "Company profile corrections require fresh profile_evidence")
        string(change.get("reason"), "change.reason")
        privacy_check(dumps(values), config)
        record = next((r for r in data[table] if r["id"] == key), None)
        require(record is not None, f"Unknown record {key}")
        if table == "questions":
            require(record["status"] == "active", "Cannot edit merged question")
        before = copy.deepcopy(record)
        record.update(values)
        for field in ("role_tracks", "domains", "technologies", "industries", "business_models"):
            if field in values:
                record[field] = normalize_labels(field, record[field])
        for field in ("company_type", "ownership"):
            if field in values:
                record[field] = normalize_label(field, record[field])
        if table == "questions":
            string(record["canonical"], "canonical")
            strings(record["technologies"], "technologies")
            record["normalized"] = normalize_question_text(record["canonical"])
            record["technologies"] = list(dict.fromkeys(normalize_technology(t) for t in record["technologies"]))
            record["updated_at"] = utc_now()
        audit.append({"action": "EDIT", "table": table, "id": key, "before": before, "after": copy.deepcopy(record), "reason": change["reason"]})
    return audit


def stage_curate(bank, payload):
    require(isinstance(payload, dict) and payload.get("schema_version") == 1, "Expected v1 changes object")
    with open_bank(bank) as (_, config, current):
        final = copy.deepcopy(current)
        audit = apply_changes(final, payload.get("changes"), config)
        if payload.get("override_protection") is True and "_state" in final:
            require(payload.get("user_requested") is True, "Override requires an actual user instruction")
            from .state import question
            for rule in final["_state"]["policies"].values():
                if rule["active"] and rule["kind"] == "protect":
                    value = question(final, rule["question_id"])[rule["field"]]
                    if value != rule["value"]:
                        rule.update(value=copy.deepcopy(value), updated_at=utc_now())
        return stage_snapshot(bank, current, final, config, operation="curate", audit=audit, summary={"edited_records": len(audit)})


def stage_classification(bank, response):
    require(isinstance(response, dict) and response.get("schema_version") == 1, "Expected v1 classification response")
    with open_bank(bank) as (_, config, current):
        task = read_task(bank, response.get("task_id"), "classification", current, config)
        items = response.get("items")
        require(isinstance(items, list), "items must be array")
        expected = {i["question"]["id"] for i in task["items"]}
        require(all(isinstance(i, dict) and isinstance(i.get("question_id"), str) for i in items), "Invalid classification item")
        require(len(items) == len(expected) and {i["question_id"] for i in items} == expected, "Return each requested question exactly once")
        final, changes, review = copy.deepcopy(current), [], []
        for item in items:
            confidence(item.get("confidence"), "classification.confidence")
            string(item.get("reason"), "classification.reason")
            if item.get("skip") is True:
                continue
            if item["confidence"] < 0.8 and item.get("reviewed") is not True:
                review.append({"question_id": item["question_id"], "reason": item["reason"]})
            question = item.get("question", {})
            if question:
                changes.append({"table": "questions", "id": item["question_id"], "set": question, "reason": item["reason"]})
            for occ in item.get("occurrences", []):
                require(isinstance(occ, dict) and isinstance(occ.get("set"), dict), "Invalid occurrence classification")
                target = next((o for o in final["occurrences"] if o["id"] == occ.get("id")), None)
                require(target is not None and target["question_id"] == item["question_id"], "Occurrence belongs to another question")
                values = dict(occ["set"])
                privacy_check(dumps(values), config)
                if "company" in values:
                    values["company_id"] = resolve_company(final, values.pop("company"))
                values["classification_confidence"] = item["confidence"]
                changes.append({"table": "occurrences", "id": occ["id"], "set": values, "reason": item["reason"]})
        audit = apply_changes(final, changes, config) if changes else []
        for entity in final["companies"]:
            before = next((c for c in current["companies"] if c["id"] == entity["id"]), None)
            if before != entity:
                audit.append({"action": "CLASSIFY_COMPANY", "id": entity["id"], "before": before,
                              "after": copy.deepcopy(entity), "task_id": task["id"]})
        return stage_snapshot(bank, current, final, config, operation="classification", audit=audit, review=review,
                              summary={"classified_questions": len(items), "edited_records": len(audit), "task_id": task["id"]})


def configure(bank, patch=None):
    with open_bank(bank) as (_, config, current):
        if patch is None:
            return config
        require(isinstance(patch, dict) and bool(patch), "Configuration patch must be nonempty object")
        allowed = {"source_retention", "language", "default_interview_type", "dedupe", "privacy", "taxonomy_extensions", "answer_stale_days"}
        require(set(patch) <= allowed, "Unknown or immutable configuration field")
        final = copy.deepcopy(config)
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(final.get(key), dict):
                final[key].update(value)
            else:
                final[key] = value
        extensions = patch.get("taxonomy_extensions", {})
        if isinstance(extensions, dict):
            for dimension, values in extensions.items():
                if dimension in ("role_tracks", "domains") and isinstance(values, list):
                    for value in values:
                        if value not in config.get("taxonomy_extensions", {}).get(dimension, []):
                            require(normalize_label(dimension, value) == value,
                                    f"New extension {value!r} conflicts with a built-in alias")
        return stage_snapshot(bank, current, current, config, operation="configure", next_config=final,
                              audit=[{"action": "CONFIGURE", "before": config, "after": final}], summary={"changed_fields": list(patch)})
