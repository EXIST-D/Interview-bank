"""Mock interviews and answer feedback in the Web reader.

The session, its frozen prompts, the person's answers and the feedback are the Skill's own `interview` records, saved
with the same stage-and-commit steps as the CLI, so an Agent can read and continue them. The model writes feedback only
for an answer the person typed and the server saved verbatim, checks it against the sourced or reviewed reference
answer, and its quotes are verified here before anything is stored. The model never rates the person and never writes
a self-rating: study ratings stay the person's own click."""
import secrets
import threading
from datetime import datetime, timedelta, timezone

from . import ai
from .ai_prompts import feedback_prompt, feedback_request, plan_prompt, plan_request
from .errors import BankError
from .flows import commit_unless_review
from .ids import utc_now
from .interview import interview, next_item
from .runs import abandon_run
from .schema import require
from .state import question as state_question, record as state_record, require_v2, revision
from .storage import open_bank
from .studysets import select
from .timestamps import parse_timestamp
from .web_intake import TEXT_SLOTS

MAX_RESPONSE = 8000
MAX_JD = 6000
MAX_QUESTIONS = 30
MAX_CANDIDATES = 500
MAX_FOLLOW_UPS = 2
KEEP_PLANS = 10
DIMENSIONS = ("accuracy", "coverage", "constraints", "clarity")
VERDICTS = ("met", "gap", "wrong")
CHECK_STATES = ("covered", "partial", "missed")
MODES = ("mock", "review")


def has_reference(q):
    """The rule of `interview next`: only a sourced or reviewed answer with sources is a basis for judging."""
    return bool(q and q["answer_status"] in ("source_backed", "reviewed") and q["answer"] and q["answer"]["sources"])


def _text(value, limit):
    return value.strip()[:limit] if isinstance(value, str) and value.strip() else None


def clean_feedback(raw, text, reference, limited):
    """The model's feedback reduced to what the server can stand behind: known dimensions, quotes found in the
    person's actual answer, key-point checks that exist in the reference. Returns (payload fields, checks made)."""
    if not isinstance(raw, dict):
        raise ai.AIError("模型没有返回有效的点评，请重试。")
    checks, observations = [], []
    found = raw.get("observations") if isinstance(raw.get("observations"), list) else []
    for item in found[:8]:
        note = _text(item.get("note"), 600) if isinstance(item, dict) else None
        if not note or item.get("dimension") not in DIMENSIONS:
            continue
        entry = {"dimension": item["dimension"], "note": note}
        # Without a reliable reference nothing may be called right or wrong.
        if item.get("verdict") in VERDICTS and not limited:
            entry["verdict"] = item["verdict"]
        quote = _text(item.get("quote"), 300)
        if quote and quote in text:
            entry["quote"] = quote
        elif quote:
            checks.append("一处引文在你的回答里找不到，已去掉")
        observations.append(entry)
    if not observations:
        raise ai.AIError("模型没有给出可用的点评，请重试。")
    points = len((reference or {}).get("key_points") or [])
    key_checks = {}
    if reference and not limited and isinstance(raw.get("key_point_checks"), list):
        for item in raw["key_point_checks"]:
            if isinstance(item, dict) and type(item.get("index")) is int and 0 <= item["index"] < points \
                    and item.get("status") in CHECK_STATES and item["index"] not in key_checks:
                key_checks[item["index"]] = {"index": item["index"], "status": item["status"], "note": _text(item.get("note"), 300) or ""}
    topics = [t for t in (_text(v, 80) for v in (raw.get("review_topics") if isinstance(raw.get("review_topics"), list) else [])) if t]
    follow = raw.get("follow_up")
    follow = {"prompt": _text(follow.get("prompt"), 300), "reason": _text(follow.get("reason"), 300)} if isinstance(follow, dict) else None
    if follow and not (follow["prompt"] and follow["reason"]):
        follow = None
    return {"observations": observations, "key_point_checks": [key_checks[i] for i in sorted(key_checks)],
            "review_topics": list(dict.fromkeys(topics))[:6], "follow_up": follow,
            "limited_basis": limited or raw.get("limited_basis") is True}, checks


