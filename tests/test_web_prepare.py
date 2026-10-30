"""Preparation in the Web reader: most-asked ranking with recency, the company view and saved job-description lists."""
import http.client
import json
import threading
import time
import unittest
from datetime import date

import support  # noqa: F401  (puts the Skill's scripts on sys.path)
from test_foundation import BankFixture
from test_web_interview import CONFIG, Model, finish_workers
from ibank_core import web_prepare as prep
from ibank_core.errors import ValidationError
from ibank_core.migrations import migrate
from ibank_core.normalize import normalize_question_text
from ibank_core.studysets import studyset
from ibank_core.web import LocalServer, WebApp

TODAY = date(2026, 10, 30)


def row(qid, *dates, company="c1"):
    return {"id": qid, "canonical": qid, "domains": ["backend.cache"],
            "occurrences": [{"event_date": d, "company_id": company, "round": "technical-1"} for d in dates]}


class Pure(unittest.TestCase):
    def test_partial_dates_sit_in_the_middle_of_their_period(self):
        self.assertEqual(prep.occurrence_day("2026"), date(2026, 7, 1))
        self.assertEqual(prep.occurrence_day("2026-03"), date(2026, 3, 15))
        self.assertEqual(prep.occurrence_day("2026-03-09"), date(2026, 3, 9))
        for bad in (None, "", "next year", "2026-13", 2026):
            self.assertIsNone(prep.occurrence_day(bad))

    def test_weight_halves_every_half_life_and_a_future_date_counts_as_today(self):
        self.assertEqual(prep.weight(TODAY, TODAY, 365), 1)
        self.assertAlmostEqual(prep.weight(date(2025, 10, 30), TODAY, 365), 0.5, places=2)
        self.assertAlmostEqual(prep.weight(date(2024, 10, 30), TODAY, 365), 0.25, places=2)
        self.assertEqual(prep.weight(date(2027, 1, 1), TODAY, 365), 1)
        self.assertEqual(prep.weight(None, TODAY, 365), prep.UNKNOWN_WEIGHT)

    def test_recent_questions_outrank_more_often_asked_old_ones(self):
        # Three interviews six years ago weigh less than one whose date was never recorded: that one may well be recent.
        old, recent, undated = row("old", "2019-05", "2019-06", "2019-07"), row("recent", "2026-09", "2026-10"), row("undated", None)
        by_score = [r["q"]["id"] for r in prep.rank([old, recent, undated], TODAY)]
        by_count = [r["q"]["id"] for r in prep.rank([old, recent, undated], TODAY, order="count")]
        self.assertEqual((by_score, by_count), (["recent", "undated", "old"], ["old", "recent", "undated"]))
        first = prep.rank([old, recent, undated], TODAY)[0]
        self.assertEqual((first["count"], first["last_year"], first["companies"]), (2, 2026, 1))
        # A longer memory lets the old question catch up.
        slow = prep.rank([old, recent], TODAY, half_life=730)
        self.assertEqual(slow[0]["q"]["id"], "recent")

    def test_a_window_keeps_only_dated_occurrences_inside_it(self):
        mixed = row("mixed", "2019-05", "2026-09", None)
        everything = prep.rank([mixed], TODAY)[0]
        recent = prep.rank([mixed], TODAY, window="1y")[0]
        self.assertEqual((everything["count"], everything["undated"], recent["count"], recent["undated"]), (3, 1, 1, 0))
        self.assertEqual(prep.rank([row("old", "2019-05"), row("undated", None)], TODAY, window="3y"), [])
        with self.assertRaises(ValidationError):
            prep.rank([], TODAY, half_life=111)
        with self.assertRaises(ValidationError):
            prep.rank([], TODAY, window="5y")

    def test_companies_are_listed_by_how_much_they_asked(self):
        rows = [row("a", "2026-05", company="big"), row("b", "2025-01", "2025-02", company="big"), row("c", None, company="small"), row("d", None, company=None)]
        names = [{"id": "big", "name": "大厂"}, {"id": "small", "name": "小厂"}]
        index = prep.company_index(rows, names)
        self.assertEqual([(c["name"], c["questions"], c["occurrences"], c["years"]) for c in index], [("大厂", 2, 3, ["2026", "2025"]), ("小厂", 1, 1, [])])
        self.assertEqual(index[0]["domains"], [{"id": "backend", "count": 2}])
        mine = prep.company_questions(rows, "big", TODAY)
        self.assertEqual([(m["q"]["id"], m["count"], m["rounds"], m["years"]) for m in mine], [("a", 1, ["technical-1"], ["2026"]), ("b", 2, ["technical-1"], ["2025"])])

    def test_the_job_description_mapping_quotes_the_text_and_keeps_the_gaps(self):
        jd = "熟悉 Redis，有数据库性能优化经验。"
        picks = [{"id": "q1", "quote": "熟悉 Redis", "coverage": "direct", "priority": "must", "reason": "直接考察"},
                 {"id": "q2", "quote": "熟悉 Redis", "coverage": "partial", "priority": "unspecified", "reason": "相关"},
                 {"id": "q3", "quote": "不在原文里", "coverage": "direct", "reason": "x"}, {"id": "q4", "quote": None}]
        found = prep.requirements(jd, picks, ["有数据库性能优化经验", "原文里没有", "熟悉 Redis"])
        self.assertEqual([(r["quote"], r["priority"], [m["question_id"] for m in r["matches"]]) for r in found],
                         [("熟悉 Redis", "must", ["q1", "q2"]), ("有数据库性能优化经验", "unspecified", [])])
        self.assertEqual([m["coverage"] for m in found[0]["matches"]], ["direct", "partial"])
        self.assertTrue(all(r["reason"] and r["id"].startswith("r") for r in found))


