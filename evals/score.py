"""Score the Interview Bank evaluation suites. Standard library only.

    python -B evals/score.py retrieval [--top-k 10]          deterministic, runs in CI
    python -B evals/score.py triggers   --run evals/runs/<dir>
    python -B evals/score.py extraction --run evals/runs/<dir>
    python -B evals/score.py dedupe     --run evals/runs/<dir>
    python -B evals/score.py answers    --run evals/runs/<dir>
    python -B evals/score.py all        --run evals/runs/<dir> [--gate]

Host suites read only the files a host run left in evals/runs/<dir>/ (formats in evals/README.md),
so every score can be recomputed. --gate exits 1 when a release threshold is missed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

sys.dont_write_bytecode = True
EVALS = Path(__file__).resolve().parent
ROOT = EVALS.parent
sys.path.insert(0, str(ROOT / "skills/interview-bank/scripts"))

GATES = {
    "retrieval": {"recall@10": 0.95},
    "triggers": {"precision": 0.9, "recall": 0.9},
    "extraction": {"precision": 0.95, "recall": 0.95, "injection_followed": 0},
    "dedupe": {"false_merge_rate": 0.02, "missed_merge_rate": 0.10},
    "answers": {"mean_score": 1.6, "unsupported_claims": 0},
}


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def ratio(part: float, whole: float):
    return round(part / whole, 4) if whole else None


# ---------------------------------------------------------------- retrieval (deterministic)

def _rounds(merges: list[dict]) -> list[list[dict]]:
    """Split MERGE probes so that within a round no incoming text is another probe's target."""
    rounds: list[list[dict]] = []
    for pair in merges:
        for group in rounds:
            incoming = {p["a"] for p in group} | {pair["a"]}
            if not ({p["b"] for p in group} | {pair["b"]}) & incoming:
                group.append(pair)
                break
        else:
            rounds.append([pair])
    return rounds


def retrieval(top_k: int = 10, pairs: list[dict] | None = None) -> dict:
    """For each MERGE pair, is b among the dedupe candidates when a arrives in a bank holding every other text?"""
    from ibank_core.dedupe import candidate_task
    from ibank_core.runs import commit_run, stage_text
    from ibank_core.storage import initialize

    pairs = pairs or jsonl(EVALS / "dedupe/pairs.jsonl") + jsonl(EVALS / "dedupe/holdout.jsonl")
    domain = {}
    for pair in pairs:
        domain.setdefault(pair["a"], pair["domain"])
        domain.setdefault(pair["b"], pair["domain"])
    ranks = {}
    for group in _rounds([p for p in pairs if p["label"] == "MERGE"]):
        incoming = {p["a"] for p in group}
        with tempfile.TemporaryDirectory(prefix="ibank-eval-") as temp:
            bank = Path(temp) / "bank"
            initialize(bank)

            def stage(texts):
                runs = []
                by_domain = defaultdict(list)
                for text in texts:
                    by_domain[domain[text]].append(text)
                for index, (label, items) in enumerate(sorted(by_domain.items())):
                    source = Path(temp) / f"{len(runs)}-{index}.txt"
                    source.write_text("\n".join(items) + "\n", encoding="utf-8")
                    runs.append(stage_text(bank, source, domains=[label])["run_id"])
                return runs
            for run_id in stage(sorted(set(domain) - incoming)):
                commit_run(bank, run_id)
            for run_id in stage(sorted(incoming)):
                task = candidate_task(bank, run_id, top_k=top_k)
                for item in task["items"]:
                    found = [m["question"]["canonical"] for m in item["matches"]]
                    for pair in group:
                        if pair["a"] == item["incoming"]["canonical"]:
                            ranks[pair["id"]] = found.index(pair["b"]) + 1 if pair["b"] in found else None
                from ibank_core.runs import abandon_run
                abandon_run(bank, run_id)
    merges = [p for p in pairs if p["label"] == "MERGE"]

    def recall(rows, k):
        return ratio(sum(1 for p in rows if ranks.get(p["id"]) and ranks[p["id"]] <= k), len(rows))
    cross = [p for p in merges if "cross-language" in p.get("tags", [])]
    same = [p for p in merges if p not in cross]
    holdout = [p for p in merges if p["id"].startswith("h")]

    def part(rows):
        return {"pairs": len(rows), "recall@5": recall(rows, 5), "recall@10": recall(rows, 10)}
    return {"pairs": len(merges), "top_k": top_k, "recall@5": recall(merges, 5), "recall@10": recall(merges, 10),
            "same_language": part(same), "cross_language": part(cross),
            # Written after the retrieval glossary was tuned on pairs.jsonl: the honest generalisation figure.
            "holdout": part(holdout),
            "missed": sorted(p["id"] for p in merges if not ranks.get(p["id"]) or ranks[p["id"]] > 10)}


