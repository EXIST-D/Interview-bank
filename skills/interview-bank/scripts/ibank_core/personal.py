"""The person's own layer beside the bank: favourites and learning state, in personal/ (never data/).

Only the person writes it (in the Web reader). Writes take a lock of their own (personal/.bank.lock), so saving a
favourite never waits for a long bank read and never blocks one. Files are replaced atomically, so a backup or a
reader always sees a whole version.
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from pathlib import Path

from .ids import new_id, utc_now
from .locking import bank_lock
from .schema import require
from .storage import atomic_write, bank_file, dumps, read_json

ITEM = re.compile(r"(?:q|note)_[A-Za-z0-9_]{1,80}")
FOLDER = re.compile(r"fav_[A-Za-z0-9]{1,40}")
STATES = ("unread", "read", "review", "mastered")
MAX_FOLDERS, MAX_ITEMS, MAX_NAME, MAX_READ = 200, 5000, 60, 20000


@contextmanager
def personal_lock(bank: Path):
    directory = bank_file(bank, "personal")
    directory.mkdir(exist_ok=True)
    with bank_lock(directory):
        yield


def _read(bank: Path, name: str, empty: dict) -> dict:
    path = bank_file(bank, f"personal/{name}")
    if not path.exists():
        return empty
    payload = read_json(path)
    require(isinstance(payload, dict) and payload.get("schema_version") == 1, f"Invalid personal/{name}")
    return payload


def _write(bank: Path, name: str, payload: dict):
    atomic_write(bank_file(bank, f"personal/{name}"), dumps(payload) + "\n")


def item_id(value) -> str:
    require(isinstance(value, str) and ITEM.fullmatch(value) is not None, "Expected a question or note ID")
    return value


# ---------------------------------------------------------------- favourites

def favorites(bank: Path) -> list:
    return _read(bank, "favorites.json", {"schema_version": 1, "folders": []})["folders"]


def change_favorites(bank: Path, payload: dict) -> list:
    """One change: create, rename, delete or move a folder; add or remove an item. Repeating a change is harmless."""
    require(isinstance(payload, dict) and isinstance(payload.get("action"), str), "Expected a favourites action")
    action = payload["action"]
    allowed = {"create": {"name"}, "rename": {"folder", "name"}, "delete": {"folder"}, "move": {"folder", "position"},
               "add": {"folder", "item"}, "remove": {"folder", "item"}}
    require(action in allowed and set(payload) == allowed[action] | {"action"}, "Unknown favourites action or fields")
    with personal_lock(bank):
        store = _read(bank, "favorites.json", {"schema_version": 1, "folders": []})
        folders = store["folders"]
        now = utc_now()

        def folder():
            require(isinstance(payload["folder"], str) and FOLDER.fullmatch(payload["folder"]) is not None, "Expected a folder ID")
            found = next((f for f in folders if f["id"] == payload["folder"]), None)
            require(found is not None, "This favourites folder no longer exists; refresh the page")
            return found

        def name():
            value = payload["name"].strip() if isinstance(payload["name"], str) else ""
            require(1 <= len(value) <= MAX_NAME, f"A folder name is 1 to {MAX_NAME} characters")
            return value

        if action == "create":
            require(len(folders) < MAX_FOLDERS, f"At most {MAX_FOLDERS} folders")
            folders.append({"id": new_id("fav"), "name": name(), "created_at": now,
                            "updated_at": now, "items": []})
        elif action == "rename":
            target = folder()
            target.update(name=name(), updated_at=now)
        elif action == "delete":
            target = folder()
            folders.remove(target)
        elif action == "move":
            target = folder()
            require(isinstance(payload["position"], int), "Position must be a number")
            folders.remove(target)
            folders.insert(max(0, min(payload["position"], len(folders))), target)
        else:
            target, item = folder(), item_id(payload["item"])
            present = any(entry["id"] == item for entry in target["items"])
            if action == "add" and not present:
                require(len(target["items"]) < MAX_ITEMS, f"At most {MAX_ITEMS} entries per folder")
                target["items"].insert(0, {"id": item, "added_at": now})
                target["updated_at"] = now
            elif action == "remove" and present:
                target["items"] = [entry for entry in target["items"] if entry["id"] != item]
                target["updated_at"] = now
        _write(bank, "favorites.json", store)
        return folders


# ---------------------------------------------------------------- learning state

def _empty_learning() -> dict:
    return {"schema_version": 1, "read": {}, "states": {}, "shelf": None}


def _view(payload: dict) -> dict:
    return {"read": payload.get("read", {}), "states": payload.get("states", {}), "shelf": payload.get("shelf")}


def learning(bank: Path) -> dict:
    return _view(_read(bank, "learning.json", _empty_learning()))


def change_learning(bank: Path, payload: dict) -> dict:
    """Merge one device's changes: read marks only add, a state keeps the newest change, the shelf order is replaced.

    Each device sends what it did with its own time, so two devices merge instead of overwriting each other.
    """
    require(isinstance(payload, dict) and set(payload) <= {"read", "states", "shelf"}, "Unknown learning fields")
    read = payload.get("read", {})
    states = payload.get("states", {})
    require(isinstance(read, dict) and isinstance(states, dict), "read and states are objects")
    with personal_lock(bank):
        current = _read(bank, "learning.json", _empty_learning())
        marks, saved = current.setdefault("read", {}), current.setdefault("states", {})
        for key, at in read.items():
            item_id(key)
            require(isinstance(at, str) and len(at) <= 40, "A read mark carries its time")
            marks.setdefault(key, at)
        for key, value in states.items():
            item_id(key)
            require(isinstance(value, dict) and value.get("state") in STATES and isinstance(value.get("at"), str)
                    and set(value) <= {"state", "at", "reading_digest"}, "Invalid learning state")
            if key not in saved or saved[key].get("at", "") <= value["at"]:
                saved[key] = value
        if len(marks) > MAX_READ:
            for key in sorted(marks, key=marks.get)[:len(marks) - MAX_READ]:
                del marks[key]
        if "shelf" in payload:
            shelf = payload["shelf"]
            require(isinstance(shelf, dict) and set(shelf) == {"order", "at"} and isinstance(shelf["order"], list)
                    and all(isinstance(n, str) and len(n) <= 80 for n in shelf["order"]) and len(shelf["order"]) <= 500,
                    "Invalid shelf order")
            if not current.get("shelf") or current["shelf"].get("at", "") <= shelf["at"]:
                current["shelf"] = shelf
        _write(bank, "learning.json", current)
        return _view(current)
