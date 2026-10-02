"""Regressions for defects found in the v1.10.0 review; each class names the fix (B1–B8) it guards."""
import contextlib
import io
import json
import runpy
import sys
import unittest
from datetime import datetime, timedelta, timezone

from support import CLI, Bank

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


if __name__ == "__main__":
    unittest.main()
