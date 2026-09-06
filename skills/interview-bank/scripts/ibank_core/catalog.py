"""Versioned classification vocabulary and unambiguous alias lookup.

This is label normalization, not a classifier or a corporate facts database.
"""
import copy
import json
import unicodedata
from pathlib import Path

from .errors import ValidationError

CATALOG = json.loads((Path(__file__).resolve().parents[2] / "references/classification-catalog.json").read_text(encoding="utf-8"))
DIMENSIONS = ("role_tracks", "domains", "technologies", "industries", "company_type", "ownership", "business_models")
PROFILE_FIELDS = ("company_type", "ownership", "business_models", "profile_evidence")


def key(value):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Classification label must be a nonempty string")
    return unicodedata.normalize("NFKC", value).strip().casefold()


LOOKUP, ENTRIES = {}, {}
for dimension in DIMENSIONS:
    index, entries = {}, {}
    for entry in CATALOG[dimension]:
        if entry["id"] in entries:
            raise ValueError(f"Duplicate catalog ID: {dimension}/{entry['id']}")
        entries[entry["id"]] = entry
        for label in (entry["id"], entry["label"], *entry["aliases"]):
            token = key(label)
            if token in index and index[token] != entry["id"]:
                raise ValueError(f"Ambiguous catalog alias: {dimension}/{label}")
            index[token] = entry["id"]
    for entry in entries.values():
        if entry.get("parent") and entry["parent"] not in entries:
            raise ValueError(f"Missing catalog parent: {dimension}/{entry['id']}")
    LOOKUP[dimension], ENTRIES[dimension] = index, entries


def normalize_label(dimension, value):
    token = key(value)
    return LOOKUP[dimension].get(token, token if dimension == "technologies" else value.strip())


def normalize_labels(dimension, values):
    if not isinstance(values, (list, tuple)):
        raise ValidationError(f"{dimension}: expected label array")
    return list(dict.fromkeys(normalize_label(dimension, value) for value in values))


def matches(dimension, value, selected):
    value, selected = normalize_label(dimension, value), normalize_label(dimension, selected)
    return value == selected or (dimension in ("role_tracks", "domains", "industries") and value.startswith(selected + "."))


def display(dimension, value):
    normalized = normalize_label(dimension, value)
    return ENTRIES[dimension].get(normalized, {}).get("label", value)


def catalog_view(dimension="all", query=None, limit=50, offset=0, extensions=None):
    if dimension not in (*DIMENSIONS, "all"):
        raise ValidationError("Unknown taxonomy dimension")
    if type(limit) is not int or limit <= 0 or type(offset) is not int or offset < 0:
        raise ValidationError("Invalid taxonomy pagination")
    dimensions = DIMENSIONS if dimension == "all" else (dimension,)
    terms = [key(t) for t in (query or "").split()]
    result = []
    for dim in dimensions:
        records = [*CATALOG[dim]]
        records += [{"id": label, "label": label, "aliases": [], "custom": True}
                    for label in (extensions or {}).get(dim, []) if label not in ENTRIES[dim]]
        for record in records:
            text = key(" ".join([record["id"], record["label"], *record["aliases"]]))
            if all(term in text for term in terms):
                result.append({"dimension": dim, **copy.deepcopy(record)})
    return {"catalog_version": CATALOG["catalog_version"], "dimension": dimension, "total": len(result), "offset": offset,
            "counts": {dim: len(CATALOG[dim]) for dim in DIMENSIONS}, "items": result[offset:offset + limit]}


def company_matches(entity, *, company_type=None, ownership=None, business_model=None, industry=None):
    for field, selected in (("company_type", company_type), ("ownership", ownership)):
        if selected and not matches(field, entity.get(field, "unknown"), selected):
            return False
    if business_model and not any(matches("business_models", v, business_model) for v in entity.get("business_models", [])):
        return False
    return not industry or any(matches("industries", v, industry) for v in entity.get("industries", []))