def clean_plan(raw, jd_text, candidates, limit):
    """Picks that exist in the candidate list, each with an excerpt that really is in the job description."""
    if not isinstance(raw, dict) or not isinstance(raw.get("picks"), list):
        raise ai.AIError("模型没有返回选题结果，请重试。")
    known = {q["id"]: q for q in candidates}
    picks, seen = [], set()
    for item in raw["picks"]:
        qid = item.get("id") if isinstance(item, dict) else None
        if qid not in known or qid in seen:
            continue
        seen.add(qid)
        quote = _text(item.get("quote"), 300)
        picks.append({"id": qid, "canonical": known[qid]["canonical"], "frequency": known[qid]["frequency"],
                      "answered": known[qid]["answered"], "quote": quote if quote and quote in jd_text else None,
                      "coverage": item.get("coverage") if item.get("coverage") in ("direct", "partial") else "uncertain",
                      "priority": item.get("priority") if item.get("priority") in ("must", "nice") else "unspecified",
                      "reason": _text(item.get("reason"), 200) or ""})
        if len(picks) >= limit:
            break
    uncovered = [t for t in (_text(v, 200) for v in (raw.get("uncovered") if isinstance(raw.get("uncovered"), list) else [])) if t and t in jd_text]
    return picks, uncovered[:8]


