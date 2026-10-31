"""Pasted text and links in the Web import: the screenshot pipeline, anchored to the numbered paragraphs of the post."""
import json
import tempfile
import time
import unittest
from pathlib import Path

import support  # noqa: F401  (puts the Skill's scripts on sys.path)
from ibank_core import ai
from ibank_core.demo import build_demo
from ibank_core.errors import ValidationError
from ibank_core.storage import load_data
from ibank_core.web import WebApp
from ibank_core.web_intake import IntakeJobs, MAX_TEXT, clean_page, clean_page_input, page_text, platform_of
from test_web_intake import CONFIG, ROOT, Model, Web, finish_workers

POST = "\n".join(["面经：某公司后端一面（3 月面的）", "1. Redis 为什么这么快？", "2. 讲讲 HashMap 的扩容机制", "3. 你期望的薪资是多少", "欢迎交流"])
SCORES = {"is_question": 0.99, "classification": 0.95}


def reading(**overrides):
    reply = {"status": "extracted",
             "metadata": {"company": "示例科技", "round": "technical-1", "platform": "模型猜的平台", "source_date": "2026-01-01",
                          "event_date": "2025-10-28", "event_date_quote": "面经（3 月面的）"},
             "questions": [
                 {"id": "q1", "segment_ids": [2], "canonical_suggestion": "Redis 为什么这么快？", "domains": ["backend.cache"],
                  "technologies": ["redis"], "concept": "redis.performance.why-fast", "confidence": SCORES},
                 {"id": "q2", "segment_ids": [3], "canonical_suggestion": "HashMap 的扩容机制是什么？", "domains": ["backend.cache"],
                  "confidence": SCORES},
                 # A paragraph that does not exist, and a question with no paragraph at all, are not kept.
                 {"id": "q3", "segment_ids": [99], "canonical_suggestion": "凭空出现的问题", "confidence": SCORES},
                 {"id": "q4", "original_text": "模型自己写的原文", "canonical_suggestion": "没有出处的问题", "confidence": SCORES}]}
    reply.update(overrides)
    return reply


class PageModel(Model):
    """The text model of the page import: answers from `self.reading` and records what it was shown."""

    def __init__(self):
        super().__init__({})
        self.reading, self.reads = reading(), []

    def __call__(self, endpoint, system, parts):
        if "reading step" not in system:
            return super().__call__(endpoint, system, parts)
        self.reads.append((system, parts[0]["text"]))
        ai.record({"kind": "model", "model": endpoint["model"], "hit": 1000, "miss": 9000, "output": 2000})
        if isinstance(self.reading, Exception):
            raise self.reading
        return self.reading


class PageWeb(Web):
    """The pages of the stand-in web: a URL maps to the HTML it serves."""

    def __init__(self):
        super().__init__()
        self.pages = {}

    def opener(self, request, timeout):
        import email.message
        url = request.full_url
        self.fetched.append(url)
        headers = email.message.Message()
        headers["Content-Type"] = "text/html; charset=utf-8"
        body = self.pages[url].encode()

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


def html(post, padding=True):
    lines = "".join(f"<p>{line}</p>" for line in post.splitlines())
    filler = "<p>" + "这是帖子下面的广告和推荐位。" * 20 + "</p>" if padding else ""
    return f"<html><body><nav>菜单</nav>{lines}{filler}</body></html>"


