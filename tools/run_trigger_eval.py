"""Run the trigger suite against Claude Code in fresh headless sessions and save the observations.

    python -B tools/run_trigger_eval.py --model haiku [--limit 5]

Each case runs `claude -p <query>` once, in a temporary project that contains only this Skill under
.claude/skills/, with project settings only and one turn. A case counts as triggered when the first
turn calls the Skill tool for interview-bank. Output: evals/runs/<date>-claude-code-<model>/triggers.jsonl
and meta.json; score with `python -B evals/score.py triggers --run <dir>`. Requires a logged-in
`claude` CLI. Other hosts: follow the same protocol by hand (evals/README.md).
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals/triggers/cases.jsonl"


def observe(project, query, model):
    argv = ["claude", "-p", query, "--output-format", "stream-json", "--verbose", "--max-turns", "1",
            "--setting-sources", "project", "--no-session-persistence", "--model", model]
    proc = subprocess.run(argv, cwd=project, capture_output=True, text=True, encoding="utf-8", timeout=300)
    triggered, error = False, None
    for line in proc.stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "assistant":
            for block in event["message"].get("content", []):
                if block.get("type") == "tool_use" and block.get("name") == "Skill" and "interview-bank" in json.dumps(block.get("input", {})):
                    triggered = True
                if block.get("type") == "text" and "authenticate" in block.get("text", ""):
                    error = block["text"]
    return triggered, error or (proc.stderr.strip()[:300] if proc.returncode else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()][: args.limit]
    run = ROOT / "evals/runs" / f"{date.today().isoformat()}-claude-code-{args.model}"
    run.mkdir(parents=True, exist_ok=True)
    version = subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="ibank-trigger-") as temp:
        project = Path(temp)
        shutil.copytree(ROOT / "skills/interview-bank", project / ".claude/skills/interview-bank")
        subprocess.run(["git", "init", "-q"], cwd=project, check=True)
        with (run / "triggers.jsonl").open("w", encoding="utf-8") as out:
            for case in cases:
                triggered, error = observe(project, case["query"], args.model)
                if error:
                    raise SystemExit(f"{case['id']}: host error, nothing scored: {error}")
                out.write(json.dumps({"id": case["id"], "triggered": triggered}) + "\n")
                print(case["id"], "trigger" if triggered else "-", flush=True)
    (run / "meta.json").write_text(json.dumps({"date": date.today().isoformat(), "host": f"Claude Code {version}", "model": args.model,
        "method": "claude -p, fresh session per case, project settings only, one turn, Skill tool call = triggered"},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(run)


if __name__ == "__main__":
    main()
