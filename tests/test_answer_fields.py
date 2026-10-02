"""Answer depth fields are optional to write and visible when written."""
import json
import unittest
from pathlib import Path

from support import Bank, sourced_answer

ESSENTIAL = ("question_id", "status", "short_answer", "key_points", "sources", "evidence")


class AnswerFields(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.bank.add_questions("backend.cache", "Redis 为什么快？")

    def tearDown(self):
        self.bank.close()

    def commit_answer(self, answer):
        task = self.bank.result("research", "--limit", "1")
        answer = {**answer, "question_id": task["items"][0]["question"]["id"]}
        staged = self.bank.result("answer", payload={"schema_version": 1, "task_id": task["id"], "answers": [answer]})
        self.bank.result("commit", "--run", staged["run_id"])

    def export(self, *args):
        result = self.bank.result("export", "--output", "report.md", *args)
        return Path(result["answer_output"]).read_text(encoding="utf-8"), Path(result["question_output"]).read_text(encoding="utf-8")

    def test_essential_fields_are_enough(self):
        full = sourced_answer("placeholder", "2026-09-30")
        self.commit_answer({key: full[key] for key in ESSENTIAL})
        stored = self.bank.result("show", self.bank.result("search")["questions"][0]["id"])["question"]["answer"]
        self.assertEqual(stored["status"], "source_backed")
        self.assertEqual((stored["spoken_answer"], stored["follow_up_questions"], stored["code_example"]), ("", [], None))
        answers, _ = self.export()
        self.assertNotIn("<details>", answers)

    def test_written_depth_is_folded_into_the_answer_edition_only(self):
        self.commit_answer(sourced_answer("placeholder", "2026-09-30"))
        answers, questions = self.export()
        self.assertIn("<details><summary>口述版 · 常见追问 · 易错点</summary>", answers)
        self.assertIn("- Redis 6 的 I/O 线程是什么？", answers)
        self.assertNotIn("口述版", questions)
        inline, _ = self.export("--answer-extras", "inline")
        self.assertIn("**常见追问**", inline)
        self.assertNotIn("<details>", inline)
        none, _ = self.export("--answer-extras", "none")
        self.assertNotIn("口述版", none)

    def test_optional_fields_keep_their_types(self):
        task = self.bank.result("research", "--limit", "1")
        bad = {**sourced_answer(task["items"][0]["question"]["id"], "2026-09-30"), "follow_up_questions": "not a list"}
        proc = self.bank.cli("answer", payload={"schema_version": 1, "task_id": task["id"], "answers": [bad]}, check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("follow_up_questions", json.loads(proc.stderr)["error"])


if __name__ == "__main__":
    unittest.main()
