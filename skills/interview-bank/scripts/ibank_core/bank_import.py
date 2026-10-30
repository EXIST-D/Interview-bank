"""Carry the questions of one bank into another as plain text: no media, no answers, no transcripts.

`export-bundle` writes the questions of a bank (a collector's bank, say) with their occurrences (company, role,
round, interview type, dates, the original wording) and where each came from (platform and URL) into one JSON file.
`import-bundle` stages that file in another bank as new questions and hands the result to the usual dedupe:
candidates and a review sheet, then `ingest finalize --task … --decisions …` decides and commits.
Nothing is merged on its own: the imported occurrences count in the target's frequencies only as the person decides.
"""
import hashlib
from collections import Counter, defaultdict

from .dedupe import candidate_task, task_summary
from .ids import new_company_id, new_occurrence_id, new_source_id, utc_now
from .normalize import normalize_company_alias
from .runs import combined, stage_bundle
from .schema import TABLES, TAXONOMY, require, validate_data
from .storage import open_bank, read_json

FORMAT = "ibank-question-bundle"
BUNDLE_TABLES = ("questions", "occurrences", "sources", "companies", "relations")
"""Answers are left out on purpose: the target researches its own."""


def export_bundle(bank):
    """The active questions of a bank (and the wordings merged into them) without media, answers or transcript locators."""
    with open_bank(bank, shared=True) as (_, _, data):
        questions = [q for q in data["questions"] if q["status"] == "active" and not q.get("report_exclusion")]
        wanted = {q["id"] for q in questions}
        # Wordings that were merged into a kept question travel with it: the reader lists them as its other phrasings.
        questions += [q for q in data["questions"] if q["status"] == "merged" and q["merged_into"] in wanted]
        sources = {s["id"]: s for s in data["sources"]}
        by_source = defaultdict(list)
        for occurrence in data["occurrences"]:
            if occurrence["question_id"] in wanted:
                by_source[occurrence["source_id"]].append(occurrence)

        # One text source per post URL: the images and pages a post was read from stay behind.
        merged, source_of = {}, {}
        for old_id, rows in by_source.items():
            url = sources[old_id].get("source_url")
            key = url or f"source:{old_id}"
            if key not in merged:
                sha = hashlib.sha256(key.encode("utf-8")).hexdigest()
                merged[key] = {
                    "id": f"src_{sha[:32]}", "imported_at": sources[old_id]["imported_at"], "path": None,
                    "platform": sources[old_id].get("platform"), "retention": "none", "schema_version": 1,
                    "sha256": sha, "source_date": sources[old_id].get("source_date"), "source_url": url, "type": "web",
                }
            source_of[old_id] = merged[key]["id"]

        occurrences, sequence = [], defaultdict(int)
        for occurrence in sorted(data["occurrences"], key=lambda o: (o["created_at"], o["sequence"], o["id"])):
            if occurrence["question_id"] not in wanted:
                continue
            new_source = source_of[occurrence["source_id"]]
            sequence[new_source] += 1
            row = {k: v for k, v in occurrence.items() if k != "locator"}
            row.update(source_id=new_source, sequence=sequence[new_source])
            occurrences.append(row)
        kept = {o["id"] for o in occurrences}
        for row in occurrences:
            if row["parent_occurrence_id"] not in kept:
                row["parent_occurrence_id"] = None
        used_companies = {o["company_id"] for o in occurrences if o["company_id"]}
        bundle = {
            "schema_version": 1,
            "questions": questions,
            "occurrences": occurrences,
            "sources": sorted(merged.values(), key=lambda s: s["id"]),
            "companies": [c for c in data["companies"] if c["id"] in used_companies],
            "relations": [r for r in data["relations"] if {r["from_question_id"], r["to_question_id"]} <= wanted],
        }
    counts = {table: len(bundle[table]) for table in BUNDLE_TABLES}
    counts["merged_wordings"] = sum(q["status"] == "merged" for q in bundle["questions"])
    return {"format": FORMAT, "version": 1, "exported_at": utc_now(), "bundle": bundle, "counts": counts}


def _company_index(companies):
    index = {}
    for company in companies:
        for text in (company["name"], *company["aliases"]):
            index.setdefault(normalize_company_alias(text), company["id"])
    return index


PRECISION = {"year": 4, "month": 7, "day": 10}


