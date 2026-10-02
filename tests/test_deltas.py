"""Run format 2: change sets reproduce, invert and replace full snapshots exactly."""
import copy
import json
import os
import random
import shutil
import unittest
from pathlib import Path
from unittest import mock

from support import Bank, sourced_answer
from test_foundation import BankFixture
from ibank_core import deltas, runs, storage
from ibank_core.errors import ValidationError
from ibank_core.schema import TABLES


def row(table, key, **extra):
    return {"id": f"{table[:1]}_{key}", "v": extra.get("v", 0), **extra}


def random_generation(rng, base):
    """Mutate a generation the way operations do: append, edit, delete; never reorder survivors."""
    final = copy.deepcopy(base)
    for table in TABLES:
        rows = [r for r in final[table] if rng.random() > 0.2]
        for r in rows:
            if rng.random() < 0.3:
                r["v"] += 1
        for _ in range(rng.randrange(3)):
            rows.insert(rng.randrange(len(rows) + 1), row(table, f"n{rng.randrange(10**9)}"))
        final[table] = rows
    state = final["_state"]
    state["events"] = {k: v for k, v in state["events"].items() if rng.random() > 0.2}
    state["events"][f"event_{rng.randrange(10**9)}"] = {"rating": "good"}
    if rng.random() < 0.3:
        state["version"] = 3
    return final


class DeltaEngine(unittest.TestCase):
    def base(self):
        data = {table: [row(table, str(i)) for i in range(5)] for table in TABLES}
        data["_state"] = {"version": 2, "events": {f"event_{i}": {"rating": "again"} for i in range(3)}, "policies": {}}
        return data

    def test_round_trip_on_random_generations(self):
        rng = random.Random(20261002)
        for _ in range(200):
            current = self.base()
            final = random_generation(rng, current)
            changes = deltas.diff(current, final)
            self.assertIsNotNone(changes)
            # JSON round trip: what is written to disk must still apply.
            changes = json.loads(json.dumps(changes))
            self.assertEqual(deltas.apply(current, changes), final)
            self.assertEqual(deltas.apply(final, deltas.invert(changes)), current)

    def test_unchanged_generation_has_no_changes(self):
        self.assertEqual(deltas.diff(self.base(), self.base()), [])

    def test_reordered_survivors_force_a_full_snapshot(self):
        current = self.base()
        final = copy.deepcopy(current)
        final["questions"].reverse()
        self.assertIsNone(deltas.diff(current, final))

    def test_duplicate_ids_and_state_appearing_force_a_full_snapshot(self):
        current = self.base()
        final = copy.deepcopy(current)
        final["answers"].append(copy.deepcopy(final["answers"][0]))
        self.assertIsNone(deltas.diff(current, final))
        without_state = {t: current[t] for t in TABLES}
        self.assertIsNone(deltas.diff(without_state, current))

    def test_stale_before_image_is_refused(self):
        current = self.base()
        final = copy.deepcopy(current)
        final["questions"][1]["v"] = 9
        changes = deltas.diff(current, final)
        moved = copy.deepcopy(current)
        moved["questions"][1]["v"] = 5
        with self.assertRaises(ValidationError):
            deltas.apply(moved, changes)

    def test_shape_validation(self):
        with self.assertRaises(ValidationError):
            deltas.validate_changes([{"table": "questions", "op": "insert", "id": "q_1", "after": {}}])
        with self.assertRaises(ValidationError):
            deltas.validate_changes([{"table": "nope", "op": "update", "id": "x", "before": {}, "after": {}}])


