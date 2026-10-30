"""Mock interviews and answer feedback in the Web reader, with a stand-in model."""
import http.client
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

import support  # noqa: F401  (puts the Skill's scripts on sys.path)
from ibank_core import ai, ai_prompts
from ibank_core.demo import build_demo
from ibank_core.errors import ValidationError
from ibank_core.interview import interview
from ibank_core.storage import load_data
from ibank_core.web import LocalServer, WebApp
from ibank_core.web_interview import clean_feedback, clean_plan

ROOT = Path(__file__).resolve().parents[1]
LIMITS = {"max_images_per_job": 12, "max_answers_per_job": 40, "daily_images": 60, "answer_batch": 4, "daily_research": 100,
          "daily_budget": 0, "daily_feedback": 200}
ENDPOINT = {"protocol": "openai", "base_url": "http://127.0.0.1:9", "model": "stand-in", "timeout": 5, "max_tokens": 1024,
            "temperature": 0.2, "json_mode": False, "_key": None}
CONFIG = {"vision": ENDPOINT, "text": ENDPOINT, "limits": LIMITS, "prices": {}}
FAST = "Redis 为什么快？"
DEADLOCK = "什么是死锁？"


class Model:
    """Gives feedback the way a model would: from the request text only; records what it was given."""

    def __init__(self):
        self.calls, self.fail, self.follow_up = [], [], True
        self.extra_observation = {"dimension": "clarity", "verdict": "gap", "quote": "这句话不在回答里", "note": "表述不清"}

    def __call__(self, endpoint, system, parts):
        text = parts[0]["text"]
        self.calls.append((system, text))
        ai.record({"kind": "model", "model": endpoint["model"], "hit": 0, "miss": 2000, "output": 500})
        if self.fail:
            raise self.fail.pop(0)
        if "choose practice questions" in system:
            ids = [line.split(" | ")[0] for line in text.split("--- bank questions (id | count | text) ---\n", 1)[1].splitlines()]
            return {"picks": [{"id": ids[1], "quote": "熟悉 Redis", "reason": "直接考察"}, {"id": "q_unknown", "quote": "x", "reason": "不存在"},
                              {"id": ids[1], "quote": "熟悉 Redis", "reason": "重复"}, {"id": ids[0], "quote": "不在原文里", "reason": "相关"}],
                    "uncovered": ["有数据库性能优化经验", "原文里没有的要求"]}
        answer = text.split("--- the person's response (verbatim) ---\n", 1)[1]
        # Like a careless model: it returns verdicts and key-point checks even when told there is no reference.
        reply = {"observations": [{"dimension": "coverage", "verdict": "gap", "quote": answer[:6], "note": "只讲了内存"},
                                  {"dimension": "accuracy", "verdict": "met", "note": "方向正确"}, self.extra_observation],
                 "key_point_checks": [{"index": 0, "status": "covered", "note": "提到内存"}, {"index": 1, "status": "missed", "note": ""},
                                      {"index": 99, "status": "covered", "note": "不存在的要点"}, {"index": 0, "status": "missed"}],
                 "review_topics": ["IO 多路复用", "IO 多路复用", "  "], "limited_basis": 'basis: "limited"' in text,
                 "follow_up": {"prompt": "那单线程会不会成为瓶颈？", "reason": "回答没有讲边界"} if self.follow_up else None}
        return reply


