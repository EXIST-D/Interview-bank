"""Composite commands do the usual sequence in one call and still stop at review items."""
import json
import unittest

from support import Bank, sourced_answer


class Calls(Bank):
    """Counts CLI invocations, the cost the composite commands exist to cut."""

    def __init__(self):
        self.calls = 0
        super().__init__()

    def cli(self, *args, **kwargs):
        self.calls += 1
        return super().cli(*args, **kwargs)


def extraction(intake, texts):
    sid = intake["first"][0]["source_id"]
    return {"schema_version": 1, "sources": [{"source_id": sid, "status": "extracted", "metadata": {"round": "technical-1"},
            "questions": [{"id": f"c{i}", "original_text": text, "sequence": i + 1, "domains": ["backend.cache"],
                           "technologies": ["redis"], "confidence": {"is_question": 0.99, "classification": 0.95}}
                          for i, text in enumerate(texts)]}]}


def decide(bank, submitted, action="KEEP_DISTINCT", **overrides):
    """Host decisions for every incoming question of an ingest submit result."""
    dedupe = submitted["dedupe"]
    decisions = [{"question_id": item["question_id"], "action": action, "confidence": 0.95, "reason": "Different core question",
                  **({"target_id": item["candidates"][0]["ref"]} if action != "KEEP_DISTINCT" else {}),
                  **overrides.get(item["question_id"], {})} for item in dedupe["items"]]
    path = bank.root / "decisions.json"
    path.write_text(json.dumps({"schema_version": 1, "task_id": dedupe["task_id"], "decisions": decisions}, ensure_ascii=False), encoding="utf-8")
    return str(path)


class IngestFlow(unittest.TestCase):
    def setUp(self):
        self.bank = Calls()

    def tearDown(self):
        self.bank.close()

    def image(self, name, content):
        path = self.bank.root / name
        path.write_bytes(content)
        return str(path)

    def test_first_import_needs_three_calls(self):
        start = self.bank.calls
        intake = self.bank.result("ingest", "images", self.image("a.png", b"synthetic image a"))
        self.assertEqual((intake["sources"], intake["first"][0]["type"]), (1, "image"))
        path = self.bank.root / "extraction.json"
        path.write_text(json.dumps(extraction(intake, ["Redis 为什么快？", "Redis 持久化有哪些方式？"]), ensure_ascii=False), encoding="utf-8")
        submitted = self.bank.result("ingest", "submit", "--intake", intake["intake_id"], "--extraction", str(path))
        self.assertEqual((submitted["status"], submitted["dedupe"]["with_candidates"]), ("dedupe_pending", 1))
        final = self.bank.result("ingest", "finalize", "--task", submitted["dedupe"]["task_id"],
                                 "--decisions", decide(self.bank, submitted))
        self.assertTrue(final["committed"])
        self.assertEqual(self.bank.calls - start, 3)
        self.assertEqual(self.bank.result("search")["total"], 2)

    def test_uncertain_candidates_stop_for_review(self):
        intake = self.bank.result("ingest", "images", self.image("a.png", b"synthetic image a"))
        path = self.bank.root / "e1.json"
        path.write_text(json.dumps(extraction(intake, ["Redis 为什么快？"]), ensure_ascii=False), encoding="utf-8")
        first = self.bank.result("ingest", "submit", "--intake", intake["intake_id"], "--extraction", str(path))
        self.bank.result("ingest", "finalize", "--task", first["dedupe"]["task_id"])
        second_intake = self.bank.result("ingest", "images", self.image("b.png", b"synthetic image b"))
        path.write_text(json.dumps(extraction(second_intake, ["Redis 为什么这么快？"]), ensure_ascii=False), encoding="utf-8")
        second = self.bank.result("ingest", "submit", "--intake", second_intake["intake_id"], "--extraction", str(path))
        self.assertEqual(second["dedupe"]["with_candidates"], 1)
        pending = self.bank.result("ingest", "finalize", "--task", second["dedupe"]["task_id"])
        self.assertEqual((pending["status"], pending["committed"]), ("review_required", False))
        self.bank.result("abandon", "--run", pending["stage_run"])
        merged = self.bank.result("ingest", "finalize", "--task", second["dedupe"]["task_id"],
                                  "--decisions", decide(self.bank, second, "MERGE_VARIANT"))
        self.assertTrue(merged["committed"])
        self.assertEqual(merged["dedupe"]["MERGE_VARIANT"], 1)
        self.assertEqual(self.bank.result("search")["questions"][0]["frequency"], 2)

    def test_answer_commit_in_one_call(self):
        self.bank.add_questions("backend.cache", "Redis 为什么快？")
        task = self.bank.result("research", "--limit", "1")
        result = self.bank.result("answer", "--commit", payload={"schema_version": 1, "task_id": task["id"],
                                                                 "answers": [sourced_answer(task["items"][0]["question"]["id"], "2026-09-30")]})
        self.assertTrue(result["committed"])
        self.assertEqual(self.bank.result("search")["questions"][0]["answer_status"], "source_backed")


