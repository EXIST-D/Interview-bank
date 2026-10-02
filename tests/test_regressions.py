"""Regressions for defects found in the v1.10.0 review; each class names the fix (B1–B8) it guards."""
import contextlib
import io
import json
import runpy
import sys
import threading
import time
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

from support import CLI, SKILL, Bank

from ibank_core import web
from ibank_core.doctor import doctor
from ibank_core.errors import LockConflict
from ibank_core.locking import bank_lock
from ibank_core.timestamps import parse_timestamp


class Timestamps(unittest.TestCase):
    """B7: agents and browsers write a trailing Z; Python 3.10 rejected it."""

    def test_trailing_z_parses_on_every_supported_python(self):
        self.assertEqual(parse_timestamp("2026-09-30T10:00:00Z"), datetime(2026, 9, 30, 10, tzinfo=timezone.utc))
        self.assertEqual(parse_timestamp("2026-09-30T10:00:00.123Z").microsecond, 123000)

    def test_workflow_deadline_with_z_is_usable(self):
        bank = Bank()
        try:
            bank.add_questions("backend.cache", "Redis 为什么快？")
            bank.cli("migrate", "apply")
            deadline = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            created = bank.result("workflow", "create", payload={"name": "z", "expression": {}, "limits": {"deadline": deadline}})
            bank.result("commit", "--run", created["run_id"])
            workflow_id = created["summary"]["workflow_id"]
            self.assertIsNotNone(bank.result("workflow", "next", "--id", workflow_id)["task"])
        finally:
            bank.close()


class PythonVersionGuard(unittest.TestCase):
    """B7: the CLI documented Python 3.10+ but never checked it."""

    def test_cli_refuses_python_older_than_3_10(self):
        real, stderr = sys.version_info, io.StringIO()
        sys.version_info = (3, 9, 6, "final", 0)
        argv, sys.argv = sys.argv, [str(CLI), "doctor", "--json"]
        try:
            with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
                runpy.run_path(str(CLI), run_name="__main__")
        finally:
            sys.version_info, sys.argv = real, argv
        self.assertEqual(raised.exception.code, 1)
        self.assertIn("requires Python 3.10+", json.loads(stderr.getvalue())["error"])


class Locking(unittest.TestCase):
    """B1/B2: reads queued behind an exclusive non-blocking lock failed; Web saves raced their commit."""

    def setUp(self):
        self.bank = Bank()
        self.bank.add_questions("backend.cache", "Redis 为什么快？")
        self.bank.cli("migrate", "apply")
        self.app = web.WebApp(self.bank.path)

    def tearDown(self):
        self.bank.close()

    def test_concurrent_reads_queue_instead_of_failing(self):
        outcomes, barrier = [], threading.Barrier(8)

        def read():
            barrier.wait()
            try:
                self.app.library({})
                outcomes.append("ok")
            except LockConflict:
                outcomes.append("conflict")

        threads = [threading.Thread(target=read) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(outcomes, ["ok"] * 8)

    def test_lock_still_times_out_when_held_too_long(self):
        held = threading.Event()

        def hold():
            with bank_lock(self.bank.path):
                held.set()
                time.sleep(0.6)

        thread = threading.Thread(target=hold)
        thread.start()
        held.wait(5)
        with self.assertRaises(LockConflict):
            with bank_lock(self.bank.path, timeout=0.1):
                pass
        thread.join()

    def test_web_practice_saves_while_readers_are_active(self):
        card = self.app.library({})["questions"][0]
        stop, errors = threading.Event(), []

        def keep_reading():
            # Browser-like traffic: repeated reads with a short pause, not a tight loop.
            while not stop.is_set():
                try:
                    self.app.library({})
                except Exception as exc:  # any failure here is a regression
                    errors.append(exc)
                time.sleep(0.02)

        readers = [threading.Thread(target=keep_reading) for _ in range(3)]
        for reader in readers:
            reader.start()
        try:
            for rating in ("again", "hard", "good"):
                payload = {"question_id": card["id"], "revision": card["revision"], "rating": rating,
                           "request_id": str(uuid.uuid4()), "note": "", "timezone": "Asia/Shanghai"}
                self.assertTrue(self.app.record(payload)["saved"])
        finally:
            stop.set()
            for reader in readers:
                reader.join()
        self.assertEqual(errors, [])
        self.assertEqual(doctor(self.bank.path)["pending_runs"], [])
        history = self.bank.result("study", "history")["events"]
        self.assertEqual([event["rating"] for event in history], ["again", "hard", "good"])


class PracticeLimitOptions(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside, self.options = False, []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "select":
            self.inside = attrs.get("id") == "practice-limit"
        elif tag == "option" and self.inside:
            self.options.append((attrs.get("value"), "selected" in attrs))

    def handle_endtag(self, tag):
        if tag == "select":
            self.inside = False


class WebPracticeMarkup(unittest.TestCase):
    """B3: a malformed </option> tag dropped the default 10-question option."""

    def test_practice_limit_offers_5_10_20_with_10_selected(self):
        parser = PracticeLimitOptions()
        parser.feed((SKILL / "assets" / "web" / "index.html").read_text(encoding="utf-8"))
        self.assertEqual(parser.options, [("5", False), ("10", True), ("20", False)])


if __name__ == "__main__":
    unittest.main()