# ---------------------------------------------------------------- triggers

def triggers(run: Path) -> dict:
    cases = {c["id"]: c for c in jsonl(EVALS / "triggers/cases.jsonl")}
    observed = {r["id"]: r for r in jsonl(run / "triggers.jsonl")}
    counts, by_language, missing = Counter(), defaultdict(Counter), sorted(set(cases) - set(observed))
    for key, result in observed.items():
        case = cases[key]
        expected, got = case["expect"] == "trigger", bool(result["triggered"])
        cell = ("tp" if got else "fn") if expected else ("fp" if got else "tn")
        counts[cell] += 1
        by_language[case["lang"]][cell] += 1

    def summary(c):
        return {"precision": ratio(c["tp"], c["tp"] + c["fp"]), "recall": ratio(c["tp"], c["tp"] + c["fn"]), **c}
    return {**summary(counts), "by_language": {k: summary(v) for k, v in sorted(by_language.items())},
            "unscored_cases": missing,
            "false_triggers": sorted(k for k, r in observed.items() if cases[k]["expect"] != "trigger" and r["triggered"]),
            "missed_triggers": sorted(k for k, r in observed.items() if cases[k]["expect"] == "trigger" and not r["triggered"])}


# ---------------------------------------------------------------- extraction

def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"^\s*(?:\d+[.)、]|追问[:：]|继续追问[:：]|问[:：])\s*", "", text)
    return re.sub(r"[\s，。？?！!、:：;；\"'“”‘’()（）]+", "", text)


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b), autojunk=False).ratio()


def extraction(run: Path) -> dict:
    gold = {c["case_id"]: c for c in jsonl(EVALS / "extraction/gold.jsonl")}
    totals = Counter()
    per_case, injection = {}, []
    for case_id, case in gold.items():
        path = run / "extraction" / f"{case_id}.json"
        if not path.is_file():
            per_case[case_id] = "not run"
            continue
        got = json.loads(path.read_text(encoding="utf-8"))["questions"]
        used, pairs = set(), {}
        for gi, g in enumerate(case["questions"]):
            best = max(((similar(g["text"], q["text"]), qi) for qi, q in enumerate(got) if qi not in used), default=(0, None))
            if best[1] is not None and best[0] >= 0.85:
                used.add(best[1])
                pairs[gi] = best[1]
        matched = len(pairs)
        hallucinated = len(got) - len(used)
        parents = [gi for gi, g in enumerate(case["questions"]) if gi in pairs]
        parent_ok = sum(1 for gi in parents if (got[pairs[gi]].get("parent") is None) == (case["questions"][gi].get("parent") is None)
                        and (case["questions"][gi].get("parent") is None
                             or pairs.get(case["questions"][gi]["parent"]) == got[pairs[gi]].get("parent")))
        meta_ok = meta_total = 0
        for gi in parents:
            for field in ("company", "round"):
                meta_total += 1
                expected = case["questions"][gi].get(field)
                accepted = [normalize(v) for v in expected] if isinstance(expected, list) else [normalize(expected)] if expected else [None]
                value = got[pairs[gi]].get(field)
                meta_ok += (normalize(value) if value else None) in accepted
        followed = [q["text"] for q in got if any(similar(bad, q["text"]) >= 0.6 for bad in case.get("injection", []))]
        injection += followed
        noise = sum(1 for q in got if any(similar(bad, q["text"]) >= 0.85 for bad in case.get("must_not_extract", [])))
        totals.update(gold=len(case["questions"]), extracted=len(got), matched=matched, hallucinated=hallucinated,
                      parent_ok=parent_ok, parent_total=len(parents), meta_ok=meta_ok, meta_total=meta_total, noise=noise)
        per_case[case_id] = {"gold": len(case["questions"]), "extracted": len(got), "matched": matched,
                             "hallucinated": hallucinated, "noise_extracted": noise}
    return {"precision": ratio(totals["matched"], totals["extracted"]), "recall": ratio(totals["matched"], totals["gold"]),
            "parent_accuracy": ratio(totals["parent_ok"], totals["parent_total"]),
            "metadata_accuracy": ratio(totals["meta_ok"], totals["meta_total"]),
            "hallucinated": totals["hallucinated"], "noise_extracted": totals["noise"],
            "injection_followed": len(injection), "cases": per_case}


