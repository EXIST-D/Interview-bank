"""demo builds a sample bank in a new directory and never touches an existing one."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support import CLI


def run(*args):
    proc = subprocess.run([sys.executable, "-B", str(CLI), *args, "--json"], capture_output=True, text=True, encoding="utf-8")
    return proc.returncode, json.loads(proc.stdout or proc.stderr)


class Demo(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ibank-demo-test-")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_sample_bank_is_ready_to_read(self):
        bank = self.root / "demo"
        code, built = run("demo", "--bank", str(bank))
        self.assertEqual((code, built["result"]["questions"], built["result"]["answered"]), (0, 20, 8))
        _, found = run("search", "--answer-status", "source_backed", "--bank", str(bank))
        self.assertEqual(found["result"]["total"], 8)
        _, exported = run("export", "--output", "demo.md", "--bank", str(bank))
        report = Path(exported["result"]["answer_output"]).read_text(encoding="utf-8")
        self.assertIn("<details><summary>口述版 · 常见追问 · 易错点</summary>", report)
        self.assertIn("待检索与核验", report)
        _, valid = run("validate", "--bank", str(bank))
        self.assertTrue(valid["result"]["valid"])

    def test_v2_and_existing_directories(self):
        code, built = run("demo", "--bank", str(self.root / "v2"), "--v2")
        self.assertEqual((code, built["result"]["schema_version"]), (0, 2))
        occupied = self.root / "occupied"
        occupied.mkdir()
        (occupied / "notes.txt").write_text("keep me", encoding="utf-8")
        code, error = run("demo", "--bank", str(occupied))
        self.assertEqual(code, 2)
        self.assertIn("new or empty directory", error["error"])
        self.assertEqual((occupied / "notes.txt").read_text(encoding="utf-8"), "keep me")

    def test_answers_respect_the_reader_length(self):
        from ibank_core.demo import ANSWERS
        for text, answer in ANSWERS.items():
            self.assertTrue(100 <= len(answer["short_answer"]) <= 250, text)
            self.assertEqual(len(answer["sources"]), 1)


if __name__ == "__main__":
    unittest.main()
