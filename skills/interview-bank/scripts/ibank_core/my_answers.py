"""The person's own answers, one per question, kept apart from reference answers and canonical data.

Only the person writes them (in the Web reader); the agent reads them for exports and mock interviews
but never writes or rewrites them. They live in ``personal/my-answers.json`` so a reference-answer
commit, a migration or an undo never touches them, and the last few versions of each stay recoverable.
"""
from __future__ import annotations

from pathlib import Path

from .ids import utc_now
from .schema import require
from .storage import atomic_write, bank_file, dumps, open_bank, read_json

RELATIVE = "personal/my-answers.json"
MAX_TEXT = 20000
HISTORY = 10


def load(bank: Path) -> dict:
    """Every stored answer by question ID. The caller holds the bank lock (shared is enough)."""
    path = bank_file(bank, RELATIVE)
    if not path.exists():
        return {}
    payload = read_json(path)
    require(isinstance(payload, dict) and payload.get("schema_version") == 1 and isinstance(payload.get("answers"), dict),
            f"Invalid {RELATIVE}")
    return payload["answers"]


def _targets(data: dict) -> dict:
    return {q["id"]: (q["merged_into"] or q["id"]) for q in data["questions"]}


def for_question(answers: dict, data: dict, qid: str) -> dict | None:
    """The answer shown for a question, including one written before a merge into it (the newest wins)."""
    targets = _targets(data)
    found = [entry for key, entry in answers.items() if entry.get("text") and targets.get(key, key) == qid]
    if not found:
        return None
    entry = max(found, key=lambda e: e["updated_at"])
    return {"text": entry["text"], "updated_at": entry["updated_at"]}


def texts(answers: dict, data: dict) -> dict:
    """Question ID → own answer text, for exports."""
    shown = {}
    for qid in {target for target in _targets(data).values()}:
        entry = for_question(answers, data, qid)
        if entry:
            shown[qid] = entry["text"]
    return shown


def save(bank: Path, question_id: str, text: str, expected_updated_at: str) -> dict:
    """Write or clear one answer. expected_updated_at is what the page last saw ('' for none); a newer save wins only once."""
    require(isinstance(text, str) and len(text) <= MAX_TEXT, f"An answer is at most {MAX_TEXT} characters")
    require(isinstance(expected_updated_at, str), "expected_updated_at must be a string")
    text = text.replace("\r\n", "\n").strip()
    with open_bank(bank) as (_, _config, data):
        q = next((q for q in data["questions"] if q["id"] == question_id), None)
        require(q is not None and q["status"] == "active", "This question is no longer available; refresh the list")
        answers = load(bank)
        current = for_question(answers, data, question_id)
        seen = current["updated_at"] if current else ""
        require(seen == expected_updated_at, "Your answer was changed elsewhere; reload it before saving")
        entry = answers.get(question_id, {"history": []})
        if entry.get("text"):
            entry["history"] = ([{"text": entry["text"], "updated_at": entry["updated_at"]}] + entry.get("history", []))[:HISTORY]
        # An answer written before a merge moves to the surviving question with its history.
        for key in [k for k, e in answers.items() if k != question_id and e.get("text") and _targets(data).get(k) == question_id]:
            old = answers.pop(key)
            entry["history"] = ([{"text": old["text"], "updated_at": old["updated_at"]}] + old.get("history", []) + entry["history"])[:HISTORY]
        now = utc_now()
        entry.update({"text": text, "updated_at": now, "question": q["canonical"][:200]})
        answers[question_id] = entry
        atomic_write(bank_file(bank, RELATIVE), dumps({"schema_version": 1, "answers": answers}) + "\n")
    return {"saved": True, "my_answer": {"text": text, "updated_at": now} if text else None}
