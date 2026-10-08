"""Optional login for the Web reader when it is hosted behind the user's own HTTPS proxy.

Accounts live in a root-owned file that only the server owner writes (tools/deploy/set-login.py): one scrypt hash
per account and the name of that account's bank. A successful login sets a signed, HttpOnly, Secure,
SameSite=Strict cookie naming the account. Each account's signing key mixes the proxy token with that account's
password hash, so changing a password signs only that account out everywhere. Failed attempts are limited per
client and in total. Standard library only.

File format 2: {"schema_version": 2, "users": {"<name>": {"salt", "n", "r", "p", "hash", "bank"}}}.
Format 1 (one account, the 1.15 single-bank login) still loads: its bank is the account name.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from collections import deque
from pathlib import Path

from .schema import require

SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1}
SESSION_SECONDS = 14 * 24 * 3600
COOKIE = "ibank_session"
WINDOW = 15 * 60
PER_CLIENT = 5
OVERALL = 30
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
DUMMY = {"salt": "00" * 16, **SCRYPT, "hash": "00" * 32}


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, maxmem=64 * 1024 * 1024, dklen=32)


def make_user(username: str, password: str, bank: str | None = None) -> dict:
    """One account record. Names are also directory names, so they are plain ASCII."""
    require(isinstance(username, str) and NAME.fullmatch(username), "Username: letters, digits, '.', '_' or '-', at most 64")
    require(isinstance(password, str) and 10 <= len(password) <= 256, "Password: 10-256 characters")
    bank = bank or username
    require(NAME.fullmatch(bank) is not None, "Bank name: letters, digits, '.', '_' or '-', at most 64")
    salt = secrets.token_bytes(16)
    return {"salt": salt.hex(), **SCRYPT, "hash": _derive(password, salt, **SCRYPT).hex(), "bank": bank}


def make_login(username: str, password: str, bank: str | None = None) -> dict:
    return {"schema_version": 2, "users": {username: make_user(username, password, bank)}}


def load_login(path) -> dict:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    require(isinstance(raw, dict) and raw.get("schema_version") in (1, 2), "Login file: unsupported format")
    if raw["schema_version"] == 1:
        require(isinstance(raw.get("username"), str) and raw["username"], "Login file: missing username")
        users = {raw["username"]: {k: raw[k] for k in ("salt", "n", "r", "p", "hash")} | {"bank": raw["username"]}}
    else:
        users = raw.get("users")
        require(isinstance(users, dict) and users, "Login file: no accounts")
    for name, user in users.items():
        require(isinstance(user, dict) and all(type(user.get(k)) is int for k in ("n", "r", "p")) and user["n"] >= 2 ** 14,
                f"Login file: weak or missing parameters for {name}")
        require(isinstance(user.get("bank"), str) and NAME.fullmatch(user["bank"]), f"Login file: invalid bank for {name}")
        bytes.fromhex(user["salt"]), bytes.fromhex(user["hash"])
    return {"schema_version": 2, "users": users}


def verify(login: dict, username: str, password: str) -> str | None:
    """The account name when the password matches. Unknown names cost the same work as known ones."""
    if not isinstance(username, str) or not isinstance(password, str) or len(password) > 256:
        return None
    user = login["users"].get(username)
    record = user or DUMMY
    derived = _derive(password, bytes.fromhex(record["salt"]), record["n"], record["r"], record["p"])
    return username if hmac.compare_digest(derived, bytes.fromhex(record["hash"])) and user else None


class Sessions:
    def __init__(self, token: str, login: dict):
        self.keys = {name: hashlib.sha256(f"{token}\n{user['hash']}".encode("utf-8")).digest()
                     for name, user in login["users"].items()}

    def issue(self, username: str, now: float | None = None) -> str:
        expires = int((now or time.time()) + SESSION_SECONDS)
        payload = base64.urlsafe_b64encode(json.dumps([username, expires, secrets.token_hex(8)]).encode()).decode().rstrip("=")
        return f"{payload}.{hmac.new(self.keys[username], payload.encode(), hashlib.sha256).hexdigest()}"

    def user(self, value: str | None, now: float | None = None) -> str | None:
        """The signed-in account, or None for a missing, expired, forged or revoked session."""
        if not value or value.count(".") != 1:
            return None
        payload, signature = value.split(".")
        try:
            username, expires, _ = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        except (ValueError, TypeError):
            return None
        key = self.keys.get(username) if isinstance(username, str) else None
        if key is None or not hmac.compare_digest(signature, hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()):
            return None
        return username if type(expires) is int and expires > (now or time.time()) else None

    def valid(self, value: str | None, now: float | None = None) -> bool:
        return self.user(value, now) is not None


class Attempts:
    """Failed logins within the last 15 minutes: five per client, thirty in total."""

    def __init__(self):
        self.lock, self.failures = threading.Lock(), {}

    def _recent(self, key, now):
        queue = self.failures.setdefault(key, deque())
        while queue and queue[0] <= now - WINDOW:
            queue.popleft()
        return queue

    def blocked(self, client: str, now: float | None = None) -> bool:
        now = now or time.time()
        with self.lock:
            return len(self._recent(client, now)) >= PER_CLIENT or len(self._recent("*", now)) >= OVERALL

    def failed(self, client: str, now: float | None = None):
        now = now or time.time()
        with self.lock:
            self._recent(client, now).append(now)
            self._recent("*", now).append(now)

    def succeeded(self, client: str):
        with self.lock:
            self.failures.pop(client, None)
