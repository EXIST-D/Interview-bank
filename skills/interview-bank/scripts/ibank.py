#!/usr/bin/env python3
"""Interview Bank CLI: Python 3.10+, no third-party runtime dependencies."""
import sys

# Installed skill is read-only, including on the first invocation.
sys.dont_write_bytecode = True

if sys.version_info < (3, 10):
    MESSAGE = (f"Interview Bank requires Python 3.10+, but {sys.executable} is {sys.version.split()[0]}. "
               "Run this CLI with a newer interpreter. To find one: macOS/Linux `ls /opt/homebrew/bin/python3.1* "
               "/usr/local/bin/python3.1* ~/.local/bin/python3.1* /usr/bin/python3.1*`; Windows `py -0p`, then `py -3.12`.")
    if "--json" in sys.argv:
        import json
        print(json.dumps({"ok": False, "command": None, "error": MESSAGE, "code": 1}), file=sys.stderr)
    else:
        print(f"Error: {MESSAGE}", file=sys.stderr)
    raise SystemExit(1)

import argparse
import json
from pathlib import Path

from ibank_core.doctor import doctor
from ibank_core import __version__
from ibank_core.catalog import DIMENSIONS, catalog_view
from ibank_core.companies import list_companies
from ibank_core.errors import BankError, describe_error
from ibank_core.index import rebuild_index
from ibank_core.runs import commit_run, stage_bundle, stage_text, show_run, undo_run, abandon_run, run_path
from ibank_core.ingestion import intake_images, stage_extraction, save_extraction
from ibank_core.curation import stage_curate, stage_classification, configure
from ibank_core.tasks import classification_task
from ibank_core.dedupe import candidate_task, stage_decisions
from ibank_core.answers import research_task, stage_answers, review_answer
from ibank_core.schema import require, validate_data
from ibank_core.search import search, detail
from ibank_core.export import export_bank
from ibank_core.output import encode, fit
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
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Machine-readable JSON envelope (compact, size-bounded)")
    common.add_argument("--pretty", action="store_true", default=argparse.SUPPRESS, help="Indent JSON output for reading")
    root = argparse.ArgumentParser(description=__doc__, parents=[common])
    root.add_argument("--version", action="version", version=__version__)
    sub = root.add_subparsers(dest="command", required=True)
    web = sub.add_parser("web", parents=[common], help="Open an optional loopback-only question reader and practice UI")
    web.add_argument("--port", type=int, default=0, help="Local port; 0 selects an available port")
    web.add_argument("--read-only", action="store_true", help="Disable saving practice ratings")
    web.add_argument("--open", action="store_true", help="Open the launch URL in the default browser")
    web.add_argument("--token-file", help="Hosting behind a reverse proxy: a fixed token the proxy sends as X-Interview-Token")
    web.add_argument("--public-origin", action="append", default=[],
                     help="Hosting behind a reverse proxy: the https:// origin the browser uses (repeatable)")
    web.add_argument("--login-file", help="Hosting: show a login page; the file is written by tools/deploy/set-login.py")
    demo = sub.add_parser("demo", parents=[common], help="Create a sample bank (20 synthetic questions, 8 sourced answers) in a new directory")
    demo.add_argument("--v2", action="store_true", help="Also migrate it to V2 so Web practice can be saved")
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
    ingest = sub.add_parser("ingest", parents=[common], help="Composite intake: images/media -> submit extraction -> finalize dedupe")
    ingest_sub = ingest.add_subparsers(dest="ingest_action", required=True)
    for kind in ("images", "media"):
        step = ingest_sub.add_parser(kind, parents=[common], help=f"Intake {kind} and return a compact reading list")
        step.add_argument("paths", nargs="+")
        step.add_argument("--retention", choices=("reference", "copy", "none"))
        step.add_argument("--recursive", action="store_true")
        step.add_argument("--reprocess", action="store_true")
    submit = ingest_sub.add_parser("submit", parents=[common], help="extract-save + stage + dedupe candidates")
    submit.add_argument("--intake", required=True)
    submit.add_argument("--extraction", type=Path, required=True)
    submit.add_argument("--top-k", type=positive_int, help="Candidates per incoming question (default: bank dedupe.top_k)")
    finalize = ingest_sub.add_parser("finalize", parents=[common], help="dedupe decisions + commit (+ optional workflow)")
    finalize.add_argument("--task", required=True)
    finalize.add_argument("--decisions", type=Path, help="Host decisions; omitted = exact matches only, others need review")
    finalize.add_argument("--workflow", help="Also create and commit a V2 research workflow over this intake")
    finalize.add_argument("--defer-review", action="store_true",
                          help="Commit the decided questions; REVIEW items stay separate and wait for the user in the Web reader")
    save = sub.add_parser("extract-save", parents=[common], help="Save partial vision results and resume a batch")
    save.add_argument("--run", required=True)
    save.add_argument("--input", type=Path, required=True)
    run = sub.add_parser("run-show", parents=[common], help="Inspect runs; page task/intake items with --offset/--limit")
    run.add_argument("--run")
    run.add_argument("--offset", type=int)
    run.add_argument("--limit", type=positive_int)
    gc = sub.add_parser("gc", parents=[common], help="Compact old run snapshots and drop expired tasks (dry-run unless --apply)")
    gc.add_argument("--apply", action="store_true", help="Actually compact/delete; review the dry-run with the user first")
    gc.add_argument("--keep-days", type=int, default=30, help="Keep every run younger than this many days (default 30)")
    gc.add_argument("--keep-last", type=int, default=20, help="Always keep the newest N stages and N tasks (default 20)")
    backup = sub.add_parser("backup", parents=[common], help="Create, verify or restore a verified ZIP of the canonical bank")
    backup.add_argument("action", choices=("create", "verify", "restore"))
    backup.add_argument("--archive", type=Path, help="Backup ZIP (verify/restore); a bare name is looked up in bank/backups")
    backup.add_argument("--destination", type=Path, help="restore: a new directory that must not exist yet")
    backup.add_argument("--include-runs", action="store_true", help="create: also archive runs/ (audit, undo points, intakes)")
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
    candidates = sub.add_parser("dedupe-candidates", parents=[common],
                                help="Candidates and a topic-grouped review sheet for a stage (--run) or existing questions (--question)")
    candidates.add_argument("--run")
    candidates.add_argument("--question", action="append")
    candidates.add_argument("--top-k", type=positive_int, help="Candidate count (default: bank dedupe.top_k)")
    judge = sub.add_parser("dedupe", parents=[common], help="Stage host judgments or automatic exact decisions")
    decision_source = judge.add_mutually_exclusive_group(required=True)
    decision_source.add_argument("--input", "--decisions", dest="input", type=Path, help="Host decisions (refs n…/e… accepted)")
    decision_source.add_argument("--task", help="Apply exact matches; non-exact candidates become REVIEW")
    decision_source.add_argument("--resolve", metavar="RUN", help="Stage the user's Web decisions on a run's review or deferred items")
    judge.add_argument("--defer-review", action="store_true", help="REVIEW items do not block the stage; the user decides them later")
    show = sub.add_parser("show", parents=[common])
    show.add_argument("question_id")
    research = sub.add_parser("research", parents=[common], help="Prepare host web-research tasks; no automatic bulk answering")
    research.add_argument("--question", action="append")
    research.add_argument("--limit", type=positive_int, default=10)
    for field in ("query", "company", "role", "technology", "answer-status"):
        research.add_argument(f"--{field}")
    answer = sub.add_parser("answer", parents=[common], help="Stage evidence-backed answer versions")
    answer.add_argument("--input", type=Path, required=True)
    answer.add_argument("--commit", action="store_true", help="Commit at once when the stage has no review items")
    answer.add_argument("--page-texts", type=Path, help="JSON object mapping citation URL -> text file of the page you read; checks evidence_quote")
    citations = sub.add_parser("verify-citations", parents=[common], help="Optional online check that cited URLs still respond (only on request)")
    citations.add_argument("--question", action="append", default=[])
    citations.add_argument("--workflow")
    citations.add_argument("--limit", type=positive_int, default=50)
    pages = sub.add_parser("page-text", parents=[common], help="Save the text of pages you cite so answer --page-texts can check quotes (network)")
    pages.add_argument("urls", nargs="+")
    recheck = sub.add_parser("answer-recheck", parents=[common], help="Rebind source-backed answers to reworded questions after a coverage check")
    recheck.add_argument("--input", type=Path, required=True)
    review = sub.add_parser("answer-review", parents=[common])
    review.add_argument("--question", required=True)
    review.add_argument("--status", choices=("reviewed", "stale"), required=True)
    review.add_argument("--reason", required=True)
    review.add_argument("--human-reviewed", action="store_true", help="Deprecated and ignored: reviewed always needs an interactive confirmation")
    for name in ("search", "stats", "export"):
        query = sub.add_parser(name, parents=[common])
        for field in ("query", "company", "role", "domain", "technology", "round", "industry", "interview-type", "difficulty", "date-from", "date-to", "as-of", "answer-status", "question-type", "company-type", "ownership", "business-model"):
            query.add_argument(f"--{field}")
        query.add_argument("--recent-days", type=positive_int)
        if name == "export":
            query.add_argument("--output", required=True)
            query.add_argument("--include-paths", action="store_true")
            query.add_argument("--answers", choices=("both", "with", "without"), default="both", help="Markdown reports: both editions (default), with answers, or questions only")
            query.add_argument("--answer-extras", choices=("folded", "inline", "none"), default="folded", help="Spoken answer, follow-ups and pitfalls in the answer edition (default: folded <details>)")
            query.add_argument("--format", choices=("markdown", "json", "jsonl", "csv", "viewer", "anki"), default="markdown",
                               help="anki: tab-separated notes for File > Import in Anki")
        else:
            query.add_argument("--limit", type=positive_int, default=20 if name == "search" else 10)
            query.add_argument("--format", choices=("human", "json", "jsonl"), default="human")
        if name == "search":
            query.add_argument("--offset", type=int, default=0)
            query.add_argument("--detail", action="store_true", help="Full records with matching occurrences and answer history instead of cards")
    from ibank_core.advanced_cli import add_parsers
    add_parsers(sub, common)
    from ibank_core.media import add_parsers as add_media_parsers
    add_media_parsers(sub, common)
    from ibank_core.portability import add_parsers as add_portability_parsers
    add_portability_parsers(sub, common)
    return root


