"""config.language = en renders reports in English; Chinese stays the default and is unchanged."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support import CLI


def run(bank, *args, payload=None):
    argv = [sys.executable, "-B", str(CLI), *args, "--bank", str(bank), "--json"]
    if payload is not None:
        path = Path(bank).parent / "payload.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        argv += ["--input", str(path)]
    proc = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)["result"]


class Reports(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ibank-i18n-")
        self.bank = Path(self.temp.name) / "demo"
        run(self.bank, "demo")

    def tearDown(self):
        self.temp.cleanup()

    def report(self, name):
        result = run(self.bank, "export", "--output", name)
        return Path(result["answer_output"]).read_text(encoding="utf-8")

    def test_english_report(self):
        run(self.bank, "commit", "--run", run(self.bank, "config", payload={"language": "en"})["run_id"])
        report = self.report("en.md")
        self.assertTrue(report.startswith("# Interview question report"))
        for phrase in ("## Topics", "Answer (reference) · verified against sources", "Sources: ", "pending research and verification",
                       "Caching (3)", "<details><summary>Spoken version · Follow-up questions · Common mistakes</summary>"):
            self.assertIn(phrase, report)
        self.assertNotIn("答案（参考）", report)
        self.assertIn("Redis 为什么快？", report)  # questions are never translated

    def test_chinese_default(self):
        report = self.report("zh.md")
        self.assertTrue(report.startswith("# 面试题整理报告"))
        self.assertIn("答案（参考） · 已核验来源", report)


if __name__ == "__main__":
    unittest.main()
