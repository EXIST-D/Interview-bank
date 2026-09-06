"""V1 shape and cross-record validation, using only the standard library."""
import json
import math
import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

from .errors import ValidationError
from .catalog import CATALOG, PROFILE_FIELDS
from .normalize import normalize_company_alias, normalize_question_text, normalize_technology, legacy_technology_key

TABLES = ("questions", "occurrences", "sources", "companies", "answers", "relations")
PREFIXES = dict(zip(TABLES, ("q", "occ", "src", "company", "ans", "rel")))
TAXONOMY = json.loads((Path(__file__).resolve().parents[2] / "references/taxonomy.json").read_text(encoding="utf-8"))
for _dimension in ("role_tracks", "domains"):
    TAXONOMY[_dimension] = list(dict.fromkeys(TAXONOMY[_dimension] + [entry["id"] for entry in CATALOG[_dimension]]))
FIELDS = {
    "questions": "canonical normalized language question_type role_tracks domains technologies difficulty status merged_into created_at updated_at",
    "occurrences": "question_id source_id original_text company_id role_tracks interview_type round event_date sequence parent_occurrence_id extraction_confidence classification_confidence created_at",
    "sources": "type path sha256 platform source_url source_date imported_at retention",
    "companies": "name aliases industries",
    "answers": "question_id version status short_answer spoken_answer key_points deep_dive interviewer_intent common_mistakes follow_up_questions code_example sources created_at verified_at",
    "relations": "from_question_id to_question_id type confidence created_at",
}


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def string(value, label, nullable=False, empty=False):
    if nullable and value is None:
        return
    require(isinstance(value, str) and (empty or bool(value.strip())), f"{label}: expected string")


def strings(value, label, allowed=None):
    require(isinstance(value, list), f"{label}: expected list")
    for item in value:
        string(item, label)
        if allowed is not None:
            require(item in allowed, f"{label}: unknown taxonomy value {item!r}")
    require(len(set(value)) == len(value), f"{label}: duplicate labels")


def timestamp(value, label, nullable=False):
    if nullable and value is None:
        return
    string(value, label)
    try:
        parsed = datetime.fromisoformat(value)
        require(parsed.tzinfo is not None, f"{label}: timezone required")
    except ValueError as exc:
        raise ValidationError(f"{label}: invalid ISO timestamp") from exc


def partial_date(value, label):
    if value is None:
        return
    string(value, label)
    require(bool(re.fullmatch(r"\d{4}(?:-\d{2})?(?:-\d{2})?", value)), f"{label}: expected YYYY, YYYY-MM or YYYY-MM-DD")
    try:
        date.fromisoformat(value + {4: "-01-01", 7: "-01"}.get(len(value), ""))
    except ValueError as exc:
        raise ValidationError(f"{label}: invalid date") from exc


def confidence(value, label):
    require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1,
            f"{label}: expected confidence in [0, 1]")


def validate_manifest(manifest):
    require(isinstance(manifest, dict), "manifest: expected object")
    require(type(manifest.get("schema_version")) is int and manifest["schema_version"] == 1, "manifest: unsupported schema_version; migration required")
    require(type(manifest.get("bank_version")) is int and manifest["bank_version"] == 1, "manifest: unsupported bank_version; migration required")
    timestamp(manifest.get("created_at"), "manifest.created_at")
    timestamp(manifest.get("last_updated_at"), "manifest.last_updated_at")


def validate_config(config):
    require(isinstance(config, dict), "config: expected object")
    if "answer_stale_days" in config:
        require(type(config["answer_stale_days"]) is int and config["answer_stale_days"] > 0, "answer_stale_days must be positive integer")
    require(type(config.get("bank_version")) is int and config["bank_version"] == 1, "config: unsupported bank_version")
    require(config.get("source_retention") in ("reference", "copy", "none"), "config: invalid source_retention")
    string(config.get("language"), "config.language")
    require(config.get("default_interview_type") in TAXONOMY["interview_type"], "config: invalid interview type")
    privacy = config.get("privacy")
    require(isinstance(privacy, dict) and type(privacy.get("persist_pii")) is bool, "config: invalid privacy policy")
    dedupe = config.get("dedupe")
    require(isinstance(dedupe, dict), "config: missing dedupe options")
    require(type(dedupe.get("top_k")) is int and 1 <= dedupe["top_k"] <= 100, "config: top_k must be 1..100")
    for field in ("auto_merge_exact", "semantic_merge_requires_agent"):
        require(type(dedupe.get(field)) is bool, f"config.dedupe.{field}: expected boolean")
    extensions = config.get("taxonomy_extensions", {})
    require(isinstance(extensions, dict), "config: invalid taxonomy_extensions")
    for key, values in extensions.items():
        require(key in ("role_tracks", "domains"), f"config: cannot extend {key}")
        strings(values, f"config.taxonomy_extensions.{key}")


