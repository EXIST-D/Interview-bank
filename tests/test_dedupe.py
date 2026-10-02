from test_foundation import BankFixture
from ibank_core.dedupe import candidate_task, stage_decisions
from ibank_core.runs import commit_run, stage_bundle, undo_run
from ibank_core.errors import ValidationError, ReviewRequired
from ibank_core.storage import load_data
from ibank_core.normalize import normalize_question_text


class DedupTests(BankFixture):
    def incoming(self, title):
        self.seed()
        q = {**self.bundle["questions"][1], "id": "q_new", "canonical": title, "normalized": normalize_question_text(title)}
        occ = {**self.bundle["occurrences"][1], "id": "occ_new", "question_id": "q_new", "sequence": 5}
        return stage_bundle(self.bank, {"schema_version": 1, "questions": [q], "occurrences": [occ]})

    def response(self, task, action, score=0.99):
        return {"schema_version": 1, "task_id": task["id"], "decisions": [{"question_id": "q_new", "target_id": "q_demo1", "action": action,
            "confidence": score, "reason": "Same complete answer"}]}

    def test_exact_merges_occurrences_and_preserves_question(self):
        run = self.incoming("Redis 为什么性能高？")
        task = candidate_task(self.bank, run["run_id"])
        result = stage_decisions(self.bank, task_id=task["id"])
        commit_run(self.bank, result["run_id"])
        data = load_data(self.bank)
        self.assertEqual(next(q for q in data["questions"] if q["id"] == "q_new")["merged_into"], "q_demo1")
        self.assertEqual(next(o for o in data["occurrences"] if o["id"] == "occ_new")["question_id"], "q_demo1")
        self.assertEqual(len(data["questions"]), 4)
        undone = undo_run(self.bank, result["run_id"])
        self.assertEqual(undone["summary"]["undo_scope"], "dedupe_only_preserve_import")
        commit_run(self.bank, undone["run_id"])
        restored = load_data(self.bank)
        self.assertEqual(len(restored["questions"]), 4)
        self.assertTrue(all(q["status"] == "active" for q in restored["questions"]))
        self.assertEqual(next(o for o in restored["occurrences"] if o["id"] == "occ_new")["question_id"], "q_new")

    def test_variant_and_related_are_different(self):
        run = self.incoming("Redis 为什么这么快？")
        task = candidate_task(self.bank, run["run_id"])
        result = stage_decisions(self.bank, self.response(task, "KEEP_RELATED"))
        commit_run(self.bank, result["run_id"])
        data = load_data(self.bank)
        self.assertEqual(len(data["relations"]), 1)
        self.assertTrue(all(q["status"] == "active" for q in data["questions"]))

    def test_uncertain_merge_is_review_and_false_exact_is_rejected(self):
        run = self.incoming("Redis 为什么这么快？")
        task = candidate_task(self.bank, run["run_id"])
        result = stage_decisions(self.bank, self.response(task, "MERGE_VARIANT", 0.5))
        with self.assertRaises(ReviewRequired):
            commit_run(self.bank, result["run_id"])
        with self.assertRaisesRegex(ValidationError, "identical"):
            stage_decisions(self.bank, self.response(task, "MERGE_EXACT"))
        result = stage_decisions(self.bank, self.response(task, "MERGE_VARIANT"))
        commit_run(self.bank, result["run_id"])
        self.assertEqual(len([q for q in load_data(self.bank)["questions"] if q["status"] == "active"]), 3)
