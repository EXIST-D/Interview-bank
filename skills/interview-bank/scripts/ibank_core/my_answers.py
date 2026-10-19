"""The person's own notes ("my answer"): one per interview question or collection note, kept apart from canonical data.

Only the person writes them (in the Web reader); the agent reads them for exports and mock interviews but never
writes or rewrites them. They live in ``personal/my-answers.json`` so a reference-answer commit, a migration or an
undo never touches them, and the last few versions of each stay recoverable. A note whose question or entry was
later removed is kept and listed as missing: the person's words are never dropped.
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
    """Every stored note by item ID. Safe without a lock: the file is replaced atomically."""
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
    """The note shown for a question, including one written before a merge into it (the newest wins)."""
    targets = _targets(data)
    found = [entry for key, entry in answers.items() if key.startswith("q_") and entry.get("text") and targets.get(key, key) == qid]
    if not found:
        return None
    entry = max(found, key=lambda e: e["updated_at"])
    return {"text": entry["text"], "updated_at": entry["updated_at"]}


def for_note(answers: dict, note_id: str) -> dict | None:
    entry = answers.get(note_id)
    return {"text": entry["text"], "updated_at": entry["updated_at"]} if entry and entry.get("text") else None


def texts(answers: dict, data: dict) -> dict:
    """Question ID → own answer text, for exports."""
    shown = {}
    for qid in set(_targets(data).values()):
        entry = for_question(answers, data, qid)
        if entry:
            shown[qid] = entry["text"]
    return shown


def _item(bank: Path, data: dict, item_id: str):
    """(title, section) of a question or a collection note the person may write about, or a refusal."""
    if item_id.startswith("q_"):
        q = next((q for q in data["questions"] if q["id"] == item_id), None)
        require(q is not None and q["status"] == "active", "This question is no longer available; refresh the list")
        return q["canonical"], "bank"
    require(item_id.startswith("note_"), "Expected a question or note ID")
    from .note_experiences import find
    from .notes import load_notes
    note = find(load_notes(bank), item_id)
    require(note is not None, "This note is no longer available; refresh the list")
    return note["title"], section_of(note)


def section_of(note: dict) -> str:
    from .note_organization import LEARNING_KINDS
    if "experience" in note:
        return "experiences"
    return "learning" if note["organization"]["kind"] in LEARNING_KINDS else "knowledge"


def save(bank: Path, item_id: str, text: str, expected_updated_at: str) -> dict:
    """Write or clear one note. expected_updated_at is what the page last saw ('' for none); a newer save wins only once."""
    require(isinstance(item_id, str), "Expected a question or note ID")
    require(isinstance(text, str) and len(text) <= MAX_TEXT, f"An answer is at most {MAX_TEXT} characters")
    require(isinstance(expected_updated_at, str), "expected_updated_at must be a string")
    text = text.replace("\r\n", "\n").strip()
    with open_bank(bank, shared=True) as (_, _config, data):
        title, section = _item(bank, data, item_id)
        questions = {"questions": data["questions"]}
        targets = _targets(data)
    from .personal import personal_lock
    with personal_lock(bank):
        answers = load(bank)
        current = for_question(answers, questions, item_id) if item_id.startswith("q_") else for_note(answers, item_id)
        seen = current["updated_at"] if current else ""
        require(seen == expected_updated_at, "Your answer was changed elsewhere; reload it before saving")
        entry = answers.get(item_id, {"history": []})
        if entry.get("text"):
            entry["history"] = ([{"text": entry["text"], "updated_at": entry["updated_at"]}] + entry.get("history", []))[:HISTORY]
        # A question's answer written before a merge moves to the surviving question with its history.
        if item_id.startswith("q_"):
            for key in [k for k, e in answers.items() if k != item_id and e.get("text") and targets.get(k) == item_id]:
                old = answers.pop(key)
                entry["history"] = ([{"text": old["text"], "updated_at": old["updated_at"]}] + old.get("history", []) + entry["history"])[:HISTORY]
        now = utc_now()
        entry.update({"text": text, "updated_at": now, "question": title[:200], "section": section})
        answers[item_id] = entry
        atomic_write(bank_file(bank, RELATIVE), dumps({"schema_version": 1, "answers": answers}) + "\n")
    return {"saved": True, "my_answer": {"text": text, "updated_at": now} if text else None}


def listing(bank: Path, data: dict, bundle: dict, query: str = "", section: str = "") -> list:
    """Every non-empty note, newest first, with where it belongs now; items removed since are flagged, not dropped."""
    from .export import report_group
    from .note_experiences import find
    targets = _targets(data)
    questions = {q["id"]: q for q in data["questions"]}
    sources = {c["name"]: c["title"] for c in bundle["collections"]}
    from .fulltext import terms
    words = terms(query)
    rows = []
    for key, entry in load(bank).items():
        if not entry.get("text"):
            continue
        if key.startswith("q_"):
            target = questions.get(targets.get(key, key))
            title = target["canonical"] if target else entry.get("question", "")
            where = report_group(target) if target else None
            kind, item, missing = "bank", (target["id"] if target else key), target is None or target["status"] != "active"
        else:
            note = find(bundle, key)
            title = note["title"] if note else entry.get("question", "")
            where = sources.get(note["collection"], note["collection"]) if note else None
            kind, item, missing = (section_of(note) if note else entry.get("section", "knowledge")), key, note is None
        if section and kind != section:
            continue
        text = title.casefold() + "\n" + entry["text"].casefold()
        if not all(word in text for word in words):
            continue
        rows.append({"id": item, "section": kind, "title": title, "where": where, "text": entry["text"],
                     "updated_at": entry["updated_at"], "missing": missing, "versions": len(entry.get("history", []))})
    return sorted(rows, key=lambda row: row["updated_at"], reverse=True)
