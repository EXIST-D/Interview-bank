import csv
import json
from test_foundation import BankFixture
from ibank_core.export import export_bank
from ibank_core.search import search, detail
from ibank_core.stats import stats
from ibank_core.errors import ValidationError


class AnalyticsTests(BankFixture):
    def test_partial_dates_and_recent_frequency(self):
        self.seed()
        result = search(self.bank, query="Redis", date_from="2026-08-15", date_to="2026-08-20")
        self.assertEqual(result["questions"][0]["frequency"], 1)
        self.assertEqual(search(self.bank, recent_days=30, as_of="2026-09-05")["total"], 3)
        self.assertEqual(search(self.bank, date_from="2027")["total"], 0)
        with self.assertRaises(ValidationError):
            search(self.bank, date_from="2026-09", date_to="2026-08")
        self.assertEqual(stats(self.bank)["by_month"], {"2026-07": 1, "2026-08": 3})

    def test_detail_and_missing_answers(self):
        self.seed()
        self.assertEqual(search(self.bank, answer_status="missing")["total"], 3)
        self.assertEqual(detail(self.bank, "q_demo1")["question"]["total_frequency"], 2)
        self.assertEqual(search(self.bank, domain="backend")["total"], 2)
        self.assertEqual(len(search(self.bank, limit=1, offset=2)["questions"]), 1)

    def test_all_export_formats_and_no_path_leak(self):
        self.seed()
        for format in ("markdown", "json", "jsonl", "csv", "viewer"):
            with self.subTest(format=format):
                result = export_bank(self.bank, f"study.{format}", format, company="字节", technology="mysql")
                content = (self.bank / "exports" / f"study.{format}").read_text(encoding="utf-8-sig")
                self.assertEqual(result["questions"], 1)
                self.assertIn("MySQL", content)
                self.assertNotIn(str(self.base), content)
        payload = json.loads((self.bank / "exports/study.json").read_text(encoding="utf-8"))
        self.assertIsNone(payload["sources"][0]["path"])
        with self.assertRaises(ValidationError):
            export_bank(self.bank, "../data/questions.jsonl", "jsonl")

    def test_csv_formula_protection(self):
        from ibank_core.normalize import normalize_question_text
        q = self.bundle["questions"][0]
        q["canonical"] = '=HYPERLINK("https://example.com")'
        q["normalized"] = normalize_question_text(q["canonical"])
        self.seed()
        export_bank(self.bank, "formulas.csv", "csv")
        with (self.bank / "exports/formulas.csv").open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertTrue(next(r for r in rows if r["id"] == "q_demo0")["question"].startswith("'="))
