"""answer-recheck rebinds an answer to reworded wording without pretending to new evidence."""
import json
import unittest
from datetime import date, timedelta

from support import Bank, sourced_answer


class AnswerRecheck(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.bank.add_questions("backend.cache", "Redis 为什么快？")
        self.bank.result("migrate", "apply")
        self.qid = self.bank.result("search")["questions"][0]["id"]

    def tearDown(self):
        self.bank.close()

    def answer(self, accessed_at=None):
        accessed_at = accessed_at or (date.today() - timedelta(days=3)).isoformat()
        task = self.bank.result("research", "--limit", "1")
        staged = self.bank.result("answer", payload={"schema_version": 1, "task_id": task["id"],
                                                     "answers": [sourced_answer(self.qid, accessed_at)]})
        self.bank.result("commit", "--run", staged["run_id"])

    def reword(self, text="Redis 为什么这么快？"):
        self.bank.stage_commit("curate", payload={"schema_version": 1, "changes": [
            {"table": "questions", "id": self.qid, "set": {"canonical": text}, "reason": "措辞统一"}]})

    def recheck(self, **overrides):
        item = {"question_id": self.qid, "reason": "只调整了措辞，原答案仍覆盖", "checks": ["逐条对照 key_points 0"],
                "covers_current_wording": True, **overrides}
        return self.bank.cli("answer-recheck", payload={"schema_version": 1, "rechecks": [item]}, check=False)

    def current(self):
        return self.bank.result("search", "--detail")["questions"][0]

    def test_rewording_is_rechecked_without_refreshing_evidence(self):
        self.answer()
        before = self.current()["answer"]
        self.reword()
        stale = self.current()
        self.assertEqual((stale["answer_status"], stale["answer_stale_reason"]), ("stale", "wording_changed"))
        staged = json.loads(self.recheck().stdout)["result"]
        self.bank.result("commit", "--run", staged["run_id"])
        after = self.current()
        self.assertEqual((after["answer_status"], after["answer_stale_reason"]), ("source_backed", None))
        self.assertEqual(after["answer"]["version"], before["version"] + 1)
        self.assertEqual(after["answer"]["verified_at"], before["verified_at"])
        self.assertEqual(after["answer"]["sources"], before["sources"])
        self.assertIn("逐条对照 key_points 0", after["answer"]["checks"])
        audit = json.loads((self.bank.path / "runs" / staged["run_id"] / "run.json").read_text(encoding="utf-8"))["audit"]
        self.assertEqual((audit[0]["action"], audit[0]["actor"]), ("ANSWER_RECHECK", "agent"))

    def test_refusals(self):
        self.answer()
        current = self.recheck()
        self.assertIn("already matches", json.loads(current.stderr)["error"])
        self.reword()
        self.assertIn("covers_current_wording", json.loads(self.recheck(covers_current_wording=False).stderr)["error"])
        self.assertIn("checks", json.loads(self.recheck(checks=[]).stderr)["error"])

    def test_old_evidence_needs_research(self):
        self.answer(accessed_at=(date.today() - timedelta(days=400)).isoformat())
        self.reword()
        self.assertEqual(self.current()["answer_stale_reason"], "evidence_age")
        self.assertIn("research it again", json.loads(self.recheck().stderr)["error"])

    def test_v1_bank_is_refused(self):
        plain = Bank()
        try:
            plain.add_questions("backend.cache", "Redis 为什么快？")
            proc = plain.cli("answer-recheck", payload={"schema_version": 1, "rechecks": [{"question_id": "q_x"}]}, check=False)
            self.assertIn("migrate", json.loads(proc.stderr)["error"])
        finally:
            plain.close()


if __name__ == "__main__":
    unittest.main()