class Fixture(BankFixture):
    def setUp(self):
        super().setUp()
        self.addCleanup(finish_workers, "ibank-coach-")
        # Redis was asked twice, recently, by two companies; MySQL once, in 2019; React once, with no date recorded.
        occurrences = {o["id"]: o for o in self.bundle["occurrences"]}
        occurrences["occ_demo0"]["event_date"] = "2019-05"
        occurrences["occ_demo1"]["event_date"] = "2026-08"
        occurrences["occ_repeat"]["event_date"] = "2026-07"
        occurrences["occ_demo2"]["event_date"] = None
        self.seed()
        migrate(self.bank, "apply")
        self.model = Model()
        self.app = WebApp(self.bank, read_only=True, allow_practice=True, ai_config=CONFIG, allow_intake=True)
        self.app.coach.call = self.model

    def plan(self):
        plan = self.app.interview_plan({"jd_text": "岗位要求：熟悉 Redis，有数据库性能优化经验，了解分布式缓存。", "limit": 5})
        deadline = time.monotonic() + 15
        while plan["status"] == "running" and time.monotonic() < deadline:
            time.sleep(0.02)
            plan = self.app.coach.plan_result(plan["id"])
        self.assertEqual(plan["status"], "done")
        return plan


class Prepare(Fixture):
    def test_the_ranking_follows_recency_filters_and_windows(self):
        top = self.app.prepare_top({})
        self.assertEqual([(q["id"], q["rank"], q["count"]) for q in top["questions"]], [("q_demo1", 1, 2), ("q_demo2", 2, 1), ("q_demo0", 3, 1)])
        self.assertEqual((top["total"], top["undated"], top["half_life"], top["dated"], top["occurrences"]), (3, 1, 365, 3, 4))
        self.assertGreater(top["questions"][0]["score"], top["questions"][1]["score"])
        self.assertEqual((top["questions"][0]["companies_n"], top["questions"][0]["last_year"]), (2, 2026))
        self.assertEqual([q["id"] for q in self.app.prepare_top({"order": "count"})["questions"]][:1], ["q_demo1"])
        self.assertEqual([q["id"] for q in self.app.prepare_top({"window": "1y"})["questions"]], ["q_demo1"])
        self.assertEqual([q["id"] for q in self.app.prepare_top({"technology": "mysql"})["questions"]], ["q_demo0"])
        page = self.app.prepare_top({"limit": "1", "offset": "1"})
        self.assertEqual((page["total"], [q["id"] for q in page["questions"]], page["questions"][0]["rank"]), (3, ["q_demo2"], 2))
        for bad in ({"nonsense": "1"}, {"window": "10y"}, {"limit": "0"}, {"half_life": "7"}):
            with self.assertRaises((ValidationError, ValueError)):
                self.app.prepare_top(bad)

    def test_the_company_view_lists_what_each_company_asked(self):
        companies = self.app.prepare_companies()
        self.assertEqual([(c["name"], c["questions"], c["occurrences"]) for c in companies["companies"]], [("字节跳动", 3, 3), ("美团", 1, 1)])
        meituan = self.app.prepare_company({"id": "company_meituan"})
        self.assertEqual((meituan["name"], meituan["total"]), ("美团", 1))
        self.assertEqual((meituan["questions"][0]["id"], meituan["questions"][0]["rounds"], meituan["questions"][0]["years_here"]), ("q_demo1", ["technical-1"], ["2026"]))
        self.assertEqual(meituan["summary"]["domains"][0]["label"], "后端技术")
        with self.assertRaises(ValidationError):
            self.app.prepare_company({"id": "company_missing"})

    def test_a_job_description_selection_is_saved_as_a_list_and_read_back(self):
        self.assertEqual(self.app.prepare_lists(), {"lists": [], "can_save": True})
        plan = self.plan()
        self.assertEqual([(p["coverage"], p["priority"]) for p in plan["picks"]], [("direct", "must"), ("uncertain", "unspecified")])
        self.assertNotIn("_jd", plan)
        kept = [p["id"] for p in plan["picks"]]
        saved = self.app.prepare_save({"plan_id": plan["id"], "question_ids": kept, "name": "  后端岗位  "})
        listing = self.app.prepare_lists()["lists"]
        self.assertEqual([(l["id"], l["name"], l["questions"], l["requirements"], l["covered"], l["has_jd"]) for l in listing],
                         [(saved["id"], "后端岗位", 2, 2, 1, True)])
        detail = self.app.prepare_list({"id": saved["id"]})
        self.assertEqual({q["id"] for q in detail["questions"]}, set(kept))
        self.assertEqual(detail["summary"], {"questions": 2, "unseen": 2, "weak": 0, "familiar": 0, "due": 2})
        by_quote = {r["quote"]: r for r in detail["requirements"]}
        self.assertEqual(set(by_quote), {"熟悉 Redis", "有数据库性能优化经验"})
        self.assertEqual((by_quote["熟悉 Redis"]["priority"], by_quote["熟悉 Redis"]["matches"][0]["coverage"]), ("must", "direct"))
        self.assertEqual(by_quote["有数据库性能优化经验"]["matches"], [])
        self.assertEqual(detail["coverage"]["uncovered"], ["r2"])
        # The same record the CLI reads.
        item = studyset(self.bank, "show", key=saved["id"])
        self.assertEqual((item["name"], item["mode"], item["jd_coverage"]["directly_covered"]), ("后端岗位", "snapshot", 1))
        self.assertIn("熟悉 Redis", item["jd_text"])

    def test_a_list_keeps_only_the_questions_the_person_ticked(self):
        plan = self.plan()
        only = plan["picks"][0]["id"]
        saved = self.app.prepare_save({"plan_id": plan["id"], "question_ids": [only], "name": ""})
        detail = self.app.prepare_list({"id": saved["id"]})
        self.assertEqual([q["id"] for q in detail["questions"]], [only])
        self.assertTrue(detail["name"].startswith("JD 备考 "))
        for bad in ({"plan_id": plan["id"], "question_ids": [], "name": "x"}, {"plan_id": "plan_gone", "question_ids": [only], "name": "x"},
                    {"plan_id": plan["id"], "question_ids": [only], "name": "x" * 121}, {"plan_id": plan["id"]}):
            with self.assertRaises(ValidationError):
                self.app.prepare_save(bad)
        with self.assertRaises(ValidationError):
            self.app.prepare_list({"id": "set_missing"})

    def test_a_changed_question_is_flagged_in_the_list(self):
        plan = self.plan()
        saved = self.app.prepare_save({"plan_id": plan["id"], "question_ids": [p["id"] for p in plan["picks"]], "name": "x"})
        from ibank_core.storage import open_bank
        from ibank_core.runs import stage_snapshot, commit_run
        import copy
        with open_bank(self.bank) as (manifest, config, data):
            final = copy.deepcopy(data)
            target = next(q for q in final["questions"] if q["id"] == plan["picks"][0]["id"])
            target["canonical"] += "（改写）"
            target["normalized"] = normalize_question_text(target["canonical"])
            staged = stage_snapshot(self.bank, data, final, config, operation="curate")
            commit_run(self.bank, staged["run_id"], loaded=(manifest, config, data))
        detail = self.app.prepare_list({"id": saved["id"]})
        self.assertEqual(detail["changed"], [plan["picks"][0]["id"]])
        matched = [m for r in detail["requirements"] for m in r["matches"] if m["question_id"] == plan["picks"][0]["id"]]
        self.assertTrue(matched and all(m["needs_recheck"] and m["coverage"] == "uncertain" for m in matched))
        self.assertEqual(self.app.prepare_lists()["lists"][0]["changed"], 1)


