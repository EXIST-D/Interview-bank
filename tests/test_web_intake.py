"""Screenshot import in the Web reader: the Skill's intake, dedupe and answer pipeline with a stand-in model."""
import http.client
import json
import os
import re
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import support  # noqa: F401  (puts the Skill's scripts on sys.path)
from ibank_core import ai, ai_prompts
from ibank_core.demo import build_demo
from ibank_core.errors import ValidationError
from ibank_core.storage import load_data
from ibank_core.web import LocalServer, WebApp
from ibank_core.web_intake import IntakeJobs, clean_source

ROOT = Path(__file__).resolve().parents[1]
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x01" * 64
LIMITS = {"max_images_per_job": 12, "max_answers_per_job": 40, "daily_images": 60, "answer_batch": 4, "daily_research": 100, "daily_budget": 0}
ENDPOINT = {"protocol": "openai", "base_url": "http://127.0.0.1:9", "model": "stand-in", "timeout": 5, "max_tokens": 1024,
            "temperature": 0.2, "json_mode": False, "_key": None}
CONFIG = {"vision": ENDPOINT, "text": ENDPOINT, "limits": LIMITS}


def image(tag, kind=PNG):
    return kind + tag.encode()


class Model:
    """Answers like a model would, keyed by the screenshot bytes; records what each step was given."""

    def __init__(self, screenshots):
        self.screenshots, self.calls, self.before_dedupe, self.skip_answers = screenshots, [], None, set()
        # (words in the new question, existing wording, action, confidence, merged wording)
        self.merges = [("单线程", "Redis 为什么快？", "MERGE_VARIANT", 0.7, None)]

    def __call__(self, endpoint, system, parts):
        self.calls.append((system, parts))
        ai.record({"kind": "model", "model": endpoint["model"], "hit": 1000, "miss": 9000, "output": 2000})
        if "vision step" in system:
            images = [p["image"] for p in parts if "image" in p]
            reply = self.screenshots[images[0]]
            if isinstance(reply, Exception):
                raise reply
            return reply
        text = parts[0]["text"]
        if "You research one interview question" in system:
            urls = re.findall(r"^\[\d+\] URL: (\S+)$", text, re.M)
            if "拒答" in text:
                return {"skip": True, "reason": "网页之间说法矛盾"}
            return {"status": "source_backed", "short_answer": "按官方文档的结论。", "key_points": ["有出处的要点", "没有出处的要点"],
                    "sources": [{"url": urls[0], "title": "官方文档", "publisher": "Example", "type": "official_doc",
                                 "evidence_note": "说明了该机制", "evidence_quote": "RDB 是定时快照"},
                                {"url": urls[-1], "title": "转载", "evidence_quote": "页面里没有这句话"},
                                {"url": "https://never-read.example/page", "title": "没读过的页面"}],
                    "evidence": [{"key_point": 0, "source_urls": [urls[0]]}, {"key_point": 1, "source_urls": ["https://never-read.example/page"]}]}
        if "deduplication step" in system:
            if self.before_dedupe:
                self.before_dedupe()
            listing = json.loads(text.split("candidates:\n", 1)[1].split("\n\nThe review sheet", 1)[0])
            decisions = []
            for item in listing:
                for words, existing, action, confidence, canonical in self.merges:
                    if words in item["question"]:
                        target = next(c["ref"] for c in item["candidates"] if c["question"] == existing)
                        decisions.append({"question_id": item["ref"], "action": action, "target_id": target,
                                          "confidence": confidence, "reason": "可能是同一个问题",
                                          **({"canonical": canonical} if canonical else {})})
            return {"decisions": decisions}
        questions = json.loads(text.split(":\n", 1)[1])
        return {"answers": [{"question_id": q["question_id"], "skip": True, "reason": "暂时无法回答"}
                            if q["question"] in self.skip_answers else
                            {"question_id": q["question_id"], "short_answer": f"{q['question']} 的结论。",
                             "key_points": ["要点一", "要点二"], "common_mistakes": ["混淆概念"]} for q in questions]}


class Web:
    """A stand-in search engine and the pages it finds; records what was searched and fetched."""

    def __init__(self):
        self.queries, self.fetched = [], []
        self.results = lambda query: [{"title": "Redis 持久化", "url": "https://redis.io/docs/persistence", "site": "Redis", "snippet": "", "date": None},
                                      {"title": "转载", "url": "https://blog.example/redis", "site": "Blog", "snippet": "", "date": None}]

    def search(self, settings, query):
        self.queries.append(query)
        ai.record({"kind": "search", "provider": settings["provider"]})
        return self.results(query)

    def opener(self, request, timeout):
        import email.message
        url = request.full_url
        self.fetched.append(url)
        headers = email.message.Message()
        headers["Content-Type"] = "text/html; charset=utf-8"
        article = "<p>RDB 是定时快照，AOF 记录每条写命令。</p>" + "<p>持久化的取舍取决于恢复速度与数据完整性。</p>" * 12
        body = ('<html><body>{"l1":"var arg1=\'5dcd8af6\';"}</body></html>' if "stub" in url else
                f"<html><body><nav>菜单</nav>{article}<p>{url}</p></body></html>").encode()

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self, size=-1):
                return body

            def geturl(self):
                return url
        response = Response()
        response.headers = headers
        return response


