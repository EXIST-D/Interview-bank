"""Actions only a person can take are structural: an agent cannot claim them with a flag."""
import http.client
import json
import os
import subprocess
import sys
import threading
import unittest

from support import CLI, Bank, sourced_answer
from ibank_core.web import LocalServer, WebApp


class HumanActions(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.bank.add_questions("backend.cache", "Redis 为什么快？")
        self.qid = self.bank.result("search")["questions"][0]["id"]
        task = self.bank.result("research", "--limit", "1")
        staged = self.bank.result("answer", payload={"schema_version": 1, "task_id": task["id"],
                                                     "answers": [sourced_answer(self.qid, "2026-09-30")]})
        self.bank.result("commit", "--run", staged["run_id"])

    def tearDown(self):
        self.bank.close()

    def latest(self):
        return self.bank.result("show", self.qid)["question"]["answer"]

    def test_agent_cannot_mark_reviewed_from_a_pipe(self):
        proc = self.bank.cli("answer-review", "--question", self.qid, "--status", "reviewed", "--reason", "看过", "--human-reviewed", check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("人工审阅通过", json.loads(proc.stderr)["error"])
        self.assertEqual(self.latest()["status"], "source_backed")

    def test_agent_may_mark_stale_and_is_recorded_as_agent(self):
        staged = self.bank.result("answer-review", "--question", self.qid, "--status", "stale", "--reason", "Redis 8 改了默认值")
        audit = json.loads((self.bank.path / "runs" / staged["run_id"] / "run.json").read_text(encoding="utf-8"))["audit"][0]
        self.assertEqual((audit["actor"], audit["human_reviewed"]), ("agent", False))

    @unittest.skipIf(os.name == "nt", "pty is POSIX-only")
    def test_interactive_terminal_confirmation(self):
        import pty
        argv = [sys.executable, "-B", str(CLI), "answer-review", "--question", self.qid, "--status", "reviewed",
                "--reason", "本人对照官方 FAQ 核对", "--bank", str(self.bank.path), "--json"]
        leader, follower = pty.openpty()
        try:
            os.write(leader, "我已审阅\n".encode())  # what the person types at the prompt
            proc = subprocess.run(argv, stdin=follower, capture_output=True, text=True, encoding="utf-8", timeout=60)
        finally:
            os.close(leader)
            os.close(follower)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.bank.result("commit", "--run", json.loads(proc.stdout)["result"]["run_id"])
        self.assertEqual(self.latest()["status"], "reviewed")


class WebReview(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.bank.add_questions("backend.cache", "Redis 为什么快？")
        self.qid = self.bank.result("search")["questions"][0]["id"]
        task = self.bank.result("research", "--limit", "1")
        staged = self.bank.result("answer", payload={"schema_version": 1, "task_id": task["id"],
                                                     "answers": [sourced_answer(self.qid, "2026-09-30")]})
        self.bank.result("commit", "--run", staged["run_id"])
        self.app = WebApp(self.bank.path)
        self.server = LocalServer(self.app)
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        thread.start()
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close(), thread.join(timeout=2)))

    def tearDown(self):
        self.bank.close()

    def post(self, body):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        conn.request("POST", "/api/review", json.dumps(body), {"X-Interview-Token": self.server.token, "Content-Type": "application/json"})
        response = conn.getresponse()
        result = response.status, json.loads(response.read())
        conn.close()
        return result

    def test_review_button_commits_with_web_actor(self):
        answer = self.app.question(self.qid)["answer"]
        self.assertTrue(self.app.library({})["can_review"])
        code, result = self.post({"question_id": self.qid, "answer_id": answer["id"], "decision": "reviewed", "note": "对照了官方 FAQ"})
        self.assertEqual((code, result["status"]), (200, "reviewed"))
        self.assertEqual(self.app.question(self.qid)["answer"]["status"], "reviewed")
        self.assertFalse(self.bank.result("doctor")["pending_runs"])
        runs = [json.loads(p.read_text(encoding="utf-8")) for p in (self.bank.path / "runs").glob("run_*/run.json")]
        review = next(r for r in runs if r.get("operation") == "answer-review")
        self.assertEqual(review["audit"][0]["actor"], "local_web")

    def test_review_of_an_outdated_view_or_without_note_is_refused(self):
        answer = self.app.question(self.qid)["answer"]
        self.assertEqual(self.post({"question_id": self.qid, "answer_id": "ans_old", "decision": "reviewed", "note": "看过"})[0], 400)
        self.assertEqual(self.post({"question_id": self.qid, "answer_id": answer["id"], "decision": "reviewed", "note": " "})[0], 400)
        self.app.read_only = True
        self.assertEqual(self.post({"question_id": self.qid, "answer_id": answer["id"], "decision": "reviewed", "note": "看过"})[0], 400)
        self.assertEqual(self.app.question(self.qid)["answer"]["status"], "source_backed")


class RelayedPractice(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.bank.add_questions("backend.cache", "Redis 为什么快？")
        self.bank.result("migrate", "apply")
        self.qid = self.bank.result("search")["questions"][0]["id"]

    def tearDown(self):
        self.bank.close()

    def test_cli_rating_needs_the_users_words(self):
        payload = {"request_id": "r1", "question_id": self.qid, "rating": "good"}
        proc = self.bank.cli("study", "record", payload=payload, check=False)
        self.assertIn("user_quote", json.loads(proc.stderr)["error"])
        staged = self.bank.result("study", "record", payload={**payload, "user_quote": "这题我能讲清楚了"})
        self.bank.result("commit", "--run", staged["run_id"])
        event = self.bank.result("study", "history")["events"][0]
        self.assertEqual((event["rating_source"], event["user_quote"]), ("agent_relayed", "这题我能讲清楚了"))

    def test_policy_keeps_the_instruction(self):
        payload = {"kind": "protect", "question_id": self.qid, "field": "canonical", "reason": "保留原话", "user_requested": True}
        self.assertNotEqual(self.bank.cli("policy", "add", payload=payload, check=False).returncode, 0)
        staged = self.bank.result("policy", "add", payload={**payload, "user_quote": "这道题的题干不要改"})
        self.bank.result("commit", "--run", staged["run_id"])
        self.assertEqual(self.bank.result("policy", "list")["policies"][0]["user_quote"], "这道题的题干不要改")


if __name__ == "__main__":
    unittest.main()
