"""1.14 dedupe: review sheet and refs, targets beyond the candidate list, default_action and deferred review."""
import json
import unittest
from pathlib import Path

from support import Bank
from test_flows import extraction


def image(bank, name, content):
    path = bank.root / name
    path.write_bytes(content)
    return str(path)


def submit(bank, name, texts, domains=("backend.cache",), *extra):
    intake = bank.result("ingest", "images", image(bank, name, name.encode() * 3))
    payload = extraction(intake, texts)
    for question in payload["sources"][0]["questions"]:
        question["domains"], question["technologies"] = list(domains), []
    path = bank.root / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return bank.result("ingest", "submit", "--intake", intake["intake_id"], "--extraction", str(path), *extra)


def write(bank, name, payload):
    path = bank.root / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(path)


class ReviewSheet(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()

    def tearDown(self):
        self.bank.close()

    def test_sheet_groups_paraphrases_and_refs_resolve(self):
        submitted = submit(self.bank, "a.png", ["新框架出来时你怎么判断值不值得引入？", "Redis 持久化有哪些方式？",
                                                "面对一个新技术，你的决策清单是什么？"], ("engineering.architecture",))
        dedupe = submitted["dedupe"]
        self.assertEqual([i["ref"] for i in dedupe["items"]], ["n1", "n2", "n3"])
        sheet = Path(dedupe["review_sheet"]).read_text(encoding="utf-8")
        # The two paraphrases share almost no wording but sit in the same topic group of the sheet.
        self.assertIn("n1 新框架出来时你怎么判断值不值得引入？", sheet)
        self.assertIn("n3 面对一个新技术，你的决策清单是什么？", sheet)
        decisions = {"decisions": [{"question_id": "n3", "action": "MERGE_VARIANT", "target_id": "n1", "confidence": 0.92,
                                    "reason": "同一考点：评估新技术是否引入"}], "default_action": "KEEP_DISTINCT"}
        final = self.bank.result("ingest", "finalize", "--task", dedupe["task_id"], "--decisions", write(self.bank, "d.json", decisions))
        self.assertTrue(final["committed"])
        self.assertEqual((final["dedupe"]["MERGE_VARIANT"], final["dedupe"]["KEEP_DISTINCT"]), (1, 2))
        self.assertEqual(self.bank.result("search")["total"], 2)

    def test_unknown_target_fails_loudly_and_task_must_match(self):
        submitted = submit(self.bank, "a.png", ["Redis 为什么快？"])
        task = submitted["dedupe"]["task_id"]
        bad = {"decisions": [{"question_id": "n1", "action": "KEEP_RELATED", "target_id": "e99", "confidence": 0.9, "reason": "x"}]}
        proc = self.bank.cli("ingest", "finalize", "--task", task, "--decisions", write(self.bank, "bad.json", bad), check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("e99", proc.stderr)
        wrong = {"task_id": "run_other", "decisions": [], "default_action": "KEEP_DISTINCT"}
        proc = self.bank.cli("ingest", "finalize", "--task", task, "--decisions", write(self.bank, "w.json", wrong), check=False)
        self.assertIn("belongs to task run_other", proc.stderr)
        proc = self.bank.cli("ingest", "finalize", "--task", task, "--decisions",
                             write(self.bank, "x.json", {"decisions": [], "default_action": "MERGE_VARIANT"}), check=False)
        self.assertIn("default_action may only be KEEP_DISTINCT", proc.stderr)

    def test_existing_questions_can_be_linked_later(self):
        self.bank.add_questions("backend.cache", "Redis 为什么快？", "Redis 持久化有哪些方式？")
        ids = [q["id"] for q in self.bank.result("search")["questions"]]
        task = self.bank.result("dedupe-candidates", "--question", ids[0])
        payload = {"task_id": task["task_id"], "decisions": [{"question_id": "n1", "action": "KEEP_RELATED", "target_id": ids[1],
                                                               "confidence": 0.9, "reason": "同属 Redis 基础"}]}
        self.bank.stage_commit("dedupe", "--decisions", write(self.bank, "rel.json", payload))
        self.assertEqual(self.bank.result("validate")["counts"]["relations"], 1)

    def test_task_file_is_compact(self):
        submitted = submit(self.bank, "a.png", [f"Redis 第 {n} 个问题是什么？" for n in range(20)])
        task = self.bank.result("run-show", "--run", submitted["dedupe"]["task_id"])
        match = next(m for i in task["items"] for m in i["matches"])
        self.assertEqual(set(match["question"]), {"id", "canonical"})


class DeferredReview(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()

    def tearDown(self):
        self.bank.close()

    def test_defer_commits_the_rest_and_the_person_decides_later(self):
        first = submit(self.bank, "a.png", ["Redis 为什么快？"])
        self.bank.result("ingest", "finalize", "--task", first["dedupe"]["task_id"])
        second = submit(self.bank, "b.png", ["Redis 为什么这么快？", "Redis 持久化有哪些方式？"])
        decisions = {"decisions": [{"question_id": "n1", "action": "REVIEW", "target_id": "e1", "confidence": 0.7,
                                    "reason": "可能同题，留给用户判断"}], "default_action": "KEEP_DISTINCT"}
        final = self.bank.result("ingest", "finalize", "--task", second["dedupe"]["task_id"], "--defer-review",
                                 "--decisions", write(self.bank, "d.json", decisions))
        self.assertTrue(final["committed"])
        self.assertEqual(final["deferred_review"], 1)
        self.assertEqual(self.bank.result("search")["total"], 3)

        from ibank_core.dedupe import record_human_decision, review_queue
        queue = review_queue(self.bank.path)
        self.assertEqual((len(queue), queue[0]["deferred"], queue[0]["target"]), (1, True, "Redis 为什么快？"))
        record_human_decision(self.bank.path, queue[0]["run_id"], queue[0]["question_id"], "MERGE_VARIANT", "同一题")
        resolved = self.bank.result("dedupe", "--resolve", final["run_id"])
        self.assertEqual((resolved["resolves"], resolved["still_open"]), (final["run_id"], 0))
        self.assertEqual(review_queue(self.bank.path)[0]["resolution"], "staged")
        self.bank.result("commit", "--run", resolved["run_id"])
        self.assertEqual(review_queue(self.bank.path), [])
        top = self.bank.result("search")["questions"][0]
        self.assertEqual((self.bank.result("search")["total"], top["frequency"]), (2, 2))

    def test_without_defer_a_review_item_still_blocks(self):
        first = submit(self.bank, "a.png", ["Redis 为什么快？"])
        self.bank.result("ingest", "finalize", "--task", first["dedupe"]["task_id"])
        second = submit(self.bank, "b.png", ["Redis 为什么这么快？"])
        decisions = {"decisions": [{"question_id": "n1", "action": "REVIEW", "target_id": "e1", "confidence": 0.7, "reason": "不确定"}]}
        pending = self.bank.result("ingest", "finalize", "--task", second["dedupe"]["task_id"],
                                   "--decisions", write(self.bank, "d.json", decisions))
        self.assertEqual(pending["status"], "review_required")
        self.assertIn("--defer-review", pending["next"])


if __name__ == "__main__":
    unittest.main()


class SubmitOutput(unittest.TestCase):
    def test_large_import_stays_within_the_output_budget(self):
        import os
        bank = Bank()
        try:
            intake = bank.result("ingest", "images", image(bank, "big.png", b"big image bytes"))
            payload = extraction(intake, [f"第 {n} 题：Redis 缓存第 {n} 种用法是什么，适合哪些场景？" for n in range(150)])
            path = Path(write(bank, "big.json", payload))
            env = {**os.environ, "INTERVIEW_BANK_MAX_OUTPUT": "8192"}
            proc = bank.cli("ingest", "submit", "--intake", intake["intake_id"], "--extraction", str(path), env=env)
            self.assertLessEqual(len(proc.stdout.encode("utf-8")), 8192 + 512)
            dedupe = json.loads(proc.stdout)["result"]["dedupe"]
            self.assertEqual(dedupe["incoming"], 150)
            self.assertLessEqual(len(dedupe["items"]), 15)
            self.assertIn("run-show", dedupe["full_task"])
            self.assertTrue(Path(dedupe["review_sheet"]).is_file())
        finally:
            bank.close()
