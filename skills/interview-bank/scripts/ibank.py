#!/usr/bin/env python3
"""Interview Bank CLI: Python 3.10+, no third-party runtime dependencies."""
import sys

# Installed skill is read-only, including on the first invocation.
sys.dont_write_bytecode = True

import argparse
import json
import sqlite3
from pathlib import Path

from ibank_core.doctor import doctor
from ibank_core import __version__
from ibank_core.catalog import DIMENSIONS, catalog_view
from ibank_core.companies import list_companies
from ibank_core.errors import BankError
from ibank_core.index import rebuild_index
from ibank_core.runs import commit_run, stage_bundle, stage_text, show_run, undo_run, abandon_run, run_path
from ibank_core.ingestion import intake_images, stage_extraction, save_extraction
from ibank_core.curation import stage_curate, stage_classification, configure
from ibank_core.tasks import classification_task
from ibank_core.dedupe import candidate_task, stage_decisions
from ibank_core.answers import research_task, stage_answers, review_answer
from ibank_core.schema import validate_data
from ibank_core.search import search, detail
from ibank_core.export import export_bank
from ibank_core.stats import stats
from ibank_core.storage import initialize, open_bank, read_json, resolve_bank


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--bank", default=argparse.SUPPRESS, help="Explicit bank directory; overrides INTERVIEW_BANK_HOME")
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Machine-readable JSON envelope")
    root = argparse.ArgumentParser(description=__doc__, parents=[common])
    root.add_argument("--version", action="version", version=__version__)
    sub = root.add_subparsers(dest="command", required=True)
    for name in ("init", "doctor", "validate", "rebuild-index"):
        sub.add_parser(name, parents=[common])
    taxonomy = sub.add_parser("taxonomy", parents=[common], help="Browse classification IDs, Chinese labels and aliases (no bank needed)")
    taxonomy.add_argument("--dimension", choices=("all", *DIMENSIONS), default="all")
    taxonomy.add_argument("--query")
    taxonomy.add_argument("--limit", type=positive_int, default=50)
    taxonomy.add_argument("--offset", type=int, default=0)
    companies = sub.add_parser("companies", parents=[common], help="Find employers, aliases and evidenced company profiles in this bank")
    for field in ("query", "industry", "company-type", "ownership", "business-model"):
        companies.add_argument(f"--{field}")
    companies.add_argument("--limit", type=positive_int, default=50)
    companies.add_argument("--offset", type=int, default=0)
    stage = sub.add_parser("stage", parents=[common], help="Stage a structured JSON bundle or selected question lines")
    source = stage.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="JSON bundle with schema_version and canonical table arrays")
    source.add_argument("--text", type=Path, help="UTF-8 file: one already selected question per nonblank line")
    source.add_argument("--extracted", type=Path, help="Host vision extraction JSON; requires --run intake ID")
    source.add_argument("--from-intake", help="Stage the saved/resumed extraction from this intake ID")
    stage.add_argument("--run")
    stage.add_argument("--company")
    for field in ("role", "domain", "technology"):
        stage.add_argument(f"--{field}", action="append", default=[])
    stage.add_argument("--round", default="unknown")
    stage.add_argument("--interview-type", default="unknown")
    stage.add_argument("--event-date")
    stage.add_argument("--question-type", default="concept")
    stage.add_argument("--difficulty", default="unknown")
    stage.add_argument("--retention", choices=("reference", "none"))
    commit = sub.add_parser("commit", parents=[common])
    commit.add_argument("--run", required=True)
    images = sub.add_parser("images", parents=[common], help="Prepare a vision task from images/directories")
    images.add_argument("paths", nargs="+")
    images.add_argument("--retention", choices=("reference", "copy", "none"))
    images.add_argument("--recursive", action="store_true")
    images.add_argument("--reprocess", action="store_true", help="Retry known sources that have no question occurrences")
    save = sub.add_parser("extract-save", parents=[common], help="Save partial vision results and resume a batch")
    save.add_argument("--run", required=True)
    save.add_argument("--input", type=Path, required=True)
    run = sub.add_parser("run-show", parents=[common])
    run.add_argument("--run")
    abandon = sub.add_parser("abandon", parents=[common])
    abandon.add_argument("--run", required=True)
    undo = sub.add_parser("undo", parents=[common], help="Stage an audited undo of the latest snapshot operation")
    undo.add_argument("--run", required=True)
    classify = sub.add_parser("classify", parents=[common], help="Create a semantic classification task or stage its response")
    classify.add_argument("--question", action="append")
    classify.add_argument("--input", type=Path)
    curate = sub.add_parser("curate", parents=[common], help="Stage audited metadata/wording corrections")
    curate.add_argument("--input", type=Path, required=True)
    config = sub.add_parser("config", parents=[common], help="Inspect config or stage a validated config patch")
    config.add_argument("--input", type=Path)
    candidates = sub.add_parser("dedupe-candidates", parents=[common])
    candidates.add_argument("--run")
    candidates.add_argument("--question", action="append")
    candidates.add_argument("--top-k", type=positive_int, help="Candidate count (default: bank dedupe.top_k)")
    judge = sub.add_parser("dedupe", parents=[common], help="Stage host judgments or automatic exact decisions")
    decision_source = judge.add_mutually_exclusive_group(required=True)
    decision_source.add_argument("--input", type=Path)
    decision_source.add_argument("--task", help="Apply exact matches; non-exact candidates become REVIEW")
    show = sub.add_parser("show", parents=[common])
    show.add_argument("question_id")
    research = sub.add_parser("research", parents=[common], help="Prepare host web-research tasks; no automatic bulk answering")
    research.add_argument("--question", action="append")
    research.add_argument("--limit", type=positive_int, default=10)
    for field in ("query", "company", "role", "technology", "answer-status"):
        research.add_argument(f"--{field}")
    answer = sub.add_parser("answer", parents=[common], help="Stage evidence-backed answer versions")
    answer.add_argument("--input", type=Path, required=True)
    review = sub.add_parser("answer-review", parents=[common])
    review.add_argument("--question", required=True)
    review.add_argument("--status", choices=("reviewed", "stale"), required=True)
    review.add_argument("--reason", required=True)
    review.add_argument("--human-reviewed", action="store_true")
    for name in ("search", "stats", "export"):
        query = sub.add_parser(name, parents=[common])
        for field in ("query", "company", "role", "domain", "technology", "round", "industry", "interview-type", "difficulty", "date-from", "date-to", "as-of", "answer-status", "question-type", "company-type", "ownership", "business-model"):
            query.add_argument(f"--{field}")
        query.add_argument("--recent-days", type=positive_int)
        if name == "export":
            query.add_argument("--output", required=True)
            query.add_argument("--include-paths", action="store_true")
            query.add_argument("--answers", choices=("both", "with", "without"), default="both", help="Markdown reports: both editions (default), with answers, or questions only")
            query.add_argument("--format", choices=("markdown", "json", "jsonl", "csv", "viewer"), default="markdown")
        else:
            query.add_argument("--limit", type=positive_int, default=50 if name == "search" else 10)
            query.add_argument("--format", choices=("human", "json", "jsonl"), default="human")
        if name == "search":
            query.add_argument("--offset", type=int, default=0)
    from ibank_core.advanced_cli import add_parsers
    add_parsers(sub, common)
    return root