def build_addition(current, config, wrapper, fill_event_date=None):
    """What the target gets: the bundle's new questions with ids, companies and sources fitted to the target.

    fill_event_date (year, month or day) gives an occurrence without an interview date the date its post was
    published, cut to that precision: an approximation, good enough to file a question under a period. The exact
    publish date stays on the source."""
    require(fill_event_date in (None, *PRECISION), "fill_event_date must be year, month or day")
    require(isinstance(wrapper, dict) and wrapper.get("format") == FORMAT and wrapper.get("version") == 1,
            f"Not a question bundle: expected format {FORMAT}")
    bundle = wrapper["bundle"]
    taxonomy = {field: set(TAXONOMY[field]) | set(config.get("taxonomy_extensions", {}).get(field, []))
                for field in ("domains", "role_tracks")}
    dropped = defaultdict(set)

    def keep_known(values, field):
        known = [v for v in values if v in taxonomy[field]]
        dropped[field].update(set(values) - set(known))
        return known

    existing_questions = {q["id"] for q in current["questions"]}
    skipped = {q["id"] for q in bundle["questions"] if q["id"] in existing_questions}
    questions = []
    for question in bundle["questions"]:
        if question["id"] in skipped:
            continue
        questions.append({**question, "domains": keep_known(question["domains"], "domains"),
                          "role_tracks": keep_known(question.get("role_tracks", []), "role_tracks")})
    wanted = {q["id"] for q in questions}

    index = _company_index(current["companies"])
    company_of, new_companies, taken = {}, [], {c["id"] for c in current["companies"]}
    for company in bundle["companies"]:
        names = [normalize_company_alias(t) for t in (company["name"], *company["aliases"])]
        matches = {index[n] for n in names if n in index}
        require(len(matches) <= 1, f"Company {company['name']} matches several companies of the target: {sorted(matches)}")
        if matches:
            company_of[company["id"]] = matches.pop()
            continue
        row = dict(company)
        if row["id"] in taken:
            row["id"] = new_company_id()
        taken.add(row["id"])
        company_of[company["id"]] = row["id"]
        new_companies.append(row)
        index.update({n: row["id"] for n in names})

    have_sha = {s["sha256"]: s["id"] for s in current["sources"]}
    source_of, new_sources, taken_sources = {}, [], {s["id"] for s in current["sources"]}
    needed = {o["source_id"] for o in bundle["occurrences"] if o["question_id"] in wanted}
    for source in bundle["sources"]:
        if source["id"] not in needed:
            continue
        if source["sha256"] in have_sha:
            source_of[source["id"]] = have_sha[source["sha256"]]
            continue
        row = dict(source)
        if row["id"] in taken_sources:
            row["id"] = new_source_id()
        taken_sources.add(row["id"])
        source_of[source["id"]] = row["id"]
        new_sources.append(row)

    next_sequence = defaultdict(int)
    for occurrence in current["occurrences"]:
        next_sequence[occurrence["source_id"]] = max(next_sequence[occurrence["source_id"]], occurrence["sequence"])
    taken_occurrences = {o["id"] for o in current["occurrences"]}
    published = {s["id"]: s.get("source_date") for s in bundle["sources"]}
    occurrence_of, occurrences, filled = {}, [], 0
    for occurrence in bundle["occurrences"]:
        if occurrence["question_id"] not in wanted:
            continue
        row = {**occurrence, "source_id": source_of[occurrence["source_id"]],
               "company_id": company_of.get(occurrence["company_id"]) if occurrence["company_id"] else None,
               "role_tracks": keep_known(occurrence.get("role_tracks", []), "role_tracks")}
        if fill_event_date and not row["event_date"] and published.get(occurrence["source_id"]):
            row["event_date"] = published[occurrence["source_id"]][:PRECISION[fill_event_date]]
            filled += 1
        if row["id"] in taken_occurrences:
            row["id"] = new_occurrence_id()
        taken_occurrences.add(row["id"])
        next_sequence[row["source_id"]] += 1
        row["sequence"] = next_sequence[row["source_id"]]
        occurrence_of[occurrence["id"]] = row["id"]
        occurrences.append(row)
    for row in occurrences:
        row["parent_occurrence_id"] = occurrence_of.get(row["parent_occurrence_id"])
    existing_relations = {(r["from_question_id"], r["to_question_id"], r["type"]) for r in current["relations"]}
    relations = [r for r in bundle["relations"]
                 if {r["from_question_id"], r["to_question_id"]} <= wanted
                 and (r["from_question_id"], r["to_question_id"], r["type"]) not in existing_relations]
    addition = {table: [] for table in TABLES}
    addition.update(questions=questions, occurrences=occurrences, sources=new_sources, companies=new_companies,
                    relations=relations)
    report = {
        "new_questions": sum(q["status"] == "active" for q in questions),
        "new_merged_wordings": sum(q["status"] == "merged" for q in questions), "new_occurrences": len(occurrences), "new_sources": len(new_sources),
        "new_companies": [c["name"] for c in new_companies],
        "reused_companies": sum(1 for old, new in company_of.items() if new in {c["id"] for c in current["companies"]}),
        "already_in_target": len(skipped),
        "event_dates_filled_from_publish_date": filled,
        "years": dict(sorted(Counter(o["event_date"][:4] if o["event_date"] else "unknown" for o in occurrences).items())),
        "dropped_tags": {field: sorted(values) for field, values in dropped.items() if values},
    }
    return addition, report


def import_bundle(bank, wrapper, top_k=None, dry_run=False, fill_event_date=None):
    with open_bank(bank, shared=True) as (_, config, current):
        addition, report = build_addition(current, config, wrapper, fill_event_date)
        validate_data(combined(current, addition), config)
    if dry_run or not addition["questions"]:
        return {"status": "dry_run" if dry_run else "nothing_new", "report": report, "valid": True}
    staged = stage_bundle(bank, {"schema_version": 1, **{t: addition[t] for t in TABLES}})
    task = candidate_task(bank, staged["run_id"], top_k)
    summary = task_summary(bank, task)
    return {"status": "dedupe_pending", "stage_run": staged["run_id"], "report": report, "dedupe": summary,
            "next": (f"Read the review sheet ({summary['review_sheet']}), then ingest finalize --task {task['id']} "
                     "--decisions <file> --defer-review. Imported questions stay separate unless a decision merges them.")}


def read_bundle(path):
    return read_json(path)