class InterviewCase(unittest.TestCase):
    def setUp(self):
        work = ROOT / ".work/tests"
        work.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=work)
        self.addCleanup(self.temp.cleanup)
        self.bank = Path(self.temp.name) / "bank"
        build_demo(self.bank, v2=True)
        self.model = Model()
        self.app = WebApp(self.bank, read_only=True, allow_practice=True, ai_config=CONFIG, allow_intake=True)
        self.coach = self.app.coach
        self.coach.call = self.model
        self.ids = {q["canonical"]: q["id"] for q in load_data(self.bank)["questions"]}

    def graded(self, session_id, count=1):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            view = self.coach.session(session_id)
            if sum(r["feedback"] is not None for r in view["responses"]) >= count or (view["grading"] or {}).get("state") == "failed":
                return view
            time.sleep(0.02)
        self.fail("feedback never arrived")

    def answer(self, session_id, question_id, text, request_id):
        return self.coach.answer({"session": session_id, "question_id": question_id, "request_id": request_id, "text": text})

    def test_a_mock_interview_from_start_to_summary(self):
        # The person's order is kept, not the library's.
        view = self.coach.start({"question_ids": [self.ids[DEADLOCK], self.ids[FAST]], "meta": {"direction": "后端基础"}})
        self.assertEqual((view["total"], view["current"]["status"], view["current"]["prompt"]), (2, "question", DEADLOCK))
        self.assertEqual(view["meta"], {"direction": "后端基础", "mode": "mock", "interface": "web"})
        view = self.answer(view["id"], self.ids[DEADLOCK], "多个线程互相等待对方释放锁。", "r1")
        self.assertEqual(view["current"]["status"], "awaiting_feedback")
        view = self.graded(view["id"])
        # No reference answer: the model is told so, and nothing may be called right or wrong.
        system, request = self.model.calls[0]
        self.assertIn('basis: "limited"', request)
        self.assertNotIn("Key points", request)
        feedback = view["responses"][0]["feedback"]
        self.assertTrue(feedback["limited_basis"])
        self.assertTrue(all("verdict" not in o for o in feedback["observations"]))
        self.assertEqual(feedback["key_point_checks"], [])
        self.assertEqual(feedback["generated_by"]["model"], "stand-in")
        self.assertIsNone(feedback["reference_answer_id"])
        self.assertEqual(view["current"]["prompt"], FAST)

        view = self.answer(view["id"], self.ids[FAST], "Redis 把数据放在内存里，所以很快。", "r2")
        view = self.graded(view["id"], 2)
        system, request = self.model.calls[1]
        self.assertIn("Redis 把数据放在内存里，所以很快。", request)
        self.assertIn("0. 数据集放在内存中", request)
        self.assertIn(ai_prompts.section("practice.md", "Writing feedback"), system)
        feedback = view["responses"][1]["feedback"]
        self.assertFalse(feedback["limited_basis"])
        # Quotes the person did not write are dropped; unknown or repeated key points are ignored.
        self.assertEqual([o.get("quote") for o in feedback["observations"]], ["Redis", None, None])
        self.assertEqual([c["index"] for c in feedback["key_point_checks"]], [0, 1])
        self.assertEqual(feedback["review_topics"], ["IO 多路复用"])
        self.assertEqual(feedback["generated_by"]["checks"], ["一处引文在你的回答里找不到，已去掉"])
        self.assertTrue(feedback["reference_sources"])
        self.assertEqual(feedback["suggested_follow_up"]["prompt"], "那单线程会不会成为瓶颈？")

        # The suggested follow-up is asked as the next prompt; two follow-ups at most.
        view = self.coach.follow_up({"session": view["id"]})
        self.assertEqual((view["current"]["prompt"], view["current"]["follow_up"], view["current"]["question_id"]), ("那单线程会不会成为瓶颈？", True, self.ids[FAST]))
        view = self.answer(view["id"], self.ids[FAST], "单线程在 CPU 密集时会成为瓶颈。", "r3")
        view = self.graded(view["id"], 3)
        self.assertEqual(view["follow_ups_left"], 1)
        self.assertIn("Asked as a follow-up: 那单线程会不会成为瓶颈？", self.model.calls[2][1])
        self.assertIn("Earlier in this exchange the person answered: Redis 把数据放在内存里", self.model.calls[2][1])
        self.coach.follow_up({"session": view["id"]})
        self.answer(view["id"], self.ids[FAST], "可以用多实例分担。", "r4")
        view = self.graded(view["id"], 4)
        self.assertEqual(view["follow_ups_left"], 0)
        with self.assertRaises(ValidationError):
            self.coach.follow_up({"session": view["id"]})

        self.assertEqual(view["current"]["status"], "completed")
        view = self.coach.end({"session": view["id"]})
        self.assertEqual(view["status"], "completed")
        self.assertEqual((view["summary"]["answered"], view["summary"]["graded"], view["summary"]["limited"]), (4, 4, 1))
        self.assertEqual(view["summary"]["key_points"], {"covered": 3, "partial": 0, "missed": 3})
        self.assertEqual(view["summary"]["weak_topics"], ["IO 多路复用"])

        # The same record the CLI reads, written through the same checks.
        shown = interview(self.bank, "show", key=view["id"])
        self.assertEqual([r["text"] for r in shown["responses"]][:2], ["多个线程互相等待对方释放锁。", "Redis 把数据放在内存里，所以很快。"])
        usage = self.app.intake.ledger.view()["today"]
        self.assertEqual((usage["calls"], usage["input"], usage["output"]), (4, 8000, 2000))
        self.assertEqual(load_data(self.bank)["_state"]["events"], {})

    def test_the_prompt_never_carries_the_reference_answer(self):
        view = self.coach.start({"question_ids": [self.ids[FAST]], "mode": "review"})
        self.assertEqual(view["meta"]["mode"], "review")
        text = json.dumps(view, ensure_ascii=False)
        self.assertNotIn("数据集放在内存中", text)
        self.assertNotIn("answer", view["current"])
        self.assertTrue(view["name"].startswith("批改："))

    def test_a_failed_grading_keeps_the_answer_and_can_be_tried_again(self):
        view = self.coach.start({"question_ids": [self.ids[FAST]], "mode": "review"})
        self.model.fail = [ai.AIError("模型服务返回 HTTP 429：调用太频繁。")]
        self.answer(view["id"], self.ids[FAST], "因为在内存里。", "retry-1")
        view = self.graded(view["id"])
        self.assertEqual(view["grading"]["state"], "failed")
        self.assertIn("HTTP 429", view["grading"]["error"])
        self.assertEqual((view["responses"][0]["text"], view["responses"][0]["feedback"], view["current"]["status"]), ("因为在内存里。", None, "awaiting_feedback"))
        # The failed call was still billed.
        self.assertEqual(self.app.intake.ledger.view()["today"]["calls"], 1)
        # Sending the same answer again records nothing twice; a new grading starts.
        self.answer(view["id"], self.ids[FAST], "因为在内存里。", "retry-1")
        view = self.graded(view["id"])
        self.assertEqual(len(view["responses"]), 1)
        self.assertEqual(view["responses"][0]["feedback"]["generated_by"]["model"], "stand-in")
        self.assertIsNone(view["grading"])
        with self.assertRaises(ValidationError):
            self.answer(view["id"], self.ids[FAST], "不同的内容", "retry-1")
        # An answer left without feedback (for example by a restart) is graded on request.
        self.coach.follow_up({"session": view["id"]})
        self.model.fail = [ai.AIError("连不上模型服务")]
        self.answer(view["id"], self.ids[FAST], "再答一次。", "retry-2")
        self.assertEqual(self.graded(view["id"], 2)["grading"]["state"], "failed")
        self.coach.work.clear()
        self.assertTrue(self.coach.regrade({"session": view["id"]})["grading"])
        self.assertEqual(self.graded(view["id"], 2)["current"]["status"], "completed")

    def test_empty_long_and_unknown_answers_are_refused_before_anything_is_saved(self):
        view = self.coach.start({"question_ids": [self.ids[FAST]]})
        for text in ("   ", "字" * 8001):
            with self.assertRaises(ValidationError):
                self.answer(view["id"], self.ids[FAST], text, "bad")
        with self.assertRaises(ValidationError):
            self.answer(view["id"], self.ids[DEADLOCK], "不是当前这一题", "bad2")
        with self.assertRaises(ValidationError):
            self.coach.session("session_missing")
        self.assertEqual(self.coach.session(view["id"])["responses"], [])
        self.assertEqual(self.model.calls, [])

    def test_daily_limits_stop_new_gradings(self):
        view = self.coach.start({"question_ids": [self.ids[FAST], self.ids[DEADLOCK]]})
        self.coach.limits = {**LIMITS, "daily_feedback": 1}
        self.answer(view["id"], self.ids[FAST], "在内存里。", "limit-1")
        view = self.graded(view["id"])
        self.assertEqual(view["left_today"], 0)
        with self.assertRaises(ValidationError) as caught:
            self.answer(view["id"], self.ids[DEADLOCK], "互相等待。", "limit-2")
        self.assertIn("批改次数", str(caught.exception))
        self.coach.limits = LIMITS
        ledger = self.app.intake.ledger
        ledger.prices, ledger.budget = {"stand-in": {"hit": 0, "miss": 1, "output": 4}}, 0.001
        ledger.add([{"at": ai.datetime.now(ai.timezone.utc).isoformat(timespec="seconds"), "kind": "model", "model": "stand-in",
                     "hit": 0, "miss": 1_000_000, "output": 0}])
        with self.assertRaises(ValidationError) as caught:
            self.answer(view["id"], self.ids[DEADLOCK], "互相等待。", "limit-3")
        self.assertIn("费用", str(caught.exception))

    def test_a_job_description_picks_questions_from_the_bank_only(self):
        jd = "岗位要求：熟悉 Redis，有数据库性能优化经验。"
        plan = self.app.interview_plan({"jd_text": jd, "limit": 5})
        deadline = time.monotonic() + 15
        while plan["status"] == "running" and time.monotonic() < deadline:
            time.sleep(0.02)
            plan = self.coach.plan_result(plan["id"])
        self.assertEqual(plan["status"], "done")
        # The unknown ID and the repeat are gone; a quote that is not in the text is dropped, not the question.
        self.assertEqual(len(plan["picks"]), 2)
        self.assertEqual([p["quote"] for p in plan["picks"]], ["熟悉 Redis", None])
        self.assertTrue(all(p["id"].startswith("q_") and p["canonical"] for p in plan["picks"]))
        self.assertEqual(plan["uncovered"], ["有数据库性能优化经验"])
        request = self.model.calls[0][1]
        self.assertIn(jd, request)
        self.assertIn(FAST, request)
        picks = [p["id"] for p in plan["picks"]]
        view = self.app.interview_start({"question_ids": picks, "direction": "Redis 岗位", "jd": "熟悉 Redis",
                                         "reasons": {p["id"]: {"quote": p["quote"], "reason": p["reason"]} for p in plan["picks"]}})
        self.assertEqual(view["current"]["question_id"], picks[0])
        self.assertEqual(view["meta"]["reasons"][picks[0]]["reason"], "直接考察")
        with self.assertRaises(ValidationError):
            self.app.interview_plan({"jd_text": "太短"})

    def test_direction_filters_choose_answered_questions_first(self):
        view = self.app.interview_start({"filters": {}, "limit": 5, "direction": "全部"})
        questions = {q["id"]: q for q in load_data(self.bank)["questions"]}
        states = {questions[qid]["canonical"] for qid in self.coach_ids(view)}
        self.assertEqual(len(states), 5)
        reference = {"HTTP/2 相比 HTTP/1.1 有哪些改进？", "Kubernetes 中 Pod 是什么？", "MySQL 的事务隔离级别有哪些？", "React 列表渲染为什么需要 key？", FAST,
                     "Redis 持久化有哪些方式？", "什么是聚簇索引？", "什么是闭包？"}
        self.assertTrue(states <= reference)
        shuffled = self.app.interview_start({"filters": {"technology": "redis"}, "limit": 2, "order": "random"})
        self.assertEqual(shuffled["total"], 2)
        with self.assertRaises(ValidationError):
            self.app.interview_start({"filters": {"technology": "no-such"}, "limit": 2})
        with self.assertRaises(ValidationError):
            self.app.interview_start({"filters": {"nonsense": "x"}})
        with self.assertRaises(ValidationError):
            self.app.interview_start({"filters": {}, "question_ids": [self.ids[FAST]]})

    def coach_ids(self, view):
        return load_data(self.bank)["_state"]["sessions"][view["id"]]["question_ids"]

    def test_cleaning_drops_verdicts_without_a_reference_and_rejects_empty_feedback(self):
        raw = {"observations": [{"dimension": "accuracy", "verdict": "wrong", "quote": "答案", "note": "不对"}, {"dimension": "unknown", "note": "x"}, {"dimension": "clarity"}],
               "key_point_checks": [{"index": 0, "status": "covered"}], "follow_up": {"prompt": "只有问题"}}
        fields, _ = clean_feedback(raw, "我的答案", {"key_points": ["一点"]}, True)
        self.assertEqual(fields["observations"], [{"dimension": "accuracy", "note": "不对", "quote": "答案"}])
        self.assertEqual((fields["key_point_checks"], fields["follow_up"], fields["limited_basis"]), ([], None, True))
        fields, _ = clean_feedback(raw, "我的答案", {"key_points": ["一点"]}, False)
        self.assertEqual(fields["observations"][0]["verdict"], "wrong")
        self.assertEqual(fields["key_point_checks"][0]["status"], "covered")
        self.assertFalse(fields["limited_basis"])
        for bad in ({"observations": []}, {"observations": [{"dimension": "x", "note": "y"}]}, None, "text"):
            with self.assertRaises(ai.AIError):
                clean_feedback(bad, "我的答案", None, True)
        with self.assertRaises(ai.AIError):
            clean_plan({"picks": "none"}, "jd", [], 3)


