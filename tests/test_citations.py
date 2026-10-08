"""Citation checks: evidence quotes against supplied page text, and an optional link check."""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from support import REDIS_FAQ, Bank, sourced_answer
from ibank_core.citations import verify_citations


class Pages(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, body=True):
        routes = {"/ok": 200, "/gone": 404, "/head-refused": 405}
        if self.path == "/moved":
            self.send_response(301)
            self.send_header("Location", "/ok")
            self.end_headers()
            return
        code = routes.get(self.path, 404)
        if self.path == "/head-refused" and self.command == "GET":
            code = 200
        self.send_response(code)
        self.send_header("Content-Length", "2")
        self.end_headers()
        if body:
            self.wfile.write(b"ok")

    def do_HEAD(self):
        self.reply(body=False)

    def do_GET(self):
        self.reply()


class EvidenceQuotes(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.bank.add_questions("backend.cache", "Redis 为什么快？")
        self.page = self.bank.root / "faq.txt"
        self.page.write_text("Redis is an in-memory   data store.\nIt is fast.", encoding="utf-8")
        (self.bank.root / "pages.json").write_text(json.dumps({REDIS_FAQ: "faq.txt"}), encoding="utf-8")

    def tearDown(self):
        self.bank.close()

    def stage(self, quote, pages=True):
        task = self.bank.result("research", "--limit", "1")
        answer = sourced_answer(task["items"][0]["question"]["id"], "2026-09-30")
        answer["sources"][0]["evidence_quote"] = quote
        args = ["answer"] + (["--page-texts", str(self.bank.root / "pages.json")] if pages else [])
        return self.bank.cli(*args, payload={"schema_version": 1, "task_id": task["id"], "answers": [answer]}, check=False)

    def committed_citation(self, proc):
        self.bank.result("commit", "--run", json.loads(proc.stdout)["result"]["run_id"])
        return self.bank.result("search", "--detail")["questions"][0]["answer"]["sources"][0]

    def test_quote_found_in_page_text_is_verified(self):
        proc = self.stage("redis is an IN-MEMORY data store")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.committed_citation(proc)["quote_verified"])

    def test_quote_missing_from_page_text_is_refused(self):
        proc = self.stage("Redis is a disk-first database")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("does not occur", json.loads(proc.stderr)["error"])

    def test_quote_without_page_text_is_kept_unverified(self):
        proc = self.stage("Redis is an in-memory data store.", pages=False)
        self.assertFalse(self.committed_citation(proc)["quote_verified"])


class LinkCheck(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Pages)
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        thread.start()
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close(), thread.join(timeout=2)))
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.bank = Bank()
        self.bank.add_questions("backend.cache", "Redis 为什么快？")
        task = self.bank.result("research", "--limit", "1")
        answer = sourced_answer(task["items"][0]["question"]["id"], "2026-09-30")
        urls = [self.base + path for path in ("/ok", "/gone", "/head-refused", "/moved")]
        answer["sources"] = [{**answer["sources"][0], "url": url, "title": url} for url in urls]
        answer["evidence"] = [{"key_point": 0, "source_urls": urls}]
        staged = self.bank.result("answer", payload={"schema_version": 1, "task_id": task["id"], "answers": [answer]})
        self.bank.result("commit", "--run", staged["run_id"])

    def tearDown(self):
        self.bank.close()

    def test_status_redirects_and_head_fallback(self):
        report = verify_citations(self.bank.path, allow_private=True)
        by_path = {r["url"].removeprefix(self.base): r for r in report["results"]}
        self.assertTrue(by_path["/ok"]["ok"])
        self.assertEqual((by_path["/gone"]["ok"], by_path["/gone"]["status"]), (False, 404))
        self.assertTrue(by_path["/head-refused"]["ok"])
        self.assertTrue(by_path["/moved"]["ok"] and by_path["/moved"]["final_url"].endswith("/ok"))
        self.assertEqual(report["broken"], 1)
        self.assertTrue((self.bank.path / "logs").is_dir())

    def test_loopback_targets_are_refused_by_default(self):
        report = verify_citations(self.bank.path)
        self.assertEqual(report["broken"], 4)
        self.assertTrue(all("not a public address" in r["error"] for r in report["results"]))


if __name__ == "__main__":
    unittest.main()


class Article(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        if self.path == "/old-link":
            self.send_response(301)
            self.send_header("Location", "/article")
            self.end_headers()
            return
        pages = {"/article": ("text/html; charset=utf-8", "<html><head><title>t</title><script>var x = 1;</script></head><body>"
                              "<nav>menu</nav><p>Redis is an <b>in-memory</b> data store &amp; it is fast.</p>"
                              "<style>p{}</style><li>RDB</li><li>AOF</li></body></html>"),
                 "/binary": ("image/png", "PNG")}
        if self.path not in pages:
            self.send_response(403)
            self.end_headers()
            return
        kind, body = pages[self.path]
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class PageText(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Article)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.bank.close()

    def test_saves_readable_text_and_reports_failures(self):
        from pathlib import Path
        from ibank_core.citations import page_texts
        result = page_texts(self.bank.path, [f"{self.base}/article", f"{self.base}/blocked", f"{self.base}/binary"], allow_private=True)
        self.assertEqual((result["saved"], result["failed"]), (1, 2))
        text = Path(result["results"][0]["path"]).read_text(encoding="utf-8")
        self.assertIn("Redis is an in-memory data store & it is fast.", text)
        self.assertNotIn("var x", text)
        self.assertNotIn("p{}", text)
        self.assertEqual(result["results"][1]["error"], "HTTP 403")
        mapping = json.loads(Path(result["page_texts"]).read_text(encoding="utf-8"))
        self.assertEqual(list(mapping), [f"{self.base}/article"])

    def test_redirects_are_flagged(self):
        from pathlib import Path
        from ibank_core.citations import page_texts
        result = page_texts(self.bank.path, [f"{self.base}/old-link"], allow_private=True)
        self.assertTrue(result["results"][0]["redirected"])
        self.assertEqual(result["redirected"], [f"{self.base}/old-link"])
        self.assertIn("redirected elsewhere", result["warning"])
        mapping = json.loads(Path(result["page_texts"]).read_text(encoding="utf-8"))
        self.assertEqual(mapping[f"{self.base}/old-link"], mapping[f"{self.base}/article"])

    def test_private_addresses_are_refused_by_default(self):
        from ibank_core.citations import page_texts
        result = page_texts(self.bank.path, [f"{self.base}/article"])
        self.assertEqual(result["results"][0]["error"], "refused: not a public address")
