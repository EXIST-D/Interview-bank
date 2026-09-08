"""Disposable SQLite projection; callers hold the bank lock."""
import json
import os
import sqlite3
import tempfile
from contextlib import closing

from .schema import TABLES
from .storage import bank_file, dumps, fingerprint, open_bank

INDEX_VERSION = "1"


def projection_digest(data):
    # Personal workflows/events are not indexed. They must not trigger a full
    # question-index rebuild on every interview answer or practice record.
    return fingerprint({table: data[table] for table in TABLES})


def fts5_available():
    with closing(sqlite3.connect(":memory:")) as conn:
        try:
            conn.execute("CREATE VIRTUAL TABLE fts_probe USING fts5(text)")
            return True
        except sqlite3.OperationalError:
            return False


def index_status(bank, data):
    path = bank_file(bank, "cache/bank.sqlite")
    if not path.is_file():
        return "missing"
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
            if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                return "corrupt"
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not set(TABLES) <= tables:
                return "stale"
            metadata = dict(conn.execute("SELECT key, value FROM metadata"))
            return "current" if metadata == {"fingerprint": projection_digest(data), "index_version": INDEX_VERSION} else "stale"
    except sqlite3.DatabaseError:
        return "corrupt"


def build_index(bank, data):
    destination = bank_file(bank, "cache/bank.sqlite")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".bank-", suffix=".sqlite", dir=destination.parent)
    os.close(fd)
    try:
        conn = sqlite3.connect(temporary)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.executescript("""
                CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE questions (id TEXT PRIMARY KEY, canonical TEXT, normalized TEXT, status TEXT, payload TEXT NOT NULL);
                CREATE TABLE companies (id TEXT PRIMARY KEY, name TEXT, payload TEXT NOT NULL);
                CREATE TABLE sources (id TEXT PRIMARY KEY, sha256 TEXT UNIQUE, payload TEXT NOT NULL);
                CREATE TABLE occurrences (id TEXT PRIMARY KEY, question_id TEXT REFERENCES questions(id),
                    source_id TEXT REFERENCES sources(id), company_id TEXT REFERENCES companies(id),
                    round TEXT, event_date TEXT, payload TEXT NOT NULL);
                CREATE TABLE answers (id TEXT PRIMARY KEY, question_id TEXT REFERENCES questions(id), version INTEGER, payload TEXT NOT NULL);
                CREATE TABLE relations (id TEXT PRIMARY KEY, from_question_id TEXT REFERENCES questions(id),
                    to_question_id TEXT REFERENCES questions(id), payload TEXT NOT NULL);
                CREATE INDEX occurrence_question ON occurrences(question_id);
                CREATE INDEX occurrence_company ON occurrences(company_id);
            """)
            columns = {"questions": ("canonical", "normalized", "status"), "companies": ("name",),
                       "sources": ("sha256",), "occurrences": ("question_id", "source_id", "company_id", "round", "event_date"),
                       "answers": ("question_id", "version"), "relations": ("from_question_id", "to_question_id")}
            for table in ("questions", "companies", "sources", "occurrences", "answers", "relations"):
                fields = columns[table]
                conn.executemany(f"INSERT INTO {table} VALUES ({','.join('?' for _ in range(len(fields) + 2))})",
                                 [(row["id"], *(row[f] for f in fields), dumps(row)) for row in data[table]])
            conn.executemany("INSERT INTO metadata VALUES (?, ?)", [("fingerprint", projection_digest(data)), ("index_version", INDEX_VERSION)])
            conn.commit()
        finally:
            conn.close()
        with open(temporary, "r+b") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {"index": "current", "counts": {t: len(data[t]) for t in TABLES}, "fts5_available": fts5_available()}


def rebuild_index(bank):
    with open_bank(bank) as (_, _, data):
        return build_index(bank, data)


def connect_index(bank, data):
    if index_status(bank, data) != "current":
        build_index(bank, data)
    conn = sqlite3.connect(bank_file(bank, "cache/bank.sqlite").as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def rows(conn, table):
    return [json.loads(row[0]) for row in conn.execute(f"SELECT payload FROM {table}")]