class HttpCase(unittest.TestCase):
    def setUp(self):
        work = ROOT / ".work/tests"
        work.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=work)
        self.addCleanup(self.temp.cleanup)
        self.bank = Path(self.temp.name) / "bank"
        build_demo(self.bank, v2=True)

    def serve(self, **options):
        self.model = Model()
        app = WebApp(self.bank, read_only=True, ai_config=CONFIG, **options)
        if app.coach:
            app.coach.call = self.model
        self.server = LocalServer(app)
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        thread.start()
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close(), thread.join(timeout=2)))
        return app

    def call(self, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        conn.request("POST" if body is not None else "GET", path, json.dumps(body) if body is not None else None,
                     {"X-Interview-Token": self.server.token, "Content-Type": "application/json"})
        response = conn.getresponse()
        result = response.status, json.loads(response.read())
        conn.close()
        return result

    def test_the_endpoints_run_an_interview_and_stay_off_when_not_enabled(self):
        self.serve(allow_intake=True, allow_practice=True)
        self.assertTrue(self.call("/api/library")[1]["can_interview"])
        status, overview = self.call("/api/interview")
        self.assertEqual((status, overview["enabled"], overview["model"], overview["left_today"]), (200, True, "stand-in", 200))
        status, view = self.call("/api/interview/start", {"filters": {"technology": "redis"}, "limit": 1, "direction": "Redis"})
        self.assertEqual((status, view["total"]), (200, 1))
        qid = view["current"]["question_id"]
        status, view = self.call("/api/interview/answer", {"session": view["id"], "question_id": qid, "request_id": "http-1", "text": "内存。"})
        self.assertEqual(status, 200)
        deadline = time.monotonic() + 15
        while not view["responses"][0]["feedback"] and time.monotonic() < deadline:
            time.sleep(0.02)
            view = self.call("/api/interview/session?id=" + view["id"])[1]
        self.assertTrue(view["responses"][0]["feedback"])
        self.assertEqual(self.call("/api/interview")[1]["sessions"][0]["graded"], 1)
        self.assertEqual(view["current"]["status"], "completed")
        self.assertEqual(self.call("/api/interview/end", {"session": view["id"]})[1]["status"], "completed")
        self.assertEqual(self.call("/api/interview/nonsense", {})[0], 404)
        self.assertEqual(self.call("/api/interview/answer", {"session": "x"})[0], 400)
        self.assertEqual(self.call("/api/interview/session?id=nope")[0], 400)

    def test_without_practice_ai_or_v2_there_is_no_interview(self):
        self.serve(allow_intake=True)
        self.assertFalse(self.call("/api/library")[1]["can_interview"])
        self.assertEqual(self.call("/api/interview")[1], {"enabled": False})
        self.assertEqual(self.call("/api/interview/start", {"question_ids": ["q"]})[0], 400)


class V1Case(unittest.TestCase):
    def test_a_v1_bank_offers_no_interview(self):
        work = ROOT / ".work/tests"
        work.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=work) as temp:
            bank = Path(temp) / "bank"
            build_demo(bank)
            app = WebApp(bank, read_only=True, allow_practice=True, ai_config=CONFIG, allow_intake=True)
            self.assertFalse(app.library({})["can_interview"])
            with self.assertRaises(ValidationError):
                app.interview_overview()


if __name__ == "__main__":
    unittest.main()