SEARCH = {"provider": "bocha", "url": "https://search.example", "count": 8, "pages": 2, "timeout": 5, "_key": "k"}
FIRST = image("first")
SECOND = image("second", JPEG)
EXTRACTION = {
    "status": "extracted",
    "metadata": {"round": "technical-1", "platform": "牛客", "company": "模型看到的公司"},
    "questions": [
        {"id": "a", "original_text": "请做一下自我介绍", "sequence": 1, "confidence": {"is_question": 0.99, "classification": 0.9}},
        {"id": "b", "original_text": "Redis 为什么快？", "sequence": 2, "question_type": "concept", "domains": ["backend.cache", "not.a.domain"],
         "technologies": ["Redis"], "confidence": {"is_question": 0.99, "classification": 0.95}},
        {"id": "c", "original_text": "Redis 单线程为什么还这么快？", "sequence": 3, "domains": ["backend.cache"], "technologies": ["redis"],
         "confidence": {"is_question": 0.95, "classification": 0.9}},
        {"id": "d", "original_text": "说说 MCP 协议", "canonical_suggestion": "什么是 MCP 协议？", "sequence": 4, "domains": ["ai.agent.protocol"],
         "confidence": {"is_question": 0.95, "classification": 0.9}},
        {"id": "e", "parent_id": "d", "original_text": "那它和 function call 呢", "canonical_suggestion": "MCP 和 Function Calling 有什么区别？",
         "sequence": 5, "domains": ["ai.agent.tool-use"], "confidence": {"is_question": 0.7, "classification": 0.85}},
        {"id": "f", "original_text": "期望薪资多少", "sequence": 6, "confidence": {"is_question": 0.9, "classification": 0.9}},
    ],
}


def finish_workers(prefix):
    """A background job may still be writing when a test ends; wait for it before the bank folder is deleted."""
    for worker in threading.enumerate():
        if worker.name.startswith(prefix):
            worker.join(10)