def dispatch(args):
    if args.command == "taxonomy" and not getattr(args, "bank", None):
        return catalog_view(args.dimension, args.query, args.limit, args.offset)
    bank = resolve_bank(getattr(args, "bank", None))
    from ibank_core.advanced_cli import COMMANDS, dispatch as advanced_dispatch
    if args.command in COMMANDS:
        return advanced_dispatch(bank, args)
    if args.command == "taxonomy":
        with open_bank(bank) as (_, config, _):
            return catalog_view(args.dimension, args.query, args.limit, args.offset, config.get("taxonomy_extensions"))
    if args.command == "companies":
        return list_companies(bank, **{k: getattr(args, k) for k in ("query", "industry", "company_type", "ownership", "business_model", "limit", "offset")})
    if args.command == "init":
        created = initialize(bank)
        return {"bank": str(bank), "created": created, **rebuild_index(bank)}
    if args.command == "doctor":
        return doctor(bank)
    if args.command == "validate":
        with open_bank(bank) as (_, config, data):
            return {"valid": True, "counts": validate_data(data, config)}
    if args.command == "rebuild-index":
        return rebuild_index(bank)
    if args.command == "stage":
        if args.from_intake:
            return stage_extraction(bank, args.from_intake, read_json(run_path(bank, args.from_intake) / "extraction.json"))
        if args.extracted:
            return stage_extraction(bank, args.run, read_json(args.extracted))
        if args.input:
            return stage_bundle(bank, read_json(args.input), args.run)
        return stage_text(bank, args.text, run_id=args.run, company=args.company, roles=args.role,
                          domains=args.domain, technologies=args.technology, round_name=args.round,
                          interview_type=args.interview_type, event_date=args.event_date,
                          question_type=args.question_type, difficulty=args.difficulty, retention=args.retention)
    if args.command == "images":
        return intake_images(bank, args.paths, retention=args.retention, recursive=args.recursive, reprocess=args.reprocess)
    if args.command == "run-show":
        return show_run(bank, args.run)
    if args.command == "extract-save":
        return save_extraction(bank, args.run, read_json(args.input))
    if args.command == "abandon":
        return abandon_run(bank, args.run)
    if args.command == "undo":
        return undo_run(bank, args.run)
    if args.command == "classify":
        return stage_classification(bank, read_json(args.input)) if args.input else classification_task(bank, args.question)
    if args.command == "curate":
        return stage_curate(bank, read_json(args.input))
    if args.command == "config":
        return configure(bank, read_json(args.input) if args.input else None)
    if args.command == "dedupe-candidates":
        return candidate_task(bank, args.run, args.top_k, args.question)
    if args.command == "dedupe":
        return stage_decisions(bank, read_json(args.input) if args.input else None, args.task)
    if args.command == "research":
        return research_task(bank, args.question, args.limit, **{k: getattr(args, k) for k in ("query", "company", "role", "technology", "answer_status")})
    if args.command == "answer":
        return stage_answers(bank, read_json(args.input))
    if args.command == "answer-review":
        return review_answer(bank, args.question, args.status, args.reason, args.human_reviewed)
    if args.command == "commit":
        result = commit_run(bank, args.run)
        # Canonical commit remains successful even if a disposable cache fails.
        try:
            result["index"] = rebuild_index(bank)["index"]
        except (BankError, OSError, sqlite3.Error) as exc:
            result["index"] = "rebuild_required"
            result["warning"] = str(exc)
        return result
    if args.command == "show":
        return detail(bank, args.question_id)
    filters = {key: getattr(args, key) for key in
               ("query", "company", "role", "domain", "technology", "industry", "interview_type", "difficulty", "date_from", "date_to", "recent_days", "as_of", "answer_status", "question_type", "company_type", "ownership", "business_model")}
    filters["round_name"] = args.round
    if args.command == "export":
        return export_bank(bank, args.output, args.format, include_paths=args.include_paths, answer_mode=args.answers, **filters)
    if args.command == "search":
        return search(bank, limit=args.limit, offset=args.offset, **filters)
    return stats(bank, limit=args.limit, **filters)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    machine = getattr(args, "json", False) or getattr(args, "format", None) == "json"
    try:
        result = dispatch(args)
    except (BankError, OSError, ValueError, sqlite3.Error) as exc:
        code = exc.code if isinstance(exc, BankError) else 1
        error = {"ok": False, "command": args.command, "error": str(exc), "code": code}
        print(json.dumps(error, ensure_ascii=False) if machine else f"Error: {exc}", file=sys.stderr)
        return code
    if machine:
        print(json.dumps({"ok": True, "command": args.command, "result": result}, ensure_ascii=False, indent=2))
    elif getattr(args, "format", None) == "jsonl" and args.command != "export":
        for item in result.get("questions", []) if args.command == "search" else [result]:
            print(json.dumps(item, ensure_ascii=False))
    elif args.command == "search":
        print(f"{result['total']} matching questions")
        for q in result["questions"]:
            print(f"{q['id']}  [{q['frequency']} matching / {q['total_frequency']} total]  {q['canonical']}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
