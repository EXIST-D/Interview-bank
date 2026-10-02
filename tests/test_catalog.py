import csv
import io
import json
import subprocess
import sys

from test_foundation import BankFixture, CLI
from ibank_core.catalog import catalog_view, matches
from ibank_core.companies import list_companies
from ibank_core.curation import configure, stage_classification, stage_curate
from ibank_core.errors import ValidationError
from ibank_core.export import export_bank
from ibank_core.ingestion import intake_images, stage_extraction
from ibank_core.normalize import normalize_technology
from ibank_core.runs import commit_run, stage_text, undo_run
from ibank_core.search import search
from ibank_core.stats import stats
from ibank_core.storage import fingerprint, load_data
from ibank_core.tasks import classification_task


class CatalogTests(BankFixture):
    def text_import(self):
        path = self.base / "selected.txt"
        path.write_text("向量索引如何实现近邻搜索？\n", encoding="utf-8")
        run = stage_text(self.bank, path, roles=["Java后端", "backend.java"], domains=["向量数据库"], technologies=["Postgres", "pgvector"])
        commit_run(self.bank, run["run_id"])
        return load_data(self.bank)["questions"][0]

    def profile_import(self):
        path = self.base / "company.png"
        path.write_bytes(b"synthetic host-reviewed image")
        intake = intake_images(self.bank, [path])
        company = {"name": "测试银行甲", "aliases": ["Example Alpha"], "industries": ["银行"],
                   "company_type": "专业服务企业", "ownership": "民营", "business_models": ["ToB", "按量付费"],
                   "profile_evidence": "合成验收资料明确说明：民营银行，向企业客户提供按量付费的金融服务。"}
        response = {"schema_version": 1, "sources": [{"source_id": intake["items"][0]["source"]["id"], "status": "extracted",
            "metadata": {"company": company, "role_tracks": ["Java后端"]}, "questions": [{"id": "q1", "sequence": 1,
                "original_text": "如何保证支付重试幂等？", "domains": ["分布式事务"], "technologies": ["SpringBoot"],
                "confidence": {"is_question": 0.99, "classification": 0.99}}]}]}
        commit_run(self.bank, stage_extraction(self.bank, intake["id"], response)["run_id"])
        return load_data(self.bank)

    def test_aliases_preserve_versions_and_distinct_frameworks(self):
        self.assertEqual(normalize_technology("SpringBoot"), "spring-boot")
        self.assertEqual(normalize_technology(" K8S "), "kubernetes")
        self.assertEqual(normalize_technology("Postgres"), "postgresql")
        self.assertNotEqual(normalize_technology("Python3"), normalize_technology("Python"))
        self.assertNotEqual(normalize_technology("React Native"), normalize_technology("React"))
        self.assertNotEqual(normalize_technology("C++"), normalize_technology("C"))
        self.assertEqual(normalize_technology("MyNewFramework"), "mynewframework")

    def test_catalog_discovery_is_readonly_and_bankless(self):
        result = subprocess.run([sys.executable, "-B", str(CLI), "taxonomy", "--dimension", "domains", "--query", "向量", "--json"],
                                cwd=self.base, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["result"]["items"][0]["id"], "backend.database.vector")
        self.assertFalse((self.base / "interview-bank").exists())
        page = catalog_view("industries", "金融", limit=1)
        self.assertGreaterEqual(page["total"], 1)
        self.assertEqual(len(page["items"]), 1)

    def test_chinese_ingestion_leaf_labels_and_parent_filters(self):
        q = self.text_import()
        self.assertEqual(q["role_tracks"], ["backend.java"])
        self.assertEqual(q["domains"], ["backend.database.vector"])
        self.assertEqual(search(self.bank, role="后端", domain="数据库", technology="Postgres")["total"], 1)
        self.assertEqual(search(self.bank, role="Go后端")["total"], 0)
        self.assertFalse(matches("domains", "backend.database", "向量数据库"))

    def test_old_bank_labels_remain_readable_without_rewriting(self):
        self.bundle["companies"][0]["industries"] = ["银行"]
        self.bundle["questions"][0]["technologies"] = ["springboot", "reactjs"]
        self.seed()
        before = fingerprint(load_data(self.bank))
        self.assertGreater(search(self.bank, industry="finance")["total"], 0)
        self.assertGreater(search(self.bank, industry="银行")["total"], 0)
        self.assertIn("finance.banking", stats(self.bank)["industries"])
        self.assertEqual(search(self.bank, technology="Spring Boot")["total"], 1)
        self.assertIn("spring-boot", stats(self.bank)["technologies"])
        self.assertEqual(before, fingerprint(load_data(self.bank)))

    def test_company_profiles_queries_and_all_exports(self):
        data = self.profile_import()
        company = data["companies"][0]
        self.assertEqual(company["ownership"], "private")
        self.assertEqual(company["industries"], ["finance.banking"])
        self.assertEqual(search(self.bank, role="后端", industry="金融", ownership="民营", business_model="B2B")["total"], 1)
        self.assertEqual(search(self.bank, ownership="国企")["total"], 0)
        self.assertEqual(list_companies(self.bank, query="Alpha", industry="金融")["companies"][0]["occurrences"], 1)
        self.assertEqual(stats(self.bank)["business_models"]["b2b"], 1)
        for fmt in ("markdown", "json", "jsonl", "csv", "viewer"):
            output = export_bank(self.bank, f"profile.{fmt}", fmt, ownership="民营")
            from pathlib import Path
            text = Path(output["output"]).read_text(encoding="utf-8-sig")
            if fmt == "markdown":
                evidence = json.loads(Path(output["details_output"]).read_text(encoding="utf-8"))
                self.assertEqual(evidence["companies"][0]["industries"], ["finance.banking"])
                self.assertEqual(evidence["companies"][0]["ownership"], "private")
                self.assertEqual(evidence["companies"][0]["profile_evidence"], company["profile_evidence"])
            elif fmt == "csv":
                row = next(csv.DictReader(io.StringIO(text)))
                self.assertEqual(json.loads(row["companies_json"])[0]["ownership"], "private")
            else:
                self.assertEqual(json.loads(text)["companies"][0]["ownership"], "private")

    def test_company_evidence_required_and_conflicts_do_not_overwrite(self):
        data = self.profile_import()
        company, q = data["companies"][0], data["questions"][0]
        task = classification_task(self.bank)
        response = {"schema_version": 1, "task_id": task["id"], "items": [{"question_id": q["id"], "confidence": 1,
            "reason": "Company metadata update", "occurrences": [{"id": data["occurrences"][0]["id"],
                "set": {"company": {"name": company["name"], "ownership": "国有"}}}]}]}
        with self.assertRaisesRegex(ValidationError, "evidence"):
            stage_classification(self.bank, response)
        response["items"][0]["occurrences"][0]["set"]["company"]["profile_evidence"] = "Synthetic contradictory note"
        with self.assertRaisesRegex(ValidationError, "Conflicting"):
            stage_classification(self.bank, response)
        self.assertEqual(data, load_data(self.bank))

    def test_reclassification_normalizes_and_audits_company(self):
        self.seed()
        data = load_data(self.bank)
        q, occ = data["questions"][0], data["occurrences"][0]
        task = classification_task(self.bank, [q["id"]])
        response = {"schema_version": 1, "task_id": task["id"], "items": [{"question_id": q["id"], "confidence": 0.95,
            "reason": "明确的缓存与 Java 岗位上下文", "question": {"role_tracks": ["Java后端"], "domains": ["缓存"], "technologies": ["SpringBoot"]},
            "occurrences": [{"id": occ["id"], "set": {"role_tracks": ["Java后端"], "company": {"name": "新增企业乙", "industries": ["新能源"]}}}]}]}
        staged = stage_classification(self.bank, response)
        from ibank_core.runs import show_run
        self.assertTrue(any(a["action"] == "CLASSIFY_COMPANY" for a in show_run(self.bank, staged["run_id"])["audit"]))
        commit_run(self.bank, staged["run_id"])
        self.assertEqual(search(self.bank, role="backend", industry="能源", technology="Spring Boot")["total"], 1)

    def test_explicit_company_correction_and_undo(self):
        data = self.profile_import()
        company = data["companies"][0]
        run = stage_curate(self.bank, {"schema_version": 1, "changes": [{"table": "companies", "id": company["id"],
            "set": {"ownership": "国企", "profile_evidence": "用户明确修正该合成示例为国有企业。"}, "reason": "用户纠错"}]})
        commit_run(self.bank, run["run_id"])
        self.assertEqual(list_companies(self.bank, ownership="国企")["total"], 1)
        commit_run(self.bank, undo_run(self.bank, run["run_id"])["run_id"])
        self.assertEqual(load_data(self.bank), data)

    def test_custom_taxonomy_survives_and_alias_conflicts_are_rejected(self):
        patch = {"taxonomy_extensions": {"role_tracks": ["custom-specialist"], "domains": ["custom.topic"]}}
        commit_run(self.bank, configure(self.bank, patch)["run_id"])
        self.assertEqual(catalog_view("domains", "custom", extensions=patch["taxonomy_extensions"])["items"][0]["id"], "custom.topic")
        with self.assertRaises(ValidationError):
            configure(self.bank, {"taxonomy_extensions": {"role_tracks": ["后端"]}})
        from ibank_core.schema import validate_config
        old_config = configure(self.bank)
        old_config["taxonomy_extensions"] = {"role_tracks": ["后端"]}
        validate_config(old_config)  # Previously legal custom labels must remain readable.

    def test_company_context_filters_cannot_match_different_occurrences(self):
        self.seed()
        data = load_data(self.bank)
        companies = data["companies"]
        # Same canonical question can appear in two employers with different profiles.
        from ibank_core.runs import stage_bundle
        extra = {**data["occurrences"][0], "id": "occ_extra", "sequence": 99, "company_id": companies[1]["id"]}
        commit_run(self.bank, stage_bundle(self.bank, {"schema_version": 1, "occurrences": [extra]})["run_id"])
        changes = [{"table": "companies", "id": c["id"], "set": {"ownership": owner, "profile_evidence": "Synthetic verified test metadata"}, "reason": "test"}
                   for c, owner in zip(companies, ["private", "state-owned"])]
        commit_run(self.bank, stage_curate(self.bank, {"schema_version": 1, "changes": changes})["run_id"])
        self.assertEqual(search(self.bank, company=companies[0]["id"], ownership="state-owned")["total"], 0)
