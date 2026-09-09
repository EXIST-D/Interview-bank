"""Vision-first image intake and validated host extraction. No OCR/LLM dependency."""
import copy
import hashlib
import re
from pathlib import Path

from .editorial import is_self_introduction
from .ids import new_run_id, new_source_id, utc_now
from .catalog import PROFILE_FIELDS, normalize_label, normalize_labels
from .normalize import normalize_company_alias, normalize_question_text, normalize_technology
from .runs import run_path, stage_snapshot
from .schema import require, string, confidence, strings
from .storage import atomic_bytes, atomic_write, bank_file, dumps, fingerprint, open_bank, read_json

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


def stable_id(prefix, *parts):
    return prefix + "_" + hashlib.sha256(dumps(parts).encode()).hexdigest()[:32]


def privacy_check(text, config):
    if config["privacy"]["persist_pii"]:
        return
    patterns = (r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", r"(?<!\d)1[3-9]\d{9}(?!\d)",
                r"(?:微信|手机号|QQ群|群号|wechat)\s*[:：]\s*\S+")
    require(not any(re.search(p, text, re.I) for p in patterns),
            "Possible personal contact information; remove irrelevant PII before staging")


def intake_images(bank, paths, *, retention=None, recursive=False, reprocess=False):
    files = []
    for supplied in paths:
        path = Path(supplied).expanduser().resolve()
        if path.is_dir():
            files.extend(sorted(p for p in (path.rglob("*") if recursive else path.iterdir())
                                if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES))
        else:
            require(path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES, f"Unsupported/missing image: {path}")
            files.append(path)
    require(bool(files), "No supported image files found")
    with open_bank(bank) as (_, config, current):
        retention = retention or config["source_retention"]
        require(retention in ("reference", "copy", "none"), "Invalid retention")
        existing = {s["sha256"]: s for s in current["sources"]}
        items, duplicates, batch_hashes = [], [], set()
        for path in files:
            require(path.stat().st_size <= 50 * 1024 * 1024, f"Image exceeds 50 MiB: {path}")
            raw = path.read_bytes()
            require(bool(raw), f"Empty image: {path}")
            digest = hashlib.sha256(raw).hexdigest()
            old = existing.get(digest)
            can_retry = reprocess and old and not any(o["source_id"] == old["id"] for o in current["occurrences"])
            if digest in batch_hashes or (digest in existing and not can_retry):
                duplicates.append({"sha256": digest, "source_id": existing[digest]["id"]})
                continue
            batch_hashes.add(digest)
            source_id = old["id"] if can_retry else new_source_id()
            source_path = str(path)
            if retention == "copy":
                source_path = f"media/{digest}{path.suffix.lower()}"
                target = bank_file(bank, source_path)
                if not target.exists():
                    atomic_bytes(target, raw)
                require(hashlib.sha256(target.read_bytes()).hexdigest() == digest, "Stored media hash mismatch")
            source = {"schema_version": 1, "id": source_id, "type": "image", "path": source_path if retention != "none" else None,
                      "sha256": digest, "platform": None, "source_url": None, "source_date": None,
                      "imported_at": utc_now(), "retention": retention}
            if can_retry:
                source = copy.deepcopy(old)
            items.append({"source": source, "view_path": str(bank / source_path) if retention == "copy" else str(path),
                          "order": len(items) + 1, "reprocess": bool(can_retry)})
            existing[digest] = source
        run_id = new_run_id()
        payload = {"schema_version": 1, "id": run_id, "operation": "image-intake", "created_at": utc_now(),
                   "items": items, "duplicates": duplicates}
        payload["digest"] = fingerprint(items)
        atomic_write(run_path(bank, run_id) / "intake.json", dumps(payload) + "\n")
        return payload


