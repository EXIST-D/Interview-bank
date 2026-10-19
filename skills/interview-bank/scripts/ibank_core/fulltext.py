"""Full-text search over collection notes: an SQLite FTS5 trigram index under cache/, with a plain scan as fallback.

Trigrams need no word segmentation, so Chinese and English are searched the same way. The index is derived data:
it is rebuilt whenever a collection file changes and is never backed up or synced.
"""
import hashlib
import json
import os
import sqlite3
import threading

from .storage import bank_file

MAX_TERMS = 8
NAME = "notes-search.sqlite"
_lock = threading.Lock()


def terms(query):
    """Whitespace separates terms that must all appear; case does not matter."""
    words = []
    for word in (query or "").casefold().split():
        if word not in words:
            words.append(word)
    return words[:MAX_TERMS]


def _supported():
    try:
        with sqlite3.connect(":memory:") as db:
            db.execute("CREATE VIRTUAL TABLE t USING fts5(x, tokenize='trigram')")
        return True
    except sqlite3.Error:
        return False


SUPPORTED = _supported()


def documents(bundle):
    """What the boards show: the notes, plus reading units and public experiences composed from them (last one wins)."""
    found = {n["id"]: n for n in bundle["notes"]}
    for collection in bundle["collections"]:
        for note in [*collection.get("readings", []), *collection.get("experiences", [])]:
            found[note["id"]] = note
    return list(found.values())


def _key(bank, notes):
    # Collection files and their organisation compose the text; links and link judgements never change it.
    directory = bank_file(bank, "collections")
    files = sorted((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in directory.iterdir()
                   if p.is_file() and p.name not in ("links.jsonl", "_judged.json")) if directory.is_dir() else []
    return hashlib.sha256(json.dumps([files, len(notes)]).encode()).hexdigest()


def _build(path, key, notes):
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    temporary.unlink(missing_ok=True)
    try:
        with sqlite3.connect(temporary) as db:
            db.execute("CREATE VIRTUAL TABLE notes USING fts5(id UNINDEXED, title, body, tokenize='trigram')")
            db.executemany("INSERT INTO notes VALUES (?, ?, ?)", ((n["id"], n["title"], n["body"]) for n in notes))
            db.execute("INSERT INTO notes(notes) VALUES ('optimize')")
            db.execute("CREATE TABLE meta (key TEXT)")
            db.execute("INSERT INTO meta VALUES (?)", (key,))
        db.close()
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _index(bank, notes):
    """The current index file, building it when collections changed; None when it cannot be kept."""
    path = bank_file(bank, "cache") / NAME
    key = _key(bank, notes)
    with _lock:
        try:
            if path.exists():
                with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
                    current = db.execute("SELECT key FROM meta").fetchone()
                db.close()
                if current and current[0] == key:
                    return path
            path.parent.mkdir(exist_ok=True)
            _build(path, key, notes)
            return path
        except (OSError, sqlite3.Error):
            return None


def prepare(bank, bundle):
    """Build the index now if it is missing or out of date."""
    return SUPPORTED and _index(bank, documents(bundle)) is not None


def _like(word):
    return "%" + word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _scan(notes, words):
    title_hits, body_hits = [], []
    for note in notes:
        title = note["title"].casefold()
        if all(w in title for w in words):
            title_hits.append(note["id"])
        elif all(w in title or w in note["body"].casefold() for w in words):
            body_hits.append(note["id"])
    return title_hits + body_hits


def rank(bank, notes, query):
    """IDs of the notes holding every term, best first: all terms in the title, then by BM25 with titles weighted.

    `notes` is every document of the bank (`documents`); callers narrow the result themselves.
    """
    words = terms(query)
    if not words:
        return [n["id"] for n in notes]
    path = _index(bank, notes) if SUPPORTED else None
    if path is None:
        return _scan(notes, words)
    # Trigrams index terms of three or more characters; shorter ones (缓存, Go) are matched by LIKE inside SQLite.
    long_words = [w for w in words if len(w) >= 3]
    clauses, values = [], []
    if long_words:
        clauses.append("notes MATCH ?")
        values.append(" AND ".join('"' + w.replace('"', '""') + '"' for w in long_words))
    for word in words:
        if len(word) < 3:
            clauses.append("(title LIKE ? ESCAPE '\\' OR body LIKE ? ESCAPE '\\')")
            values += [_like(word), _like(word)]
    in_title = " AND ".join(["title LIKE ? ESCAPE '\\'"] * len(words))
    order = f"({in_title}) DESC" + (", bm25(notes, 0, 10.0, 1.0)" if long_words else ", rowid")
    sql = f"SELECT id FROM notes WHERE {' AND '.join(clauses)} ORDER BY {order}"
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
            found = [row[0] for row in db.execute(sql, [*values, *map(_like, words)])]
        db.close()
        return found
    except sqlite3.Error:
        return _scan(notes, words)


def search(bank, bundle, candidates, query):
    """The candidates (any subset of the bundle's notes) that match, in rank order."""
    by_id = {n["id"]: n for n in candidates}
    return [by_id[i] for i in rank(bank, documents(bundle), query) if i in by_id]
