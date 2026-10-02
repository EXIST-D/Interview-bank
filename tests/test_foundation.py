import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "skills/interview-bank/scripts"), str(ROOT / "tools")]
from demo_data import make_bundle
from ibank_core import ids, storage
from ibank_core.doctor import doctor
from ibank_core.errors import ValidationError
from ibank_core.index import rebuild_index
from ibank_core.locking import bank_lock
from ibank_core.normalize import normalize_company_alias, normalize_question_text, normalize_technology
from ibank_core.runs import commit_run, stage_bundle, stage_text
from ibank_core.schema import TABLES, validate_manifest, validate_record, validate_run
from ibank_core.search import search
from ibank_core.stats import stats

CLI = ROOT / "skills/interview-bank/scripts/ibank.py"


class BankFixture(unittest.TestCase):
    def setUp(self):
        work = ROOT / ".work/tests"
        work.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=work)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.bank = self.base / "bank"
        storage.initialize(self.bank)
        self.bundle = make_bundle(self.base)

    def seed(self, bundle=None):
        staged = stage_bundle(self.bank, bundle or self.bundle)
        return commit_run(self.bank, staged["run_id"])

    def cli(self, *argv):
        env = {**os.environ, "TEMP": str(ROOT / ".work"), "TMP": str(ROOT / ".work"), "PYTHONDONTWRITEBYTECODE": "1"}
        return subprocess.run([sys.executable, "-B", str(CLI), *argv, "--bank", str(self.bank), "--json"],
                              cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")


class BankCase(BankFixture):
    def test_init_is_idempotent_and_preserves_manifest(self):
        before = (self.bank / "manifest.json").read_bytes()
        self.assertFalse(storage.initialize(self.bank))
        self.assertEqual(before, (self.bank / "manifest.json").read_bytes())
        self.assertEqual(set(storage.load_data(self.bank)), set(TABLES))

    def test_init_refuses_unrelated_directory(self):
        with self.assertRaises(ValidationError):
            storage.initialize(self.base)
        self.assertTrue((self.base / "mock-source.txt").exists())

    def test_ids_unique_with_prefixes(self):
        for kind in ("question", "occurrence", "source", "answer", "relation", "company", "run"):
            values = {getattr(ids, f"new_{kind}_id")() for _ in range(1000)}
            self.assertEqual(len(values), 1000)

    def test_conservative_normalization(self):
        self.assertEqual(normalize_question_text(" 1. 问：Ｒｅｄｉｓ 持久化？？ "), "redis持久化")
        for a, b in [("B+树", "B树"), ("C++", "C"), ("C#", "C"), ("Redis 6.0", "Redis 60"),
                     ("a b", "ab"), ("x != y", "x = y")]:
            self.assertNotEqual(normalize_question_text(a), normalize_question_text(b))
        self.assertEqual(normalize_technology(" K8S "), "kubernetes")
        self.assertEqual(normalize_company_alias(" ＢｙｔｅＤａｎｃｅ "), "bytedance")

    def test_stage_does_not_mutate_canonical_and_commit_is_idempotent(self):
        staged = stage_bundle(self.bank, self.bundle)
        self.assertEqual(len(storage.load_data(self.bank)["questions"]), 0)
        result = commit_run(self.bank, staged["run_id"])
        self.assertEqual(result["counts"]["questions"], 3)
        again = commit_run(self.bank, staged["run_id"])
        self.assertTrue(again["already_committed"])
        self.assertEqual(len(storage.load_data(self.bank)["occurrences"]), 4)
        self.assertTrue((self.bank / "runs" / staged["run_id"] / "report.md").is_file())

    def test_text_source_hash_original_and_duplicate_reimport(self):
        text = self.base / "questions.txt"
        text.write_text("  Redis 为什么快？  \n\nC++ 与 C 的区别？\n", encoding="utf-8")
        first = stage_text(self.bank, text, roles=["backend"], technologies=["Redis"], company="字节")
        commit_run(self.bank, first["run_id"])
        data = storage.load_data(self.bank)
        self.assertEqual(data["occurrences"][0]["original_text"], "  Redis 为什么快？  ")
        self.assertEqual(data["sources"][0]["sha256"], hashlib.sha256(text.read_bytes()).hexdigest())
        second = stage_text(self.bank, text)
        self.assertEqual(second["duplicate_sources"], 1)
        commit_run(self.bank, second["run_id"])
        self.assertEqual(len(storage.load_data(self.bank)["questions"]), 2)

    def test_retention_none_does_not_store_path(self):
        staged = stage_text(self.bank, self.base / "mock-source.txt", retention="none")
        commit_run(self.bank, staged["run_id"])
        self.assertIsNone(storage.load_data(self.bank)["sources"][0]["path"])

    def test_bad_foreign_key_and_duplicate_id(self):
        for mutate in (lambda b: b["occurrences"][0].update(source_id="src_absent"),
                       lambda b: b["questions"].append(copy.deepcopy(b["questions"][0]))):
            bundle = copy.deepcopy(self.bundle)
            mutate(bundle)
            with self.assertRaises(ValidationError):
                stage_bundle(self.bank, bundle)
        self.assertFalse(storage.load_data(self.bank)["questions"])

    def test_required_fields_enums_types_and_unsupported_version(self):
        for key, value in [("canonical", ""), ("schema_version", 2), ("schema_version", True),
                           ("difficulty", "extreme"), ("role_tracks", ["invented"]), ("domains", ["invented"]),
                           ("technologies", ["JS"]), ("normalized", "wrong")]:
            with self.subTest(key=key, value=value):
                q = {**self.bundle["questions"][0], key: value}
                with self.assertRaises(ValidationError):
                    validate_record("questions", q)
        q = dict(self.bundle["questions"][0])
        del q["canonical"]
        with self.assertRaises(ValidationError):
            validate_record("questions", q)

    def test_provenance_required_for_active_questions(self):
        bundle = copy.deepcopy(self.bundle)
        bundle["occurrences"] = []
        with self.assertRaisesRegex(ValidationError, "provenance"):
            stage_bundle(self.bank, bundle)

    def test_merged_targets_and_occurrence_transfer(self):
        bundle = copy.deepcopy(self.bundle)
        bundle["questions"][0].update(status="merged", merged_into="q_demo1")
        with self.assertRaisesRegex(ValidationError, "merged question"):
            stage_bundle(self.bank, bundle)
        bundle["occurrences"][0]["question_id"] = "q_demo1"
        self.seed(bundle)
        self.assertEqual(search(self.bank)["total"], 2)
        self.assertEqual(len(storage.load_data(self.bank)["questions"]), 3)

    def test_merge_cycles_and_self_merges_rejected(self):
        for target in ("q_demo0", "q_missing"):
            bundle = copy.deepcopy(self.bundle)
            bundle["questions"][0].update(status="merged", merged_into=target)
            with self.assertRaises(ValidationError):
                stage_bundle(self.bank, bundle)

    def test_follow_up_order_and_invalid_confidence(self):
        bundle = copy.deepcopy(self.bundle)
        bundle["occurrences"][1]["parent_occurrence_id"] = "occ_demo0"
        stage_bundle(self.bank, bundle)
        bundle["occurrences"][0]["parent_occurrence_id"] = "occ_demo1"
        with self.assertRaisesRegex(ValidationError, "precede"):
            stage_bundle(self.bank, bundle)
        for value in (float("nan"), 1.2, True, "1"):
            occ = {**self.bundle["occurrences"][0], "extraction_confidence": value}
            with self.assertRaises(ValidationError):
                validate_record("occurrences", occ)

    def test_duplicate_source_hash_and_ambiguous_company_alias(self):
        for table, record in [("sources", {**self.bundle["sources"][0], "id": "src_other"}),
                              ("companies", {**self.bundle["companies"][0], "id": "company_other"})]:
            bundle = copy.deepcopy(self.bundle)
            bundle[table].append(record)
            with self.assertRaises(ValidationError):
                stage_bundle(self.bank, bundle)

    def test_configured_taxonomy_extension(self):
        config = storage.read_json(self.bank / "config.json")
        config["taxonomy_extensions"]["domains"] = ["business.finance"]
        storage.atomic_write(self.bank / "config.json", storage.dumps(config))
        self.bundle["questions"][0]["domains"] = ["business.finance"]
        self.seed()
        self.assertEqual(search(self.bank, domain="business.finance")["total"], 1)

    def test_answer_versions_and_citation_requirements(self):
        answer = {"schema_version": 1, "id": "ans_demo", "question_id": "q_demo0", "version": 1,
            "status": "ai_draft", "short_answer": "示例", "spoken_answer": "", "key_points": [],
            "deep_dive": "", "interviewer_intent": "", "common_mistakes": [], "follow_up_questions": [],
            "code_example": None, "sources": [], "created_at": ids.utc_now(), "verified_at": None}
        self.bundle["answers"] = [answer]
        stage_bundle(self.bank, self.bundle)
        answer["status"] = "source_backed"
        with self.assertRaisesRegex(ValidationError, "citations"):
            stage_bundle(self.bank, self.bundle)
        answer["status"] = "ai_draft"
        self.bundle["answers"].append({**answer, "id": "ans_second"})
        with self.assertRaisesRegex(ValidationError, "duplicate answer version"):
            stage_bundle(self.bank, self.bundle)

    def test_manifest_and_run_validation(self):
        with self.assertRaises(ValidationError):
            validate_manifest({"schema_version": 99})
        with self.assertRaises(ValidationError):
            validate_run({"schema_version": 1, "id": "../escape"})

    def test_jsonl_unicode_bom_append_and_line_error(self):
        path = self.base / "test.jsonl"
        path.write_text('\ufeff{"text":"中文"}\n', encoding="utf-8")
        storage.append_jsonl(path, [{"text": "第二行"}])
        self.assertEqual(len(storage.read_jsonl(path)), 2)
        path.write_text('{"ok":true}\ninvalid\n', encoding="utf-8")
        with self.assertRaisesRegex(ValidationError, ":2:"):
            storage.read_jsonl(path)

    def test_failed_atomic_replace_preserves_previous_file(self):
        path = self.base / "atomic.jsonl"
        storage.write_jsonl_atomic(path, [{"n": 1}])
        with patch.object(storage.os, "replace", side_effect=OSError("simulated failure")):
            with self.assertRaises(OSError):
                storage.write_jsonl_atomic(path, [{"n": 2}])
        self.assertEqual(storage.read_jsonl(path), [{"n": 1}])
        self.assertFalse(list(self.base.glob("*.tmp")))

    def test_interrupted_commit_recovers_and_retry_does_not_duplicate(self):
        run_id = stage_bundle(self.bank, self.bundle)["run_id"]
        original = storage.atomic_write
        writes = 0

        def interrupted(path, content):
            nonlocal writes
            writes += 1
            if writes == 4:
                raise OSError("simulated process interruption")
            return original(path, content)

        with patch.object(storage, "atomic_write", side_effect=interrupted):
            with self.assertRaises(OSError):
                commit_run(self.bank, run_id)
        self.assertTrue((self.bank / ".transaction.json").exists())
        result = commit_run(self.bank, run_id)
        self.assertTrue(result["already_committed"])
        self.assertEqual(stats(self.bank)["occurrences"], 4)
        self.assertFalse((self.bank / ".transaction.json").exists())

    def test_stage_tamper_and_stale_duplicate_rejected(self):
        first = stage_bundle(self.bank, self.bundle)["run_id"]
        second = stage_bundle(self.bank, self.bundle)["run_id"]
        self.seed()
        with self.assertRaisesRegex(ValidationError, "duplicate ID"):
            commit_run(self.bank, first)
        path = self.bank / "runs" / second / "questions.jsonl"
        storage.write_jsonl_atomic(path, [])
        with self.assertRaisesRegex(ValidationError, "changed"):
            commit_run(self.bank, second)

    def test_lock_conflict_across_processes_and_release(self):
        with bank_lock(self.bank):
            process = self.cli("validate")
            self.assertEqual(process.returncode, 4, process.stderr)
        self.assertEqual(self.cli("validate").returncode, 0)

    def test_path_resolution_precedence_and_skill_guard(self):
        with patch.dict(os.environ, {"INTERVIEW_BANK_HOME": str(self.bank)}):
            self.assertEqual(storage.resolve_bank(cwd=self.base), self.bank)
            self.assertEqual(storage.resolve_bank(str(self.base / "explicit")), self.base / "explicit")
        for path in (storage.SKILL_ROOT, storage.SKILL_ROOT / "data", storage.SKILL_ROOT.parent):
            with self.assertRaises(ValidationError):
                storage.guard_bank_path(path)
        with self.assertRaises(ValidationError):
            stage_bundle(self.bank, self.bundle, "../escape")

    def test_journal_cannot_write_outside_bank(self):
        journal = {"schema_version": 1, "files": {"../escaped.txt": "oops"}}
        storage.atomic_write(self.bank / ".transaction.json", storage.dumps(journal))
        with self.assertRaises(ValidationError):
            with storage.open_bank(self.bank):
                pass
        self.assertFalse((self.base / "escaped.txt").exists())

    def test_queries_need_no_cache_and_rebuild_index_is_retired(self):
        self.seed()
        cache = self.bank / "cache/bank.sqlite"
        self.assertEqual(search(self.bank, query="Redis")["total"], 1)
        self.assertFalse(cache.exists())
        cache.write_bytes(b"leftover cache from an older version")
        self.assertTrue(doctor(self.bank)["legacy_index_cache"])
        self.assertEqual(search(self.bank)["total"], 3)
        result = rebuild_index(self.bank)
        self.assertEqual((result["index"], result["deprecated"], result["legacy_cache_removed"]), ("not_used", True, True))
        self.assertFalse(cache.exists())
        self.assertFalse(doctor(self.bank)["legacy_index_cache"])

    def test_alias_keyword_and_same_occurrence_filters(self):
        self.seed()
        result = search(self.bank, query="MySQL 索引", company="ByteDance", role="backend", technology="mysql", round_name="technical-2")
        self.assertEqual(result["total"], 1)
        # Redis occurs at ByteDance round 2 and Meituan round 1, never ByteDance round 1.
        self.assertEqual(search(self.bank, query="Redis", company="字节", round_name="technical-1")["total"], 0)
        self.assertEqual(search(self.bank, query="' OR 1=1 --")["total"], 0)
        self.assertEqual(search(self.bank, role="frontend", technology="react")["total"], 1)

    def test_frequency_is_occurrences_not_canonical_count(self):
        self.seed()
        result = stats(self.bank)
        self.assertEqual((result["questions"], result["occurrences"]), (3, 4))
        self.assertEqual(result["top_questions"][0]["canonical"], "Redis 为什么性能高？")
        filtered = search(self.bank, query="Redis", company="字节")["questions"][0]
        self.assertEqual((filtered["frequency"], filtered["total_frequency"]), (1, 2))

    def test_thousand_questions_can_commit_validate_rebuild_search(self):
        bundle = make_bundle(self.base, count=1000)
        self.seed(bundle)
        self.assertEqual(doctor(self.bank)["counts"]["questions"], 1000)
        self.assertEqual(search(self.bank, query="示例题 1000")["total"], 1)
        self.assertEqual(stats(self.bank)["occurrences"], 1001)

    def test_cli_workflow_outputs_exit_codes_and_bytecode(self):
        for command in ("init", "doctor", "validate", "rebuild-index"):
            process = self.cli(command)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertTrue(json.loads(process.stdout)["ok"])
        process = self.cli("stage", "--text", str(self.base / "mock-source.txt"), "--role", "backend")
        self.assertEqual(process.returncode, 0, process.stderr)
        run_id = json.loads(process.stdout)["result"]["run_id"]
        self.assertEqual(self.cli("commit", "--run", run_id).returncode, 0)
        self.assertEqual(self.cli("search", "--query", "Redis").returncode, 0)
        self.assertEqual(self.cli("stats").returncode, 0)
        self.assertFalse(list(storage.SKILL_ROOT.rglob("__pycache__")))
        storage.atomic_write(self.bank / "data/questions.jsonl", "bad json\n")
        self.assertEqual(self.cli("validate").returncode, 2)

    def test_missing_bank_cli_exit_three(self):
        process = subprocess.run([sys.executable, "-B", str(CLI), "doctor", "--bank", str(self.base / "absent"), "--json"],
                                 capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.returncode, 3)
        self.assertEqual(json.loads(process.stderr)["code"], 3)

    def test_malformed_bundle_returns_validation_error_without_traceback(self):
        path = self.base / "invalid.json"
        path.write_text('{"schema_version":1,"questions":null}', encoding="utf-8")
        process = self.cli("stage", "--input", str(path))
        self.assertEqual(process.returncode, 2)
        self.assertEqual(json.loads(process.stderr)["code"], 2)

    def test_process_exit_releases_os_lock(self):
        code = ("import sys; from pathlib import Path; "
                "sys.path.insert(0, sys.argv[1]); "
                "from ibank_core.locking import bank_lock; "
                "lock = bank_lock(Path(sys.argv[2])); lock.__enter__(); "
                "print('LOCKED', flush=True); input()")
        child = subprocess.Popen([sys.executable, "-B", "-c", code, str(CLI.parent), str(self.bank)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), "LOCKED")
            self.assertEqual(self.cli("validate").returncode, 4)
            child.terminate()
            child.wait(timeout=10)
            self.assertEqual(self.cli("validate").returncode, 0)
        finally:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=10)

    def test_missing_source_is_reported_without_dropping_provenance(self):
        self.seed()
        (self.base / "mock-source.txt").unlink()
        self.assertEqual(doctor(self.bank)["missing_source_files"], ["src_demo"])
        self.assertEqual(search(self.bank)["total"], 3)


if __name__ == "__main__":
    unittest.main()
