from test_foundation import BankFixture
from ibank_core.tasks import classification_task
from ibank_core.curation import stage_classification, stage_curate
from ibank_core.runs import commit_run
from ibank_core.errors import ValidationError, ReviewRequired
from ibank_core.storage import load_data


class ClassificationTests(BankFixture):
    def response(self):
        task = classification_task(self.bank, ["q_demo0"])
        return {"schema_version": 1, "task_id": task["id"], "items": [{"question_id": "q_demo0", "confidence": 0.95,
            "reason": "Database indexing knowledge", "question": {"role_tracks": ["backend", "fullstack"], "domains": ["backend.database"]},
            "occurrences": [{"id": "occ_demo0", "set": {"company": "字节", "role_tracks": ["backend"], "round": "technical-2"}}]}]}

    def test_semantic_response_and_alias_resolution(self):
        self.seed()
        response = self.response()
        run = stage_classification(self.bank, response)
        commit_run(self.bank, run["run_id"])
        data = load_data(self.bank)
        self.assertEqual(data["questions"][0]["role_tracks"], ["backend", "fullstack"])
        self.assertEqual(data["occurrences"][0]["company_id"], "company_bytedance")

    def test_low_confidence_and_incomplete_response(self):
        self.seed()
        response = self.response()
        response["items"][0]["confidence"] = 0.3
        run = stage_classification(self.bank, response)
        with self.assertRaises(ReviewRequired):
            commit_run(self.bank, run["run_id"])
        response["items"] = []
        with self.assertRaises(ValidationError):
            stage_classification(self.bank, response)

    def test_curate_preserves_original_wording(self):
        self.seed()
        payload = {"schema_version": 1, "changes": [{"table": "questions", "id": "q_demo0", "set": {"canonical": "MySQL 为何用 B+ 树？"}, "reason": "Minimal wording fix"}]}
        run = stage_curate(self.bank, payload)
        commit_run(self.bank, run["run_id"])
        self.assertEqual(load_data(self.bank)["occurrences"][0]["original_text"], self.bundle["occurrences"][0]["original_text"])
        payload["changes"][0].update(table="occurrences", id="occ_demo0", set={"original_text": "invented"})
        with self.assertRaises(ValidationError):
            stage_curate(self.bank, payload)
