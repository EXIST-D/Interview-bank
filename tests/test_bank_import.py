"""export-bundle / import-bundle: carry the questions of one bank into another as text, then dedupe."""
import json
import unittest

from support import Bank


def add_post(bank, name, url, questions, *, company="示例科技", merge=None, concepts=None):
    """A web post with the given questions committed into the bank, with company and round metadata."""
    page = bank.root / f"{name}.txt"
    page.write_text("面经\n\n" + "\n\n".join(f"{i}. {q}" for i, q in enumerate(questions, start=1)) + "\n", encoding="utf-8")
    intake = bank.result("web-intake", "--url", url, "--text", str(page))
    source_id = intake["items"][0]["source_id"]
    count = len(questions) + 1
    extraction = {"schema_version": 1, "sources": [{
        "source_id": source_id, "status": "extracted", "reviewed_segment_ids": list(range(1, count + 1)),
        "metadata": {"platform": "牛客", "source_url": url, "source_date": "2026-10-20", "company": {"name": company},
                     "role_tracks": ["backend.java"], "round": "technical-1", "interview_type": "intern"},
        "questions": [{"id": f"{name}-{i}", "sequence": i, "original_text": text, "segment_ids": [i + 1], "reviewed": True,
                       "correction": "去掉列表序号", "domains": ["backend.cache"],
                       "confidence": {"is_question": 1, "classification": 0.9},
                       **({"concept": concepts[text]} if concepts and text in concepts else {})} for i, text in enumerate(questions, start=1)]}]}
    path = bank.root / f"{name}.json"
    path.write_text(json.dumps(extraction, ensure_ascii=False), encoding="utf-8")
    submitted = bank.result("ingest", "submit", "--intake", intake["id"], "--extraction", str(path))
    task = submitted["dedupe"]["task_id"]
    decisions = bank.root / f"{name}-decisions.json"
    rows = []
    for position, target in (merge or {}).items():
        found = bank.result("search", "--query", target, "--limit", "5")["questions"]
        rows.append({"question_id": f"n{position}", "action": "MERGE_VARIANT", "confidence": 0.95, "reason": "同一道题",
                     "target_id": next(q["id"] for q in found if q["canonical"] == target)})
    decisions.write_text(json.dumps({"task_id": task, "default_action": "KEEP_DISTINCT", "decisions": rows}), encoding="utf-8")
    assert bank.result("ingest", "finalize", "--task", task, "--decisions", str(decisions))["committed"]


