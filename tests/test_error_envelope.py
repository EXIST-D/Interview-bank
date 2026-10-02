"""Errors carry a stable error_type and a next-step hint, so agents do not parse English prose."""
import json
import os
import subprocess
import sys
import unittest

from support import CLI, Bank
from ibank_core.errors import LockConflict, ReviewRequired, ValidationError, describe_error
from ibank_core.locking import bank_lock


class ErrorEnvelope(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()

    def tearDown(self):
        self.bank.close()

    def error(self, *args, env=None, payload=None):
        proc = self.bank.cli(*args, check=False, env=env, payload=payload)
        self.assertNotEqual(proc.returncode, 0)
        return proc.returncode, json.loads(proc.stderr)

    def test_lock_conflict(self):
        with bank_lock(self.bank.path):
            code, error = self.error("stats", env={**os.environ, "INTERVIEW_BANK_LOCK_TIMEOUT": "0.2"})
        self.assertEqual((code, error["error_type"]), (4, "LockConflict"))
        self.assertIn("never delete .bank.lock", error["hint"])

    def test_stale_stage(self):
        source = self.bank.root / "q.txt"
        source.write_text("Redis 为什么快？\n", encoding="utf-8")
        self.bank.add_questions("backend.cache", "Redis 持久化有哪些方式？")
        task = self.bank.result("research", "--limit", "1")
        self.bank.add_questions("backend.cache", "缓存穿透是什么？")
        code, error = self.error("answer", payload={"schema_version": 1, "task_id": task["id"], "answers": []})
        self.assertEqual((code, error["error_type"]), (2, "StaleInput"))

    def test_invalid_input_and_missing_bank(self):
        code, error = self.error("show", "q_missing")
        self.assertEqual((code, error["error_type"]), (2, "InvalidInput"))
        proc = subprocess.run([sys.executable, "-B", str(CLI), "doctor", "--bank", str(self.bank.root / "nowhere"), "--json"],
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual((proc.returncode, json.loads(proc.stderr)["error_type"]), (3, "BankUnavailable"))

    def test_classification_table(self):
        self.assertEqual(describe_error(ReviewRequired("x"))[0], "ReviewRequired")
        self.assertEqual(describe_error(LockConflict("x"))[0], "LockConflict")
        self.assertEqual(describe_error(ValidationError("Run run_x was compacted by gc"))[0], "Compacted")
        self.assertEqual(describe_error(ValidationError("Possible personal contact information: …"))[0], "PrivacyRejected")
        self.assertEqual(describe_error(ValidationError("This feature requires explicit migrate apply to format V2"))[0], "NeedsMigration")
        self.assertEqual(describe_error(OSError("disk"))[0], "OSError")


if __name__ == "__main__":
    unittest.main()
