"""Replay the 2026-09-05 host research example and classification via the CLI.

Sources were actually read during development. Replaying this fixture does not
perform fresh research and retains the original accessed_at dates.
"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
from acceptance import run_cli


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", type=Path, default=ROOT / ".work/acceptance-final")
    bank = parser.parse_args().bank.resolve()
    if not bank.is_relative_to(ROOT):
        raise ValueError("Acceptance artifacts must stay in this repository")
    q = run_cli(bank, "search", "--query", "Redis 为什么快", "--limit", "1")["questions"][0]
    task = run_cli(bank, "classify", "--question", q["id"])
    response = {"schema_version": 1, "task_id": task["id"], "items": [{"question_id": q["id"], "confidence": 0.97,
        "reason": "题目讨论 Redis 性能机制，属于后端缓存概念题；不据此推断来源中的公司、轮次或日期。",
        "question": {"question_type": "concept", "domains": ["backend.cache"], "technologies": ["redis"], "role_tracks": ["backend"], "difficulty": "medium"}}]}
    path = bank / "classification-response.json"
    path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
    run = run_cli(bank, "classify", "--input", str(path))
    run_cli(bank, "commit", "--run", run["run_id"])
    task = run_cli(bank, "research", "--question", q["id"])
    answer = json.loads((ROOT / "examples/answer-sample.json").read_text(encoding="utf-8"))
    answer["question_id"] = q["id"]
    path = bank / "answer-response.json"
    path.write_text(json.dumps({"schema_version": 1, "task_id": task["id"], "answers": [answer]}, ensure_ascii=False, indent=2), encoding="utf-8")
    run = run_cli(bank, "answer", "--input", str(path))
    receipt = run_cli(bank, "commit", "--run", run["run_id"])
    exports = []
    for format in ("markdown", "json", "jsonl", "csv", "viewer"):
        exports.append(run_cli(bank, "export", "--query", "Redis 为什么快", "--output", f"redis-reference.{format}", "--format", format))
    result = {"question_id": q["id"], "receipt": receipt, "detail": run_cli(bank, "show", q["id"]), "exports": exports,
              "validate": run_cli(bank, "validate")}
    (bank / "enrichment-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"question_id": q["id"], "answer_status": result["detail"]["question"]["answer_status"],
                      "version": result["detail"]["question"]["answer"]["version"], "export": exports[0]["output"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