class PageCase(unittest.TestCase):
    def setUp(self):
        work = ROOT / ".work/tests"
        work.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=work)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(finish_workers, "ibank-intake-")
        self.bank = Path(self.temp.name) / "bank"
        build_demo(self.bank, v2=True)
        self.web, self.model = PageWeb(), PageModel()
        self.app = WebApp(self.bank, read_only=True, allow_my_answers=True, allow_practice=True)
        self.jobs = self.app.intake = IntakeJobs(self.app.bank, CONFIG, self.app.mutation_lock, call=self.model, fetch=self.web.opener)

    def wait(self, job_id, *states):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            job = self.jobs.job(job_id)
            if job["status"] in states:
                return job
            time.sleep(0.02)
        self.fail(f"job stayed {job['status']}: {job.get('error')}")

    def paste(self, text=POST, **extra):
        job = self.jobs.create({"hints": extra.pop("hints", {}), "input": "text", "text": text, **extra})
        return self.wait(job["id"], "review", "done")

    def confirm(self, job, keep=None):
        sources = [{"source_id": s["source_id"], "metadata": {}, "questions": [{"id": q["id"], "keep": keep is None or q["id"] in keep}
                                                                              for q in s["questions"]]}
                   for s in job["sources"] if s["status"] == "extracted"]
        self.jobs.confirm({"job": job["id"], "sources": sources})
        return self.wait(job["id"], "done", "merge_review")

    def rows(self):
        data = load_data(self.bank)
        return {q["canonical"]: q for q in data["questions"] if q["status"] == "active"}, data


class PastedText(PageCase):
    def test_questions_are_anchored_to_the_paragraphs_they_cite(self):
        job = self.paste(source_date="2026-10-20")
        (source,) = job["sources"]
        self.assertEqual((job["input"], source["status"], source["segments"]), ("text", "extracted", 5))
        by_id = {q["id"]: q for q in source["questions"]}
        self.assertEqual(len(by_id), 2)
        first = by_id["s1-q1"]
        # The original wording is the paragraph itself; the model's wording is only the suggestion.
        self.assertEqual((first["original_text"], first["canonical_suggestion"], first["segment_ids"]), ("1. Redis 为什么这么快？", "Redis 为什么这么快？", [2]))
        self.assertEqual(first["concept"], "redis.performance.why-fast")
        system, text = self.model.reads[0]
        self.assertIn("[2] 1. Redis 为什么这么快？", text)
        self.assertNotIn("event_date", system)
        self.assertNotIn("Keys already in the bank", system)

    def test_the_model_chooses_neither_platform_nor_posting_date_nor_interview_date(self):
        # The reply carries a date and a quote that really is in the post, as a title like "面经10.28" would give.
        (source,) = self.paste()["sources"]
        self.assertEqual(source["metadata"], {"company": "示例科技", "round": "technical-1"})

    def test_the_interview_date_is_the_persons_hint(self):
        (source,) = self.paste(hints={"event_date": "2026-03"})["sources"]
        self.assertEqual(source["metadata"]["event_date"], "2026-03")

    def test_a_confirmed_import_saves_a_text_source_with_the_post_date_and_the_persons_interview_date(self):
        job = self.paste(source_date="2026-10-20", hints={"company": "手填的公司", "event_date": "2026-03"})
        done = self.confirm(job)
        self.assertEqual(done["status"], "done")
        self.assertEqual(sorted(q["canonical"] for q in done["result"]["added"]), ["HashMap 的扩容机制是什么？", "Redis 为什么这么快？"])
        questions, data = self.rows()
        source = next(s for s in data["sources"] if s["id"] == job["sources"][0]["source_id"])
        self.assertEqual((source["type"], source["source_url"], source["platform"], source["source_date"]), ("text", None, None, "2026-10-20"))
        occurrence = next(o for o in data["occurrences"] if o["question_id"] == questions["Redis 为什么这么快？"]["id"])
        self.assertEqual(occurrence["original_text"], "1. Redis 为什么这么快？")
        self.assertEqual(occurrence["locator"]["segment_ids"], [2])
        self.assertEqual(occurrence["event_date"], "2026-03")  # what the person entered, not the posting date
        self.assertEqual(questions["Redis 为什么这么快？"].get("concept"), "redis.performance.why-fast")

    def test_the_posting_date_never_becomes_the_interview_date(self):
        job = self.paste(source_date="2026-10-20")
        self.confirm(job)
        questions, data = self.rows()
        dates = {o["event_date"] for o in data["occurrences"] if o["question_id"] in {questions["Redis 为什么这么快？"]["id"]}}
        self.assertEqual(dates, {None})

    def test_the_same_text_twice_adds_nothing(self):
        self.confirm(self.paste())
        again = self.paste()
        self.assertEqual((again["status"], again["result"]["nothing_new"]), ("done", True))

    def test_a_question_the_person_unticks_is_left_out(self):
        job = self.paste()
        self.confirm(job, keep={"s1-q1"})
        questions, _ = self.rows()
        self.assertIn("Redis 为什么这么快？", questions)
        self.assertNotIn("HashMap 的扩容机制是什么？", questions)

    def test_a_post_with_no_questions_is_reported_and_can_be_confirmed_empty(self):
        self.model.reading = {"status": "no_questions", "reason": "只有闲聊", "questions": []}
        job = self.paste()
        self.assertEqual((job["sources"][0]["status"], job["sources"][0]["reason"]), ("no_questions", "只有闲聊"))
        self.jobs.confirm({"job": job["id"], "sources": []})
        self.assertEqual(self.wait(job["id"], "done", "review")["status"], "done")

    def test_a_failed_reading_can_be_read_again(self):
        self.model.reading = ai.AIError("模型暂时不可用")
        job = self.paste()
        self.assertEqual((job["status"], job["sources"][0]["status"], job["sources"][0]["error"]), ("review", "failed", "模型暂时不可用"))
        self.model.reading = reading()
        self.jobs.retry_extract({"job": job["id"]})
        job = self.wait(job["id"], "review")
        self.assertEqual(job["sources"][0]["status"], "extracted")

    def test_a_restart_while_reading_leaves_the_post_to_be_read_again(self):
        job = self.paste()
        path = self.jobs._dir(job["id"]) / "job.json"
        stored = json.loads(path.read_text(encoding="utf-8"))
        stored.update(status="extracting", progress={"phase": "extract", "done": 0, "total": 1})
        stored["sources"][0].update(status="pending", questions=[], metadata={})
        path.write_text(json.dumps(stored, ensure_ascii=False), encoding="utf-8")
        restarted = IntakeJobs(self.app.bank, CONFIG, self.app.mutation_lock, call=self.model, fetch=self.web.opener)
        recovered = restarted.job(job["id"])
        self.assertEqual((recovered["status"], recovered["sources"][0]["status"]), ("review", "failed"))
        self.jobs = restarted
        restarted.retry_extract({"job": job["id"]})
        self.assertEqual(self.wait(job["id"], "review")["sources"][0]["status"], "extracted")

    def test_cancelling_drops_the_import(self):
        job = self.paste()
        self.jobs.cancel({"job": job["id"]})
        self.assertIsNone(self.jobs.overview()["active"])
        self.assertEqual(self.rows()[0].get("Redis 为什么这么快？"), None)

    def test_one_import_at_a_time(self):
        self.paste()
        with self.assertRaises(ValidationError):
            self.jobs.create({"hints": {}, "input": "text", "text": POST + "\n另一篇"})

    def test_the_overview_tells_how_much_text_is_read(self):
        self.assertEqual(self.jobs.overview()["limits"]["max_text"], MAX_TEXT)


