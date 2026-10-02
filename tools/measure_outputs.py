"""Measure what agents receive: stdout bytes per command, and runs/ growth per write, on a synthetic bank.

Usage: python -B tools/measure_outputs.py [--questions 1000]
Banks are created in a temporary directory and removed afterwards.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "skills/interview-bank/scripts/ibank.py"
COMMANDS = [("search", "--query", "Redis"), ("search", "--limit", "200"), ("classify",), ("dedupe-candidates",),
            ("research", "--limit", "10"), ("stats",), ("doctor",)]


def run(bank, *args):
    proc = subprocess.run([sys.executable, "-B", str(CLI), *args, "--bank", str(bank), "--json"],
                          capture_output=True, text=True, encoding="utf-8")
    if proc.returncode:
        raise RuntimeError(proc.stderr)
    return proc.stdout


def tree_bytes(path):
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--questions", type=int, default=1000)
    count = parser.parse_args().questions
    with tempfile.TemporaryDirectory(prefix="ibank-measure-") as temp:
        bank, source = Path(temp) / "bank", Path(temp) / "questions.txt"
        run(bank, "init")
        source.write_text("".join(f"Redis 的原理与实现细节是什么？（变体 {i}）\n" for i in range(count)), encoding="utf-8")
        run(bank, "commit", "--run", json.loads(run(bank, "stage", "--text", str(source), "--domain", "backend.cache"))["result"]["run_id"])
        report = {"questions": count, "stdout_bytes": {}}
        for args in COMMANDS:
            out = run(bank, *args)
            report["stdout_bytes"][" ".join(args)] = {"bytes": len(out.encode("utf-8")), "paged": "_page" in json.loads(out)["result"]}
        before = tree_bytes(bank / "runs")
        task = json.loads(run(bank, "research", "--limit", "10"))["result"]
        answers = [{"question_id": item["question"]["id"], "status": "ai_draft", "short_answer": "草稿", "key_points": ["要点"],
                    "sources": []} for item in task["items"]]
        payload = Path(temp) / "answers.json"
        payload.write_text(json.dumps({"schema_version": 1, "task_id": task["id"], "answers": answers}, ensure_ascii=False), encoding="utf-8")
        staged = json.loads(run(bank, "answer", "--input", str(payload)))["result"]
        run(bank, "commit", "--run", staged["run_id"])
        report["runs_bytes_per_answer_batch"] = tree_bytes(bank / "runs") - before
        report["data_bytes"] = tree_bytes(bank / "data")
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
