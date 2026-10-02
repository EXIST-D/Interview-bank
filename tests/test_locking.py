"""Readers share the bank lock, writers exclude everyone, and a reader replays a crashed writer's journal."""
import json
import os
import subprocess
import sys
import textwrap
import unittest

from support import SKILL, Bank
from ibank_core import storage
from ibank_core.errors import LockConflict
from ibank_core.locking import bank_lock


class SharedLocks(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.path = self.bank.path

    def tearDown(self):
        self.bank.close()

    def test_readers_share_and_writers_wait(self):
        with bank_lock(self.path, shared=True):
            with bank_lock(self.path, timeout=0.5, shared=True):
                pass  # a second reader gets in at once
            with self.assertRaises(LockConflict):
                with bank_lock(self.path, timeout=0.2):
                    pass
        with bank_lock(self.path):
            with self.assertRaises(LockConflict):
                with bank_lock(self.path, timeout=0.2, shared=True):
                    pass
        with bank_lock(self.path, timeout=0.2):
            pass

    def test_other_process_reader_blocks_a_writer(self):
        script = textwrap.dedent(f"""
            import sys, time
            sys.path.insert(0, {str(SKILL / "scripts")!r})
            from pathlib import Path
            from ibank_core.locking import bank_lock
            with bank_lock(Path({str(self.path)!r}), shared=True):
                print("held", flush=True)
                sys.stdin.readline()
        """)
        child = subprocess.Popen([sys.executable, "-B", "-c", script], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), "held")
            with bank_lock(self.path, timeout=0.5, shared=True):
                pass
            proc = self.bank.cli("stage", "--text", str(self.question_file()), check=False,
                                 env={**os.environ, "INTERVIEW_BANK_LOCK_TIMEOUT": "0.3"})
            self.assertEqual(proc.returncode, 4, proc.stderr)
            self.assertEqual(json.loads(self.bank.cli("search").stdout)["result"]["total"], 0)
        finally:
            child.communicate("\n", timeout=10)

    def question_file(self):
        path = self.bank.root / "q.txt"
        path.write_text("Redis 为什么快？\n", encoding="utf-8")
        return path

    def test_reader_replays_a_crashed_writer_journal(self):
        manifest = storage.read_json(self.path / "manifest.json")
        manifest["last_updated_at"] = "2026-10-02T00:00:00+00:00"
        journal = {"schema_version": 1, "files": {"manifest.json": storage.dumps(manifest) + "\n"}}
        (self.path / ".transaction.json").write_text(json.dumps(journal), encoding="utf-8")
        with storage.open_bank(self.path, shared=True) as (loaded, _, _):
            self.assertEqual(loaded["last_updated_at"], "2026-10-02T00:00:00+00:00")
        self.assertFalse((self.path / ".transaction.json").exists())


if __name__ == "__main__":
    unittest.main()