def validate_run(run):
    require(isinstance(run, dict), "run: expected object")
    require(type(run.get("schema_version")) is int and run["schema_version"] == 1, "run: unsupported schema_version")
    require(isinstance(run.get("id"), str) and re.fullmatch(r"run_[a-zA-Z0-9_-]+", run["id"]), "run: invalid id")
    require(run.get("status") in ("staged", "committed", "superseded", "abandoned"), "run: invalid status")
    timestamp(run.get("created_at"), "run.created_at")
    require(isinstance(run.get("digest"), str) and re.fullmatch(r"[0-9a-f]{64}", run["digest"]), "run: invalid digest")


def validate_record(table, row, taxonomy=None):
    taxonomy = taxonomy or TAXONOMY
    require(isinstance(row, dict), f"{table}: expected object")
    label = f"{table}/{row.get('id', '?')}"
    required = {"schema_version", "id", *FIELDS[table].split()}
    require(required <= row.keys(), f"{label}: missing fields {sorted(required - row.keys())}")
    optional = set(PROFILE_FIELDS) if table == "companies" else {"report_exclusion"} if table == "questions" else set()
    require(not row.keys() - required - optional, f"{label}: unexpected fields {sorted(row.keys() - required - optional)}")
    require(type(row["schema_version"]) is int and row["schema_version"] == 1, f"{label}: unsupported schema_version; migration required")
    require(isinstance(row["id"], str) and re.fullmatch(PREFIXES[table] + r"_[a-zA-Z0-9_-]+", row["id"]), f"{label}: invalid id")
    for field in ("created_at", "updated_at", "imported_at"):
        if field in row:
            timestamp(row[field], f"{label}.{field}")
    for field in ("role_tracks", "domains"):
        if field in row:
            strings(row[field], f"{label}.{field}", taxonomy[field])
    for field in ("difficulty", "question_type", "round", "interview_type"):
        if field in row:
            require(row[field] in taxonomy[field], f"{label}: invalid {field}")
    if table == "questions":
        if "report_exclusion" in row:
            string(row["report_exclusion"], f"{label}.report_exclusion", nullable=True)
        for field in ("canonical", "normalized", "language"):
            string(row[field], f"{label}.{field}")
        require(row["normalized"] == normalize_question_text(row["canonical"]), f"{label}: normalized key mismatch")
        strings(row["technologies"], f"{label}.technologies")
        require(all(t in (normalize_technology(t), legacy_technology_key(t)) for t in row["technologies"]), f"{label}: technologies must be normalized")
        require(row["status"] in ("active", "merged"), f"{label}: invalid status")
        string(row["merged_into"], f"{label}.merged_into", nullable=True)
        require((row["status"] == "merged") == (row["merged_into"] is not None), f"{label}: inconsistent merged_into")
    elif table == "occurrences":
        for field in ("question_id", "source_id", "original_text"):
            string(row[field], f"{label}.{field}")
        for field in ("company_id", "parent_occurrence_id"):
            string(row[field], f"{label}.{field}", nullable=True)
        partial_date(row["event_date"], f"{label}.event_date")
        require(type(row["sequence"]) is int and row["sequence"] > 0, f"{label}: sequence must be positive integer")
        for field in ("extraction_confidence", "classification_confidence"):
            confidence(row[field], f"{label}.{field}")
    elif table == "sources":
        require(row["type"] in ("image", "text", "web", "audio", "video"), f"{label}: invalid source type")
        require(row["retention"] in ("reference", "copy", "none"), f"{label}: invalid retention")
        require(isinstance(row["sha256"], str) and re.fullmatch(r"[a-f0-9]{64}", row["sha256"]), f"{label}: invalid sha256")
        for field in ("path", "platform", "source_url"):
            string(row[field], f"{label}.{field}", nullable=True)
        require(row["retention"] == "none" or row["path"] is not None or row["source_url"] is not None, f"{label}: source reference missing")
        require(row["retention"] != "none" or row["path"] is None, f"{label}: retention none must omit path")
        partial_date(row["source_date"], f"{label}.source_date")
    elif table == "companies":
        string(row["name"], f"{label}.name")
        strings(row["aliases"], f"{label}.aliases")
        strings(row["industries"], f"{label}.industries")
        for field in ("company_type", "ownership"):
            if field in row:
                require(row[field] in [e["id"] for e in CATALOG[field]], f"{label}: invalid {field}")
        if "business_models" in row:
            strings(row["business_models"], f"{label}.business_models", [e["id"] for e in CATALOG["business_models"]])
        if any(field in row for field in PROFILE_FIELDS):
            string(row.get("profile_evidence"), f"{label}.profile_evidence: describe the source of company facts")
    elif table == "answers":
        string(row["question_id"], f"{label}.question_id")
        require(type(row["version"]) is int and row["version"] > 0, f"{label}: invalid version")
        require(row["status"] in ("ai_draft", "source_backed", "reviewed", "stale"), f"{label}: invalid answer status (missing is derived)")
        for field in ("short_answer", "spoken_answer", "deep_dive", "interviewer_intent"):
            string(row[field], f"{label}.{field}", empty=True)
        string(row["code_example"], f"{label}.code_example", nullable=True, empty=True)
        for field in ("key_points", "common_mistakes", "follow_up_questions"):
            strings(row[field], f"{label}.{field}")
        timestamp(row["verified_at"], f"{label}.verified_at", nullable=True)
        require(isinstance(row["sources"], list), f"{label}: sources must be list")
        require(row["status"] != "source_backed" or bool(row["sources"]), f"{label}: source_backed requires citations")
        require(row["status"] != "reviewed" or row["verified_at"] is not None, f"{label}: reviewed requires verified_at")
        for citation in row["sources"]:
            require(isinstance(citation, dict), f"{label}: invalid citation")
            for key in ("title", "url", "publisher", "type", "accessed_at"):
                string(citation.get(key), f"{label}.sources.{key}")
            parsed = urlparse(citation["url"])
            require(parsed.scheme in ("http", "https") and bool(parsed.netloc), f"{label}: invalid citation URL")
            partial_date(citation["accessed_at"], f"{label}.sources.accessed_at")
    elif table == "relations":
        for field in ("from_question_id", "to_question_id"):
            string(row[field], f"{label}.{field}")
        require(row["type"] in ("related", "prerequisite", "follow_up", "contrast", "broader", "narrower"), f"{label}: invalid relation type")
        require(row["from_question_id"] != row["to_question_id"], f"{label}: self relation")
        confidence(row["confidence"], f"{label}.confidence")


