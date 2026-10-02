"""backup create / verify / restore: verified archives that restore only into a new directory."""
import json
import unittest
import zipfile
from pathlib import Path

from support import SKILL, Bank, sourced_answer
from ibank_core.storage import load_bank


class Backups(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.bank.add_questions("backend.cache", "Redis 为什么快？", "Redis 持久化有哪些方式？")
        task = self.bank.result("research", "--limit", "1")
        answer = sourced_answer(task["items"][0]["question"]["id"], "2026-09-30")
        staged = self.bank.result("answer", payload={"schema_version": 1, "task_id": task["id"], "answers": [answer]})
        self.bank.result("commit", "--run", staged["run_id"])

    def tearDown(self):
        self.bank.close()

    def create(self, *args):
        return self.bank.result("backup", "create", *args)

    def names(self, archive):
        with zipfile.ZipFile(archive) as handle:
            return handle.namelist()

    def test_create_archives_only_the_canonical_bank(self):
        created = self.create()
        names = self.names(created["archive"])
        self.assertIn("manifest.json", names)
        self.assertIn("data/answers.jsonl", names)
        self.assertFalse([n for n in names if n.startswith(("runs/", "cache/", "backups/", "exports/"))])
        self.assertTrue(Path(created["archive"]).with_suffix(".zip.sha256").is_file())
        self.assertEqual(created["counts"]["answers"], 1)
        with_runs = self.create("--include-runs")
        self.assertTrue([n for n in self.names(with_runs["archive"]) if n.startswith("runs/")])

    def test_verify_and_restore_into_a_new_directory(self):
        created = self.create()
        verified = self.bank.result("backup", "verify", "--archive", Path(created["archive"]).name)
        self.assertTrue(verified["valid"] and verified["sidecar_checked"])
        self.assertEqual(verified["counts"]["questions"], 2)
        target = self.bank.root / "restored-bank"
        restored = self.bank.result("backup", "restore", "--archive", created["archive"], "--destination", str(target))
        self.assertEqual(Path(restored["restored_bank"]), target.resolve())
        manifest, _, data = load_bank(target)
        self.assertEqual((len(data["questions"]), len(data["answers"])), (2, 1))
        self.assertTrue((target / "runs").is_dir())
        self.assertFalse([p for p in target.parent.iterdir() if ".restore-" in p.name])
        again = self.bank.cli("backup", "restore", "--archive", created["archive"], "--destination", str(target), check=False)
        self.assertEqual(again.returncode, 2)
        self.assertIn("must not exist", json.loads(again.stderr)["error"])

    def test_tampered_archives_are_refused(self):
        archive = Path(self.create()["archive"])
        with zipfile.ZipFile(archive, "a") as handle:
            handle.writestr("unlisted.txt", "unexpected")
        proc = self.bank.cli("backup", "verify", "--archive", str(archive), check=False)
        self.assertIn("entry mismatch", json.loads(proc.stderr)["error"])
        clean = Path(self.create()["archive"])
        clean.with_suffix(".zip.sha256").write_text("0" * 64 + "\n", encoding="utf-8")
        proc = self.bank.cli("backup", "restore", "--archive", str(clean), "--destination", str(self.bank.root / "x"), check=False)
        self.assertIn("sidecar", json.loads(proc.stderr)["error"])
        self.assertFalse((self.bank.root / "x").exists())

    def test_restore_refuses_the_skill_directory(self):
        archive = self.create()["archive"]
        proc = self.bank.cli("backup", "restore", "--archive", archive, "--destination", str(SKILL / "restored"), check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse((SKILL / "restored").exists())


if __name__ == "__main__":
    unittest.main()