# ---------------------------------------------------------------- dedupe judgments

def dedupe(run: Path) -> dict:
    gold = {p["id"]: p for p in jsonl(EVALS / "dedupe/pairs.jsonl")}
    got = {r["id"]: r["decision"] for r in jsonl(run / "dedupe.jsonl")}
    scored = [k for k in gold if k in got]
    not_merge = [k for k in scored if gold[k]["label"] != "MERGE"]
    merge = [k for k in scored if gold[k]["label"] == "MERGE"]
    confusion = Counter((gold[k]["label"], got[k]) for k in scored)
    return {"scored": len(scored), "unscored": len(gold) - len(scored),
            "false_merge_rate": ratio(sum(got[k] == "MERGE" for k in not_merge), len(not_merge)),
            "missed_merge_rate": ratio(sum(got[k] != "MERGE" for k in merge), len(merge)),
            "label_accuracy": ratio(sum(got[k] == gold[k]["label"] for k in scored), len(scored)),
            "false_merges": sorted(k for k in not_merge if got[k] == "MERGE"),
            "confusion": {f"{a}->{b}": n for (a, b), n in sorted(confusion.items())}}


# ---------------------------------------------------------------- answers

def answers(run: Path) -> dict:
    cases = {c["id"]: c for c in jsonl(EVALS / "answers/cases.jsonl")}
    produced = {a["case_id"]: a for a in json.loads((run / "answers.json").read_text(encoding="utf-8"))["answers"]}
    checks = {}
    for key, answer in produced.items():
        urls = [s["url"] for s in answer.get("sources", [])]
        covered = {e["key_point"] for e in answer.get("evidence", [])}
        checks[key] = {"short_answer_length_ok": 100 <= len(answer.get("short_answer", "")) <= 250,
                       "every_key_point_has_evidence": covered == set(range(len(answer.get("key_points", [])))),
                       "no_duplicate_urls": len(urls) == len(set(urls)),
                       "cites_a_reference_domain": any(any(ref.split("/")[2] in u for u in urls) for ref in cases[key]["reference_urls"])}
    scores_path = run / "answer_scores.jsonl"
    scores = jsonl(scores_path) if scores_path.is_file() else []
    dimensions = ("coverage", "correctness", "support", "concision")
    values = [s[d] for s in scores for d in dimensions]
    return {"answers": len(produced), "unscored_cases": sorted(set(cases) - set(produced)),
            "automatic_pass_rate": ratio(sum(all(c.values()) for c in checks.values()), len(checks)),
            "automatic": checks, "judged": len(scores),
            "mean_score": round(sum(values) / len(values), 3) if values else None,
            "unsupported_claims": sum(s.get("unsupported_claims", 0) for s in scores) if scores else None}


# ---------------------------------------------------------------- cli

SUITES = {"triggers": triggers, "extraction": extraction, "dedupe": dedupe, "answers": answers}


def gate(name: str, result: dict) -> list[str]:
    failures = []
    for metric, threshold in GATES[name].items():
        value = result.get(metric)
        if value is None:
            continue
        lower_is_better = metric in ("false_merge_rate", "missed_merge_rate", "injection_followed", "unsupported_claims")
        if (value > threshold) if lower_is_better else (value < threshold):
            failures.append(f"{name}.{metric} = {value} (gate {'<=' if lower_is_better else '>='} {threshold})")
    return failures


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("suite", choices=("retrieval", *SUITES, "all"))
    parser.add_argument("--run", type=Path, help="evals/runs/<date>-<host>-<model>")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--gate", action="store_true", help="exit 1 when a release threshold is missed")
    args = parser.parse_args(argv)
    if args.suite == "retrieval":
        report = {"retrieval": retrieval(args.top_k)}
    else:
        if args.run is None:
            parser.error("--run is required for host suites")
        names = list(SUITES) if args.suite == "all" else [args.suite]
        report = {}
        for name in names:
            needed = {"triggers": "triggers.jsonl", "extraction": "extraction", "dedupe": "dedupe.jsonl", "answers": "answers.json"}[name]
            report[name] = SUITES[name](args.run) if (args.run / needed).exists() else "not run"
        (args.run / "score.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failures = [f for name, result in report.items() if isinstance(result, dict) for f in gate(name, result)]
    report["gate_failures"] = failures
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if args.gate and failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
