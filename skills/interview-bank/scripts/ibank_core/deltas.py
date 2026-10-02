"""Record-level change sets between two bank generations (run format 2).

A snapshot stage used to store the whole final bank plus a whole before-image. A change set stores
only what differs, keyed by record ID:

    {"table": "answers", "op": "insert", "id": "ans_…", "index": 12, "after": {…}}
    {"table": "questions", "op": "update", "id": "q_…", "before": {…}, "after": {…}}
    {"table": "relations", "op": "delete", "id": "rel_…", "index": 3, "before": {…}}
    {"table": "_state", "collection": "events", "op": "insert", "id": "event_…", "after": {…}}
    {"table": "_state", "key": "version", "op": "set", "before": 2, "after": 2}

``index`` is the record's position in the list that contains it (the final list for an insert, the
original list for a delete), so inverting a change set restores order as well as content. Callers
always compare the applied result with a recorded fingerprint; anything the format cannot express
(reordered records, duplicate IDs, a state block appearing or vanishing) makes ``diff`` return
``None`` and the caller falls back to full snapshots.
"""
from __future__ import annotations

import copy
from typing import Any, Optional

from .errors import ValidationError
from .schema import TABLES

Data = dict[str, Any]
Change = dict[str, Any]
MISSING = {"$missing": True}


def _by_id(rows: list[dict]) -> Optional[dict[str, int]]:
    positions = {}
    for index, row in enumerate(rows):
        key = row.get("id") if isinstance(row, dict) else None
        if not isinstance(key, str) or key in positions:
            return None
        positions[key] = index
    return positions


def _table_diff(table: str, before: list[dict], after: list[dict]) -> Optional[list[Change]]:
    old, new = _by_id(before), _by_id(after)
    if old is None or new is None:
        return None
    kept_old = [key for key in old if key in new]
    kept_new = [key for key in new if key in old]
    if kept_old != kept_new:
        return None  # Surviving records changed order; a change set cannot express that.
    changes: list[Change] = []
    for key, index in old.items():
        if key not in new:
            changes.append({"table": table, "op": "delete", "id": key, "index": index, "before": before[index]})
    for key, index in new.items():
        if key not in old:
            changes.append({"table": table, "op": "insert", "id": key, "index": index, "after": after[index]})
        elif before[old[key]] != after[index]:
            changes.append({"table": table, "op": "update", "id": key, "before": before[old[key]], "after": after[index]})
    return changes


def _state_diff(before: dict, after: dict) -> list[Change]:
    changes: list[Change] = []
    for key in sorted(set(before) | set(after)):
        old, new = before.get(key, MISSING), after.get(key, MISSING)
        if isinstance(old, dict) and isinstance(new, dict) and old is not MISSING and new is not MISSING:
            for item in old:
                if item not in new:
                    changes.append({"table": "_state", "collection": key, "op": "delete", "id": item, "before": old[item]})
            for item, value in new.items():
                if item not in old:
                    changes.append({"table": "_state", "collection": key, "op": "insert", "id": item, "after": value})
                elif old[item] != value:
                    changes.append({"table": "_state", "collection": key, "op": "update", "id": item,
                                    "before": old[item], "after": value})
        elif old != new:
            changes.append({"table": "_state", "key": key, "op": "set", "before": old, "after": new})
    return changes


def diff(current: Data, final: Data) -> Optional[list[Change]]:
    """Changes turning current into final, or None when only a full snapshot is faithful."""
    if ("_state" in current) != ("_state" in final) or set(final) - {*TABLES, "_state"}:
        return None
    changes: list[Change] = []
    for table in TABLES:
        part = _table_diff(table, current[table], final[table])
        if part is None:
            return None
        changes.extend(part)
    if "_state" in current:
        changes.extend(_state_diff(current["_state"], final["_state"]))
    return changes


def _mismatch(change: Change) -> ValidationError:
    where = change.get("collection") or change.get("key") or ""
    return ValidationError(f"Run changes do not match the bank ({change['table']}{'/' + where if where else ''} "
                           f"{change['op']} {change.get('id', '')}); the bank moved on or the run was edited")