class RunFormat(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.bank.add_questions("backend.cache", "Redis 为什么快？", "Redis 持久化有哪些方式？", "缓存穿透是什么？")

    def tearDown(self):
        self.bank.close()

    def answer_batch(self, env=None):
        task = self.bank.result("research", "--limit", "3")
        answers = [sourced_answer(item["question"]["id"], "2026-09-30") for item in task["items"]]
        proc = self.bank.cli("answer", payload={"schema_version": 1, "task_id": task["id"], "answers": answers}, env=env)
        return json.loads(proc.stdout)["result"]["run_id"]

    def test_snapshot_stage_stores_only_the_change_set(self):
        run_id = self.answer_batch()
        path = self.bank.path / "runs" / run_id
        meta = json.loads((path / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["format"], 2)
        self.assertEqual(sorted(p.name for p in path.iterdir()), ["changes.jsonl", "run.json"])
        changes = [json.loads(line) for line in (path / "changes.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual({(c["table"], c["op"]) for c in changes}, {("answers", "insert")})
        self.bank.result("commit", "--run", run_id)
        self.assertEqual(self.bank.result("search", "--answer-status", "source_backed")["total"], 3)

    def test_environment_forces_full_snapshots(self):
        run_id = self.answer_batch(env={**os.environ, "INTERVIEW_BANK_RUN_FORMAT": "1"})
        path = self.bank.path / "runs" / run_id
        self.assertTrue((path / "before.json").is_file())
        self.assertNotIn("format", json.loads((path / "run.json").read_text(encoding="utf-8")))

    def test_undo_restores_byte_identical_data(self):
        before = {p.name: p.read_bytes() for p in (self.bank.path / "data").iterdir()}
        run_id = self.answer_batch()
        self.bank.result("commit", "--run", run_id)
        undo = self.bank.result("undo", "--run", run_id)
        self.assertTrue((self.bank.path / "runs" / undo["run_id"] / "changes.jsonl").is_file())
        self.bank.result("commit", "--run", undo["run_id"])
        self.assertEqual({p.name: p.read_bytes() for p in (self.bank.path / "data").iterdir()}, before)

    def test_format_one_runs_stay_undoable_after_upgrade(self):
        run_id = self.answer_batch(env={**os.environ, "INTERVIEW_BANK_RUN_FORMAT": "1"})
        self.bank.result("commit", "--run", run_id)
        undo = self.bank.result("undo", "--run", run_id)
        self.bank.result("commit", "--run", undo["run_id"])
        self.assertEqual(self.bank.result("search", "--answer-status", "source_backed")["total"], 0)

    def test_edited_change_set_is_refused(self):
        run_id = self.answer_batch()
        path = self.bank.path / "runs" / run_id / "changes.jsonl"
        path.write_text(path.read_text(encoding="utf-8").replace("基于内存", "基于磁盘"), encoding="utf-8")
        proc = self.bank.cli("commit", "--run", run_id, check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Staged files changed", proc.stderr)

    def test_answer_batch_growth_does_not_scale_with_the_bank(self):
        source = self.bank.root / "many.txt"
        source.write_text("".join(f"Redis 的原理与实现细节是什么？（变体 {i}）\n" for i in range(300)), encoding="utf-8")
        self.bank.stage_commit("stage", "--text", str(source), "--domain", "backend.cache")
        run_id = self.answer_batch()
        size = sum(p.stat().st_size for p in (self.bank.path / "runs" / run_id).iterdir())
        self.assertLess(size, 64 * 1024)
        self.assertLess(size * 20, sum(p.stat().st_size for p in (self.bank.path / "data").iterdir()))

    def test_commit_rewrites_only_changed_tables(self):
        run_id = self.answer_batch()
        stamp = {p.name: p.stat().st_mtime_ns for p in (self.bank.path / "data").iterdir()}
        self.bank.result("commit", "--run", run_id)
        changed = {p.name for p in (self.bank.path / "data").iterdir() if p.stat().st_mtime_ns != stamp[p.name]}
        self.assertEqual(changed, {"answers.jsonl"})


class Equivalence(unittest.TestCase):
    """The same staged generation committed through format 1 and format 2 yields identical bytes."""

    def setUp(self):
        self.bank = Bank()
        self.bank.add_questions("backend.cache", "Redis 为什么快？", "Redis 持久化有哪些方式？")
        self.bank.result("migrate", "apply")

    def tearDown(self):
        self.bank.close()

    def commit_in(self, path, mutate, run_format):
        with mock.patch.dict(os.environ, {"INTERVIEW_BANK_RUN_FORMAT": run_format}):
            with storage.open_bank(path) as (_, config, current):
                final = copy.deepcopy(current)
                mutate(final)
                staged = runs.stage_snapshot(path, current, final, config, operation="curate")
            runs.commit_run(path, staged["run_id"])
            return staged["run_id"]

    def snapshot(self, path):
        return {p.name: p.read_bytes() for p in sorted((path / "data").iterdir())}

    def check(self, mutate):
        copies = {}
        for run_format in ("1", "2"):
            target = self.bank.root / f"copy-{run_format}"
            shutil.copytree(self.bank.path, target)
            run_id = self.commit_in(target, mutate, run_format)
            meta = json.loads((target / "runs" / run_id / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(meta.get("format", 1), int(run_format))
            copies[run_format] = self.snapshot(target)
        self.assertEqual(copies["1"], copies["2"])

    def test_edit_question(self):
        def mutate(data):
            data["questions"][0]["difficulty"] = "hard"
        self.check(mutate)

    def test_delete_and_insert_relation(self):
        def mutate(data):
            first, second = data["questions"][0]["id"], data["questions"][1]["id"]
            data["relations"].append({"schema_version": 1, "id": "rel_test", "from_question_id": first,
                                      "to_question_id": second, "type": "related", "confidence": 0.9,
                                      "created_at": "2026-10-02T00:00:00+00:00"})
        self.check(mutate)

    def test_state_change(self):
        def mutate(data):
            data["_state"]["studysets"]["set_test"] = {"id": "set_test"}
        with mock.patch("ibank_core.runs.validate_data"):
            self.check(mutate)


class SnapshotImportMergeUndo(BankFixture):
    """Undoing a merge replays a format-2 import stage onto the merge's before-image."""

    def test_merge_undo_keeps_a_snapshot_import(self):
        from ibank_core.dedupe import candidate_task, stage_decisions
        from ibank_core.normalize import normalize_question_text
        self.seed()
        with storage.open_bank(self.bank) as (_, config, current):
            final = copy.deepcopy(current)
            title = "Redis 为什么性能高？"
            final["questions"].append({**self.bundle["questions"][1], "id": "q_new", "canonical": title,
                                       "normalized": normalize_question_text(title)})
            final["occurrences"].append({**self.bundle["occurrences"][1], "id": "occ_new", "question_id": "q_new", "sequence": 5})
            imported = runs.stage_snapshot(self.bank, current, final, config, operation="image-ingest")
        meta = json.loads((Path(self.bank) / "runs" / imported["run_id"] / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["format"], 2)
        task = candidate_task(self.bank, imported["run_id"])
        merged = stage_decisions(self.bank, task_id=task["id"])
        runs.commit_run(self.bank, merged["run_id"])
        undone = runs.undo_run(self.bank, merged["run_id"])
        self.assertEqual(undone["summary"]["undo_scope"], "dedupe_only_preserve_import")
        runs.commit_run(self.bank, undone["run_id"])
        restored = storage.load_data(self.bank)
        self.assertEqual(next(q for q in restored["questions"] if q["id"] == "q_new")["status"], "active")
        self.assertEqual(next(o for o in restored["occurrences"] if o["id"] == "occ_new")["question_id"], "q_new")


if __name__ == "__main__":
    unittest.main()
