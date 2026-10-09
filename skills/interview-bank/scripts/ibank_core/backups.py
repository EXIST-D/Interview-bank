"""Verified, self-describing bank backups that restore into a new directory.

An archive holds the canonical bank (manifest, config, data/, media/, collections/) and, optionally, runs/.
``_BACKUP_MANIFEST.json`` lists the SHA-256 of every entry; a ``.sha256`` sidecar covers the archive.
Restoring never touches an existing directory: it unpacks next to the destination, validates the
result as a bank and only then renames it into place.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable, Optional

from .ids import new_id, utc_now
from .schema import require
from .storage import atomic_write, bank_file, dumps, guard_bank_path, load_bank, open_bank

MANIFEST_NAME = "_BACKUP_MANIFEST.json"
CANONICAL = ("manifest.json", "config.json", "data", "media", "collections")


def bank_files(bank: Path, include_runs: bool = False) -> list[Path]:
    """Canonical files of a bank, refusing symlinks and paths that escape it."""
    roots = [*CANONICAL, *(("runs",) if include_runs else ())]
    paths = []
    for name in roots:
        root = bank / name
        candidates = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file()) if root.is_dir() else []
        for path in candidates:
            require(not path.is_symlink() and path.resolve().is_relative_to(bank.resolve()), f"Backup rejects escaped path: {path}")
            paths.append(path)
    return paths


def write_archive(bank: Path, paths: Iterable[Path], archive: Path, **meta) -> dict:
    """Write and immediately re-verify an archive; return its manifest summary."""
    paths = list(paths)
    hashes = {p.relative_to(bank).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as handle:
        for path in paths:
            handle.write(path, path.relative_to(bank).as_posix())
        handle.writestr(MANIFEST_NAME, dumps({"version": 1, "files": hashes, **meta}))
    with zipfile.ZipFile(archive) as handle:
        require(handle.testzip() is None, "Backup CRC failed")
        for name, sha in hashes.items():
            require(hashlib.sha256(handle.read(name)).hexdigest() == sha, "Backup hash failed")
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    atomic_write(archive.with_suffix(".zip.sha256"), sha + "\n")
    return {"archive": str(archive), "sha256": sha, "files": len(hashes), "bytes": archive.stat().st_size,
            "uncompressed_bytes": sum(p.stat().st_size for p in paths)}


def create_backup(bank: Path, include_runs: bool = False) -> dict:
    """Snapshot the canonical bank under its lock into bank/backups/."""
    with open_bank(bank) as (manifest, _, data):
        archive = bank_file(bank, f"backups/backup-{utc_now()[:19].replace(':', '').replace('-', '')}-{new_id('b')[2:10]}.zip")
        result = write_archive(bank, bank_files(bank, include_runs), archive, kind="backup", created_at=utc_now(),
                               bank_schema_version=manifest["schema_version"], include_runs=include_runs)
        counts = {table: len(rows) for table, rows in data.items() if table != "_state"}
        return {**result, "include_runs": include_runs, "counts": counts,
                "hint": "Keep a copy outside this bank (another disk or cloud folder); backups/ is inside the bank."}


def _members(handle: zipfile.ZipFile) -> dict:
    require(MANIFEST_NAME in handle.namelist(), "Not an Interview Bank backup: manifest missing")
    manifest = json.loads(handle.read(MANIFEST_NAME))
    require(isinstance(manifest, dict) and manifest.get("version") == 1 and isinstance(manifest.get("files"), dict),
            "Unsupported backup manifest")
    require(set(handle.namelist()) == {MANIFEST_NAME, *manifest["files"]}, "Backup entry mismatch")
    for name in manifest["files"]:
        parts = Path(name).parts
        require(bool(parts) and not Path(name).is_absolute() and ".." not in parts and "\\" not in name, f"Unsafe backup path: {name}")
    return manifest


def _extract(archive: Path, target: Path) -> dict:
    with zipfile.ZipFile(archive) as handle:
        manifest = _members(handle)
        require(handle.testzip() is None, "Backup CRC failed")
        for name, sha in manifest["files"].items():
            raw = handle.read(name)
            require(hashlib.sha256(raw).hexdigest() == sha, f"Backup hash mismatch: {name}")
            path = target / name
            require(path.resolve().is_relative_to(target.resolve()), f"Unsafe backup path: {name}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    return manifest


def _sidecar(archive: Path) -> Optional[bool]:
    sidecar = archive.with_suffix(".zip.sha256")
    if not sidecar.is_file():
        return None
    return sidecar.read_text(encoding="utf-8").split()[0] == hashlib.sha256(archive.read_bytes()).hexdigest()


def verify_backup(archive: Path) -> dict:
    """Check entries, hashes and the sidecar, then load the unpacked copy as a bank."""
    archive = Path(archive).expanduser().resolve()
    require(archive.is_file(), f"Backup not found: {archive}")
    with tempfile.TemporaryDirectory(prefix="ibank-verify-") as temp:
        manifest = _extract(archive, Path(temp))
        sidecar = _sidecar(archive)
        require(sidecar is not False, "Backup archive does not match its .sha256 sidecar")
        loaded_manifest, _, data = load_bank(Path(temp))
    return {"archive": str(archive), "valid": True, "files": len(manifest["files"]), "sidecar_checked": sidecar is True,
            "created_at": manifest.get("created_at"), "kind": manifest.get("kind", "migration"),
            "bank_schema_version": loaded_manifest["schema_version"],
            "counts": {table: len(rows) for table, rows in data.items() if table != "_state"}}


def restore_into(archive: Path, destination: Path) -> dict:
    """Unpack into a sibling temporary directory, validate, then rename to a destination that must not exist."""
    archive = Path(archive).expanduser().resolve()
    require(archive.is_file(), f"Backup not found: {archive}")
    destination = guard_bank_path(destination)
    require(not destination.exists(), "Restore destination must not exist; choose a new directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.restore-", dir=destination.parent))
    try:
        manifest = _extract(archive, staging)
        require(_sidecar(archive) is not False, "Backup archive does not match its .sha256 sidecar")
        load_bank(staging)
        for directory in ("media", "runs", "cache", "exports"):
            (staging / directory).mkdir(exist_ok=True)
        os.replace(staging, destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return {"restored_bank": str(destination), "files": len(manifest["files"]), "original_bank_unchanged": True,
            "hint": "Point --bank (or INTERVIEW_BANK_HOME) at the restored directory only when you intend to switch."}
