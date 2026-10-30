"""`sources`: a read-only list of what the bank already imported, so a collector knows what not to send again."""
import json
import unittest

from support import Bank

URL = "https://example.org/posts/backend-interview"


class SourceList(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        page = self.bank.root / "page.txt"
        page.write_text("后端一面面经\n\n1. Redis 为什么快？\n\n2. MySQL 索引为什么用 B+ 树？\n", encoding="utf-8")
        self.intake = self.bank.result("web-intake", "--url", URL, "--text", str(page))
        self.source_id = self.intake["items"][0]["source_id"]

    def tearDown(self):
        self.bank.close()

    def extract(self):
        extraction = {"schema_version": 1, "sources": [{
            "source_id": self.source_id, "status": "extracted", "reviewed_segment_ids": [1, 2, 3],
            "questions": [{"id": "w1", "sequence": 1, "original_text": "Redis 为什么快？", "segment_ids": [2], "reviewed": True,
                           "correction": "去掉列表序号", "domains": ["backend.cache"],
                           "confidence": {"is_question": 1, "classification": 0.9}}]}]}
        path = self.bank.root / "extraction.json"
        path.write_text(json.dumps(extraction, ensure_ascii=False), encoding="utf-8")
        submitted = self.bank.result("ingest", "submit", "--intake", self.intake["id"], "--extraction", str(path))
        self.assertTrue(self.bank.result("ingest", "finalize", "--task", submitted["dedupe"]["task_id"])["committed"])

    def test_a_source_appears_once_it_is_committed_with_its_questions(self):
        self.assertEqual(self.bank.result("sources")["total"], 0, "an intake nobody committed from is not imported")
        self.extract()
        listed = self.bank.result("sources")
        self.assertEqual(listed["total"], 1)
        (row,) = listed["sources"]
        self.assertEqual((row["id"], row["type"], row["platform"], row["source_url"]), (self.source_id, "web", "example.org", URL))
        self.assertEqual((row["occurrences"], row["questions"], row["engine"]), (1, 1, "web-text"))

    def test_filters_and_paging(self):
        self.extract()
        self.assertEqual(self.bank.result("sources", "--url", URL)["total"], 1)
        self.assertEqual(self.bank.result("sources", "--url", URL + "/")["total"], 0, "--url is an exact match")
        self.assertEqual(self.bank.result("sources", "--query", "BACKEND-INTERVIEW")["total"], 1)
        self.assertEqual(self.bank.result("sources", "--query", "nothing-like-this")["total"], 0)
        self.assertEqual(self.bank.result("sources", "--platform", "example.org")["total"], 1)
        self.assertEqual(self.bank.result("sources", "--type", "image")["total"], 0)
        page = self.bank.result("sources", "--limit", "1", "--offset", "1")
        self.assertEqual((page["total"], page["offset"], page["sources"]), (1, 1, []))
        self.assertEqual(self.bank.cli("sources", "--limit", "0", check=False).returncode, 2)

    def test_the_output_fields_are_a_stable_contract(self):
        """A collector outside this repository reads these fields: within 1.x they are added to, never renamed or removed."""
        self.extract()
        listed = self.bank.result("sources")
        self.assertEqual(set(listed), {"total", "offset", "sources"})
        self.assertEqual(set(listed["sources"][0]), {"id", "type", "platform", "source_url", "source_date", "imported_at", "retention",
                                                      "engine", "model", "segments", "occurrences", "questions"})

    def test_it_is_read_only_and_hides_file_paths(self):
        self.extract()
        table = self.bank.path / "data" / "sources.jsonl"
        before = table.read_bytes()
        listed = self.bank.cli("sources").stdout
        self.assertEqual(table.read_bytes(), before)
        self.assertNotIn(str(self.bank.path), listed)
        self.assertNotIn('"path"', listed)


if __name__ == "__main__":
    unittest.main()
