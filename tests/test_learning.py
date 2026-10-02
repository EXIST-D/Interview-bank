"""Learning loop: Anki export, the optional FSRS scheduler, problem links and a study calendar."""
import unittest
from pathlib import Path

from support import Bank, sourced_answer
from ibank_core.scheduler import fsrs_step, retrievability, simple_interval


class Scheduler(unittest.TestCase):
    def test_simple_schedule_is_unchanged(self):
        self.assertEqual([simple_interval(r, 0) for r in ("again", "hard", "good", "easy")], [1, 1, 3, 7])
        self.assertEqual(simple_interval("good", 10), 20)

    def test_fsrs_first_review_uses_default_stability(self):
        days, state = fsrs_step("good", None, 0)
        self.assertEqual(days, 4)  # w[2] = 3.7145 days at 90 % retention
        self.assertAlmostEqual(state["stability"], 3.7145)
        self.assertAlmostEqual(retrievability(state["stability"], state["stability"]), 0.9)

    def test_fsrs_grows_on_success_and_shrinks_on_lapse(self):
        _, state = fsrs_step("good", None, 0)
        longer, after_good = fsrs_step("good", state, 4)
        shorter, after_again = fsrs_step("again", state, 4)
        self.assertGreater(after_good["stability"], state["stability"])
        self.assertLess(after_again["stability"], state["stability"])
        self.assertGreater(after_again["difficulty"], state["difficulty"])
        self.assertGreater(longer, shorter)
        self.assertGreater(fsrs_step("good", state, 4, desired_retention=0.8)[0], longer)


class LearningLoop(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.bank.add_questions("backend.cache", "Redis 为什么快？", "实现一个 LRU 缓存")
        questions = {q["canonical"]: q["id"] for q in self.bank.result("search")["questions"]}
        self.redis, self.lru = questions["Redis 为什么快？"], questions["实现一个 LRU 缓存"]
        task = self.bank.result("research", "--question", self.redis)
        self.bank.result("answer", "--commit", payload={"schema_version": 1, "task_id": task["id"],
                                                        "answers": [sourced_answer(self.redis, "2026-09-30")]})

    def tearDown(self):
        self.bank.close()

    def test_anki_export(self):
        result = self.bank.result("export", "--format", "anki", "--output", "cards.txt")
        lines = Path(result["output"]).read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[:3], ["#separator:Tab", "#html:true", "#tags column:3"])
        rows = {line.split("\t")[0]: line.split("\t") for line in lines[3:]}
        self.assertIn("redis.io", rows["Redis 为什么快？"][1])
        self.assertNotIn("待核验", rows["Redis 为什么快？"][2])
        self.assertEqual(rows["实现一个 LRU 缓存"][1], "")
        self.assertIn("待核验", rows["实现一个 LRU 缓存"][2])
        self.assertTrue(all(len(row) == 3 for row in rows.values()))

    def test_problem_link_is_curated_and_shown(self):
        link = {"url": "https://leetcode.cn/problems/lru-cache/", "title": "LeetCode 146. LRU 缓存", "evidence": "题面与截图一致"}
        self.bank.stage_commit("curate", payload={"schema_version": 1, "changes": [
            {"table": "questions", "id": self.lru, "set": {"problem_url": link}, "reason": "关联原题"}]})
        report = Path(self.bank.result("export", "--output", "r.md")["question_output"]).read_text(encoding="utf-8")
        self.assertIn("原题链接：[LeetCode 146. LRU 缓存](<https://leetcode.cn/problems/lru-cache/>)", report)
        bad = self.bank.cli("curate", payload={"schema_version": 1, "changes": [
            {"table": "questions", "id": self.lru, "set": {"problem_url": {"url": "https://leetcode.cn/problems/lru-cache/"}}, "reason": "x"}]},
            check=False)
        self.assertNotEqual(bad.returncode, 0)

    def test_fsrs_scheduler_and_calendar(self):
        self.bank.result("migrate", "apply")
        self.bank.stage_commit("config", payload={"review": {"scheduler": "fsrs", "desired_retention": 0.9}})
        staged = self.bank.result("study", "record", "--commit", payload={
            "request_id": "f1", "question_id": self.redis, "rating": "good", "user_quote": "会了"})
        event = self.bank.result("study", "history")["events"][0]
        self.assertEqual((event["interval_days"], round(event["fsrs"]["stability"], 2)), (4, 3.71))
        self.assertTrue(staged["committed"])
        topic = self.bank.stage_commit("studyset", "create", payload={"name": "缓存专题", "question_ids": [self.redis, self.lru]})
        plan = self.bank.result("studyset", "plan", "--id", topic["summary"]["studyset_id"], "--per-day", "1",
                                "--start", "2026-10-05", "--output", "cache.ics")
        self.assertEqual((plan["days"], plan["last_day"]), (2, "2026-10-06"))
        calendar = Path(plan["output"]).read_bytes().decode("utf-8")
        self.assertIn("DTSTART;VALUE=DATE:20261005", calendar)
        self.assertEqual(calendar.count("BEGIN:VEVENT"), 2)
        self.assertTrue(all(len(line.encode("utf-8")) <= 75 for line in calendar.split("\r\n")))


if __name__ == "__main__":
    unittest.main()
