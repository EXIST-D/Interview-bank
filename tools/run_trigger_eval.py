"""Run the trigger suite against Claude Code in fresh headless sessions and save the observations.

    python -B tools/run_trigger_eval.py --model claude-haiku-5-5 [--limit 5] [--max-turns 3]

Each case runs `claude -p <query>` once, in a temporary project that contains only this Skill under
.claude/skills/, with project settings only. A case counts as triggered when the Skill tool is called for
interview-bank within --max-turns turns (default 1). Smaller models often look for the user's files first,
so a one-turn run understates their recall; record the turn limit with the result. Output: evals/runs/<date>-claude-code-<model>[-turnsN]-skill-<version>/triggers.jsonl
and meta.json; score with `python -B evals/score.py triggers --run <dir>`. Requires a logged-in
`claude` CLI. Other hosts: follow the same protocol by hand (evals/README.md).
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals/triggers/cases.jsonl"


def observe(project, query, model, max_turns=1):
    argv = ["claude", "-p", query, "--output-format", "stream-json", "--verbose", "--max-turns", str(max_turns),
            "--setting-sources", "project", "--no-session-persistence", "--model", model]
    proc = subprocess.run(argv, cwd=project, capture_output=True, text=True, encoding="utf-8", timeout=300)
    # Judge by the session's own events: stderr may carry harmless warnings, and a turn that calls a tool ends
    # with error_max_turns (non-zero exit) by design. API errors arrive as synthetic assistant messages.
    triggered, error, finished = False, None, False
    for line in proc.stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "assistant":
            if event.get("is_api_error_message"):
                error = f"API error: {event.get('error')}"
            for block in event["message"].get("content", []):
                if block.get("type") == "tool_use" and block.get("name") == "Skill" and "interview-bank" in json.dumps(block.get("input", {})):
                    triggered = True
                if block.get("type") == "text" and "authenticate" in block.get("text", ""):
                    error = block["text"]
        elif event.get("type") == "result":
            finished = event.get("subtype") in ("success", "error_max_turns")
    if not finished and not error:
        error = proc.stderr.strip()[:300] or f"no result event (exit {proc.returncode})"
    return triggered, error


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-turns", type=int, default=1)
    args = parser.parse_args()
    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()][: args.limit]
    suffix = f"-turns{args.max_turns}" if args.max_turns != 1 else ""
    skill_version = re.search(r'version: "([^"]+)"', (ROOT / "skills/interview-bank/SKILL.md").read_text(encoding="utf-8")).group(1)
    run = ROOT / "evals/runs" / f"{date.today().isoformat()}-claude-code-{args.model}{suffix}-skill-{skill_version}"
    run.mkdir(parents=True, exist_ok=True)
    version = subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="ibank-trigger-") as temp:
        project = Path(temp)
        shutil.copytree(ROOT / "skills/interview-bank", project / ".claude/skills/interview-bank")
        subprocess.run(["git", "init", "-q"], cwd=project, check=True)
        with (run / "triggers.jsonl").open("w", encoding="utf-8") as out:
            for case in cases:
                triggered, error = observe(project, case["query"], args.model, args.max_turns)
                if error:
                    raise SystemExit(f"{case['id']}: host error, nothing scored: {error}")
                out.write(json.dumps({"id": case["id"], "triggered": triggered}) + "\n")
                print(case["id"], "trigger" if triggered else "-", flush=True)
    (run / "meta.json").write_text(json.dumps({"date": date.today().isoformat(), "host": f"Claude Code {version}", "model": args.model,
        "max_turns": args.max_turns, "skill_version": skill_version,
        "method": f"claude -p, fresh session per case, project settings only, Skill tool call within {args.max_turns} turn(s) = triggered"},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(run)


if __name__ == "__main__":
    main()
