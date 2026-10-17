"""The person's own answers: independent of reference answers, kept across merges, exported and served safely."""
import json
import unittest

import zipfile

from support import Bank

from ibank_core import my_answers
from ibank_core.errors import BankError
from ibank_core.export import export_bank
from ibank_core.storage import open_bank
from ibank_core.web import WebApp


class MyAnswers(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.bank.add_questions('database', '如何防止缓存穿透？', 'Redis 为什么这么快？')
        with open_bank(self.bank.path, shared=True) as (_, _c, data):
            active = [q for q in data["questions"] if q["status"] == "active"]
        self.qid, self.other = active[0]["id"], active[1]["id"]

    def tearDown(self):
        self.bank.close()

    def test_save_edit_clear_and_history(self):
        first = my_answers.save(self.bank.path, self.qid, "  我会先讲原理\n再讲取舍  ", "")
        self.assertEqual(first["my_answer"]["text"], "我会先讲原理\n再讲取舍")
        stamp = first["my_answer"]["updated_at"]
        with self.assertRaises(BankError):
            my_answers.save(self.bank.path, self.qid, "另一个设备的旧页面", "")
        second = my_answers.save(self.bank.path, self.qid, "第二版", stamp)
        cleared = my_answers.save(self.bank.path, self.qid, "", second["my_answer"]["updated_at"])
        self.assertIsNone(cleared["my_answer"])
        stored = my_answers.load(self.bank.path)[self.qid]
        self.assertEqual([h["text"] for h in stored["history"]], ["第二版", "我会先讲原理\n再讲取舍"])
        self.assertEqual(my_answers.save(self.bank.path, self.qid, "重新写", "")["my_answer"]["text"], "重新写")

    def test_reference_answers_and_canonical_data_stay_untouched(self):
        before = {name: (self.bank.path / "data" / name).read_bytes() for name in ("answers.jsonl", "questions.jsonl")}
        my_answers.save(self.bank.path, self.qid, "我的思路", "")
        after = {name: (self.bank.path / "data" / name).read_bytes() for name in before}
        self.assertEqual(before, after)
        self.assertTrue((self.bank.path / "personal" / "my-answers.json").is_file())

    def test_answer_written_before_a_merge_shows_on_the_surviving_question(self):
        my_answers.save(self.bank.path, self.other, "合并前写的", "")
        with open_bank(self.bank.path, shared=True) as (_, _c, data):
            for q in data["questions"]:
                if q["id"] == self.other:
                    q["merged_into"], q["status"] = self.qid, "merged"
            shown = my_answers.for_question(my_answers.load(self.bank.path), data, self.qid)
        self.assertEqual(shown["text"], "合并前写的")

    def test_web_reads_and_refuses_writes_unless_allowed(self):
        my_answers.save(self.bank.path, self.qid, "只给自己看", "")
        read_only = WebApp(self.bank.path, read_only=True)
        self.assertEqual(read_only.question(self.qid)["my_answer"]["text"], "只给自己看")
        library = read_only.library({"limit": "100"})
        self.assertFalse(library["can_write_answer"])
        self.assertTrue(next(q for q in library["questions"] if q["id"] == self.qid)["has_my_answer"])
        payload = {"question_id": self.qid, "text": "改一下", "expected_updated_at": read_only.question(self.qid)["my_answer"]["updated_at"]}
        with self.assertRaises(BankError):
            read_only.my_answer(payload)
        hosted = WebApp(self.bank.path, read_only=True, allow_my_answers=True)
        self.assertTrue(hosted.library({"limit": "1"})["can_write_answer"])
        self.assertEqual(hosted.my_answer(payload)["my_answer"]["text"], "改一下")
        with self.assertRaises(BankError):
            hosted.my_answer({"question_id": self.qid, "text": "x" * (my_answers.MAX_TEXT + 1), "expected_updated_at": ""})
        with self.assertRaises(BankError):
            hosted.my_answer({"question_id": self.qid, "text": "多了字段", "expected_updated_at": "", "rating": "good"})

    def test_answers_edition_quotes_my_answer_and_question_edition_omits_it(self):
        my_answers.save(self.bank.path, self.qid, "# 不应变成标题\n- 第一点", "")
        export_bank(self.bank.path, "report.md")
        answers = (self.bank.path / "exports" / "report.md").read_text(encoding="utf-8")
        questions = (self.bank.path / "exports" / "report（题目版）.md").read_text(encoding="utf-8")
        self.assertIn("> # 不应变成标题\n> - 第一点", answers)
        self.assertIn("我的答案", answers)
        self.assertNotIn("我的答案", questions)
        details = json.loads((self.bank.path / "exports" / "report.md.details.json").read_text(encoding="utf-8"))
        self.assertEqual(details["my_answers"], {self.qid: "# 不应变成标题\n- 第一点"})

    def test_show_and_backup_include_it(self):
        my_answers.save(self.bank.path, self.qid, "备份里也要有", "")
        self.assertEqual(self.bank.result("show", self.qid)["my_answer"]["text"], "备份里也要有")
        archive = self.bank.result("backup", "create")["archive"]
        with zipfile.ZipFile(archive) as handle:
            self.assertIn("personal/my-answers.json", handle.namelist())


if __name__ == "__main__":
    unittest.main()