class InterviewFlow(unittest.TestCase):
    def setUp(self):
        self.bank = Calls()
        self.bank.add_questions("backend.cache", "Redis 为什么快？", "Redis 持久化有哪些方式？")
        self.bank.result("migrate", "apply")

    def tearDown(self):
        self.bank.close()

    def test_turn_and_review_cover_a_question_in_two_calls(self):
        ids = [q["id"] for q in self.bank.result("search")["questions"]]
        session = self.bank.result("interview", "start", "--commit", payload={"name": "两题模拟", "question_ids": ids})
        self.assertTrue(session["committed"])
        key = session["summary"]["session_id"]
        prompt = self.bank.result("interview", "next", "--id", key)
        start = self.bank.calls
        for number in range(2):
            turn = self.bank.result("interview", "turn", "--id", key, payload={
                "question_id": prompt["question_id"], "request_id": f"turn-{number}", "text": "内存加事件循环。"})
            packet = turn["next"]
            self.assertEqual(packet["status"], "awaiting_feedback")
            review = self.bank.result("interview", "review", "--id", key, payload={
                "response_id": packet["response"]["id"], "limited_basis": True,
                "observations": [{"dimension": "coverage", "quote": "内存", "note": "Mentions memory only"}]})
            prompt = review["next"]
        self.assertEqual(prompt["status"], "completed")
        self.assertEqual(self.bank.calls - start, 4)
        again = self.bank.result("interview", "turn", "--id", key, payload={
            "question_id": ids[0], "request_id": "turn-0", "text": "内存加事件循环。"})
        self.assertTrue(again["already_recorded"])

    def test_study_record_commit(self):
        qid = self.bank.result("search")["questions"][0]["id"]
        result = self.bank.result("study", "record", "--commit", payload={
            "request_id": "s1", "question_id": qid, "rating": "good", "user_quote": "这题会了"})
        self.assertTrue(result["committed"])
        self.assertEqual(len(self.bank.result("study", "history")["events"]), 1)

    def test_finalize_can_open_a_workflow(self):
        image = self.bank.root / "c.png"
        image.write_bytes(b"synthetic image c")
        intake = self.bank.result("ingest", "images", str(image))
        path = self.bank.root / "e.json"
        path.write_text(json.dumps(extraction(intake, ["缓存穿透是什么？"]), ensure_ascii=False), encoding="utf-8")
        submitted = self.bank.result("ingest", "submit", "--intake", intake["intake_id"], "--extraction", str(path))
        final = self.bank.result("ingest", "finalize", "--task", submitted["dedupe"]["task_id"],
                                 "--decisions", decide(self.bank, submitted), "--workflow", "新截图研究")
        flow = self.bank.result("workflow", "show", "--id", final["workflow_id"])
        self.assertEqual(len(flow["items"]) if isinstance(flow["items"], list) else flow["remaining"], 1)


if __name__ == "__main__":
    unittest.main()
