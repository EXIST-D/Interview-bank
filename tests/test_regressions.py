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
from unittest import mock

from support import CLI, SKILL, Bank, sourced_answer

from ibank_core import dates, web
from ibank_core.answers import stage_answers
from ibank_core.catalog import CATALOG
from ibank_core.dates import latest_calendar_date
from ibank_core.doctor import doctor
from ibank_core.errors import LockConflict, ValidationError
from ibank_core.export import report_group
from ibank_core.locking import bank_lock
from ibank_core.privacy import contact_findings
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


class ReportGrouping(unittest.TestCase):
    """B4: ten of eighteen top-level domains fell into a catch-all 其他知识题 section."""

    def test_every_builtin_top_level_domain_gets_its_catalog_label(self):
        labels = {entry["id"]: entry["label"] for entry in CATALOG["domains"]}
        tops = sorted({entry["id"].split(".")[0] for entry in CATALOG["domains"]})
        for top in tops:
            with self.subTest(domain=top):
                self.assertNotEqual(report_group({"domains": [top]}), "其他知识题")
        self.assertEqual(report_group({"domains": ["mobile"]}), labels["mobile"])
        self.assertEqual(report_group({"domains": ["security"]}), labels["security"])

    def test_first_domain_decides_the_group(self):
        self.assertEqual(report_group({"domains": ["mobile", "backend.cache"]}), "移动技术")
        self.assertEqual(report_group({"domains": ["backend.cache", "mobile"]}), "缓存")

    def test_unknown_extension_domains_still_fall_back(self):
        self.assertEqual(report_group({"domains": ["custom.topic"]}), "其他知识题")
        self.assertEqual(report_group({"domains": []}), "其他知识题")

    def test_exported_report_has_no_catch_all_section_for_builtin_domains(self):
        bank = Bank()
        try:
            bank.add_questions("mobile", "Handler 消息机制的原理是什么？")
            bank.add_questions("security", "XSS 和 CSRF 有什么区别？")
            output = bank.result("export", "--output", "report.md")["answer_output"]
            with open(output, encoding="utf-8") as handle:
                headings = [line for line in handle if line.startswith("## ")]
            self.assertTrue(any("移动技术" in line for line in headings))
            self.assertTrue(any("信息安全" in line for line in headings))
            self.assertFalse(any("其他知识题" in line for line in headings))
        finally:
            bank.close()


class PrivacyGuard(unittest.TestCase):
    """B5: stage --text skipped the guard while other paths rejected technical examples."""

    def test_technical_examples_are_not_contact_details(self):
        for text in ("微信：朋友圈的 Feed 流如何设计？", "如何用正则校验形如 test@example.com 的邮箱？",
                     "npm install react@18.2.0 有什么影响？", "@Autowired 与 @Resource 的区别？"):
            with self.subTest(text=text):
                self.assertEqual(contact_findings(text), [])

    def test_real_contact_details_are_found(self):
        for text in ("联系我 微信：abc123", "手机 13800138000", "邮箱 zhangsan@qq.com的", "QQ群：123456789",
                     "微信号：　wxid_abc123"):
            with self.subTest(text=text):
                self.assertTrue(contact_findings(text))

    def test_text_stage_applies_the_same_guard(self):
        bank = Bank()
        try:
            source = bank.root / "pii.txt"
            source.write_text("联系我 微信：abc123 或 13800138000\n", encoding="utf-8")
            proc = bank.cli("stage", "--text", str(source), check=False)
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn("personal contact information", proc.stderr)
        finally:
            bank.close()


class BeijingJustAfterMidnight(datetime):
    """Frozen clock: 2026-09-30 16:30 UTC is already 2026-10-01 00:30 in Beijing."""
    @classmethod
    def now(cls, tz=None):
        instant = datetime(2026, 9, 30, 16, 30, tzinfo=timezone.utc)
        return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)


class CitationDates(unittest.TestCase):
    """B6: accessed_at was compared with the UTC date, rejecting UTC+8 local dates after midnight."""

    def setUp(self):
        self.bank = Bank()
        self.bank.add_questions("backend.cache", "Redis 为什么快？")
        self.task = self.bank.result("research", "--limit", "1")

    def tearDown(self):
        self.bank.close()

    def stage(self, accessed_at):
        response = {"schema_version": 1, "task_id": self.task["id"],
                    "answers": [sourced_answer(self.task["items"][0]["question"]["id"], accessed_at)]}
        with mock.patch.object(dates, "datetime", BeijingJustAfterMidnight):
            return stage_answers(self.bank.path, response)

    def test_beijing_local_date_after_midnight_is_accepted(self):
        self.assertEqual(self.stage("2026-10-01")["status"], "staged")

    def test_truly_future_dates_are_still_rejected(self):
        with self.assertRaisesRegex(ValidationError, "future"):
            self.stage("2026-10-02")

    def test_latest_calendar_date_is_never_behind_any_local_date(self):
        for hours in range(-12, 15):
            local = datetime.now(timezone(timedelta(hours=hours))).date()
            self.assertGreaterEqual(latest_calendar_date(), local)


if __name__ == "__main__":
    unittest.main()
