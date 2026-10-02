from pathlib import Path
from test_foundation import BankFixture
from ibank_core.answers import research_task, stage_answers, review_answer
from ibank_core.runs import commit_run
from ibank_core.search import search, detail
from ibank_core.errors import ValidationError
from ibank_core.export import export_bank


class AnswerTests(BankFixture):
    def response(self, status="ai_draft"):
        task = research_task(self.bank, ["q_demo1"])
        answer = {"question_id": "q_demo1", "status": status, "short_answer": "内存数据结构减少访问开销。", "spoken_answer": "主要数据操作在内存中执行。",
            "key_points": ["内存数据结构"], "deep_dive": "不同数据类型有不同复杂度，需要避免大键与慢命令。", "interviewer_intent": "区分机制与绝对性能承诺",
            "common_mistakes": ["认为所有命令都是常数时间"], "follow_up_questions": ["如何定位慢命令？"], "code_example": None, "sources": []}
        return {"schema_version": 1, "task_id": task["id"], "answers": [answer]}

    def test_draft_versioning_and_explicit_review(self):
        self.seed()
        commit_run(self.bank, stage_answers(self.bank, self.response())["run_id"])
        self.assertEqual(search(self.bank, answer_status="ai_draft")["total"], 1)
        with self.assertRaises(ValidationError):
            review_answer(self.bank, "q_demo1", "reviewed", "checked")
        run = review_answer(self.bank, "q_demo1", "reviewed", "Human checked", True)
        commit_run(self.bank, run["run_id"])
        versions = detail(self.bank, "q_demo1")["question"]["answer_versions"]
        self.assertEqual([a["version"] for a in versions], [1, 2])
        self.assertEqual(versions[0]["status"], "ai_draft")
        self.assertEqual(search(self.bank, answer_status="stale", as_of="2099-01-01")["total"], 1)

    def test_evidence_coverage_required(self):
        self.seed()
        response = self.response("source_backed")
        with self.assertRaisesRegex(ValidationError, "requires citations"):
            stage_answers(self.bank, response)
        from ibank_core.dates import today
        response["answers"][0]["sources"] = [{"url": "https://redis.io/docs/latest/develop/data-types/", "title": "Redis data types",
            "publisher": "Redis", "type": "official", "accessed_at": today().isoformat(), "evidence_note": "Fixture citation, not a live fetch"}]
        with self.assertRaisesRegex(ValidationError, "Every key point"):
            stage_answers(self.bank, response)
        response["answers"][0]["evidence"] = [{"key_point": 0, "source_urls": [response["answers"][0]["sources"][0]["url"]]}]
        commit_run(self.bank, stage_answers(self.bank, response)["run_id"])
        self.assertEqual(search(self.bank, answer_status="source_backed")["total"], 1)
        result = export_bank(self.bank, 'editions.md')
        self.assertIn('内存数据结构减少访问开销', Path(result['answer_output']).read_text(encoding='utf-8'))
        self.assertNotIn('内存数据结构减少访问开销', Path(result['question_output']).read_text(encoding='utf-8'))
        self.assertEqual(result['answered_questions'], 1)

    def test_stale_research_and_partial_answers_rejected(self):
        self.seed()
        response = self.response()
        other = self.response()
        commit_run(self.bank, stage_answers(self.bank, response)["run_id"])
        with self.assertRaisesRegex(ValidationError, "stale"):
            stage_answers(self.bank, other)
        response = self.response()
        response["answers"] = []
        with self.assertRaises(ValidationError):
            stage_answers(self.bank, response)
