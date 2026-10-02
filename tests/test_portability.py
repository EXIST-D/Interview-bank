import copy
import json
import math
from unittest.mock import patch

from test_foundation import BankFixture
from ibank_core.errors import ValidationError
from ibank_core.ingestion import stage_extraction
from ibank_core.media import intake_media, media_task
from ibank_core.portability import (capability_report, host_profile, media_plan, normalize_result,
                                    provider_import, provider_task)
from ibank_core.runs import commit_run
from ibank_core.storage import read_json, load_data


class PortabilityTests(BankFixture):
    def profile(self, execution="local"):
        return {"schema_version":1, "name":"Synthetic host", "capabilities":{
            "web_search":{"available":False,"evidence":"Synthetic host has no search tool"}},
            "transcription":{"tool":"fixture.transcribe","provider":"Fixture provider","execution":execution,
                             "destination":"https://asr.example.test/transcribe" if execution == "remote" else None,
                             "evidence":"Synthetic adapter contract test, not a live provider"}}

    def intake(self, retention="reference"):
        path = self.base / "interview.wav"
        path.write_bytes(b"synthetic media: no real ASR in contract tests")
        return intake_media(self.bank, [path], retention=retention)

    def response(self, packet, format="segments"):
        result = {"segments":[{"start":1,"end":3,"text":"Redis 为什么快？","speaker":"SPEAKER_01"}]}
        if format == "chunks": result = {"chunks":[{"timestamp":[1,3],"text":"Redis 为什么快？"}]}
        if format == "text": result = {"text":"Redis 为什么快？"}
        return {"schema_version":1,"task_id":packet["id"],"source_sha256":packet["source_sha256"],
                "provider":packet["provider"],"format":format,"result":result,"model":"fixture", "duration":4}

    def packet(self, intake, profile=None, consent=None):
        return provider_task(self.bank,intake["id"],intake["items"][0]["source_id"],profile or self.profile(),consent)

    def test_capabilities_distinguish_unknown_from_measured_and_leave_no_probe_file(self):
        before = set(self.base.iterdir())
        report = capability_report(self.base)
        self.assertTrue(report["workspace_writable"])
        self.assertTrue(report["python"]["supported"])
        self.assertEqual(report["host"]["capabilities"],{})
        self.assertEqual(report["local_asr"]["model_load"],"not_tested")
        self.assertFalse(report["network_request_performed"])
        self.assertEqual(before,set(self.base.iterdir()))
        result = self.cli("capabilities","--workspace",str(self.base))
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)["result"]["host_evidence_kind"],"host_declared_not_independently_detected")

    def test_missing_dependencies_are_actionable_without_global_install(self):
        from importlib.metadata import PackageNotFoundError
        with patch("ibank_core.portability.importlib.metadata.version",side_effect=PackageNotFoundError):
            report = capability_report(self.base,probe_asr=True)
        self.assertEqual(report["local_asr"]["status"],"missing_dependencies")

    def test_sidecars_found_after_copy_and_ambiguous_or_invalid_not_silently_chosen(self):
        intake = self.intake("copy")
        subtitle = self.base / "interview.srt"
        subtitle.write_text("1\n00:00:01,000 --> 00:00:03,000\nRedis 为什么快？",encoding="utf-8")
        with patch("ibank_core.portability.capability_report",return_value={"host":host_profile(),"local_asr":{"status":"missing_dependencies"}}):
            plan = media_plan(self.bank,intake["id"])
            self.assertEqual(plan["items"][0]["route"],"provided")
            (self.base / "interview.txt").write_text("Alternative transcript",encoding="utf-8")
            self.assertEqual(media_plan(self.bank,intake["id"])["items"][0]["route"],"sidecar_review")
            subtitle.write_text("malformed",encoding="utf-8")
            decision = media_plan(self.bank,intake["id"])["items"][0]
            self.assertEqual(decision["route"],"sidecar_review")
            self.assertTrue(any(not s["valid"] for s in decision["sidecars"]))

    def test_route_prefers_host_and_can_select_local_without_claiming_model_load(self):
        intake = self.intake()
        model = self.base / "model"
        model.mkdir()
        for name in ("model.bin","config.json","tokenizer.json"): (model/name).write_text("fixture")
        with patch("ibank_core.portability.capability_report",return_value={"host":host_profile(self.profile()),"local_asr":{"status":"importable"}}):
            self.assertEqual(media_plan(self.bank,intake["id"],model=str(model))["items"][0]["route"],"host")
            local = media_plan(self.bank,intake["id"],model=str(model),prefer="local")
            self.assertEqual(local["items"][0]["route"],"local")
            self.assertEqual(local["action_performed"],"plan_only")
        with patch("ibank_core.portability.capability_report",return_value={"host":host_profile(),"local_asr":{"status":"missing_dependencies"}}):
            self.assertEqual(media_plan(self.bank,intake["id"])["items"][0]["route"],"local_setup")
            self.assertEqual(media_plan(self.bank,intake["id"],prefer="host")["items"][0]["route"],"blocked")

    def test_host_result_roundtrip_idempotent_commit_and_none_privacy(self):
        intake = self.intake("none")
        packet = self.packet(intake)
        response = self.response(packet)
        provider_import(self.bank,intake["id"],response)
        self.assertTrue(provider_import(self.bank,intake["id"],response)["already_imported"])
        sid = packet["source_id"]
        page = media_task(self.bank,intake["id"],sid)
        self.assertEqual(page["segments"][0]["speaker"],"SPEAKER_01")
        extracted = {"schema_version":1,"sources":[{"source_id":sid,"status":"extracted","reviewed_segment_ids":[1],
            "questions":[{"id":"host-q","sequence":1,"original_text":"Redis 为什么快？","segment_ids":[1],"reviewed":True,
                          "confidence":{"is_question":1,"classification":1}}]}]}
        commit_run(self.bank,stage_extraction(self.bank,intake["id"],extracted)["run_id"])
        self.assertTrue(provider_import(self.bank,intake["id"],response)["already_imported"])
        item = read_json(self.bank/"runs"/intake["id"]/"intake.json")["items"][0]
        self.assertNotIn("original_path",item)
        self.assertNotIn("view_path",item)
        self.assertEqual(load_data(self.bank)["occurrences"][0]["locator"]["start"],1)
        self.assertTrue(load_data(self.bank)["sources"][0]["transcription"]["engine"].startswith("host:"))

    def test_remote_gate_binds_exact_destination_file_and_provider(self):
        intake = self.intake()
        profile = self.profile("remote")
        with self.assertRaisesRegex(ValidationError,"Remote transfer"):
            self.packet(intake,profile)
        source = read_json(self.bank/"runs"/intake["id"]/"intake.json")["items"][0]["source"]
        consent = {"provider":profile["transcription"]["provider"],"destination":profile["transcription"]["destination"],
                   "source_sha256":source["sha256"],"cost_note":"Synthetic fixture: no real charge or request", "user_instruction":"Synthetic authorization fixture"}
        for key in ("provider","destination","source_sha256"):
            wrong = {**consent,key:"wrong"}
            with self.assertRaisesRegex(ValidationError,"does not cover"):
                self.packet(intake,profile,wrong)
        packet = self.packet(intake,profile,consent)
        self.assertFalse(packet["network_request_performed"])
        provider_import(self.bank,intake["id"],self.response(packet,"chunks"))

    def test_unknown_location_and_credentials_in_destination_rejected(self):
        intake = self.intake()
        with self.assertRaisesRegex(ValidationError,"where transcription runs"):
            self.packet(intake,self.profile("unknown"))
        for destination in ("https://name:secret@example.test/", "https://example.test/?key=secret", "http://example.test/", 12):
            profile=self.profile("remote")
            profile["transcription"]["destination"]=destination
            with self.assertRaises(ValidationError): host_profile(profile)

    def test_wrong_source_response_or_replaced_result_rejected(self):
        intake = self.intake()
        packet = self.packet(intake)
        response = self.response(packet)
        wrong = {**response,"source_sha256":"0"*64}
        with self.assertRaisesRegex(ValidationError,"does not match"):
            provider_import(self.bank,intake["id"],wrong)
        provider_import(self.bank,intake["id"],response)
        changed = copy.deepcopy(response)
        changed["result"]["segments"][0]["text"]="A different question"
        with self.assertRaisesRegex(ValidationError,"different transcript"):
            provider_import(self.bank,intake["id"],changed)

    def test_response_formats_times_and_unknown_payload_fields(self):
        self.assertEqual(normalize_result({"text":"题目\n回答"},"text")[1]["start"],None)
        self.assertEqual(normalize_result({"chunks":[{"timestamp":[1,2],"text":"q"}]},"chunks")[0]["end"],2)
        for start,end in [(1,None),(3,2),(-1,2),(math.nan,2)]:
            with self.assertRaises(ValidationError):
                normalize_result({"segments":[{"start":start,"end":end,"text":"q"}]},"segments")
        intake=self.intake(); packet=self.packet(intake)
        with self.assertRaisesRegex(ValidationError,"Unknown provider response field"):
            provider_import(self.bank,intake["id"],{**self.response(packet),"api_key":"do-not-store"})
        with self.assertRaisesRegex(ValidationError,"exceeds media duration"):
            provider_import(self.bank,intake["id"],{**self.response(packet),"duration":1})

    def test_empty_result_must_have_reason_and_preserves_no_questions(self):
        intake=self.intake(); packet=self.packet(intake)
        response={**self.response(packet),"result":{"segments":[]}}
        with self.assertRaisesRegex(ValidationError,"reviewed reason"):
            provider_import(self.bank,intake["id"],response)
        response["empty_reason"]="Fixture silence; verified independently"
        provider_import(self.bank,intake["id"],response)
        self.assertEqual(media_task(self.bank,intake["id"],packet["source_id"])["total"],0)
