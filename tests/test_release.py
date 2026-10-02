import copy
import json
import subprocess
import sys
from test_foundation import BankFixture, CLI
from ibank_core.dedupe import candidate_task, stage_decisions, exact_equivalent, merge_questions
from ibank_core.curation import configure
from ibank_core.ingestion import intake_images, stage_extraction, save_extraction
from ibank_core.runs import commit_run, stage_bundle, undo_run, abandon_run, show_run
from ibank_core.schema import validate_data
from ibank_core.storage import load_data, open_bank, read_json, read_jsonl
from ibank_core.errors import ValidationError
from ibank_core.doctor import doctor


class ReleaseTests(BankFixture):
    def test_configuration_stage_commit_undo(self):
        run = configure(self.bank, {"answer_stale_days": 30, "taxonomy_extensions": {"domains": ["business.finance"]}})
        self.assertNotIn("answer_stale_days", configure(self.bank))
        commit_run(self.bank, run["run_id"])
        self.assertEqual(configure(self.bank)["answer_stale_days"], 30)
        commit_run(self.bank, undo_run(self.bank, run["run_id"])["run_id"])
        self.assertNotIn("answer_stale_days", configure(self.bank))
        with self.assertRaises(ValidationError):
            configure(self.bank, {"answer_stale_days": "bad"})

    def test_pending_run_can_be_abandoned_without_data_loss(self):
        run = stage_bundle(self.bank, self.bundle)
        abandon_run(self.bank, run["run_id"])
        self.assertEqual(show_run(self.bank, run["run_id"])["status"], "abandoned")
        with self.assertRaises(ValidationError):
            commit_run(self.bank, run["run_id"])
        self.assertFalse(doctor(self.bank)["pending_runs"])

    def test_task_is_not_incomplete_and_can_be_inspected(self):
        self.seed()
        task = candidate_task(self.bank)
        self.assertEqual(show_run(self.bank, task["id"])["operation"], "dedupe")
        self.assertFalse(doctor(self.bank)["incomplete_runs"])

    def test_partial_image_response_can_resume(self):
        paths = []
        for i in range(2):
            path = self.base / f"image{i}.png"
            path.write_bytes(f"fixture-{i}".encode())
            paths.append(path)
        intake = intake_images(self.bank, paths)
        for i, item in enumerate(intake["items"]):
            saved = save_extraction(self.bank, intake["id"], {"schema_version": 1, "sources": [{"source_id": item["source"]["id"],
                "status": "no_questions", "questions": [], "reason": "Empty fixture"}]})
            self.assertEqual(saved["saved"], i + 1)
        response = read_json(self.bank / "runs" / intake["id"] / "extraction.json")
        commit_run(self.bank, stage_extraction(self.bank, intake["id"], response)["run_id"])
        self.assertEqual(len(load_data(self.bank)["sources"]), 2)

    def test_known_empty_source_can_be_reprocessed(self):
        path = self.base / "empty.png"
        path.write_bytes(b"fixture")
        intake = intake_images(self.bank, [path])
        sid = intake["items"][0]["source"]["id"]
        response = {"schema_version": 1, "sources": [{"source_id": sid, "status": "no_questions", "questions": [], "reason": "Unread content originally not selected"}]}
        commit_run(self.bank, stage_extraction(self.bank, intake["id"], response)["run_id"])
        retry = intake_images(self.bank, [path, path], reprocess=True)
        self.assertEqual((len(retry["items"]), len(retry["duplicates"])), (1, 1))
        self.assertEqual(retry["items"][0]["source"]["id"], sid)
        response["sources"][0].update(status="extracted", questions=[{"id": "c1", "original_text": "Redis 为什么快？", "sequence": 1,
            "confidence": {"is_question": 1.0, "classification": 1.0}}])
        commit_run(self.bank, stage_extraction(self.bank, retry["id"], response)["run_id"])
        self.assertEqual((len(load_data(self.bank)["sources"]), len(load_data(self.bank)["questions"])), (1, 1))

    def test_coding_exact_comparison_is_case_sensitive(self):
        a = {**self.bundle["questions"][0], "question_type": "coding", "canonical": "print(A)", "normalized": "print(a)"}
        b = {**a, "canonical": "print(a)"}
        self.assertFalse(exact_equivalent(a, b))

    def test_existing_merge_can_be_undone_without_deleting_questions(self):
        from ibank_core.normalize import normalize_question_text
        self.bundle["questions"][2].update(canonical="Redis 为什么性能高？", normalized=normalize_question_text("Redis 为什么性能高？"),
                                            technologies=["redis"], domains=["backend.cache"])
        self.seed()
        task = candidate_task(self.bank, question_ids=["q_demo2"])
        run = stage_decisions(self.bank, task_id=task["id"])
        commit_run(self.bank, run["run_id"])
        self.assertEqual(load_data(self.bank)["questions"][2]["status"], "merged")
        commit_run(self.bank, undo_run(self.bank, run["run_id"])["run_id"])
        self.assertEqual(load_data(self.bank)["questions"][2]["status"], "active")

    def test_merge_preserves_answers_and_relation_integrity(self):
        self.seed()
        data = load_data(self.bank)
        for version, qid in ((1, "q_demo0"), (1, "q_demo1")):
            data["answers"].append({"schema_version": 1, "id": "ans_" + qid, "question_id": qid, "version": version,
                "status": "ai_draft", "short_answer": "Answer", "spoken_answer": "", "key_points": [], "deep_dive": "",
                "interviewer_intent": "", "common_mistakes": [], "follow_up_questions": [], "code_example": None,
                "sources": [], "created_at": data["questions"][0]["created_at"], "verified_at": None})
        for i, pair in enumerate((("q_demo1", "q_demo0"), ("q_demo1", "q_demo2"), ("q_demo0", "q_demo2"))):
            data["relations"].append({"schema_version": 1, "id": f"rel_{i}", "from_question_id": pair[0], "to_question_id": pair[1],
                "type": "related", "confidence": 1.0, "created_at": data["questions"][0]["created_at"]})
        # Test mechanics with an explicit judgment; not a claim these sample topics are duplicates.
        audit = merge_questions(data, "q_demo1", "q_demo0", "MERGE_VARIANT", 1.0, "Synthetic merge mechanics test")
        validate_data(data)
        self.assertEqual(sorted(a["version"] for a in data["answers"]), [1, 2])
        self.assertEqual(len(data["relations"]), 1)
        self.assertEqual(len(audit["redundant_relations"]), 2)
        self.assertEqual(len(data["questions"]), 3)

    def test_cross_language_domain_candidates_are_retrievable(self):
        self.bundle["questions"][0].update(canonical="如何评估工具调用？", normalized="如何评估工具调用", domains=["ai.evaluation"], technologies=[])
        self.bundle["questions"][1].update(canonical="Evaluate tool calling", normalized="evaluate tool calling", domains=["ai.evaluation"], technologies=[])
        self.seed()
        task = candidate_task(self.bank, question_ids=["q_demo1"])
        self.assertIn("q_demo0", {m["question"]["id"] for m in task["items"][0]["matches"]})

    def test_duplicate_json_keys_rejected(self):
        path = self.base / "bad.json"
        path.write_text('{"schema_version":1,"schema_version":2}', encoding="utf-8")
        with self.assertRaises(ValidationError):
            read_json(path)

    def test_imported_image_merge_undo_keeps_all_original_questions(self):
        path = self.base / "two.png"
        path.write_bytes(b"host-reviewed fixture")
        intake = intake_images(self.bank, [path])
        response = {"schema_version": 1, "sources": [{"source_id": intake["items"][0]["source"]["id"], "status": "extracted",
            "questions": [{"id": f"c{i}", "sequence": i, "original_text": "Redis 为什么快？",
                           "confidence": {"is_question": 1, "classification": 1}} for i in (1, 2)]}]}
        stage = stage_extraction(self.bank, intake["id"], response)
        task = candidate_task(self.bank, stage["run_id"])
        merged = stage_decisions(self.bank, task_id=task["id"])
        commit_run(self.bank, merged["run_id"])
        self.assertEqual(sum(q["status"] == "active" for q in load_data(self.bank)["questions"]), 1)
        commit_run(self.bank, undo_run(self.bank, merged["run_id"])["run_id"])
        restored = load_data(self.bank)
        self.assertEqual(sum(q["status"] == "active" for q in restored["questions"]), 2)
        self.assertEqual((len(restored["occurrences"]), len(restored["sources"])), (2, 1))

    def test_cli_new_help_surfaces(self):
        for command in ("images", "extract-save", "classify", "curate", "dedupe-candidates", "dedupe", "research", "answer", "answer-review", "show", "export", "config", "undo", "abandon"):
            result = subprocess.run([sys.executable, "-B", str(CLI), command, "--help"], capture_output=True)
            self.assertEqual(result.returncode, 0, (command, result.stderr))

    def test_variant_then_exact_alias_chain(self):
        from ibank_core.normalize import normalize_question_text
        for q, text in zip(self.bundle["questions"], ["Redis 为什么快？", "Redis 为什么性能高？", "Redis 为什么性能高？"]):
            q.update(canonical=text, normalized=normalize_question_text(text), domains=["backend.cache"], technologies=["redis"])
        self.seed()
        task = candidate_task(self.bank)
        decisions = [
            {"question_id": "q_demo0", "action": "KEEP_DISTINCT", "confidence": 1.0, "reason": "First"},
            {"question_id": "q_demo1", "action": "MERGE_VARIANT", "target_id": "q_demo0", "confidence": 0.99, "reason": "Same scope"},
            {"question_id": "q_demo2", "action": "MERGE_EXACT", "target_id": "q_demo1", "confidence": 1.0, "reason": "Identical wording"}]
        run = stage_decisions(self.bank, {"schema_version": 1, "task_id": task["id"], "decisions": decisions})
        commit_run(self.bank, run["run_id"])
        data = load_data(self.bank)
        self.assertEqual({o["question_id"] for o in data["occurrences"]}, {"q_demo0"})
        self.assertEqual([q["merged_into"] for q in data["questions"]], [None, "q_demo0", "q_demo0"])

    def test_dedupe_refuses_abandoned_input_and_changed_configuration(self):
        run = stage_bundle(self.bank, self.bundle)
        task = candidate_task(self.bank, run["run_id"])
        abandon_run(self.bank, run["run_id"])
        with self.assertRaises(ValidationError):
            stage_decisions(self.bank, task_id=task["id"])
        from ibank_core.runs import stage_snapshot
        with open_bank(self.bank) as (_, config, current):
            snapshot = stage_snapshot(self.bank, current, current, config, operation="test-config-binding")
        commit_run(self.bank, configure(self.bank, {"dedupe": {"top_k": 2}})["run_id"])
        with self.assertRaises(ValidationError):
            candidate_task(self.bank, snapshot["run_id"])