class Coach:
    """Interview sessions of one bank. Holds the reader's mutation lock around every bank write."""

    def __init__(self, bank, config, mutation_lock, ledger, call=ai.call):
        self.bank, self.config, self.mutation, self.ledger, self.call = bank, config, mutation_lock, ledger, call
        self.limits = config["limits"]
        self.lock = threading.RLock()
        self.work, self.plans = {}, {}

    # ---- reading --------------------------------------------------------------------------------------------
    def _graded_today(self, data):
        since = datetime.now(timezone.utc) - timedelta(days=1)
        return sum(1 for s in require_v2(data)["sessions"].values() for r in s["responses"]
                   if (r.get("feedback") or {}).get("generated_by") and parse_timestamp(r["feedback"]["created_at"]) >= since)

    def _allowance(self, data):
        return max(0, self.limits.get("daily_feedback", 200) - self._graded_today(data))

    def overview(self):
        with open_bank(self.bank, shared=True) as (_, _config, data):
            sessions = sorted(require_v2(data)["sessions"].values(), key=lambda s: s["created_at"], reverse=True)
            left = self._allowance(data)
            return {"enabled": True, "model": self.config["text"]["model"], "left_today": left, "max_response": MAX_RESPONSE,
                    "max_questions": MAX_QUESTIONS, "can_plan": True, "usage": self.ledger.view(),
                    "sessions": [{"id": s["id"], "name": s["name"], "status": s["status"], "position": s["position"],
                                  "total": len(s["question_ids"]), "created_at": s["created_at"],
                                  "mode": (s.get("meta") or {}).get("mode", "mock"),
                                  "answered": len(s["responses"]), "graded": sum(r["feedback"] is not None for r in s["responses"])}
                                 for s in sessions[:20]]}

    def session(self, session_id):
        with open_bank(self.bank, shared=True) as (_, config, data):
            return self._view(data, config, state_record("sessions", data, session_id))

    def _view(self, data, config, s):
        item = next_item(data, config, self.bank, s)
        # The reference answer and the person's own note belong to the feedback step; a prompt never carries them.
        current = {k: v for k, v in item.items() if k in ("status", "question_id", "prompt", "follow_up", "remaining", "changed_since_start")}
        if item["status"] == "awaiting_feedback":
            current.update(question_id=item["response"]["question_id"], response_id=item["response"]["id"])
        with self.lock:
            work = self.work.get(s["id"])
        responses = []
        for r in s["responses"]:
            feedback = {k: v for k, v in r["feedback"].items() if k != "request_digest"} if r["feedback"] else None
            responses.append({"id": r["id"], "question_id": r["question_id"], "prompt": r["prompt"], "text": r["text"],
                              "created_at": r["created_at"], "follow_up": r["follow_up"], "feedback": feedback})
        ended = s["status"] != "running"
        return {"id": s["id"], "name": s["name"], "status": s["status"], "created_at": s["created_at"], "meta": s.get("meta") or {},
                "position": s["position"], "total": len(s["question_ids"]), "current": current, "grading": work,
                "responses": responses, "follow_ups_left": MAX_FOLLOW_UPS - self._follow_depth(s),
                "left_today": self._allowance(data), "summary": self._summary(s) if (ended or item["status"] == "completed") else None}

    @staticmethod
    def _follow_depth(s):
        depth = 0
        for r in reversed(s["responses"]):
            if not r["follow_up"]:
                break
            depth += 1
        return depth

    @staticmethod
    def _summary(s):
        graded = [r for r in s["responses"] if r["feedback"]]
        checks = [c for r in graded for c in r["feedback"].get("key_point_checks", [])]
        return {"answered": len(s["responses"]), "graded": len(graded), "ungraded": len(s["responses"]) - len(graded),
                "limited": sum(bool(r["feedback"]["limited_basis"]) for r in graded),
                "key_points": {state: sum(c["status"] == state for c in checks) for state in CHECK_STATES},
                "weak_topics": list(dict.fromkeys(t for r in graded for t in r["feedback"]["review_topics"]))[:12]}

    # ---- writing --------------------------------------------------------------------------------------------
    def _step(self, action, payload, key=None):
        """One interview step, staged and committed under the reader's lock; a retried step returns its receipt."""
        with self.mutation:
            staged = interview(self.bank, action, payload, key)
            if "run_id" not in staged:
                return staged
            try:
                return commit_unless_review(self.bank, staged)
            except BankError:
                abandon_run(self.bank, staged["run_id"])
                raise

    def start(self, payload):
        require(isinstance(payload, dict) and set(payload) <= {"name", "question_ids", "mode", "meta"}, "Invalid interview payload")
        ids, mode = payload.get("question_ids"), payload.get("mode", "mock")
        require(mode in MODES, "mode must be mock or review")
        require(isinstance(ids, list) and 1 <= len(ids) <= MAX_QUESTIONS and all(isinstance(i, str) for i in ids), f"Choose 1..{MAX_QUESTIONS} questions")
        meta = payload.get("meta") or {}
        require(isinstance(meta, dict) and set(meta) <= {"direction", "jd", "reasons"}, "Invalid session notes")
        require(all(isinstance(meta.get(k, ""), str) and len(meta.get(k, "")) <= 200 for k in ("direction", "jd")), "Invalid session notes")
        reasons = meta.get("reasons", {})
        require(isinstance(reasons, dict) and len(reasons) <= MAX_QUESTIONS and all(
            isinstance(k, str) and isinstance(v, dict) and all(x is None or isinstance(x, str) and len(x) <= 300 for x in v.values())
            for k, v in reasons.items()), "Invalid session notes")
        name = _text(payload.get("name"), 120)
        with open_bank(self.bank, shared=True) as (_, config, data):
            rows = select(data, config, self.bank, ids=ids)
            require(bool(rows), "这些题目现在不能用于面试")
            name = name or (f"批改：{rows[0]['canonical'][:30]}" if mode == "review" else f"模拟面试 {datetime.now(ai.BEIJING):%m-%d %H:%M}")
        receipt = self._step("start", {"name": name, "question_ids": list(dict.fromkeys(ids)), "limit": len(ids), "keep_order": True,
                                       "meta": {**meta, "mode": mode, "interface": "web"}})
        require(receipt.get("committed"), "无法保存这场面试，请重试")
        return self.session(receipt["receipt"]["summary"]["session_id"])

    def answer(self, payload):
        require(isinstance(payload, dict) and set(payload) == {"session", "question_id", "request_id", "text"}, "Invalid answer payload")
        require(all(isinstance(v, str) for v in payload.values()), "Answer values must be strings")
        text = payload["text"]
        require(text.strip() and len(text) <= MAX_RESPONSE, f"回答不能为空，最长 {MAX_RESPONSE} 字")
        require(1 <= len(payload["request_id"]) <= 100, "Invalid request ID")
        with open_bank(self.bank, shared=True) as (_, _config, data):
            prior = state_record("sessions", data, payload["session"])
            retried = any(r["request_id"] == payload["request_id"] for r in prior["responses"])
            if not retried:
                self._ready(data)
        self._step("answer", {"request_id": payload["request_id"], "question_id": payload["question_id"], "text": text}, payload["session"])
        self._grade_later(payload["session"])
        return self.session(payload["session"])

    def regrade(self, payload):
        require(isinstance(payload, dict) and set(payload) == {"session"} and isinstance(payload["session"], str), "Invalid payload")
        with open_bank(self.bank, shared=True) as (_, _config, data):
            self._ready(data)
        self._grade_later(payload["session"])
        return self.session(payload["session"])

    def _ready(self, data):
        require(self._allowance(data) > 0, "今天的 AI 批改次数已用完，请明天再试")
        require(not self.ledger.over_budget(), "今天的费用已达到上限（ai.json 的 limits.daily_budget），请明天再试")

    def _grade_later(self, session_id):
        with open_bank(self.bank, shared=True) as (_, config, data):
            waiting = next_item(data, config, self.bank, state_record("sessions", data, session_id))["status"] == "awaiting_feedback"
        if not waiting:
            return
        with self.lock:
            if (self.work.get(session_id) or {}).get("state") == "running":
                return
            self.work[session_id] = {"state": "running", "since": utc_now()}
        self._spawn(session_id, lambda: self._grade(session_id))

    def _spawn(self, key, work, plan=False):
        def run():
            with ai.metering():
                failure = None
                try:
                    work()
                except Exception as exc:  # The page shows the failure and offers a retry; the reader keeps serving.
                    failure = str(exc) if isinstance(exc, BankError) else "批改时发生意外错误，请重试"
                # What was spent is on the ledger before the page can see the outcome, so a poll never beats the bill.
                entries = ai.take_usage()
                if entries:
                    self.ledger.add(entries)
                with self.lock:
                    if failure is None:
                        self.work.pop(key, None)
                    elif plan:
                        self.plans[key].update(status="failed", error=failure)
                    else:
                        self.work[key] = {"state": "failed", "error": failure, "since": utc_now()}
        threading.Thread(target=run, name=f"ibank-coach-{key[-6:]}", daemon=True).start()

    def _grade(self, session_id):
        with open_bank(self.bank, shared=True) as (_, config, data):
            s = state_record("sessions", data, session_id)
            packet = next_item(data, config, self.bank, s)
            require(packet["status"] == "awaiting_feedback", "没有等待批改的回答")
            response, reference = packet["response"], packet["reference_answer"]
            mine = (packet.get("my_answer") or {}).get("text")
            q = state_question(data, response["question_id"])
            changed = s["question_revisions"][response["question_id"]] != revision(q)
            earlier = next((r["text"] for r in reversed(s["responses"][:-1]) if r["question_id"] == response["question_id"] and not r["follow_up"]), None) \
                if response["follow_up"] else None
            asked = {"canonical": s["prompts"][response["question_id"]]}
        limited = reference is None or changed
        request = feedback_request(asked, response["prompt"], response["text"], None if limited else reference, mine, earlier)
        endpoint = {**self.config["text"], "max_tokens": min(self.config["text"]["max_tokens"], 4000)}
        with TEXT_SLOTS:
            reply = self.call(endpoint, feedback_prompt(), [{"text": request}])
        entries = ai.take_usage()
        if entries:
            self.ledger.add(entries)
        fields, checks = clean_feedback(reply, response["text"], reference, limited)
        follow = fields.pop("follow_up")
        payload = {"response_id": response["id"], **fields, "generated_by": {"kind": "model", "model": self.config["text"]["model"], "checks": checks}}
        if follow:
            payload["follow_up_suggestion"] = follow
        self._step("feedback", payload, session_id)

    def follow_up(self, payload):
        require(isinstance(payload, dict) and set(payload) == {"session"} and isinstance(payload["session"], str), "Invalid payload")
        with open_bank(self.bank, shared=True) as (_, _config, data):
            s = state_record("sessions", data, payload["session"])
            last = s["responses"][-1] if s["responses"] else None
            suggestion = ((last or {}).get("feedback") or {}).get("suggested_follow_up")
            require(suggestion is not None, "这题没有可追问的后续问题")
            require(self._follow_depth(s) < MAX_FOLLOW_UPS, "同一道题最多追问两次")
            require(not s.get("follow_up"), "先回答当前的追问")
        self._step("follow-up", suggestion, payload["session"])
        return self.session(payload["session"])

    def end(self, payload):
        require(isinstance(payload, dict) and set(payload) == {"session"} and isinstance(payload["session"], str), "Invalid payload")
        self._step("end", {}, payload["session"])
        return self.session(payload["session"])

    # ---- choosing questions from a job description ----------------------------------------------------------
    def plan(self, payload, candidates):
        """Ask the model which of the bank's own questions prepare for a job description; the person confirms them."""
        require(isinstance(payload, dict) and set(payload) <= {"jd_text", "limit"}, "Invalid plan payload")
        jd = payload.get("jd_text")
        require(isinstance(jd, str) and 20 <= len(jd.strip()) <= MAX_JD, f"岗位描述需要 20 到 {MAX_JD} 字")
        limit = payload.get("limit", 10)
        require(type(limit) is int and 1 <= limit <= MAX_QUESTIONS, f"题数是 1 到 {MAX_QUESTIONS}")
        require(bool(candidates), "题库里没有可用的题")
        with open_bank(self.bank, shared=True) as (_, _config, data):
            self._ready(data)
        pool = sorted(candidates, key=lambda q: (-q["frequency"], q["id"]))[:MAX_CANDIDATES]
        key = "plan_" + secrets.token_hex(8)
        with self.lock:
            running = [p for p in self.plans.values() if p["status"] == "running"]
            require(not running, "还有一个选题没有完成，请稍等")
            # Keys with an underscore stay on the server: the job description is needed to save the picks as a list.
            self.plans[key] = {"id": key, "status": "running", "picks": [], "uncovered": [], "error": None, "considered": len(pool), "_jd": jd.strip()}
            for old in list(self.plans)[:-KEEP_PLANS]:
                del self.plans[old]
        jd = jd.strip()

        def work():
            endpoint = {**self.config["text"], "max_tokens": min(self.config["text"]["max_tokens"], 4000)}
            with TEXT_SLOTS:
                reply = self.call(endpoint, plan_prompt(), [{"text": plan_request(jd, pool, limit)}])
            picks, uncovered = clean_plan(reply, jd, pool, limit)
            with self.lock:
                self.plans[key].update(status="done", picks=picks, uncovered=uncovered)
        self._spawn(key, work, plan=True)
        return self.plan_result(key)

    def plan_result(self, key):
        with self.lock:
            require(key in self.plans, "这次选题已经过期，请重新开始")
            return {k: v for k, v in self.plans[key].items() if not k.startswith("_")}

    def plan_basis(self, key, kept):
        """The finished plan's job description and the picks the person kept, to save them as a list."""
        with self.lock:
            require(key in self.plans and self.plans[key]["status"] == "done", "这次选题已经过期，请重新开始")
            plan = self.plans[key]
            picks = [p for p in plan["picks"] if p["id"] in set(kept)]
            return plan["_jd"], [dict(p) for p in picks], list(plan["uncovered"])
