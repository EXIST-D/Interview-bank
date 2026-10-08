"""Bounded CLI output: stdout fits the byte budget, full results stay retrievable, paging is lossless."""
import json
import os
import unittest
from pathlib import Path

from support import Bank

BUDGET = 8192


class OutputBudget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = Bank()
        questions = [f"Redis 的原理与实现细节是什么？（变体 {i}）" for i in range(200)]
        cls.bank.add_questions("backend.cache", *questions)
        cls.env = {**os.environ, "INTERVIEW_BANK_MAX_OUTPUT": str(BUDGET)}

    @classmethod
    def tearDownClass(cls):
        cls.bank.close()

    def run_json(self, *args):
        proc = self.bank.cli(*args, env=self.env)
        self.assertLessEqual(len(proc.stdout.encode("utf-8")), BUDGET + 200, args)  # envelope overhead
        return json.loads(proc.stdout)["result"]

    def test_large_results_are_paged_and_saved_whole(self):
        for args in (("classify",), ("search", "--limit", "200")):
            with self.subTest(command=args[0]):
                result = self.run_json(*args)
                page = result["_page"]
                self.assertLess(page["returned"], page["total"])
                full = json.loads(Path(page["full_output"]).read_text(encoding="utf-8"))
                self.assertEqual(len(full[page["field"]]), page["total"])

    def test_dedupe_candidates_preview_and_point_to_the_full_task(self):
        result = self.run_json("dedupe-candidates")
        self.assertLess(result["previewed"], result["incoming"])
        self.assertTrue(result["full_task"].startswith("run-show --run "))
        self.assertTrue(Path(result["review_sheet"]).is_file())

    def test_classification_reference_blocks_are_omitted_from_stdout_only(self):
        result = self.run_json("classify")
        self.assertNotIn("taxonomy", result)
        self.assertIn("taxonomy", result["_page"]["omitted_keys"])
        on_disk = json.loads((self.bank.path / "runs" / result["id"] / "task.json").read_text(encoding="utf-8"))
        self.assertIn("taxonomy", on_disk)

    def test_task_items_can_be_read_page_by_page(self):
        task = self.run_json("classify")
        seen, offset = [item["question"]["id"] for item in task["items"]], task["_page"]["next_offset"]
        while offset is not None:
            page = self.run_json("run-show", "--run", task["id"], "--offset", str(offset), "--limit", "20")
            seen += [item["question"]["id"] for item in page["items"]]
            offset = page["next_offset"]  # stays correct even when the page itself had to be trimmed
        self.assertEqual(len(seen), 200)
        self.assertEqual(len(set(seen)), 200)

    def test_small_results_are_untouched_and_compact(self):
        proc = self.bank.cli("doctor", env=self.env)
        self.assertNotIn("\n ", proc.stdout)
        self.assertNotIn("_page", json.loads(proc.stdout)["result"])
        self.assertIn("\n  ", self.bank.cli("doctor", "--pretty", env=self.env).stdout)


if __name__ == "__main__":
    unittest.main()