class BundleTest(unittest.TestCase):
    def setUp(self):
        self.source, self.target = Bank(), Bank()
        add_post(self.source, "a", "https://example.org/posts/a", ["Redis 为什么快？", "MySQL 索引为什么用 B+ 树？"])
        add_post(self.target, "t", "https://example.org/posts/t", ["Redis 为什么快？", "什么是 TCP 三次握手？"])
        self.bundle_path = self.source.root / "bundle.json"
        self.source.result("export-bundle", "--output", str(self.bundle_path))
        self.bundle = json.loads(self.bundle_path.read_text(encoding="utf-8"))

    def tearDown(self):
        self.source.close()
        self.target.close()

    def test_the_bundle_is_text_only_with_one_source_per_post(self):
        tables = self.bundle["bundle"]
        self.assertEqual(self.bundle["counts"], {"questions": 2, "occurrences": 2, "sources": 1, "companies": 1, "relations": 0, "merged_wordings": 0})
        self.assertNotIn("answers", tables)
        (source,) = tables["sources"]
        self.assertEqual((source["type"], source["retention"], source["path"], source["source_url"], source["platform"]),
                         ("web", "none", None, "https://example.org/posts/a", "牛客"))
        self.assertEqual(len(source["sha256"]), 64)
        for occurrence in tables["occurrences"]:
            self.assertNotIn("locator", occurrence)
            self.assertEqual((occurrence["round"], occurrence["interview_type"], occurrence["role_tracks"]),
                             ("technical-1", "intern", ["backend.java"]))
        self.assertEqual(sorted(o["sequence"] for o in tables["occurrences"]), [1, 2])

    def test_dry_run_reports_and_writes_nothing(self):
        before = self.target.result("stats")["questions"]
        report = self.target.result("import-bundle", "--input", str(self.bundle_path), "--dry-run")
        self.assertEqual(report["status"], "dry_run")
        self.assertEqual((report["report"]["new_questions"], report["report"]["new_sources"], report["report"]["reused_companies"]),
                         (2, 1, 1))
        self.assertEqual(report["report"]["new_companies"], [])
        self.assertEqual(self.target.result("stats")["questions"], before)

    def test_wordings_merged_in_the_source_travel_with_their_question(self):
        add_post(self.source, "b", "https://example.org/posts/b", ["为什么 Redis 这么快？"], merge={1: "Redis 为什么快？"})
        wrapper = self.source.result("export-bundle", "--output", str(self.source.root / "merged.json"))
        self.assertEqual((wrapper["counts"]["questions"], wrapper["counts"]["merged_wordings"]), (3, 1))
        report = self.target.result("import-bundle", "--input", str(self.source.root / "merged.json"), "--dry-run")["report"]
        self.assertEqual((report["new_questions"], report["new_merged_wordings"], report["new_occurrences"]), (2, 1, 3))
        staged = self.target.result("import-bundle", "--input", str(self.source.root / "merged.json"))
        task = staged["dedupe"]["task_id"]
        decisions = self.target.root / "merged-decisions.json"
        decisions.write_text(json.dumps({"task_id": task, "default_action": "KEEP_DISTINCT", "decisions": []}), encoding="utf-8")
        self.assertTrue(self.target.result("ingest", "finalize", "--task", task, "--decisions", str(decisions))["committed"])
        self.assertEqual(self.target.result("validate")["valid"], True)
        redis = next(q for q in self.target.result("search", "--detail", "--limit", "50")["questions"]
                     if q["canonical"] == "Redis 为什么快？" and len(q["occurrences"]) == 2)
        self.assertEqual(len(self.target.result("show", redis["id"])["merged_variants"]), 1)

    def test_publish_dates_can_stand_in_for_missing_interview_dates(self):
        plain = self.target.result("import-bundle", "--input", str(self.bundle_path), "--dry-run")["report"]
        self.assertEqual((plain["event_dates_filled_from_publish_date"], plain["years"]), (0, {"unknown": 2}))
        with self.assertRaises(AssertionError):
            self.target.result("import-bundle", "--input", str(self.bundle_path), "--dry-run", "--fill-event-date", "week")
        report = self.target.result("import-bundle", "--input", str(self.bundle_path), "--dry-run", "--fill-event-date", "month")["report"]
        self.assertEqual((report["event_dates_filled_from_publish_date"], report["years"]), (2, {"2026": 2}))
        staged = self.target.result("import-bundle", "--input", str(self.bundle_path), "--fill-event-date", "month")
        task = staged["dedupe"]["task_id"]
        decisions = self.target.root / "fill-decisions.json"
        decisions.write_text(json.dumps({"task_id": task, "default_action": "KEEP_DISTINCT", "decisions": []}), encoding="utf-8")
        self.assertTrue(self.target.result("ingest", "finalize", "--task", task, "--decisions", str(decisions))["committed"])
        dates = {q["canonical"]: [o["event_date"] for o in q["occurrences"]]
                 for q in self.target.result("search", "--detail", "--limit", "50")["questions"]}
        self.assertEqual(dates["MySQL 索引为什么用 B+ 树？"], ["2026-10"])
        self.assertEqual(self.target.result("search", "--date-from", "2026-10", "--date-to", "2026-10")["total"], 2)

    def test_import_stages_new_questions_and_dedupe_decides_the_merge(self):
        staged = self.target.result("import-bundle", "--input", str(self.bundle_path))
        self.assertEqual(staged["status"], "dedupe_pending")
        self.assertEqual(staged["dedupe"]["exact_matches"], 1)
        task = staged["dedupe"]["task_id"]
        refs = self.target.result("dedupe-candidates", "--run", staged["stage_run"])
        incoming = {q["canonical"]: q["id"] for q in self.bundle["bundle"]["questions"]}
        decisions = {"task_id": task, "default_action": "KEEP_DISTINCT", "decisions": [
            {"question_id": incoming["Redis 为什么快？"], "action": "MERGE_EXACT", "target_id": self.find("Redis 为什么快？", staged),
             "confidence": 1.0, "reason": "同一道题"}]}
        path = self.target.root / "decisions.json"
        path.write_text(json.dumps(decisions, ensure_ascii=False), encoding="utf-8")
        final = self.target.result("ingest", "finalize", "--task", task, "--decisions", str(path))
        self.assertTrue(final["committed"], refs)
        questions = {q["canonical"]: q for q in self.target.result("search", "--detail", "--limit", "50")["questions"]}
        self.assertEqual(len(questions["Redis 为什么快？"]["occurrences"]), 2, "the merged question gained the imported occurrence")
        self.assertEqual(len(questions["MySQL 索引为什么用 B+ 树？"]["occurrences"]), 1)
        self.assertEqual(self.target.result("validate")["valid"], True)
        urls = {s["source_url"] for s in self.target.result("sources")["sources"]}
        self.assertEqual(urls, {"https://example.org/posts/t", "https://example.org/posts/a"})

        again = self.target.result("import-bundle", "--input", str(self.bundle_path))
        self.assertEqual(again["status"], "nothing_new", "importing the same bundle twice adds nothing")

    def find(self, canonical, staged):
        view = self.target.result("search", "--query", canonical, "--limit", "5")
        return next(q["id"] for q in view["questions"] if q["canonical"] == canonical)

    def test_a_file_that_is_not_a_bundle_is_refused(self):
        path = self.target.root / "other.json"
        path.write_text(json.dumps({"hello": 1}), encoding="utf-8")
        self.assertEqual(self.target.cli("import-bundle", "--input", str(path), check=False).returncode, 2)


if __name__ == "__main__":
    unittest.main()
