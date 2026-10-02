"""End-to-end smoke test of the default M1–M5 path through the real CLI, plus read-only install checks."""
import hashlib
import json
import unittest
from pathlib import Path

from support import SKILL, Bank


def skill_fingerprint():
    return {str(p.relative_to(SKILL)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(SKILL.rglob("*")) if p.is_file()}


class DefaultWorkflow(unittest.TestCase):
    def test_intake_merge_answer_export(self):
        before = skill_fingerprint()
        bank = Bank()
        try:
            bank.add_questions("backend.cache", "Redis 为什么快？", "Redis 高性能的原因是什么？")
            task = bank.result("dedupe-candidates")
            items = {item["incoming"]["canonical"]: item for item in task["items"]}
            target = next(m["question"]["id"] for m in items["Redis 高性能的原因是什么？"]["matches"]
                          if m["question"]["canonical"] == "Redis 为什么快？")
            decisions = [{"question_id": item["incoming"]["id"], "action": "KEEP_DISTINCT", "confidence": 0.95, "reason": "无候选"}
                         for name, item in items.items() if name != "Redis 高性能的原因是什么？"]
            decisions.append({"question_id": items["Redis 高性能的原因是什么？"]["incoming"]["id"], "action": "MERGE_VARIANT",
                              "target_id": target, "confidence": 0.95, "reason": "同一考点"})
            bank.stage_commit("dedupe", payload={"schema_version": 1, "task_id": task["id"], "decisions": decisions})
            staged = bank.answer_all()
            self.assertEqual(staged.returncode, 0, staged.stderr)
            bank.result("commit", "--run", json.loads(staged.stdout)["result"]["run_id"])

            exported = bank.result("export", "--output", "report.md")
            answers = Path(exported["answer_output"]).read_text(encoding="utf-8")
            questions = Path(exported["question_output"]).read_text(encoding="utf-8")
            self.assertEqual(exported["report_questions"], 1)
            self.assertIn("出现 2 次", answers)
            self.assertIn("已核验来源", answers)
            self.assertNotIn("答案（参考）", questions)
            self.assertTrue(Path(exported["details_output"]).is_file())
            self.assertEqual(bank.result("doctor")["pending_runs"], [])
        finally:
            bank.close()
        self.assertEqual(skill_fingerprint(), before, "running the CLI must not modify the installed skill")


if __name__ == "__main__":
    unittest.main()
