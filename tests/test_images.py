import copy
import json
from test_foundation import BankFixture
from ibank_core.ingestion import intake_images, stage_extraction
from ibank_core.runs import commit_run, undo_run
from ibank_core.errors import ReviewRequired, ValidationError
from ibank_core.storage import load_data, read_json


class ImageTests(BankFixture):
    # Infrastructure fixtures deliberately contain marker bytes; real visual fixtures
    # are generated and inspected separately by tools/create_visual_evals.py.
    def intake(self, retention="reference", count=1):
        paths = []
        for i in range(count):
            path = self.base / f"screen-{i}.png"
            path.write_bytes(b"test-image-fixture-" + str(i).encode())
            paths.append(path)
        return intake_images(self.bank, paths, retention=retention)

    def extraction(self, intake):
        return {"schema_version": 1, "sources": [{"source_id": item["source"]["id"], "status": "extracted",
            "metadata": {"company": "字节跳动", "role_tracks": ["backend"], "round": "technical-2"},
            "questions": [{"id": f"c{i}", "original_text": "Redis 为什么快？", "sequence": 1,
                           "domains": ["backend.cache"], "technologies": ["redis"],
                           "confidence": {"is_question": 0.99, "classification": 0.95}}]}
            for i, item in enumerate(intake["items"])]}

    def test_image_reference_copy_none_and_source_dedup(self):
        intake = self.intake(retention="copy")
        task = self.extraction(intake)
        run = stage_extraction(self.bank, intake["id"], task)
        commit_run(self.bank, run["run_id"])
        source = load_data(self.bank)["sources"][0]
        self.assertTrue((self.bank / source["path"]).is_file())
        second = intake_images(self.bank, [self.base / "screen-0.png"])
        self.assertEqual(len(second["items"]), 0)
        self.assertEqual(len(second["duplicates"]), 1)

    def test_image_none_cleans_processing_paths_after_commit(self):
        intake = self.intake(retention="none")
        run = stage_extraction(self.bank, intake["id"], self.extraction(intake))
        commit_run(self.bank, run["run_id"])
        payload = read_json(self.bank / "runs" / intake["id"] / "intake.json")
        self.assertNotIn("view_path", payload["items"][0])
        self.assertIsNone(load_data(self.bank)["sources"][0]["path"])

    def test_partial_batch_is_rejected(self):
        intake = self.intake(count=2)
        extraction = self.extraction(intake)
        extraction["sources"].pop()
        with self.assertRaisesRegex(ValidationError, "Every new image"):
            stage_extraction(self.bank, intake["id"], extraction)

    def test_empty_image_preserves_source_without_phantom_questions(self):
        intake = self.intake()
        extraction = self.extraction(intake)
        extraction["sources"][0].update(status="no_questions", reason="Only app UI", questions=[])
        run = stage_extraction(self.bank, intake["id"], extraction)
        commit_run(self.bank, run["run_id"])
        data = load_data(self.bank)
        self.assertEqual((len(data["sources"]), len(data["questions"])), (1, 0))

    def test_unreadable_and_low_confidence_block_until_reviewed(self):
        intake = self.intake()
        extraction = self.extraction(intake)
        extraction["sources"][0]["questions"][0]["confidence"]["is_question"] = 0.4
        run = stage_extraction(self.bank, intake["id"], extraction)
        with self.assertRaises(ReviewRequired):
            commit_run(self.bank, run["run_id"])
        extraction["sources"][0].update(status="unreadable", reason="Blurry", questions=[])
        run = stage_extraction(self.bank, intake["id"], extraction)
        with self.assertRaises(ReviewRequired):
            commit_run(self.bank, run["run_id"])
        extraction["sources"][0].update(status="skip", reviewed=True)
        commit_run(self.bank, stage_extraction(self.bank, intake["id"], extraction)["run_id"])

    def test_cross_image_followup_retains_chain(self):
        intake = self.intake(count=2)
        extraction = self.extraction(intake)
        extraction["sources"][1]["questions"][0]["parent_id"] = "c0"
        run = stage_extraction(self.bank, intake["id"], extraction)
        commit_run(self.bank, run["run_id"])
        occurrences = load_data(self.bank)["occurrences"]
        self.assertEqual(occurrences[1]["parent_occurrence_id"], occurrences[0]["id"])

    def test_pii_and_changed_images_rejected(self):
        intake = self.intake()
        extraction = self.extraction(intake)
        # example.com is a documentation domain (RFC 2606) and is allowed; a real mailbox is not.
        extraction["sources"][0]["questions"][0]["original_text"] = "联系 me@qq.com"
        with self.assertRaisesRegex(ValidationError, "contact information"):
            stage_extraction(self.bank, intake["id"], extraction)
        (self.base / "screen-0.png").write_bytes(b"changed")
        with self.assertRaisesRegex(ValidationError, "changed after intake"):
            stage_extraction(self.bank, intake["id"], self.extraction(intake))

    def test_snapshot_stale_conflict_and_undo(self):
        intake = self.intake()
        first = stage_extraction(self.bank, intake["id"], self.extraction(intake))
        second = stage_extraction(self.bank, intake["id"], self.extraction(intake))
        commit_run(self.bank, first["run_id"])
        with self.assertRaisesRegex(ValidationError, "changed since staging"):
            commit_run(self.bank, second["run_id"])
        with self.assertRaisesRegex(ValidationError, "physically remove"):
            undo_run(self.bank, first["run_id"])