def confirm_human_review(question_id):
    """Human review cannot be asserted by a flag: it needs a person at an interactive terminal."""
    require(sys.stdin.isatty(),
            "Human review must be confirmed by the user: open the local Web reader and press 人工审阅通过, "
            "or run answer-review --status reviewed yourself in an interactive terminal")
    print(f"Confirm that you personally reviewed the current answer of {question_id}. Type 我已审阅 (or I reviewed): ",
          end="", file=sys.stderr, flush=True)
    typed = sys.stdin.readline().strip()
    require(typed in ("我已审阅", "I reviewed"), "Not confirmed; nothing was staged")
    return "terminal"


def dispatch(args):
    if args.command == "capabilities":
        from ibank_core.portability import dispatch as portability_dispatch
        return portability_dispatch(None, args)
    if args.command == "taxonomy" and not getattr(args, "bank", None):
        return catalog_view(args.dimension, args.query, args.limit, args.offset)
    bank = resolve_bank(getattr(args, "bank", None))
    if args.command == "web":
        from ibank_core.web import serve
        return serve(bank, args.port, args.read_only, args.open, args.token_file, args.public_origin, args.login_file)
    if args.command in ("media-plan", "media-provider-task", "media-provider-import"):
        from ibank_core.portability import dispatch as portability_dispatch
        return portability_dispatch(bank, args)
    if args.command in ("media", "media-attach", "media-task", "media-transcribe", "web-intake"):
        from ibank_core.media import dispatch as media_dispatch
        return media_dispatch(bank, args)
    from ibank_core.advanced_cli import COMMANDS, dispatch as advanced_dispatch
    if args.command in COMMANDS:
        return advanced_dispatch(bank, args)
    if args.command == "taxonomy":
        with open_bank(bank, shared=True) as (_, config, _):
            return catalog_view(args.dimension, args.query, args.limit, args.offset, config.get("taxonomy_extensions"))
    if args.command == "companies":
        return list_companies(bank, **{k: getattr(args, k) for k in ("query", "industry", "company_type", "ownership", "business_model", "limit", "offset")})
    if args.command == "demo":
        from ibank_core.demo import build_demo
        return build_demo(bank, v2=args.v2)
    if args.command == "init":
        return {"bank": str(bank), "created": initialize(bank)}
    if args.command == "doctor":
        return doctor(bank)
    if args.command == "validate":
        with open_bank(bank, shared=True) as (_, config, data):
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
        return show_run(bank, args.run, args.offset, args.limit)
    if args.command == "ingest":
        from ibank_core import flows
        if args.ingest_action in ("images", "media"):
            run = flows.ingest_images if args.ingest_action == "images" else flows.ingest_media
            return run(bank, args.paths, retention=args.retention, recursive=args.recursive, reprocess=args.reprocess)
        if args.ingest_action == "submit":
            return flows.ingest_submit(bank, args.intake, read_json(args.extraction), args.top_k)
        return flows.ingest_finalize(bank, args.task, read_json(args.decisions) if args.decisions else None, args.workflow,
                                     defer_review=args.defer_review)
    if args.command == "extract-save":
        return save_extraction(bank, args.run, read_json(args.input))
    if args.command == "gc":
        from ibank_core.cleanup import gc
        return gc(bank, apply=args.apply, keep_days=args.keep_days, keep_last=args.keep_last)
    if args.command == "backup":
        from ibank_core import backups
        if args.action == "create":
            return backups.create_backup(bank, include_runs=args.include_runs)
        require(args.archive is not None, f"backup {args.action} needs --archive")
        archive = args.archive
        if not archive.exists() and len(archive.parts) == 1 and (bank / "backups" / archive).is_file():
            archive = bank / "backups" / archive
        if args.action == "verify":
            return backups.verify_backup(archive)
        require(args.destination is not None, "backup restore needs --destination <new directory>")
        return backups.restore_into(archive, args.destination)
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
        from ibank_core.dedupe import task_summary
        return task_summary(bank, candidate_task(bank, args.run, args.top_k, args.question))
    if args.command == "dedupe":
        if args.resolve:
            from ibank_core.dedupe import resolve_with_human_decisions
            return resolve_with_human_decisions(bank, args.resolve)
        return stage_decisions(bank, read_json(args.input) if args.input else None, args.task, defer_review=args.defer_review)
    if args.command == "research":
        return research_task(bank, args.question, args.limit, **{k: getattr(args, k) for k in ("query", "company", "role", "technology", "answer_status")})
    if args.command == "page-text":
        from ibank_core.citations import page_texts
        return page_texts(bank, args.urls)
    if args.command == "answer":
        pages = {}
        if args.page_texts:
            mapping = read_json(args.page_texts)
            require(isinstance(mapping, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()),
                    "--page-texts expects {\"<citation url>\": \"<path to page text>\"}")
            base = args.page_texts.resolve().parent
            pages = {url: (base / path).read_text(encoding="utf-8-sig") for url, path in mapping.items()}
        staged = stage_answers(bank, read_json(args.input), page_texts=pages)
        if args.commit:
            from ibank_core.flows import commit_unless_review
            return commit_unless_review(bank, staged)
        return staged
    if args.command == "verify-citations":
        from ibank_core.citations import verify_citations
        return verify_citations(bank, args.question, args.workflow, args.limit)
    if args.command == "answer-recheck":
        from ibank_core.answers import recheck_answers
        return recheck_answers(bank, read_json(args.input))
    if args.command == "answer-review":
        actor = "agent"
        if args.status == "reviewed":
            actor = confirm_human_review(args.question)
        return review_answer(bank, args.question, args.status, args.reason, actor=actor)
    if args.command == "commit":
        return commit_run(bank, args.run)
    if args.command == "show":
        return detail(bank, args.question_id)
    filters = {key: getattr(args, key) for key in
               ("query", "company", "role", "domain", "technology", "industry", "interview_type", "difficulty", "date_from", "date_to", "recent_days", "as_of", "answer_status", "question_type", "company_type", "ownership", "business_model")}
    filters["round_name"] = args.round
    if args.command == "export":
        return export_bank(bank, args.output, args.format, include_paths=args.include_paths, answer_mode=args.answers,
                           answer_extras_mode=args.answer_extras, **filters)
    if args.command == "search":
        return search(bank, limit=args.limit, offset=args.offset, cards=not args.detail, **filters)
    return stats(bank, limit=args.limit, **filters)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    machine = getattr(args, "json", False) or getattr(args, "format", None) == "json"
    try:
        result = dispatch(args)
    except (BankError, OSError, ValueError) as exc:
        code = exc.code if isinstance(exc, BankError) else 1
        error_type, hint = describe_error(exc)
        error = {"ok": False, "command": args.command, "error": str(exc), "code": code, "error_type": error_type, "hint": hint}
        print(json.dumps(error, ensure_ascii=False) if machine else f"Error: {exc}", file=sys.stderr)
        return code
    if machine:
        # Agents read stdout into their context: compact and size-bounded unless --pretty is asked for.
        try:
            bank = resolve_bank(getattr(args, "bank", None))
        except BankError:
            bank = None
        result = fit(args.command, result, bank)
        print(encode({"ok": True, "command": args.command, "result": result}, pretty=getattr(args, "pretty", False)))
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