class Http(Fixture):
    def test_the_endpoints(self):
        server = LocalServer(self.app)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=2)))

        def call(path, body=None):
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            conn.request("POST" if body is not None else "GET", path, json.dumps(body) if body is not None else None,
                         {"X-Interview-Token": server.token, "Content-Type": "application/json"})
            response = conn.getresponse()
            result = response.status, json.loads(response.read())
            conn.close()
            return result
        self.assertTrue(call("/api/library")[1]["can_prepare"])
        self.assertEqual(call("/api/prepare/top?window=1y&limit=5")[1]["total"], 1)
        self.assertEqual(call("/api/prepare/companies")[1]["total"], 2)
        self.assertEqual(call("/api/prepare/company?id=company_meituan")[1]["name"], "美团")
        self.assertEqual(call("/api/prepare/top?nonsense=1")[0], 400)
        self.assertEqual(call("/api/prepare/lists")[1]["lists"], [])
        plan = call("/api/interview/plan", {"jd_text": "岗位要求：熟悉 Redis，有数据库性能优化经验，了解分布式缓存。", "limit": 5})[1]
        while plan["status"] == "running":
            time.sleep(0.02)
            plan = call("/api/interview/plan?id=" + plan["id"])[1]
        status, saved = call("/api/prepare/save", {"plan_id": plan["id"], "question_ids": [p["id"] for p in plan["picks"]], "name": "接口"})
        self.assertEqual(status, 200)
        self.assertEqual(call("/api/prepare/list?id=" + saved["id"])[1]["name"], "接口")
        self.assertEqual(call("/api/prepare/save", {"plan_id": "x"})[0], 400)


class ReadOnly(BankFixture):
    def test_without_practice_nothing_can_be_saved_but_the_rest_reads(self):
        self.seed()
        migrate(self.bank, "apply")
        app = WebApp(self.bank, read_only=True)
        self.assertEqual(app.prepare_lists(), {"lists": [], "can_save": False})
        self.assertEqual(app.prepare_top({})["total"], 3)
        with self.assertRaises(ValidationError):
            app.prepare_save({"plan_id": "x", "question_ids": ["q_demo0"], "name": "x"})

    def test_a_v1_bank_has_the_ranking_but_no_lists(self):
        self.seed()
        app = WebApp(self.bank, read_only=True)
        self.assertEqual(app.prepare_top({})["total"], 3)
        with self.assertRaises(ValidationError):
            app.prepare_lists()

    def test_a_bank_without_interview_dates_says_so(self):
        for occurrence in self.bundle["occurrences"]:
            occurrence["event_date"] = None
        self.seed()
        top = WebApp(self.bank, read_only=True).prepare_top({})
        self.assertEqual((top["dated"], top["occurrences"], top["undated"]), (0, 4, 4))


if __name__ == "__main__":
    unittest.main()
