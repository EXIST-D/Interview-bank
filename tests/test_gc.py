"""gc compacts old run snapshots, keeps audit and undo, and changes nothing without --apply."""
import json
import unittest
from pathlib import Path

from support import Bank, sourced_answer


def tree_bytes(path):
    return sum(p.stat().st_size for p in Path(path).rglob("*") if p.is_file())


class GarbageCollection(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.import_run = self.bank.add_questions("backend.cache", "Redis 为什么快？", "Redis 持久化有哪些方式？")["run_id"]
        for _ in range(2):  # two answer batches -> two committed snapshot runs
            task = self.bank.result("research", "--limit", "2")
            answers = [sourced_answer(item["question"]["id"], "2026-09-30") for item in task["items"]]
            staged = self.bank.result("answer", payload={"schema_version": 1, "task_id": task["id"], "answers": answers})
            self.last = self.bank.result("commit", "--run", staged["run_id"])["run_id"]
        self.pending = self.bank.result("research", "--limit", "1")["id"]  # an unused task packet
        self.runs = self.bank.path / "runs"

    def tearDown(self):
        self.bank.close()

    def gc(self, *args):
        return self.bank.result("gc", "--keep-days", "0", "--keep-last", "0", *args)

    def test_dry_run_changes_nothing(self):
        before = tree_bytes(self.runs)
        plan = self.gc()
        self.assertEqual(plan["mode"], "dry-run")
        self.assertGreater(plan["reclaim_bytes"], 0)
        self.assertEqual(tree_bytes(self.runs), before)

    def test_apply_keeps_audit_undo_and_valid_data(self):
        plan = self.gc("--apply")
        self.assertLess(plan["runs_bytes_after"], plan["runs_bytes_before"])
        self.assertEqual(plan["kept"].get("latest undo point"), 1)
        compacted = {item["run_id"] for item in plan["compact"]}
        self.assertNotIn(self.last, compacted)
        for run_id in compacted:
            for name in ("run.json", "commit.json", "report.md"):
                self.assertTrue((self.runs / run_id / name).is_file(), (run_id, name))
            self.assertFalse((self.runs / run_id / "before.json").exists())
        self.assertIn(self.pending, {item["run_id"] for item in plan["delete_tasks"]})
        self.assertTrue(Path(plan["log"]).is_file())
        self.assertTrue(self.bank.result("validate")["valid"])
        # The latest operation is still undoable after compaction.
        undo = self.bank.result("undo", "--run", self.last)
        self.bank.result("commit", "--run", undo["run_id"])
        self.assertEqual(self.bank.result("search", "--answer-status", "source_backed")["total"], 2)

    def test_second_apply_reclaims_nothing_new(self):
        self.gc("--apply")
        again = self.gc("--apply")
        self.assertEqual((again["compact"], again["delete_tasks"]), ([], []))

    def test_defaults_keep_recent_work(self):
        plan = self.bank.result("gc")
        self.assertEqual((plan["compact"], plan["delete_tasks"]), ([], []))
        self.assertEqual(plan["policy"], {"keep_days": 30, "keep_last": 20})

    def test_compacted_run_cannot_seed_a_workflow(self):
        self.assertIn(self.import_run, {item["run_id"] for item in self.gc("--apply")["compact"]})
        self.bank.result("migrate", "apply")
        proc = self.bank.cli("workflow", "create", payload={"name": "old", "from_run": self.import_run}, check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("compacted by gc", json.loads(proc.stderr)["error"])


if __name__ == "__main__":
    unittest.main()
