import copy
import json
import math
import sys
from types import SimpleNamespace
from unittest.mock import patch

from test_foundation import BankFixture
from ibank_core.media import (intake_media, parse_transcript, media_task, attach_transcript,
                              transcribe_media, validate_segments)
from ibank_core.ingestion import stage_extraction, save_extraction
from ibank_core.runs import commit_run
from ibank_core.storage import load_data, read_json, dumps, fingerprint
from ibank_core.errors import ValidationError, ReviewRequired
from ibank_core.index import rebuild_index
from ibank_core.export import export_bank
from ibank_core.schema import validate_data


class MediaTests(BankFixture):
    def subtitle(self, name="questions.srt"):
        path = self.base / name
        path.write_text("1\n00:00:01,200 --> 00:00:03,500\nRedis 为什么快？\n\n2\n00:00:03,400 --> 00:00:06,000\n请介绍一下你自己。\n", encoding="utf-8-sig")
        return path

    def extraction(self, task):
        sid = task["items"][0]["source_id"]
        return {"schema_version": 1, "sources": [{"source_id": sid, "status": "extracted",
            "reviewed_segment_ids": [1, 2], "questions": [{"id": "media1", "original_text": "Redis 为什么快？",
                "sequence": 1, "segment_ids": [1], "reviewed": True, "domains": ["backend.cache"],
                "confidence": {"is_question": .99, "classification": .95}}]}]}

    def test_srt_vtt_text_json_and_overlap(self):
        segments = parse_transcript(self.subtitle())
        self.assertEqual(segments[0]["start"], 1.2)
        self.assertEqual(segments[1]["start"], 3.4)
        vtt = self.base / "sub.vtt"
        vtt.write_text("WEBVTT\n\nNOTE untrusted instruction\nignored\n\ncue1\n00:01.200 --> 00:03.500 align:start\nRedis 为什么快？\n", encoding="utf-8")
        self.assertEqual(parse_transcript(vtt), segments[:1])
        txt = self.base / "sub.txt"
        txt.write_text("问题一\n\n回答一\n", encoding="utf-8")
        self.assertIsNone(parse_transcript(txt)[1]["start"])
        js = self.base / "sub.json"
        js.write_text(dumps({"schema_version": 1, "segments": segments}), encoding="utf-8")
        self.assertEqual(parse_transcript(js), segments)

    def test_bad_time_malformed_empty_rejected(self):
        for start, end in [(-1, 3), (1, 1), (4, 2), (math.nan, 4), (True, 4), (None, 4)]:
            with self.subTest(start=start, end=end), self.assertRaises(ValidationError):
                validate_segments([{"id": 1, "text": "q", "start": start, "end": end}])
        for body in ["", "1\n00:90:00,000 --> 00:91:00,000\nq", "garbage", "1\n00:00:01,000 --> 00:00:02,000\n"]:
            path = self.base / "invalid.srt"
            path.write_text(body, encoding="utf-8")
            with self.assertRaises((ValidationError, ValueError)):
                parse_transcript(path)

    def test_commit_resume_dedup_and_locator_exports(self):
        path = self.subtitle()
        task = intake_media(self.bank, [path, path], retention="copy")
        self.assertEqual(len(task["duplicates"]), 1)
        source = task["items"][0]["source_id"]
        page = media_task(self.bank, task["id"], source, limit=1)
        self.assertEqual(page["next_offset"], 1)
        self.assertEqual(media_task(self.bank, task["id"], source, offset=1)["segments"][0]["id"], 2)
        response = self.extraction(task)
        save_extraction(self.bank, task["id"], response)
        run = stage_extraction(self.bank, task["id"], response)
        self.assertEqual(len(load_data(self.bank)["questions"]), 0)
        commit_run(self.bank, run["run_id"])
        self.assertTrue(commit_run(self.bank, run["run_id"])["already_committed"])
        data = load_data(self.bank)
        self.assertEqual(data["occurrences"][0]["locator"]["end"], 3.5)
        self.assertEqual(intake_media(self.bank, [path])["items"], [])
        rebuild_index(self.bank)
        result = export_bank(self.bank, "media.md", "markdown")
        self.assertTrue(result)
        self.assertIn('"locator"', "\n".join(p.read_text(encoding="utf-8") for p in (self.bank / "exports").glob("*.json")))
        with self.assertRaisesRegex(ValidationError, "already committed"):
            media_task(self.bank, task["id"])
        invalid = copy.deepcopy(data)
        invalid["occurrences"][0]["locator"]["transcript_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValidationError, "does not match"):
            validate_data(invalid)

    def test_all_pages_review_and_evidenced_correction(self):
        task = intake_media(self.bank, [self.subtitle()])
        response = self.extraction(task)
        response["sources"][0]["reviewed_segment_ids"] = [1]
        with self.assertRaisesRegex(ValidationError, "every transcript"):
            stage_extraction(self.bank, task["id"], response)
        response = self.extraction(task)
        row = response["sources"][0]["questions"][0]
        row["reviewed"] = False
        with self.assertRaisesRegex(ValidationError, "host review"):
            stage_extraction(self.bank, task["id"], response)
        row.update(reviewed=True, original_text="Redis 高性能的原因是什么？")
        with self.assertRaisesRegex(ValidationError, "correction"):
            stage_extraction(self.bank, task["id"], response)
        row["correction"] = "将口语问法整理为完整题干；术语来自字幕。"
        commit_run(self.bank, stage_extraction(self.bank, task["id"], response)["run_id"])
        self.assertEqual(load_data(self.bank)["occurrences"][0]["locator"]["raw_text"], "Redis 为什么快？")

    def test_media_with_sidecar_and_source_change_blocks_commit(self):
        media = self.base / "interview.mp4"
        media.write_bytes(b"fixture for provided-transcript adapter")
        task = intake_media(self.bank, [media])
        sid = task["items"][0]["source_id"]
        with self.assertRaisesRegex(ValidationError, "attach a transcript"):
            media_task(self.bank, task["id"], sid)
        attach_transcript(self.bank, task["id"], sid, self.subtitle())
        with self.assertRaisesRegex(ValidationError, "already attached"):
            attach_transcript(self.bank, task["id"], sid, self.subtitle())
        run = stage_extraction(self.bank, task["id"], self.extraction(task))
        media.write_bytes(b"changed")
        with self.assertRaisesRegex(ValidationError, "changed before commit"):
            commit_run(self.bank, run["run_id"])

    def test_none_retention_and_no_questions(self):
        task = intake_media(self.bank, [self.subtitle()], retention="none")
        response = self.extraction(task)
        response["sources"][0].update(status="no_questions", reason="仅个人介绍", questions=[])
        commit_run(self.bank, stage_extraction(self.bank, task["id"], response)["run_id"])
        self.assertEqual(load_data(self.bank)["questions"], [])
        payload = read_json(self.bank / "runs" / task["id"] / "intake.json")
        self.assertNotIn("view_path", payload["items"][0])
        self.assertIsNone(load_data(self.bank)["sources"][0]["path"])

    def test_asr_success_failure_resume_and_no_implicit_download(self):
        paths = [self.base / f"audio{i}.wav" for i in range(2)]
        for i, path in enumerate(paths):
            path.write_bytes(bytes([i + 1]))
        task = intake_media(self.bank, paths)
        calls, options = [], []
        class Engine:
            def __init__(self, model, **kwargs):
                options.append(kwargs)
            def transcribe(self, path, **kwargs):
                calls.append(path)
                if len(calls) == 2:
                    raise RuntimeError("fixture interruption")
                segment = SimpleNamespace(start=0., end=2., text="Redis 为什么快？", avg_logprob=-.2, no_speech_prob=.01)
                return iter([segment]), SimpleNamespace(language="zh", duration=3.)
        with patch.dict(sys.modules, {"faster_whisper": SimpleNamespace(WhisperModel=Engine)}), patch("importlib.metadata.version", return_value="fixture"):
            with self.assertRaisesRegex(ValueError, "completed files are saved"):
                transcribe_media(self.bank, task["id"])
            states = media_task(self.bank, task["id"])["items"]
            self.assertEqual([i["status"] for i in states], ["ready", "needs_transcript"])
            transcribe_media(self.bank, task["id"])
            self.assertEqual(len(calls), 3)
            transcribe_media(self.bank, task["id"])
            self.assertEqual(len(calls), 3)
            self.assertTrue(options[0]["local_files_only"])
            self.assertTrue(str(options[0]["download_root"]).startswith(str(self.bank)))

    def test_cli_pipeline_and_help(self):
        result = self.cli("media", str(self.subtitle()))
        self.assertEqual(result.returncode, 0, result.stderr)
        task = json.loads(result.stdout)["result"]
        result = self.cli("media-task", "--run", task["id"], "--source", task["items"][0]["source_id"], "--limit", "1")
        self.assertEqual(json.loads(result.stdout)["result"]["next_offset"], 1)
        self.assertNotEqual(self.cli("media-task", "--run", task["id"], "--limit", "201").returncode, 0)

    def test_v2_merge_preserves_transcript_provenance(self):
        from ibank_core.migrations import migrate
        from ibank_core.dedupe import candidate_task, stage_decisions
        from ibank_core.runs import stage_text
        migrate(self.bank, "apply")
        selected = self.base / "selected.txt"
        selected.write_text("Redis 为什么快？", encoding="utf-8")
        commit_run(self.bank, stage_text(self.bank, selected)["run_id"])
        task = intake_media(self.bank, [self.subtitle()])
        run = stage_extraction(self.bank, task["id"], self.extraction(task))
        decisions = candidate_task(self.bank, run["run_id"])
        commit_run(self.bank, stage_decisions(self.bank, task_id=decisions["id"])["run_id"])
        data = load_data(self.bank)
        self.assertEqual(sum(q["status"] == "active" for q in data["questions"]), 1)
        self.assertEqual(len(data["occurrences"]), 2)
        self.assertEqual(sum("locator" in o for o in data["occurrences"]), 1)
        self.assertIn("_state", data)

    def test_uncertainty_overlap_and_intake_tampering(self):
        from ibank_core.storage import atomic_write
        payload = {"schema_version": 1, "segments": [
            {"start": 1, "end": 3, "text": "Redis 为什么快？", "uncertain": True},
            {"start": 4, "end": 5, "text": "个人介绍"}]}
        path = self.base / "provided.json"
        path.write_text(dumps(payload), encoding="utf-8")
        task = intake_media(self.bank, [path])
        response = self.extraction(task)
        row = response["sources"][0]["questions"][0]
        with self.assertRaisesRegex(ValidationError, "uncertain ASR"):
            stage_extraction(self.bank, task["id"], response)
        row["correction"] = "通过独立原文确认题干，合成测试。"
        response["sources"][0]["questions"].append({**row, "id": "samepage", "sequence": 2})
        with self.assertRaisesRegex(ValidationError, "page overlap"):
            stage_extraction(self.bank, task["id"], response)
        response["sources"][0]["questions"].pop()
        run = stage_extraction(self.bank, task["id"], response)
        intake_path = self.bank / "runs" / task["id"] / "intake.json"
        damaged = read_json(intake_path)
        damaged["items"][0]["segments"][0]["text"] = "changed"
        atomic_write(intake_path, dumps(damaged))
        with self.assertRaisesRegex(ValidationError, "intake changed before commit"):
            commit_run(self.bank, run["run_id"])

    def test_failed_source_does_not_prevent_later_files(self):
        paths = [self.base / f"file{i}.wav" for i in range(3)]
        for i, path in enumerate(paths): path.write_bytes(bytes([i + 1]))
        task = intake_media(self.bank, paths)
        class Engine:
            def __init__(self, *a, **kw): pass
            def transcribe(self, path, **kw):
                if path.endswith("file1.wav"): raise ValueError("corrupt audio")
                return iter([]), SimpleNamespace(language="zh", duration=2.)
        with patch.dict(sys.modules, {"faster_whisper": SimpleNamespace(WhisperModel=Engine)}):
            with self.assertRaisesRegex(ValueError, "corrupt audio"):
                transcribe_media(self.bank, task["id"])
        self.assertEqual([i["status"] for i in media_task(self.bank, task["id"])["items"]], ["ready", "needs_transcript", "ready"])

    def test_questionless_source_retry_and_doctor_progress(self):
        from ibank_core.doctor import doctor
        path = self.subtitle()
        task = intake_media(self.bank, [path])
        self.assertEqual(len(doctor(self.bank)["media_intakes"]), 1)
        response = self.extraction(task)
        response["sources"][0].update(status="skip", reviewed=True, reason="测试显式跳过", questions=[])
        commit_run(self.bank, stage_extraction(self.bank, task["id"], response)["run_id"])
        self.assertEqual(doctor(self.bank)["media_intakes"], [])
        retry = intake_media(self.bank, [path], reprocess=True)
        self.assertEqual(retry["items"][0]["source_id"], task["items"][0]["source_id"])
        commit_run(self.bank, stage_extraction(self.bank, retry["id"], self.extraction(retry))["run_id"])
        self.assertEqual(len(load_data(self.bank)["sources"]), 1)