class Links(PageCase):
    URL = "https://www.nowcoder.com/discuss/123456"

    def test_a_link_is_read_by_the_server_and_its_platform_named(self):
        self.web.pages[self.URL] = html(POST)
        job = self.jobs.create({"hints": {}, "input": "url", "url": self.URL})
        job = self.wait(job["id"], "review")
        self.assertEqual((job["input"], job["origin"]["url"], job["origin"]["platform"]), ("url", self.URL, "牛客"))
        self.assertEqual(self.web.fetched, [self.URL])
        self.assertEqual(len(job["sources"][0]["questions"]), 2)
        self.confirm(job)
        _, data = self.rows()
        source = next(s for s in data["sources"] if s["id"] == job["sources"][0]["source_id"])
        self.assertEqual((source["type"], source["source_url"], source["platform"]), ("web", self.URL, "牛客"))

    def test_a_page_that_cannot_be_read_is_refused_at_once_with_the_way_out(self):
        self.web.pages[self.URL] = "<html><body>" + "<script>var arg1='5dcd8af6';</script>" + "访问验证 " * 80 + "</body></html>"
        with self.assertRaises(ValidationError) as caught:
            self.jobs.create({"hints": {}, "input": "url", "url": self.URL})
        self.assertIn("粘贴文字", str(caught.exception))
        self.assertIsNone(self.jobs.overview()["active"])
        self.assertEqual(self.jobs.overview()["recent"], [])

    def test_an_address_the_server_must_not_open_is_named_as_such(self):
        with self.assertRaises(ValidationError) as caught:
            self.jobs.create({"hints": {}, "input": "url", "url": "http://127.0.0.1:8765/secret"})
        self.assertIn("不是公开网址", str(caught.exception))
        self.assertNotIn("refused", str(caught.exception))
        self.assertEqual(self.web.fetched, [])

    def test_a_very_long_page_is_cut_and_the_person_is_told(self):
        body = "\n".join(["面试题 " + str(n) + "：" + "题目内容" * 20 for n in range(1, 400)])
        self.web.pages[self.URL] = html(body, padding=False)
        job = self.jobs.create({"hints": {}, "input": "url", "url": self.URL})
        job = self.wait(job["id"], "review", "done")
        self.assertIn(str(MAX_TEXT), job["notice"])
        self.assertLessEqual(job["origin"]["characters"], MAX_TEXT)