def validate_data(data, config=None):
    require(isinstance(data, dict) and set(data) == set(TABLES), "data: expected all six tables")
    taxonomy = {key: list(value) if isinstance(value, list) else value for key, value in TAXONOMY.items()}
    if config is not None:
        validate_config(config)
        for key, values in config.get("taxonomy_extensions", {}).items():
            taxonomy[key] += values
    by_id = {}
    for table in TABLES:
        require(isinstance(data[table], list), f"{table}: expected list")
        by_id[table] = {}
        for row in data[table]:
            validate_record(table, row, taxonomy)
            require(row["id"] not in by_id[table], f"{table}: duplicate ID {row['id']}")
            by_id[table][row["id"]] = row

    def foreign(table, key, label, active=False):
        require(key in by_id[table], f"{label}: broken foreign key {key}")
        target = by_id[table][key]
        if active:
            require(target["status"] == "active", f"{label}: reference points to merged question {key}")
        return target

    for q in data["questions"]:
        if q["status"] == "merged":
            require(q["merged_into"] != q["id"], f"{q['id']}: self merge")
            foreign("questions", q["merged_into"], q["id"], active=True)
    seen_sequences, covered = set(), set()
    for occ in data["occurrences"]:
        foreign("questions", occ["question_id"], occ["id"], active=True)
        foreign("sources", occ["source_id"], occ["id"])
        if occ["company_id"] is not None:
            foreign("companies", occ["company_id"], occ["id"])
        key = (occ["source_id"], occ["sequence"])
        require(key not in seen_sequences, f"{occ['id']}: duplicate source sequence")
        seen_sequences.add(key)
        covered.add(occ["question_id"])
        if occ["parent_occurrence_id"] is not None:
            parent = foreign("occurrences", occ["parent_occurrence_id"], occ["id"])
            require(parent["source_id"] != occ["source_id"] or parent["sequence"] < occ["sequence"], f"{occ['id']}: parent must precede child in same source")
    for occ in data["occurrences"]:
        visited = {occ["id"]}
        parent_id = occ["parent_occurrence_id"]
        while parent_id is not None:
            require(parent_id not in visited, f"{occ['id']}: follow-up cycle")
            visited.add(parent_id)
            parent_id = by_id["occurrences"][parent_id]["parent_occurrence_id"]
    for q in data["questions"]:
        require(q["status"] != "active" or q["id"] in covered, f"{q['id']}: no occurrence provenance")
    versions = set()
    for answer in data["answers"]:
        foreign("questions", answer["question_id"], answer["id"], active=True)
        key = (answer["question_id"], answer["version"])
        require(key not in versions, f"{answer['id']}: duplicate answer version")
        versions.add(key)
    for rel in data["relations"]:
        foreign("questions", rel["from_question_id"], rel["id"], active=True)
        foreign("questions", rel["to_question_id"], rel["id"], active=True)
    hashes, aliases = set(), {}
    for source in data["sources"]:
        require(source["sha256"] not in hashes, f"{source['id']}: duplicate source hash")
        hashes.add(source["sha256"])
    for company in data["companies"]:
        for alias in [company["name"], *company["aliases"]]:
            key = normalize_company_alias(alias)
            require(key not in aliases or aliases[key] == company["id"], f"{company['id']}: ambiguous company alias {alias}")
            aliases[key] = company["id"]
    return {table: len(data[table]) for table in TABLES}