def resolve_company(data, supplied):
    if supplied is None or supplied == "":
        return None
    if isinstance(supplied, str):
        supplied = {"name": supplied, "aliases": [], "industries": []}
    require(isinstance(supplied, dict), "company: expected name or object")
    require(set(supplied) <= {"name", "aliases", "industries", *PROFILE_FIELDS}, "Unknown company field")
    supplied = copy.deepcopy(supplied)
    string(supplied.get("name"), "company.name")
    strings(supplied.get("aliases", []), "company.aliases")
    strings(supplied.get("industries", []), "company.industries")
    supplied["industries"] = normalize_labels("industries", supplied.get("industries", []))
    for field in ("company_type", "ownership"):
        if field in supplied:
            supplied[field] = normalize_label(field, supplied[field])
    if "business_models" in supplied:
        supplied["business_models"] = normalize_labels("business_models", supplied["business_models"])
    if any(field in supplied for field in PROFILE_FIELDS):
        string(supplied.get("profile_evidence"), "company.profile_evidence")
    labels = [supplied["name"], *supplied.get("aliases", [])]
    keys = {normalize_company_alias(s) for s in labels}
    matches = [c for c in data["companies"] if keys & {normalize_company_alias(s) for s in [c["id"], c["name"], *c["aliases"]]}]
    require(len(matches) <= 1, "Company labels match multiple companies; curate aliases first")
    if matches:
        entity = matches[0]
        entity["aliases"] = list(dict.fromkeys(entity["aliases"] + [s for s in labels if s != entity["name"]]))
        entity["industries"] = normalize_labels("industries", entity["industries"] + supplied.get("industries", []))
        for field in ("company_type", "ownership", "business_models"):
            if field in supplied:
                require(entity.get(field) in (None, "unknown", []) or entity[field] == supplied[field],
                        f"Conflicting company {field}; use an evidenced curate correction")
                entity[field] = supplied[field]
        if "profile_evidence" in supplied:
            entity["profile_evidence"] = "\n".join(dict.fromkeys(filter(None, [entity.get("profile_evidence"), supplied["profile_evidence"]])))
    else:
        entity = {"schema_version": 1, "id": stable_id("company", supplied["name"]), "name": supplied["name"],
                  "aliases": supplied.get("aliases", []), "industries": supplied.get("industries", []),
                  **{field: supplied[field] for field in PROFILE_FIELDS if field in supplied}}
        data["companies"].append(entity)
    return entity["id"]


def stage_extraction(bank, intake_id, extraction):
    require(isinstance(extraction, dict) and extraction.get("schema_version") == 1, "Extraction must be a v1 object")
    require(isinstance(extraction.get("sources"), list), "extraction.sources must be an array")
    with open_bank(bank) as (_, config, current):
        intake = read_json(run_path(bank, intake_id) / "intake.json")
        require(not intake.get("completed_at"), "Intake already committed")
        require(intake["digest"] == fingerprint(intake["items"]), "Intake changed or completed; create a new intake")
        sources = {i["source"]["id"]: i for i in intake["items"]}
        seen, candidates, review, audit = set(), [], [], []
        final = copy.deepcopy(current)
        current_hashes = {s["sha256"] for s in current["sources"]}
        for result in extraction["sources"]:
            require(isinstance(result, dict), "Extraction source must be object")
            sid = result.get("source_id")
            require(isinstance(sid, str) and sid in sources and sid not in seen, "Unknown/duplicate extraction source_id")
            seen.add(sid)
            item = sources[sid]
            if intake.get("operation") == "media-intake":
                from .media import prepare_media_result
                result = prepare_media_result(item, result)
            # Recheck source bytes immediately before staging, to prevent mismatched provenance.
            from .media import file_hash
            require(file_hash(item["view_path"]) == item["source"]["sha256"], "Source file changed after intake")
            status = result.get("status")
            require(status in ("extracted", "no_questions", "unreadable", "skip"), "Each image needs an explicit disposition")
            questions = result.get("questions", [])
            require(isinstance(questions, list), "questions must be array")
            require((status == "extracted" and bool(questions)) or (status != "extracted" and not questions), "Disposition disagrees with extracted questions")
            if status != "extracted":
                string(result.get("reason"), "disposition.reason")
            if status == "skip":
                require(result.get("reviewed") is True, "Skipping unreadable material requires explicit review")
            if status == "unreadable":
                review.append({"source_id": sid, "reason": result["reason"]})
            if item["source"]["sha256"] in current_hashes and not item.get("reprocess"):
                audit.append({"source_id": sid, "action": "SKIP_DUPLICATE_SOURCE"})
                continue
            source = copy.deepcopy(item["source"])
            metadata = result.get("metadata", {})
            require(isinstance(metadata, dict), "metadata must be object")
            for field in ("platform", "source_url", "source_date"):
                if field in metadata:
                    source[field] = metadata[field]
            privacy_check(dumps(metadata), config)
            if item.get("reprocess"):
                require(not any(o["source_id"] == sid for o in current["occurrences"]), "Source was already processed; intake again")
                next(s for s in final["sources"] if s["id"] == sid).update(source)
            else:
                final["sources"].append(source)
            for row in questions:
                require(isinstance(row, dict), "Question candidate must be object")
                candidate = {**metadata, **row, "source_id": sid}
                for key in ("id", "original_text"):
                    string(candidate.get(key), f"candidate.{key}")
                require(candidate["id"] not in {c["id"] for c in candidates}, "Duplicate candidate ID")
                seq = candidate.get("sequence")
                require(type(seq) is int and seq > 0, "Candidate sequence must be positive")
                privacy_check(dumps(candidate), config)
                string(candidate.get("canonical_suggestion", candidate["original_text"]), "canonical_suggestion")
                require(not is_self_introduction(candidate["original_text"]) and
                        not is_self_introduction(candidate.get("canonical_suggestion", candidate["original_text"])),
                        "Omit self-introduction candidates; retain any separate technical follow-up with its own source wording")
                for field in ("role_tracks", "domains", "technologies"):
                    strings(candidate.get(field, []), f"candidate.{field}")
                    candidate[field] = normalize_labels(field, candidate.get(field, []))
                if "reviewed" in candidate:
                    require(type(candidate["reviewed"]) is bool, "reviewed must be boolean")
                scores = candidate.get("confidence", {})
                require(isinstance(scores, dict), "confidence must be object")
                for key in ("is_question", "classification"):
                    confidence(scores.get(key), f"confidence.{key}")
                for key in ("company", "round", "event_date"):
                    if key in scores:
                        confidence(scores[key], f"confidence.{key}")
                checked_scores = [scores[key] for key in ("is_question", "classification", "company", "round", "event_date") if key in scores]
                if min(checked_scores) < 0.8 and not candidate.get("reviewed", False):
                    review.append({"candidate_id": candidate["id"], "reason": "Low extraction/classification confidence"})
                candidate["qid"] = stable_id("q", intake_id, candidate["id"])
                candidate["oid"] = stable_id("occ", intake_id, candidate["id"])
                candidates.append(candidate)
            audit.append({"source_id": sid, "disposition": status, "reason": result.get("reason"), "questions": len(questions)})
        require(seen == set(sources), "Every new image must have an extraction disposition; partial batches cannot commit")
        by_candidate = {c["id"]: c for c in candidates}
        for c in candidates:
            now = utc_now()
            canonical = c.get("canonical_suggestion", c["original_text"]).strip()
            roles = c.get("role_tracks", [])
            final["questions"].append({"schema_version": 1, "id": c["qid"], "canonical": canonical,
                "normalized": normalize_question_text(canonical), "language": c.get("language", config["language"]),
                "question_type": c.get("question_type", "concept"), "role_tracks": roles,
                "domains": c.get("domains", []), "technologies": list(dict.fromkeys(normalize_technology(t) for t in c.get("technologies", []))),
                "difficulty": c.get("difficulty", "unknown"), "status": "active", "merged_into": None, "created_at": now, "updated_at": now})
            parent = c.get("parent_id")
            require(parent is None or parent in by_candidate, "parent_id must identify a candidate in this batch")
            if parent:
                require(list(by_candidate).index(parent) < list(by_candidate).index(c["id"]), "Follow-up parent must precede child in batch order")
            final["occurrences"].append({"schema_version": 1, "id": c["oid"], "question_id": c["qid"], "source_id": c["source_id"],
                "original_text": c["original_text"], "company_id": resolve_company(final, c.get("company")), "role_tracks": roles,
                "interview_type": c.get("interview_type", "unknown"), "round": c.get("round", "unknown"), "event_date": c.get("event_date"),
                "sequence": c["sequence"], "parent_occurrence_id": by_candidate[parent]["oid"] if parent else None,
                "extraction_confidence": c["confidence"]["is_question"], "classification_confidence": c["confidence"]["classification"], "created_at": now,
                **({"locator": c["locator"]} if "locator" in c else {})})
        summary = {"images": len(sources), "duplicate_sources": len(intake["duplicates"]), "question_candidates": len(candidates),
                   "review_items": len(review), "candidate_ids": {c["id"]: c["qid"] for c in candidates}}
        operation = "media-ingest" if intake.get("operation") == "media-intake" else "image-ingest"
        if operation == "media-ingest":
            summary["media_sources"] = summary.pop("images")
        result = stage_snapshot(bank, current, final, config, operation=operation, audit=audit, review=review, summary=summary, intake_id=intake_id)
        path = run_path(bank, result["run_id"])
        atomic_write(path / "extracted.json", dumps(extraction) + "\n")
        return result


