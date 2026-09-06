"""JSONL truth, atomic file replacement and recoverable multi-file commits."""
import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .errors import BankUnavailable, ValidationError
from .ids import utc_now
from .locking import bank_lock
from .schema import TABLES, require, validate_config, validate_data, validate_manifest

SKILL_ROOT = Path(__file__).resolve().parents[2]


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def jsonl_text(rows):
    return "".join(dumps(row) + "\n" for row in rows)


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=_reject_constant, object_pairs_hook=_unique_keys)
    except (ValueError, UnicodeError) as exc:
        raise ValidationError(f"{path}: invalid JSON: {exc}") from exc


def _reject_constant(value):
    raise ValueError(f"non-finite number {value}")


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def read_jsonl(path):
    records = []
    try:
        with path.open(encoding="utf-8-sig") as handle:
            for number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line, parse_constant=_reject_constant, object_pairs_hook=_unique_keys)
                    require(isinstance(row, dict), "expected object")
                    records.append(row)
                except (ValueError, ValidationError) as exc:
                    raise ValidationError(f"{path}:{number}: {exc}") from exc
    except UnicodeError as exc:
        raise ValidationError(f"{path}: expected UTF-8") from exc
    return records


def _fsync_dir(directory):
    # Windows does not expose a portable directory fsync through os.open.
    if os.name != "nt":
        fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def atomic_write(path, content):
    """Replace a file on the same filesystem; never truncate its old version."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_dir(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_bytes(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".media-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_dir(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_jsonl_atomic(path, rows):
    atomic_write(path, jsonl_text(rows))


replace_jsonl_atomic = write_jsonl_atomic


def append_jsonl(path, rows):
    """Atomic append by replacement. Caller must hold the enclosing bank lock."""
    write_jsonl_atomic(path, (read_jsonl(path) if path.exists() else []) + list(rows))


def guard_bank_path(path):
    path = Path(path).expanduser().resolve()
    require(path != SKILL_ROOT and not path.is_relative_to(SKILL_ROOT), "User bank must be outside the read-only skill directory")
    require(not SKILL_ROOT.is_relative_to(path), "Bank cannot contain the skill directory")
    return path


def resolve_bank(explicit=None, cwd=None):
    cwd = Path(cwd or Path.cwd()).resolve()
    if explicit:
        return guard_bank_path(explicit)
    if os.environ.get("INTERVIEW_BANK_HOME"):
        return guard_bank_path(os.environ["INTERVIEW_BANK_HOME"])
    for parent in (cwd, *cwd.parents):
        candidate = parent / "interview-bank"
        if (candidate / "manifest.json").is_file():
            return guard_bank_path(candidate)
        if (parent / ".git").exists():
            break
    return guard_bank_path(cwd / "interview-bank")


def bank_file(bank, relative):
    """Reject symlink escapes and path traversal for every managed location."""
    path = bank / relative
    require(path.resolve().is_relative_to(bank.resolve()), f"Managed path escapes bank: {relative}")
    return path


def empty_data():
    return {table: [] for table in TABLES}


def load_data(bank):
    try:
        return {table: read_jsonl(bank_file(bank, f"data/{table}.jsonl")) for table in TABLES}
    except FileNotFoundError as exc:
        raise BankUnavailable(f"Missing canonical file: {exc.filename}") from exc


def load_bank(bank):
    try:
        manifest = read_json(bank_file(bank, "manifest.json"))
        config = read_json(bank_file(bank, "config.json"))
    except FileNotFoundError as exc:
        raise BankUnavailable(f"Bank is not initialized: {bank}") from exc
    validate_manifest(manifest)
    validate_config(config)
    data = load_data(bank)
    validate_data(data, config)
    return manifest, config, data


def fingerprint(data):
    return hashlib.sha256(dumps(data).encode("utf-8")).hexdigest()


def _journal_target(bank, relative):
    allowed = {"manifest.json", "config.json", *(f"data/{table}.jsonl" for table in TABLES)}
    is_run = re.fullmatch(r"runs/run_[a-zA-Z0-9_-]+/(run\.json|commit\.json|report\.md|intake\.json)", relative)
    require(relative in allowed or is_run is not None, f"Unexpected journal target: {relative}")
    return bank_file(bank, relative)


def recover(bank):
    """Redo a durably recorded commit intent under lock. Safe to repeat."""
    journal = bank_file(bank, ".transaction.json")
    if not journal.exists():
        return False
    payload = read_json(journal)
    require(isinstance(payload, dict) and payload.get("schema_version") == 1 and isinstance(payload.get("files"), dict), "Invalid transaction journal")
    files = payload["files"]
    for relative, content in files.items():
        require(isinstance(content, str), "Invalid journal content")
        _journal_target(bank, relative)
    for relative, content in files.items():
        atomic_write(_journal_target(bank, relative), content)
    journal.unlink()
    _fsync_dir(bank)
    return True


def transaction(bank, files):
    """Readers also lock: no observer sees a mixture of two generations."""
    for relative in files:
        _journal_target(bank, relative)
    atomic_write(bank_file(bank, ".transaction.json"), dumps({"schema_version": 1, "files": files}) + "\n")
    recover(bank)


@contextmanager
def open_bank(bank):
    bank = guard_bank_path(bank)
    if not bank.is_dir():
        raise BankUnavailable(f"Bank does not exist: {bank}; run init")
    bank_file(bank, ".bank.lock")
    with bank_lock(bank):
        recover(bank)
        yield load_bank(bank)


def initialize(bank):
    bank = guard_bank_path(bank)
    bank.mkdir(parents=True, exist_ok=True)
    bank_file(bank, ".bank.lock")
    with bank_lock(bank):
        recover(bank)
        if (bank / "manifest.json").exists():
            load_bank(bank)
            for directory in ("media", "runs", "cache", "exports"):
                bank_file(bank, directory).mkdir(exist_ok=True)
            return False
        # Never overwrite an unrelated directory or a damaged preexisting bank.
        require(not [p for p in bank.iterdir() if p.name != ".bank.lock"], "init requires an empty directory")
        now = utc_now()
        manifest = {"schema_version": 1, "bank_version": 1, "created_at": now, "last_updated_at": now}
        config = {"bank_version": 1, "source_retention": "reference", "language": "zh-CN", "default_interview_type": "campus",
                  "dedupe": {"top_k": 10, "auto_merge_exact": True, "semantic_merge_requires_agent": True},
                  "privacy": {"persist_pii": False}, "taxonomy_extensions": {"role_tracks": [], "domains": []}}
        files = {f"data/{table}.jsonl": "" for table in TABLES}
        files.update({"manifest.json": dumps(manifest) + "\n", "config.json": dumps(config) + "\n"})
        transaction(bank, files)
        for directory in ("media", "runs", "cache", "exports"):
            bank_file(bank, directory).mkdir(exist_ok=True)
        return True