class IntakeCase(unittest.TestCase):
    def setUp(self):
        work = ROOT / ".work/tests"
        work.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=work)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(finish_workers, "ibank-intake-")  # runs before the folder is removed
        self.bank = Path(self.temp.name) / "bank"
        build_demo(self.bank, v2=True)
        self.model = Model({FIRST: EXTRACTION, SECOND: {"status": "unreadable", "reason": "太模糊"}})
        self.app = WebApp(self.bank, read_only=True, allow_my_answers=True, allow_practice=True)
        self.jobs = self.app.intake = IntakeJobs(self.app.bank, CONFIG, self.app.mutation_lock, call=self.model)

    def wait(self, job_id, *states):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            job = self.jobs.job(job_id)
            if job["status"] in states:
                return job
            time.sleep(0.02)
        self.fail(f"job stayed {job['status']}: {job.get('error')}")

    def started(self, *screenshots, hints=None):
        job = self.jobs.create({"hints": hints or {}})
        for index, raw in enumerate(screenshots):
            self.jobs.upload(job["id"], index, None, raw)
        self.jobs.start({"job": job["id"]})
        return self.wait(job["id"], "review")

    def questions(self):
        return {q["canonical"]: q for q in load_data(self.bank)["questions"] if q["status"] == "active"}

    def test_screenshots_become_questions_with_merges_and_draft_answers(self):
        before = self.questions()
        job = self.started(FIRST, SECOND, hints={"company": "字节跳动", "event_date": "2026-10"})
        first, second = sorted(job["sources"], key=lambda s: s["index"])
        self.assertEqual(second["status"], "unreadable")
        kept = {q["original_text"]: q for q in first["questions"]}
        self.assertNotIn("请做一下自我介绍", kept)
        self.assertEqual(first["metadata"]["company"], "字节跳动")
        self.assertEqual(kept["Redis 为什么快？"]["domains"], ["backend.cache"])
        self.assertEqual(kept["Redis 为什么快？"]["technologies"], ["redis"])
        follow = kept["那它和 function call 呢"]
        self.assertEqual(follow["flags"], ["low_confidence"])
        self.assertEqual(follow["parent_id"], kept["说说 MCP 协议"]["id"])
        salary = kept["期望薪资多少"]["id"]

        confirmed = self.jobs.confirm({"job": job["id"], "sources": [{"source_id": first["source_id"],
            "metadata": {"round": "technical-2"},
            "questions": [{"id": salary, "keep": False},
                          {"id": follow["id"], "canonical": "MCP 与 Function Calling 的区别？"}]}]})
        self.assertEqual(confirmed["status"], "saving")
        job = self.wait(job["id"], "merge_review")
        [item] = job["merge_review"]
        self.assertEqual((item["question"], item["target"]), ("Redis 单线程为什么还这么快？", "Redis 为什么快？"))
        with self.assertRaises(ValidationError):
            self.jobs.merge({"job": job["id"], "decisions": [{"question_id": item["question_id"], "action": "MERGE_EXACT"}]})
        self.jobs.merge({"job": job["id"], "decisions": [{"question_id": item["question_id"], "action": "KEEP_RELATED"}]})
        job = self.wait(job["id"], "done")

        after = self.questions()
        self.assertEqual(after["Redis 为什么快？"]["id"], before["Redis 为什么快？"]["id"])
        self.assertEqual(len(after), len(before) + 3)
        self.assertNotIn("期望薪资多少", after)
        self.assertIn("MCP 与 Function Calling 的区别？", after)
        self.assertEqual([m["canonical"] for m in job["result"]["merged"]], ["Redis 为什么快？"])
        self.assertEqual(job["result"]["related"], 1)
        data = load_data(self.bank)
        occurrences = [o for o in data["occurrences"] if o["question_id"] == before["Redis 为什么快？"]["id"]]
        self.assertEqual(len(occurrences), 2)
        company = next(c for c in data["companies"] if c["id"] == occurrences[-1]["company_id"])
        self.assertEqual((company["name"], occurrences[-1]["round"], occurrences[-1]["event_date"]), ("字节跳动", "technical-2", "2026-10"))
        sources = {s["sha256"]: s for s in data["sources"]}
        self.assertEqual(len(sources), len({s["sha256"] for s in data["sources"]}))
        self.assertTrue(all(s["retention"] == "copy" and (self.bank / s["path"]).is_file()
                            for s in data["sources"] if s["id"] in {first["source_id"], second["source_id"]}))
        drafts = {a["question_id"]: a for a in data["answers"] if a["status"] == "ai_draft"}
        new = [after[t]["id"] for t in ("Redis 单线程为什么还这么快？", "什么是 MCP 协议？", "MCP 与 Function Calling 的区别？")]
        self.assertEqual(set(drafts), set(new))
        self.assertTrue(all(not a["sources"] for a in drafts.values()))
        self.assertEqual(set(job["answers"]["done"]), set(new))
        self.assertEqual(list((self.bank / "cache/web-intake" / job["id"]).glob("img-*")), [])
        self.assertEqual(self.app.question(new[1])["answer_status"], "ai_draft")
        self.assertTrue(self.app.library({})["can_intake"])

        answer_prompt = next(system for system, _ in self.model.calls if "reference answers" in system)
        self.assertIn("ai_draft", answer_prompt)
        self.assertIn(ai_prompts.section("answer-policy.md", "Writing the answer"), answer_prompt)

    def test_exact_duplicates_merge_without_asking_and_a_skipped_answer_can_be_retried(self):
        self.model.screenshots[FIRST] = {"status": "extracted", "questions": [
            {"id": "x", "original_text": "Redis 为什么快？", "sequence": 1, "confidence": {"is_question": 0.99, "classification": 0.9}},
            {"id": "y", "original_text": "什么是向量数据库？", "sequence": 2, "domains": ["backend.database.vector"],
             "confidence": {"is_question": 0.99, "classification": 0.9}}]}
        self.model.skip_answers = {"什么是向量数据库？"}
        job = self.started(FIRST)
        self.jobs.confirm({"job": job["id"], "sources": []})
        job = self.wait(job["id"], "done")
        self.assertEqual(len(job["result"]["merged"]), 1)
        self.assertEqual(list(job["answers"]["failed"].values()), ["暂时无法回答"])
        self.model.skip_answers = set()
        self.jobs.retry_answers({"job": job["id"]})
        job = self.wait(job["id"], "done")
        self.assertEqual((len(job["answers"]["done"]), job["answers"]["failed"]), (1, {}))

    def test_a_merge_keeps_new_sub_points_and_asks_before_rewording_a_researched_question(self):
        self.model.screenshots[FIRST] = {"status": "extracted", "questions": [
            {"id": "x", "original_text": "Redis 单线程会不会成为瓶颈？", "sequence": 1, "domains": ["backend.cache"],
             "confidence": {"is_question": 0.99, "classification": 0.9}},
            {"id": "y", "original_text": "缓存穿透是什么，布隆过滤器怎么防？", "sequence": 2, "domains": ["backend.cache"],
             "confidence": {"is_question": 0.99, "classification": 0.9}}]}
        redis, penetration = "Redis 为什么快？单线程会不会成为瓶颈？", "什么是缓存穿透？如何解决？布隆过滤器怎么防？"
        self.model.merges = [("单线程", "Redis 为什么快？", "MERGE_VARIANT", 0.95, redis),
                             ("布隆", "什么是缓存穿透？如何解决？", "MERGE_VARIANT", 0.95, penetration)]
        before = self.questions()
        job = self.started(FIRST)
        self.jobs.confirm({"job": job["id"], "sources": []})
        job = self.wait(job["id"], "merge_review")
        [item] = job["merge_review"]
        self.assertEqual((item["target"], item["canonical"]), ("Redis 为什么快？", redis))
        self.assertIn("重新核验", item["reason"])
        self.jobs.merge({"job": job["id"], "decisions": [{"question_id": item["question_id"], "action": "MERGE_VARIANT"}]})
        job = self.wait(job["id"], "done")
        after = self.questions()
        self.assertEqual((after[redis]["id"], after[penetration]["id"]),
                         (before["Redis 为什么快？"]["id"], before["什么是缓存穿透？如何解决？"]["id"]))
        self.assertEqual(self.app.question(after[redis]["id"])["answer_status"], "stale")
        self.assertEqual(job["answers"]["done"], [after[penetration]["id"]])
        self.assertEqual(self.app.question(after[penetration]["id"])["answer_status"], "ai_draft")

    def test_choosing_related_drops_the_proposed_wording(self):
        self.model.screenshots[FIRST] = {"status": "extracted", "questions": [
            {"id": "x", "original_text": "Redis 单线程会不会成为瓶颈？", "sequence": 1, "domains": ["backend.cache"],
             "confidence": {"is_question": 0.99, "classification": 0.9}}]}
        self.model.merges = [("单线程", "Redis 为什么快？", "MERGE_VARIANT", 0.95, "Redis 为什么快？会成为瓶颈吗？")]
        job = self.started(FIRST)
        self.jobs.confirm({"job": job["id"], "sources": []})
        job = self.wait(job["id"], "merge_review")
        self.jobs.merge({"job": job["id"], "decisions": [{"question_id": job["merge_review"][0]["question_id"], "action": "KEEP_RELATED"}]})
        self.wait(job["id"], "done")
        self.assertIn("Redis 为什么快？", self.questions())
        self.assertEqual(len(load_data(self.bank)["relations"]), 1)

    def test_a_bank_change_during_judging_restages_the_same_confirmation(self):
        self.model.screenshots[FIRST] = {"status": "extracted", "questions": [
            {"id": "x", "original_text": "Redis 单线程为什么还这么快？", "sequence": 1, "domains": ["backend.cache"],
             "confidence": {"is_question": 0.99, "classification": 0.9}}]}
        job = self.started(FIRST)

        def practise():
            detail = self.app.question(self.app.library({})["questions"][0]["id"])
            self.app.record({"question_id": detail["id"], "revision": detail["revision"], "rating": "good",
                             "request_id": "during-import", "note": "", "timezone": "UTC"})
        self.model.before_dedupe = practise
        self.jobs.confirm({"job": job["id"], "sources": []})
        job = self.wait(job["id"], "merge_review")
        first_stage = self.jobs._load(job["id"])["stage_run"]
        self.jobs.merge({"job": job["id"], "decisions": [{"question_id": job["merge_review"][0]["question_id"], "action": "KEEP_DISTINCT"}]})
        job = self.wait(job["id"], "done")
        self.assertNotEqual(self.jobs._load(job["id"])["stage_run"], first_stage)
        self.assertEqual(len(job["result"]["added"]), 1)
        self.assertEqual([e["request_id"] for e in load_data(self.bank)["_state"]["events"].values()], ["during-import"])

    def test_cancel_leaves_the_bank_and_media_untouched(self):
        before = load_data(self.bank)
        media = set((self.bank / "media").iterdir())
        job = self.started(FIRST)
        self.assertGreater(len(set((self.bank / "media").iterdir())), len(media))
        self.jobs.cancel({"job": job["id"]})
        self.assertEqual(set((self.bank / "media").iterdir()), media)
        self.assertEqual(load_data(self.bank)["questions"], before["questions"])
        self.assertEqual(self.jobs.job(job["id"])["status"], "cancelled")
        self.assertIsNone(self.jobs.overview()["active"])

    def test_a_failed_reading_can_be_retried_and_a_known_screenshot_is_not_read_again(self):
        self.model.screenshots[FIRST] = ai.AIError("模型服务返回 HTTP 429")
        job = self.started(FIRST)
        self.assertEqual(job["sources"][0]["status"], "failed")
        self.model.screenshots[FIRST] = EXTRACTION
        self.jobs.retry_extract({"job": job["id"]})
        job = self.wait(job["id"], "review")
        self.assertEqual(job["sources"][0]["status"], "extracted")
        self.jobs.confirm({"job": job["id"], "sources": []})
        job = self.wait(job["id"], "merge_review")
        self.jobs.merge({"job": job["id"], "decisions": [{"question_id": i["question_id"], "action": "KEEP_DISTINCT"} for i in job["merge_review"]]})
        self.wait(job["id"], "done")
        calls = len(self.model.calls)
        again = self.jobs.create({"hints": {}})
        self.jobs.upload(again["id"], 0, None, FIRST)
        self.jobs.start({"job": again["id"]})
        again = self.wait(again["id"], "done")
        self.assertTrue(again["result"]["nothing_new"] and again["images"][0]["duplicate"])
        self.assertEqual(len(self.model.calls), calls)

    def test_parts_of_a_tall_screenshot_are_read_together(self):
        job = self.jobs.create({"hints": {}})
        self.jobs.upload(job["id"], 0, None, FIRST)
        with self.assertRaises(ValidationError):
            self.jobs.upload(job["id"], 1, 0, JPEG)
        parts = [image(f"part{n}", JPEG) for n in range(3)]
        for n, raw in enumerate(parts):
            self.jobs.upload(job["id"], 0, n, raw)
        self.model.screenshots[parts[0]] = EXTRACTION
        self.jobs.start({"job": job["id"]})
        self.wait(job["id"], "review")
        _, sent = next(call for call in self.model.calls if "vision step" in call[0])
        self.assertEqual([p["image"] for p in sent if "image" in p], parts)

    def test_uploads_and_jobs_are_validated(self):
        job = self.jobs.create({"hints": {"company": "美团"}})
        with self.assertRaises(ValidationError):
            self.jobs.create({"hints": {}})
        for bad in (b"GIF8", b"<svg></svg>", b"%PDF-1.7"):
            with self.assertRaises(ValidationError):
                self.jobs.upload(job["id"], 0, None, bad)
        with self.assertRaises(ValidationError):
            self.jobs.upload(job["id"], 99, None, PNG)
        with self.assertRaises(ValidationError):
            self.jobs.start({"job": job["id"]})
        self.jobs.upload(job["id"], 0, None, PNG + b"\x00" * (9 * 1024 * 1024))
        with self.assertRaises(ValidationError):
            self.jobs.start({"job": job["id"]})
        for view in range(3):
            self.jobs.upload(job["id"], 0, view, JPEG + bytes([view]) * (3 * 1024 * 1024))
        with self.assertRaises(ValidationError):
            self.jobs.start({"job": job["id"]})
        with self.assertRaises(ValidationError):
            self.jobs.create({"hints": {"company": "联系 " + "138" + "12345678"}})
        with self.assertRaises(ValidationError):
            self.jobs.job("../../etc")
        self.jobs.cancel({"job": job["id"]})
        jobs = IntakeJobs(self.app.bank, {**CONFIG, "limits": {**LIMITS, "daily_images": 1}}, self.app.mutation_lock, call=self.model)
        second = jobs.create({"hints": {}})
        jobs.upload(second["id"], 0, None, FIRST)
        jobs.upload(second["id"], 0, None, SECOND)
        with self.assertRaises(ValidationError):
            jobs.upload(second["id"], 1, None, PNG)

    def test_a_restart_leaves_interrupted_jobs_actionable(self):
        job = self.started(FIRST)
        # The worker saves the job once more after it reaches review; rewriting the file before it ends would be overwritten.
        for worker in threading.enumerate():
            if worker.name.startswith("ibank-intake-"):
                worker.join(10)
        stored = self.jobs._load(job["id"])
        stored["status"] = "extracting"
        stored["sources"][0]["status"] = "pending"
        self.jobs._save(stored)
        recovered = IntakeJobs(self.app.bank, CONFIG, self.app.mutation_lock, call=self.model).job(job["id"])
        self.assertEqual((recovered["status"], recovered["sources"][0]["status"]), ("review", "failed"))

    def test_model_output_is_reduced_to_the_extraction_schema(self):
        email, mobile = "a.b" + "@corp.cn", "138" + "12345678"
        source = clean_source({"status": "extracted", "metadata": {"company": f"邮箱 {email}", "round": "第一轮", "event_date": "26年"},
                               "questions": [{"original_text": "  ", "sequence": 1}, "not a question",
                                             {"original_text": f"联系我 {mobile} 讲讲 Kafka", "question_type": "bogus",
                                              "confidence": {"is_question": 3}, "parent_id": "nobody", "technologies": "kafka"}]},
                              {}, {}, "s1")
        [question] = source["questions"]
        self.assertEqual((question["question_type"], question["confidence"]["is_question"], question["technologies"]), ("concept", 0.5, []))
        self.assertNotIn("parent_id", question)
        self.assertEqual(question["flags"], ["low_confidence", "contact"])
        self.assertEqual(source["metadata"], {})
        self.assertEqual(clean_source({"status": "extracted", "questions": []}, {}, {}, "s2")["status"], "no_questions")
        self.assertEqual(clean_source("garbage", {}, {}, "s3")["status"], "no_questions")


    def researching(self, limits=None):
        self.web = Web()
        config = {**CONFIG, "search": SEARCH, "limits": {**LIMITS, **(limits or {})}}
        self.jobs = self.app.intake = IntakeJobs(self.app.bank, config, self.app.mutation_lock, call=self.model,
                                                 search=self.web.search, fetch=self.web.opener)
        return self.jobs

    def test_new_questions_are_answered_from_pages_the_server_read(self):
        self.researching()
        self.web.results = lambda query: [] if "向量" in query else Web().results(query)
        self.model.screenshots[FIRST] = {"status": "extracted", "questions": [
            {"id": "x", "original_text": "RDB 和 AOF 怎么选？", "sequence": 1, "domains": ["backend.cache"], "technologies": ["redis"],
             "confidence": {"is_question": 0.99, "classification": 0.9}},
            {"id": "y", "original_text": "什么是向量数据库？", "sequence": 2, "domains": ["backend.database.vector"],
             "confidence": {"is_question": 0.99, "classification": 0.9}}]}
        job = self.started(FIRST)
        self.jobs.confirm({"job": job["id"], "sources": []})
        job = self.wait(job["id"], "done")
        after = self.questions()
        sourced = self.app.question(after["RDB 和 AOF 怎么选？"]["id"])
        self.assertEqual(sourced["answer_status"], "source_backed")
        answer = sourced["answer"]
        self.assertEqual(answer["key_points"], ["有出处的要点"])
        self.assertEqual([s["url"] for s in answer["sources"]], ["https://redis.io/docs/persistence"])
        self.assertEqual((answer["sources"][0]["evidence_quote"], answer["sources"][0]["quote_verified"]), ("RDB 是定时快照", True))
        stored = next(a for a in load_data(self.bank)["answers"] if a["id"] == answer["id"])
        self.assertTrue(any("page text read by the server" in c for c in stored["checks"]))
        self.assertEqual(self.app.question(after["什么是向量数据库？"]["id"])["answer_status"], "ai_draft")
        self.assertEqual(job["answers"]["sourced"], [sourced["id"]])
        self.assertEqual(len(job["answers"]["done"]), 2)
        self.assertEqual(self.web.fetched, ["https://redis.io/docs/persistence", "https://blog.example/redis"])
        self.assertTrue((self.bank / "cache/pages").is_dir())

    def test_existing_drafts_are_upgraded_on_request_and_skips_keep_them(self):
        self.model.screenshots[FIRST] = {"status": "extracted", "questions": [
            {"id": "x", "original_text": "RDB 和 AOF 怎么选？", "sequence": 1, "domains": ["backend.cache"],
             "confidence": {"is_question": 0.99, "classification": 0.9}},
            {"id": "y", "original_text": "这个问题请拒答", "sequence": 2, "domains": ["backend.cache"],
             "confidence": {"is_question": 0.99, "classification": 0.9}}]}
        job = self.started(FIRST)
        self.jobs.confirm({"job": job["id"], "sources": []})
        self.wait(job["id"], "done")
        drafts = {q: self.questions()[q]["id"] for q in ("RDB 和 AOF 怎么选？", "这个问题请拒答")}
        self.assertEqual({self.app.question(i)["answer_status"] for i in drafts.values()}, {"ai_draft"})
        with self.assertRaises(ValidationError):
            self.jobs.research({})
        self.researching()
        overview = self.jobs.overview()
        self.assertGreaterEqual(overview["research"]["candidates"], 2)
        self.assertTrue(self.app.library({})["can_research"])
        job = self.jobs.research({"question_ids": list(drafts.values())})
        self.assertEqual((job["kind"], job["status"]), ("research", "answering"))
        job = self.wait(job["id"], "done")
        self.assertEqual(self.app.question(drafts["RDB 和 AOF 怎么选？"])["answer_status"], "source_backed")
        self.assertEqual(self.app.question(drafts["这个问题请拒答"])["answer_status"], "ai_draft")
        self.assertEqual(job["answers"]["failed"], {drafts["这个问题请拒答"]: "网页之间说法矛盾"})
        with self.assertRaises(ValidationError):
            self.jobs.research({"question_ids": [drafts["RDB 和 AOF 怎么选？"]]})
        demo = self.questions()["Redis 为什么快？"]["id"]
        with self.assertRaises(ValidationError):
            self.jobs.research({"question_ids": [demo]})

    def test_anti_bot_pages_are_skipped_and_a_second_query_adds_the_technology(self):
        self.researching()
        stubs = [{"title": "s", "url": f"https://stub{n}.example/q", "site": None, "snippet": "", "date": None} for n in range(3)]
        self.web.results = lambda query: (Web().results(query)[:1] if query.startswith("redis ") else stubs)
        self.model.screenshots[FIRST] = {"status": "extracted", "questions": [
            {"id": "x", "original_text": "RDB 和 AOF 怎么选？", "sequence": 1, "domains": ["backend.cache"], "technologies": ["redis"],
             "confidence": {"is_question": 0.99, "classification": 0.9}}]}
        job = self.started(FIRST)
        self.jobs.confirm({"job": job["id"], "sources": []})
        job = self.wait(job["id"], "done")
        answer = self.app.question(self.questions()["RDB 和 AOF 怎么选？"]["id"])["answer"]
        self.assertEqual([s["url"] for s in answer["sources"]], ["https://redis.io/docs/persistence"])
        self.assertEqual(self.web.queries, ["RDB 和 AOF 怎么选？", "redis RDB 和 AOF 怎么选？"])
        research = next(text for system, parts in self.model.calls if "You research" in system for text in [parts[0]["text"]])
        self.assertNotIn("stub", research)

    def test_the_daily_search_limit_falls_back_to_drafts(self):
        self.researching({"daily_research": 1})
        self.model.screenshots[FIRST] = {"status": "extracted", "questions": [
            {"id": "x", "original_text": "RDB 和 AOF 怎么选？", "sequence": 1, "domains": ["backend.cache"],
             "confidence": {"is_question": 0.99, "classification": 0.9}},
            {"id": "y", "original_text": "AOF 重写是什么？", "sequence": 2, "domains": ["backend.cache"],
             "confidence": {"is_question": 0.99, "classification": 0.9}}]}
        job = self.started(FIRST)
        self.jobs.confirm({"job": job["id"], "sources": []})
        job = self.wait(job["id"], "done")
        self.assertEqual((len(self.web.queries), len(job["answers"]["sourced"]), len(job["answers"]["done"])), (1, 1, 2))
        with self.assertRaises(ValidationError):
            self.jobs.research({})

    def test_usage_and_cost_are_recorded_per_job_and_per_day_and_a_budget_stops_new_jobs(self):
        prices = {"stand-in": {"hit": 0.02, "miss": 1, "output": 4}, "bocha": {"call": 0.036}}
        self.web = Web()
        self.jobs = self.app.intake = IntakeJobs(self.app.bank, {**CONFIG, "search": SEARCH, "prices": prices,
                                                                  "limits": {**LIMITS, "daily_budget": 0.05}},
                                                 self.app.mutation_lock, call=self.model, search=self.web.search, fetch=self.web.opener)
        self.model.screenshots[FIRST] = {"status": "extracted", "questions": [
            {"id": "x", "original_text": "RDB 和 AOF 怎么选？", "sequence": 1, "domains": ["backend.cache"], "technologies": ["redis"],
             "confidence": {"is_question": 0.99, "classification": 0.9}}]}
        job = self.started(FIRST)
        self.jobs.confirm({"job": job["id"], "sources": []})
        job = self.wait(job["id"], "done")
        usage = job["usage"]
        calls = len(self.model.calls)
        self.assertEqual((usage["calls"], usage["input"], usage["cached"], usage["output"], usage["searches"]),
                         (calls, calls * 10000, calls * 1000, calls * 2000, len(self.web.queries)))
        self.assertAlmostEqual(usage["cost"], calls * (1000 * 0.02 + 9000 * 1 + 2000 * 4) / 1e6 + len(self.web.queries) * 0.036, places=6)
        overview = self.jobs.overview()
        self.assertEqual(overview["usage"]["today"], usage)
        self.assertEqual((overview["usage"]["daily_budget"], overview["recent"][0]["usage"]), (0.05, usage))
        with self.assertRaises(ValidationError) as caught:
            self.jobs.create({"hints": {}})
        self.assertIn("费用", str(caught.exception))

    def test_old_page_texts_are_pruned(self):
        folder = self.bank / "cache/pages"
        folder.mkdir(parents=True, exist_ok=True)
        old, recent = folder / "old.txt", folder / "recent.txt"
        old.write_text("x"), recent.write_text("y")
        os.utime(old, (time.time() - 40 * 86400,) * 2)
        IntakeJobs(self.app.bank, CONFIG, self.app.mutation_lock, call=self.model)
        self.assertEqual((old.exists(), recent.exists()), (False, True))

    def test_a_redirect_to_a_private_address_is_refused(self):
        import urllib.error
        import urllib.request
        from ibank_core.citations import _Redirects
        request = urllib.request.Request("https://public.example/page")
        for target in ("http://127.0.0.1:8765/api/library", "http://100.100.100.200/latest/meta-data/", "http://10.0.0.1/"):
            with self.assertRaises(urllib.error.HTTPError, msg=target):
                _Redirects().redirect_request(request, None, 302, "Found", {}, target)
        self.assertIsNotNone(_Redirects().redirect_request(request, None, 302, "Found", {}, "https://8.8.8.8/elsewhere"))