def apply(data: Data, changes: list[Change]) -> Data:
    """Return a new generation; every before-image must match exactly or nothing is produced."""
    result = copy.deepcopy(data)
    for table in TABLES:
        mine = [c for c in changes if c["table"] == table]
        if not mine:
            continue
        rows = result[table]
        positions = _by_id(rows)
        if positions is None:
            raise ValidationError(f"{table}: duplicate or missing IDs; cannot apply a change set")
        for change in mine:
            if change["op"] == "update":
                index = positions.get(change["id"])
                if index is None or rows[index] != change["before"]:
                    raise _mismatch(change)
                rows[index] = copy.deepcopy(change["after"])
        removed = set()
        for change in mine:
            if change["op"] == "delete":
                index = positions.get(change["id"])
                if index is None or rows[index] != change["before"]:
                    raise _mismatch(change)
                removed.add(change["id"])
        rows = [row for row in rows if row["id"] not in removed]
        for change in sorted((c for c in mine if c["op"] == "insert"), key=lambda c: c["index"]):
            if change["id"] in positions and change["id"] not in removed or not 0 <= change["index"] <= len(rows):
                raise _mismatch(change)
            rows.insert(change["index"], copy.deepcopy(change["after"]))
        result[table] = rows
    state_changes = [c for c in changes if c["table"] == "_state"]
    if state_changes:
        if "_state" not in result:
            raise _mismatch(state_changes[0])
        state = result["_state"]
        for change in state_changes:
            if change["op"] == "set":
                if state.get(change["key"], MISSING) != change["before"]:
                    raise _mismatch(change)
                if change["after"] == MISSING:
                    state.pop(change["key"], None)
                else:
                    state[change["key"]] = copy.deepcopy(change["after"])
                continue
            collection = state.get(change["collection"])
            if not isinstance(collection, dict):
                raise _mismatch(change)
            present = change["id"] in collection
            if change["op"] == "insert":
                if present:
                    raise _mismatch(change)
            elif not present or collection[change["id"]] != change["before"]:
                raise _mismatch(change)
            if change["op"] == "delete":
                del collection[change["id"]]
            else:
                collection[change["id"]] = copy.deepcopy(change["after"])
    unknown = [c for c in changes if c["table"] not in (*TABLES, "_state")]
    if unknown:
        raise _mismatch(unknown[0])
    return result


def invert(changes: list[Change]) -> list[Change]:
    """The change set that undoes this one: before and after swap, insert and delete swap."""
    swapped = {"insert": "delete", "delete": "insert", "update": "update", "set": "set"}
    inverted = []
    for change in changes:
        item = {k: v for k, v in change.items() if k not in ("before", "after")}
        item["op"] = swapped[change["op"]]
        if "after" in change:
            item["before"] = change["after"]
        if "before" in change:
            item["after"] = change["before"]
        inverted.append(item)
    return inverted


def inserted(changes: list[Change], table: str) -> list[dict]:
    """Records a change set added to one table, in final order."""
    return [c["after"] for c in sorted((c for c in changes if c["table"] == table and c["op"] == "insert"),
                                       key=lambda c: c["index"])]


def validate_changes(changes: Any) -> list[Change]:
    """Shape check for a change set read from disk."""
    ops = {"insert": ("after",), "delete": ("before",), "update": ("before", "after"), "set": ("before", "after")}
    if not isinstance(changes, list):
        raise ValidationError("changes: expected list")
    for number, change in enumerate(changes, 1):
        label = f"changes[{number}]"
        if not isinstance(change, dict) or change.get("op") not in ops:
            raise ValidationError(f"{label}: invalid change")
        if change.get("table") not in (*TABLES, "_state"):
            raise ValidationError(f"{label}: unknown table")
        if any(field not in change for field in ops[change["op"]]):
            raise ValidationError(f"{label}: missing before/after")
        if change["op"] == "set":
            if change["table"] != "_state" or not isinstance(change.get("key"), str):
                raise ValidationError(f"{label}: set applies to a state key")
        elif not isinstance(change.get("id"), str):
            raise ValidationError(f"{label}: missing id")
        elif change["table"] == "_state":
            if not isinstance(change.get("collection"), str):
                raise ValidationError(f"{label}: missing state collection")
        elif change["op"] in ("insert", "delete") and type(change.get("index")) is not int:
            raise ValidationError(f"{label}: missing index")
    return changes
