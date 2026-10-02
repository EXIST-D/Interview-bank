"""A person decides uncertain merges in the Web reader; the agent applies them with dedupe --resolve."""
import http.client
import json
import threading
import unittest

from support import Bank
from ibank_core.web import LocalServer, WebApp


def extraction(intake, text):
    return {"schema_version": 1, "sources": [{"source_id": intake["first"][0]["source_id"], "status": "extracted",
            "questions": [{"id": "c1", "original_text": text, "sequence": 1, "domains": ["backend.cache"], "technologies": ["redis"],
                           "confidence": {"is_question": 0.99, "classification": 0.95}}]}]}


class MergeReview(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.bank.add_questions("backend.cache", "Redis 为什么快？")
        image = self.bank.root / "a.png"
        image.write_bytes(b"synthetic")
        intake = self.bank.result("ingest", "images", str(image))
        path = self.bank.root / "e.json"
        path.write_text(json.dumps(extraction(intake, "Redis 为什么这么快？"), ensure_ascii=False), encoding="utf-8")
        submitted = self.bank.result("ingest", "submit", "--intake", intake["intake_id"], "--extraction", str(path))
        self.pending = self.bank.result("ingest", "finalize", "--task", submitted["dedupe"]["task_id"])
        self.assertEqual(self.pending["status"], "review_required")
        self.app = WebApp(self.bank.path)
        self.server = LocalServer(self.app)
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        thread.start()
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close(), thread.join(timeout=2)))

    def tearDown(self):
        self.bank.close()

    def request(self, path, body=None, host=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        headers = {"X-Interview-Token": self.server.token, "Content-Type": "application/json"}
        if host:
            headers["Host"] = host
        conn.request("POST" if body is not None else "GET", path, json.dumps(body) if body is not None else None, headers)
        response = conn.getresponse()
        result = response.status, json.loads(response.read())
        conn.close()
        return result

    def test_queue_decision_resolve_and_commit(self):
        code, queue = self.request("/api/dedupe-reviews")
        self.assertEqual(code, 200)
        item = queue["items"][0]
        self.assertEqual((item["question"], item["target"], item["decision"]), ("Redis 为什么这么快？", "Redis 为什么快？", None))
        code, saved = self.request("/api/dedupe-decision", {"run_id": item["run_id"], "question_id": item["question_id"],
                                                            "action": "MERGE_VARIANT", "note": "同一个问题"})
        self.assertEqual((code, saved["remaining"]), (200, 0))
        self.assertEqual(self.request("/api/dedupe-reviews")[1]["items"][0]["decision"]["action"], "MERGE_VARIANT")
        resolved = self.bank.result("dedupe", "--resolve", item["run_id"])
        self.assertEqual((resolved["review"], resolved["replaces"]), ([], item["run_id"]))
        self.bank.result("commit", "--run", resolved["run_id"])
        self.assertEqual(self.bank.result("search")["questions"][0]["frequency"], 2)
        self.assertEqual(self.request("/api/dedupe-reviews")[1]["items"], [])

    def test_refusals(self):
        item = self.request("/api/dedupe-reviews")[1]["items"][0]
        bad = {"run_id": item["run_id"], "question_id": item["question_id"], "action": "MERGE_EXACT", "note": "x"}
        self.assertEqual(self.request("/api/dedupe-decision", bad)[0], 400)
        self.assertEqual(self.request("/api/dedupe-decision", {**bad, "action": "KEEP_DISTINCT", "note": " "})[0], 400)
        proc = self.bank.cli("dedupe", "--resolve", item["run_id"], check=False)
        self.assertIn("No decisions recorded", json.loads(proc.stderr)["error"])

    def test_localhost_is_accepted_and_other_hosts_are_not(self):
        port = self.server.server_port
        self.assertEqual(self.request("/api/library", host=f"localhost:{port}")[0], 200)
        self.assertEqual(self.request("/api/library", host=f"evil.example:{port}")[0], 403)


if __name__ == "__main__":
    unittest.main()