class HostedIntakeCase(IntakeCase):
    """The same import over HTTP: login and token still apply, uploads are raw image bodies."""

    def start_server(self, ai_config=CONFIG, allow_intake=True):
        self.server = LocalServer(WebApp(self.bank, True, True, True, ai_config, allow_intake))
        if self.server.app.intake:
            self.server.app.intake.call = self.model
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        thread.start()
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close(), thread.join(timeout=2)))

    def request(self, path, body=None, content_type="application/json"):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        raw = body if isinstance(body, bytes) else json.dumps(body).encode() if body is not None else None
        conn.request("POST" if body is not None else "GET", path, raw,
                     {"X-Interview-Token": self.server.token, "Content-Type": content_type})
        response = conn.getresponse()
        result = (response.status, json.loads(response.read()))
        conn.close()
        return result

    def test_http_upload_and_progress(self):
        self.start_server()
        status, job = self.request("/api/intake/jobs", {"hints": {"round": "hr"}})
        self.assertEqual(status, 200, job)
        self.assertEqual(self.request(f"/api/intake/upload?job={job['id']}&image=0", PNG, "text/plain")[0], 400)
        status, job = self.request(f"/api/intake/upload?job={job['id']}&image=0", FIRST, "image/png")
        self.assertEqual((status, job["images"][0]["mime"]), (200, "image/png"))
        self.request("/api/intake/start", {"job": job["id"]})
        self.jobs = self.server.app.intake
        self.wait(job["id"], "review")
        status, overview = self.request("/api/intake")
        self.assertEqual((overview["active"]["status"], overview["models"]["vision"]["model"]), ("review", "stand-in"))
        self.assertNotIn("_key", json.dumps(overview))
        self.assertEqual(self.request("/api/intake/nope", {})[0], 404)

    def test_read_only_reader_imports_only_when_allowed(self):
        self.start_server(allow_intake=False)
        self.assertEqual(self.request("/api/intake"), (200, {"enabled": False}))
        self.assertEqual(self.request("/api/intake/jobs", {"hints": {}})[0], 400)
        self.assertFalse(self.request("/api/library")[1]["can_intake"])

    test_screenshots_become_questions_with_merges_and_draft_answers = None
    test_exact_duplicates_merge_without_asking_and_a_skipped_answer_can_be_retried = None
    test_a_bank_change_during_judging_restages_the_same_confirmation = None
    test_cancel_leaves_the_bank_and_media_untouched = None
    test_a_failed_reading_can_be_retried_and_a_known_screenshot_is_not_read_again = None
    test_parts_of_a_tall_screenshot_are_read_together = None
    test_uploads_and_jobs_are_validated = None
    test_a_restart_leaves_interrupted_jobs_actionable = None
    test_model_output_is_reduced_to_the_extraction_schema = None
    test_new_questions_are_answered_from_pages_the_server_read = None
    test_existing_drafts_are_upgraded_on_request_and_skips_keep_them = None
    test_the_daily_search_limit_falls_back_to_drafts = None
    test_anti_bot_pages_are_skipped_and_a_second_query_adds_the_technology = None
    test_a_redirect_to_a_private_address_is_refused = None
    test_usage_and_cost_are_recorded_per_job_and_per_day_and_a_budget_stops_new_jobs = None
    test_old_page_texts_are_pruned = None