class Inputs(unittest.TestCase):
    def test_what_may_be_given(self):
        ok = clean_page_input({"input": "text", "text": "1. Redis 为什么快？", "url": "https://example.org/p/1", "source_date": "2026-10"})
        self.assertEqual((ok["input"], ok["url"], ok["source_date"]), ("text", "https://example.org/p/1", "2026-10"))
        for bad in ({"input": "images"}, {"input": "text", "text": "短"}, {"input": "text", "text": "字" * (MAX_TEXT * 2 + 1)},
                    {"input": "url"}, {"input": "url", "url": "ftp://example.org/x"}, {"input": "url", "url": "https://u:p@example.org/x"},
                    {"input": "text", "text": "1. Redis 为什么快？", "source_date": "昨天"}, {"input": "text", "text": "x" * 20, "extra": 1},
                    {"input": "url", "url": "https://example.org/?mail=a" + chr(64) + "b.com"}):  # a contact detail in the link
            with self.assertRaises(ValidationError, msg=str(bad)):
                clean_page_input(bad)

    def test_text_becomes_one_paragraph_per_line_and_is_capped(self):
        text, cut = page_text("第一行  内容\r\n\r\n 第二行　内容 \n\n\n第三行")
        self.assertEqual((text, cut), ("第一行 内容\n\n第二行 内容\n\n第三行", False))
        long_text, cut = page_text("\n".join("行" * 1000 for _ in range(40)))
        self.assertTrue(cut)
        self.assertLessEqual(len(long_text.replace("\n", "")), MAX_TEXT)

    def test_platform_names(self):
        self.assertEqual(platform_of("https://www.nowcoder.com/discuss/1"), "牛客")
        self.assertEqual(platform_of("https://m.xiaohongshu.com/x"), "小红书")
        self.assertEqual(platform_of("https://blog.example.org/a"), "blog.example.org")

    def test_paragraphs_cited_together_are_joined_in_order(self):
        segments = [{"id": 1, "text": "标题"}, {"id": 2, "text": "题目的前半句"}, {"id": 3, "text": "题目的后半句"}]
        job = {"hints": {}, "origin": {}}
        raw = {"status": "extracted", "questions": [{"id": "a", "segment_ids": [3, 2, 2], "canonical_suggestion": "完整的题目", "confidence": SCORES}]}
        (question,) = clean_page(raw, job, segments, {})["questions"]
        self.assertEqual((question["original_text"], question["segment_ids"]), ("题目的前半句\n题目的后半句", [2, 3]))


if __name__ == "__main__":
    unittest.main()