def save_extraction(bank, intake_id, patch):
    """Save a bounded host-vision response and resume later without losing work."""
    require(isinstance(patch, dict) and patch.get("schema_version") == 1 and isinstance(patch.get("sources"), list), "Expected v1 extraction response")
    with open_bank(bank) as (_, config, _):
        path = run_path(bank, intake_id)
        intake = read_json(path / "intake.json")
        source_ids = [item["source"]["id"] for item in intake["items"]]
        saved = read_json(path / "extraction.json") if (path / "extraction.json").exists() else {"schema_version": 1, "sources": []}
        results = {item["source_id"]: item for item in saved["sources"]}
        seen = set()
        for item in patch["sources"]:
            require(isinstance(item, dict) and isinstance(item.get("source_id"), str), "Invalid extraction source")
            sid = item["source_id"]
            require(sid in source_ids and sid not in seen, "Unknown/duplicate source in response")
            require(item.get("status") in ("extracted", "no_questions", "unreadable", "skip"), "Missing image disposition")
            privacy_check(dumps(item), config)
            seen.add(sid)
            results[sid] = item
        saved["sources"] = [results[sid] for sid in source_ids if sid in results]
        atomic_write(path / "extraction.json", dumps(saved) + "\n")
        return {"intake_id": intake_id, "saved": len(results), "total": len(source_ids),
                "remaining_source_ids": [sid for sid in source_ids if sid not in results], "output": str(path / "extraction.json")}