class StandIn(BaseHTTPRequestHandler):
    replies = []
    seen = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        StandIn.seen.append((self.path, dict(self.headers), body))
        status, reply = StandIn.replies.pop(0)
        raw = json.dumps(reply).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *_):
        pass


class ModelClientCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), StandIn)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close()))
        StandIn.replies, StandIn.seen = [], []
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def config(self, raw, key="sk-secret-value"):
        (self.dir / "key").write_text(key + "\n")
        os.chmod(self.dir / "key", 0o600)
        (self.dir / "ai.json").write_text(json.dumps(raw))
        return ai.load_config(self.dir / "ai.json")

    def test_openai_compatible_request_and_fenced_reply(self):
        config = self.config({"vision": {"base_url": self.base + "/v1", "model": "vl", "api_key_file": "key"},
                              "text": {"model": "chat"}, "limits": {"daily_images": 5}})
        self.assertEqual((config["text"]["model"], config["text"]["base_url"], config["limits"]["daily_images"]), ("chat", self.base + "/v1", 5))
        StandIn.replies = [(200, {"choices": [{"message": {"content": "结果如下：\n```json\n{\"status\": \"no_questions\"}\n```"}}]})]
        reply = ai.call(config["vision"], "system", [{"text": "hi"}, {"image": PNG, "mime": "image/png"}])
        self.assertEqual(reply, {"status": "no_questions"})
        path, headers, body = StandIn.seen[0]
        self.assertEqual((path, headers["Authorization"]), ("/v1/chat/completions", "Bearer sk-secret-value"))
        self.assertTrue(body["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,"))
        self.assertNotIn("sk-secret", json.dumps(ai.describe(config)))

    def test_anthropic_request_errors_and_retries(self):
        config = self.config({"vision": {"protocol": "anthropic", "base_url": self.base, "model": "claude", "api_key_file": "key"}})
        StandIn.replies = [(429, {}), (200, {"content": [{"type": "text", "text": "{\"ok\": true}"}]}), (401, {"error": "bad key"})]
        self.assertEqual(ai.call(config["vision"], "s", [{"image": JPEG, "mime": "image/jpeg"}], sleep=lambda _: None), {"ok": True})
        path, headers, body = StandIn.seen[-1]
        self.assertEqual((path, headers["X-Api-Key"], body["messages"][0]["content"][0]["source"]["media_type"]),
                         ("/v1/messages", "sk-secret-value", "image/jpeg"))
        with self.assertRaises(ai.AIError) as caught:
            ai.call(config["vision"], "s", [{"text": "x"}], sleep=lambda _: None)
        self.assertIn("401", str(caught.exception))
        self.assertNotIn("sk-secret", str(caught.exception))

    def test_configuration_is_checked(self):
        for raw in ({"vision": {"base_url": "http://models.example.com", "model": "m", "api_key_file": "key"}},
                    {"vision": {"base_url": "https://u:p@models.example.com", "model": "m", "api_key_file": "key"}},
                    {"vision": {"base_url": "https://models.example.com", "api_key_file": "key"}},
                    {"vision": {"base_url": "https://models.example.com", "model": "m", "api_key": "inline"}},
                    {"vision": {"base_url": "https://models.example.com", "model": "m", "api_key_env": "IBANK_TEST_UNSET"}},
                    {"vision": {"base_url": "https://models.example.com", "model": "m", "api_key_file": "key"}, "limits": {"daily_images": 0}},
                    {"text": {"model": "m"}}):
            with self.assertRaises(Exception, msg=raw):
                self.config(raw)
        os.environ["IBANK_TEST_KEY"] = "from-env"
        self.addCleanup(os.environ.pop, "IBANK_TEST_KEY")
        config = self.config({"vision": {"base_url": "https://models.example.com", "model": "m", "api_key_env": "IBANK_TEST_KEY"}})
        self.assertEqual(config["vision"]["_key"], "from-env")
        if os.name != "nt":
            (self.dir / "ai.json").write_text(json.dumps({"vision": {"base_url": "https://m.example.com", "model": "m", "api_key_file": "key"}}))
            (self.dir / "key").chmod(0o644)
            with self.assertRaises(ValidationError):
                ai.load_config(self.dir / "ai.json")

    def test_provider_options_and_the_shipped_example(self):
        example = json.loads((ROOT / "tools/deploy/ai.example.json").read_text(encoding="utf-8"))
        example["vision"]["api_key_file"] = example["search"]["api_key_file"] = "key"
        config = self.config(example)
        self.assertEqual((config["search"]["provider"], config["search"]["pages"], config["limits"]["daily_research"]), ("bocha", 4, 100))
        self.assertEqual((config["vision"]["model"], config["vision"]["extra_body"]), ("deepseek-flash", {"thinking": {"type": "disabled"}}))
        self.assertEqual((config["text"]["model"], config["text"]["base_url"], config["text"]["extra_body"], config["text"]["_key"]),
                         ("deepseek-flash", "https://api.deepseek.com", {"thinking": {"type": "disabled"}}, "sk-secret-value"))
        self.assertTrue(config["vision"]["json_mode"] and config["text"]["json_mode"])
        config = self.config({"vision": {"base_url": self.base + "/api/paas/v4", "model": "glm-4.6v-flash", "api_key_file": "key",
                                         "image_encoding": "base64", "extra_body": {"thinking": {"type": "enabled"}}}})
        StandIn.replies = [(200, {"choices": [{"message": {"reasoning_content": "想一想", "content": "{\"ok\": true}"}}]})]
        self.assertEqual(ai.call(config["vision"], "s", [{"image": PNG, "mime": "image/png"}]), {"ok": True})
        path, _, body = StandIn.seen[-1]
        self.assertEqual((path, body["thinking"], body["model"]), ("/api/paas/v4/chat/completions", {"type": "enabled"}, "glm-4.6v-flash"))
        self.assertFalse(body["messages"][1]["content"][0]["image_url"]["url"].startswith("data:"))
        for bad in ({"model": "other"}, {"messages": []}, "thinking"):
            with self.assertRaises(ValidationError):
                self.config({"vision": {"base_url": self.base, "model": "m", "api_key_file": "key", "extra_body": bad}})

    def test_search_section_and_both_providers(self):
        (self.dir / "search-key").write_text("bocha-secret\n")
        os.chmod(self.dir / "search-key", 0o600)
        config = self.config({"vision": {"base_url": self.base, "model": "m", "api_key_file": "key"},
                              "search": {"api_key_file": "search-key", "pages": 3}})
        self.assertEqual((config["search"]["provider"], config["search"]["pages"], config["search"]["_key"]), ("bocha", 3, "bocha-secret"))
        self.assertEqual(ai.describe(config)["search"], {"provider": "bocha", "pages": 3})
        StandIn.replies = [(200, {"code": 200, "data": {"webPages": {"value": [
            {"name": "Redis persistence", "url": "https://redis.io/docs/persistence", "summary": "RDB and AOF", "siteName": "Redis",
             "datePublished": "2025-01-01T00:00:00+08:00"}, {"name": "bad", "url": "javascript:alert(1)"}]}}}),
            (200, {"results": [{"title": "T", "url": "https://example.org/a", "content": "c"}]}), (401, {})]
        found = ai.search({**config["search"], "url": self.base + "/v1/web-search"}, "Redis 持久化")
        self.assertEqual([(r["url"], r["site"]) for r in found], [("https://redis.io/docs/persistence", "Redis")])
        path, headers, body = StandIn.seen[-1]
        self.assertEqual((path, headers["Authorization"], body["query"], body["count"]), ("/v1/web-search", "Bearer bocha-secret", "Redis 持久化", 8))
        tavily = {**config["search"], "provider": "tavily", "url": self.base + "/search"}
        self.assertEqual(ai.search(tavily, "q")[0]["url"], "https://example.org/a")
        with self.assertRaises(ai.AIError) as caught:
            ai.search(tavily, "q")
        self.assertNotIn("bocha-secret", str(caught.exception))
        for bad in ({"provider": "google"}, {"pages": 9}, {}):
            with self.assertRaises(Exception, msg=bad):
                self.config({"vision": {"base_url": self.base, "model": "m", "api_key_file": "key"},
                             "search": {"api_key_env": "IBANK_TEST_UNSET", **bad}})

    def test_usage_is_read_from_each_protocol_and_priced_by_the_hour(self):
        deepseek = ai._usage("openai", "deepseek-flash", {"usage": {"prompt_tokens": 100, "completion_tokens": 30,
                             "prompt_cache_hit_tokens": 60, "prompt_cache_miss_tokens": 40}})
        openai = ai._usage("openai", "gpt", {"usage": {"prompt_tokens": 100, "completion_tokens": 30, "prompt_tokens_details": {"cached_tokens": 20}}})
        anthropic = ai._usage("anthropic", "claude", {"usage": {"input_tokens": 80, "output_tokens": 30, "cache_read_input_tokens": 20}})
        self.assertEqual([(u["hit"], u["miss"], u["output"]) for u in (deepseek, openai, anthropic)], [(60, 40, 30), (20, 80, 30), (20, 80, 30)])
        prices = ai._prices({"deepseek-flash": {"peak": {"hit": 0.04, "miss": 2, "output": 8}, "off_peak": {"hit": 0.02, "miss": 1, "output": 4}},
                             "bocha": {"call": 0.036}})
        entry = {"kind": "model", "model": "deepseek-flash", "hit": 1_000_000, "miss": 1_000_000, "output": 1_000_000}
        self.assertAlmostEqual(ai.cost({**entry, "at": "2026-10-28T06:30:00+00:00"}, prices), 10.04)
        self.assertAlmostEqual(ai.cost({**entry, "at": "2026-10-31T06:30:00+00:00"}, prices), 5.02)
        self.assertEqual(ai.cost({"kind": "search", "provider": "bocha"}, prices), 0.036)
        self.assertIsNone(ai.cost({**entry, "model": "other", "at": "2026-10-28T06:30:00+00:00"}, prices))
        StandIn.replies = [(200, {"choices": [{"message": {"content": "{}"}}], "usage": {"prompt_tokens": 5, "completion_tokens": 2}})]
        config = self.config({"vision": {"base_url": self.base, "model": "m", "api_key_file": "key"}})
        with ai.metering():
            ai.call(config["vision"], "s", [{"text": "x"}])
            [recorded] = ai.take_usage()
        self.assertEqual((recorded["model"], recorded["miss"], recorded["output"]), ("m", 5, 2))
        self.assertEqual(ai.take_usage(), [])
        for bad in ({"m": {"hit": 1}}, {"m": {"call": -1}}):
            with self.assertRaises(ValidationError):
                ai._prices(bad)
        with self.assertRaises(ValidationError):
            self.config({"vision": {"base_url": self.base, "model": "m", "api_key_file": "key"}, "limits": {"daily_budget": 5}})

    def test_prompts_are_cut_from_the_skill_references(self):
        prompt = ai_prompts.extraction_prompt()
        for name, heading in ai_prompts.EXTRACTION_SECTIONS:
            self.assertIn(ai_prompts.section(name, heading), prompt)
        self.assertIn("backend.cache", prompt)
        self.assertIn(ai_prompts.section("dedupe.md", "Judging a pair"), ai_prompts.dedupe_prompt())
        self.assertIn("字节跳动", ai_prompts.extraction_request({"company": "字节跳动"}))


if __name__ == "__main__":
    unittest.main()
