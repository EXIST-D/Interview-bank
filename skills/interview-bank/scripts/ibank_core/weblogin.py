"""Optional login for the Web reader when it is hosted behind the user's own HTTPS proxy.

One account, stored as an scrypt hash in a root-owned file that only the person writes (tools/deploy/set-login.py).
A successful login sets a signed, HttpOnly, Secure, SameSite=Strict cookie. The signing key mixes the proxy token
with the password hash, so changing the password signs every device out. Failed attempts are limited per client
and in total. Standard library only.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
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


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, maxmem=64 * 1024 * 1024, dklen=32)


def make_login(username: str, password: str) -> dict:
    require(isinstance(username, str) and 1 <= len(username) <= 64 and username.isprintable() and ":" not in username,
            "Username: 1-64 printable characters without ':'")
    require(isinstance(password, str) and 10 <= len(password) <= 256, "Password: 10-256 characters")
    salt = secrets.token_bytes(16)
    return {"schema_version": 1, "username": username, "salt": salt.hex(), **SCRYPT,
            "hash": _derive(password, salt, **SCRYPT).hex()}


def load_login(path) -> dict:
    login = json.loads(Path(path).read_text(encoding="utf-8"))
    require(isinstance(login, dict) and login.get("schema_version") == 1, "Login file: unsupported format")
    require(isinstance(login.get("username"), str) and login["username"], "Login file: missing username")
    require(all(type(login.get(k)) is int for k in ("n", "r", "p")) and login["n"] >= 2 ** 14, "Login file: weak parameters")
    bytes.fromhex(login["salt"]), bytes.fromhex(login["hash"])
    return login


def verify(login: dict, username: str, password: str) -> bool:
    """Constant work whatever the username, so a wrong name and a wrong password look the same."""
    if not isinstance(username, str) or not isinstance(password, str) or len(password) > 256:
        return False
    derived = _derive(password, bytes.fromhex(login["salt"]), login["n"], login["r"], login["p"])
    return hmac.compare_digest(derived, bytes.fromhex(login["hash"])) & hmac.compare_digest(
        username.encode("utf-8"), login["username"].encode("utf-8"))


class Sessions:
    def __init__(self, token: str, login: dict):
        self.key = hashlib.sha256(f"{token}\n{login['hash']}".encode("utf-8")).digest()
        self.username = login["username"]

    def issue(self, now: float | None = None) -> str:
        expires = int((now or time.time()) + SESSION_SECONDS)
        payload = base64.urlsafe_b64encode(json.dumps([self.username, expires, secrets.token_hex(8)]).encode()).decode().rstrip("=")
        return f"{payload}.{hmac.new(self.key, payload.encode(), hashlib.sha256).hexdigest()}"

    def valid(self, value: str | None, now: float | None = None) -> bool:
        if not value or value.count(".") != 1:
            return False
        payload, signature = value.split(".")
        if not hmac.compare_digest(signature, hmac.new(self.key, payload.encode(), hashlib.sha256).hexdigest()):
            return False
        try:
            username, expires, _ = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        except (ValueError, TypeError):
            return False
        return username == self.username and type(expires) is int and expires > (now or time.time())


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
