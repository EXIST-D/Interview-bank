"""Screenshot import from the Web reader, with a model in the host's place.

The pipeline is the Skill's own: ingest images (copy retention) → extraction → the person's review → ingest submit
(stage + dedupe candidates) → dedupe decisions → commit → research task → ai_draft answers → commit. The model only
replaces the host's reading and judging; every write goes through the same validation, staging and audit. Merges the
model is unsure of, unreadable screenshots and low-confidence questions are decided by the person on the page.
Jobs live in <bank>/cache/web-intake (never backed up); the screenshots themselves are kept in media/.
"""
import copy
import hashlib
import json
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

from . import ai
from .ai_prompts import answer_prompt, dedupe_prompt, extraction_prompt, extraction_request, research_prompt, research_request
from .answers import _quote_text as quote_text, research_task, stage_answers
from .citations import page_texts as fetch_pages
from .dates import today
from .catalog import normalize_labels
from .dedupe import stage_decisions
from .editorial import exclusion_reason, is_self_introduction
from .errors import BankError, ValidationError
from .flows import ingest_submit
from .ids import utc_now
from .ingestion import intake_images, stable_id
from .privacy import classified_findings, privacy_check
from .runs import abandon_run, commit_run, run_path
from .schema import TAXONOMY, partial_date, require
from .storage import atomic_bytes, atomic_write, bank_file, dumps, fingerprint, open_bank, read_json
from .studysets import select
from .timestamps import parse_timestamp

MIMES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}
MAX_IMAGE, MAX_VIEW, MAX_VIEWS = 10 * 1024 * 1024, 4 * 1024 * 1024, 8
# What one model request may carry for a screenshot: base64 and the JSON body hold it about three more times.
MAX_SENT = 8 * 1024 * 1024
MAX_QUESTIONS_PER_IMAGE = 60
ACTIVE = {"collecting", "extracting", "review", "saving", "merge_review", "answering"}
RUNNING = {"extracting", "saving", "answering"}
CANCELLABLE = {"collecting", "review", "merge_review"}
KEEP_JOBS = 30
JOB_ID = re.compile(r"job_[0-9a-f]{24}")
HUMAN_ACTIONS = ("MERGE_VARIANT", "KEEP_RELATED", "KEEP_DISTINCT")
# Shared by every account of one server: one screenshot at a time keeps memory flat under a small MemoryMax.
VISION_SLOTS, TEXT_SLOTS = threading.BoundedSemaphore(1), threading.BoundedSemaphore(2)


def sniff(raw):
    """The image type from its first bytes; the browser's Content-Type is not trusted."""
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    if raw[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return None


def _text(value, limit):
    return value.strip()[:limit] if isinstance(value, str) and value.strip() else None


def _score(value, default=0.5):
    return float(value) if type(value) in (int, float) and 0 <= value <= 1 else default


def _date(value):
    if not isinstance(value, str):
        return None
    try:
        partial_date(value.strip(), "date")
        return value.strip()
    except ValidationError:
        return None


def _labels(dimension, values, allowed, limit):
    if not isinstance(values, list):
        return []
    try:
        found = normalize_labels(dimension, [v for v in values if isinstance(v, str) and v.strip()])
    except ValidationError:
        return []
    return [v for v in found if allowed is None or v in allowed][:limit]


def clean_hints(raw):
    require(isinstance(raw, dict) and set(raw) <= {"company", "position", "round", "interview_type", "event_date"},
            "Hints: company, position, round, interview_type, event_date")
    hints = {key: _text(raw.get(key), 80) for key in ("company", "position")}
    require(raw.get("round") in (None, "", *TAXONOMY["round"]), "Unknown round")
    require(raw.get("interview_type") in (None, "", *TAXONOMY["interview_type"]), "Unknown interview type")
    hints.update(round=raw.get("round") or None, interview_type=raw.get("interview_type") or None)
    require(raw.get("event_date") in (None, "") or _date(raw["event_date"]), "Interview date is YYYY, YYYY-MM or YYYY-MM-DD")
    hints["event_date"] = raw.get("event_date") or None
    require(not classified_findings(dumps(hints)), "Leave contact details out of the hints")
    return {k: v for k, v in hints.items() if v}


def clean_metadata(raw, hints, extensions):
    raw = raw if isinstance(raw, dict) else {}
    company = raw.get("company")
    if isinstance(company, dict):
        company = company.get("name")
    metadata = {
        "company": hints.get("company") or _text(company, 80),
        "round": hints.get("round") or (raw.get("round") if raw.get("round") in TAXONOMY["round"] else None),
        "interview_type": hints.get("interview_type") or (raw.get("interview_type") if raw.get("interview_type") in TAXONOMY["interview_type"] else None),
        "event_date": hints.get("event_date") or _date(raw.get("event_date")),
        "platform": _text(raw.get("platform"), 40),
        "source_date": _date(raw.get("source_date")),
        "role_tracks": _labels("role_tracks", raw.get("role_tracks"), set(TAXONOMY["role_tracks"]) | set(extensions.get("role_tracks", [])), 3),
    }
    for field in ("platform", "company"):
        if classified_findings(dumps(metadata)):
            metadata[field] = None
    return {k: v for k, v in metadata.items() if v}


def clean_source(raw, hints, extensions, prefix):
    """A model's extraction for one screenshot, reduced to what the Skill's extraction schema accepts, plus flags for review."""
    raw = raw if isinstance(raw, dict) else {}
    found = raw.get("questions") if isinstance(raw.get("questions"), list) else []
    status = raw.get("status") if raw.get("status") in ("extracted", "no_questions", "unreadable") else (
        "extracted" if found else "no_questions")
    domains = set(TAXONOMY["domains"]) | set(extensions.get("domains", []))
    roles = set(TAXONOMY["role_tracks"]) | set(extensions.get("role_tracks", []))
    questions, ids, dropped = [], {}, 0
    for row in found[:MAX_QUESTIONS_PER_IMAGE] if status == "extracted" else []:
        if not isinstance(row, dict) or not _text(row.get("original_text"), 4000):
            continue
        original = _text(row["original_text"], 4000)
        canonical = _text(row.get("canonical_suggestion"), 2000) or original
        if is_self_introduction(original) or is_self_introduction(canonical):
            dropped += 1
            continue
        cid = f"{prefix}-q{len(questions) + 1}"
        parent = ids.get(str(row.get("parent_id"))) if row.get("parent_id") is not None else None
        ids[str(row.get("id"))] = cid
        scores = row.get("confidence") if isinstance(row.get("confidence"), dict) else {}
        confidence = {"is_question": _score(scores.get("is_question")), "classification": _score(scores.get("classification"))}
        for key in ("company", "round", "event_date"):
            if key in scores and type(scores[key]) in (int, float):
                confidence[key] = _score(scores[key])
        question = {"id": cid, "original_text": original, "canonical_suggestion": canonical, "sequence": len(questions) + 1,
                    "question_type": row.get("question_type") if row.get("question_type") in TAXONOMY["question_type"] else "concept",
                    "domains": _labels("domains", row.get("domains"), domains, 3),
                    "technologies": _labels("technologies", [t for t in row.get("technologies", []) if isinstance(t, str) and len(t) <= 40]
                                            if isinstance(row.get("technologies"), list) else [], None, 8),
                    "role_tracks": _labels("role_tracks", row.get("role_tracks"), roles, 3),
                    "confidence": confidence}
        if row.get("difficulty") in TAXONOMY["difficulty"]:
            question["difficulty"] = row["difficulty"]
        if parent:
            question["parent_id"] = parent
        flags = []
        if min(confidence.values()) < 0.8:
            flags.append("low_confidence")
        if classified_findings(original + "\n" + canonical):
            flags.append("contact")
        questions.append({**question, "flags": flags})
    reason = _text(raw.get("reason"), 300)
    if status == "extracted" and not questions:
        status = "no_questions"
        reason = "只包含自我介绍等不收录的内容" if dropped else (reason or "没有识别到面试题")
    if status != "extracted":
        reason = reason or ("截图无法看清" if status == "unreadable" else "没有识别到面试题")
    return {"status": status, "reason": reason if status != "extracted" else None,
            "metadata": clean_metadata(raw.get("metadata"), hints, extensions), "questions": questions,
            "self_introductions_dropped": dropped}


def build_extraction(job):
    """The Skill's extraction response from the model's reading and the person's confirmation."""
    sources = []
    for source in job["sources"]:
        confirmed = source.get("confirmed", {})
        if source["status"] == "extracted":
            edits = {q["id"]: q for q in confirmed.get("questions", [])}
            kept, rows = set(), []
            for q in source["questions"]:
                edit = edits.get(q["id"], {"keep": True})
                if not edit.get("keep", True):
                    continue
                kept.add(q["id"])
                row = {k: v for k, v in q.items() if k != "flags"}
                row["canonical_suggestion"] = edit.get("canonical") or q["canonical_suggestion"]
                if row.get("parent_id") not in kept:
                    row.pop("parent_id", None)
                if "low_confidence" in q["flags"]:
                    row["reviewed"] = True
                if "contact" in q["flags"]:
                    row.update(pii_reviewed=True, pii_reason="网页导入时由本人查看并确认保留")
                rows.append(row)
            if rows:
                sources.append({"source_id": source["source_id"], "status": "extracted",
                                "metadata": confirmed.get("metadata", source["metadata"]), "questions": rows})
            else:
                sources.append({"source_id": source["source_id"], "status": "no_questions",
                                "reason": "网页导入时本人去掉了这张截图的全部候选题"})
        elif source["status"] == "no_questions":
            sources.append({"source_id": source["source_id"], "status": "no_questions", "reason": source["reason"]})
        else:
            sources.append({"source_id": source["source_id"], "status": "skip", "reviewed": True,
                            "reason": f"网页导入时本人确认跳过：{source.get('reason') or source.get('error') or '无法识别'}"})
    return {"schema_version": 1, "sources": sources}


def needs_answer(q):
    """No answer yet, or an AI draft written for wording a merge has since changed; researched answers are left alone."""
    return q["answer_status"] == "missing" or (q["answer_status"] == "stale" and q["answer"]["status"] == "ai_draft")


def needs_research(q):
    """Worth looking up: no answer, an AI draft, or an answer that went stale (old evidence or changed wording)."""
    return q["answer_status"] in ("missing", "ai_draft", "stale")


SOURCE_TYPES = ("official_doc", "standard", "paper", "blog", "forum", "news", "other")


def url_key(url):
    """Models rewrite URLs slightly (percent-encoding, a trailing slash, host case); compare what they point at."""
    if not isinstance(url, str):
        return None
    parts = urlsplit(unquote(url.strip()))
    return f"{parts.scheme.lower()}://{(parts.hostname or '').lower()}{parts.path.rstrip('/')}?{parts.query}"


def clean_sourced(raw, qid, pages, provider):
    """A model's answer from the pages the server read, reduced to what stage_answers accepts as source_backed.

    Only URLs that were read can be cited; a quote not found verbatim in its page is dropped; a key point left
    without a supporting page is dropped. Returns (answer, None) or (None, reason)."""
    if isinstance(raw, dict) and isinstance(raw.get("answers"), list) and raw["answers"]:
        raw = raw["answers"][0]  # the policy's response envelope, copied from the shown example
    if not isinstance(raw, dict) or raw.get("skip") is True:
        return None, (_text(raw.get("reason"), 300) if isinstance(raw, dict) else None) or "网页不足以支撑完整答案"
    by_url = {url_key(url): page for page in pages for url in page["urls"]}
    accessed = today().isoformat()
    citations, seen = [], {}
    for row in raw.get("sources", []) if isinstance(raw.get("sources"), list) else []:
        page = by_url.get(url_key(row.get("url"))) if isinstance(row, dict) else None
        if page is None or page["url"] in seen.values():
            continue
        host = urlsplit(page["url"]).hostname or page["url"]
        citation = {"title": _text(row.get("title"), 300) or _text(page.get("title"), 300) or host, "url": page["url"],
                    "publisher": _text(row.get("publisher"), 120) or _text(page.get("site"), 120) or host,
                    "type": row.get("type") if row.get("type") in SOURCE_TYPES else "other", "accessed_at": accessed,
                    "evidence_note": _text(row.get("evidence_note"), 2000) or f"服务器于 {accessed} 读取该页面正文，答案要点据此整理"}
        quote = _text(row.get("evidence_quote"), 300)
        if quote and quote_text(quote) in quote_text(page["text"]):
            citation["evidence_quote"] = quote
        seen[url_key(row["url"])] = page["url"]
        seen[url_key(page["url"])] = page["url"]
        citations.append(citation)
    if not citations:
        return None, "答案没有引用服务器读到的网页"
    points = [p for p in (_text(v, 600) for v in raw.get("key_points", []) if isinstance(raw.get("key_points"), list)) if p]
    support = {}
    for link in raw.get("evidence", []) if isinstance(raw.get("evidence"), list) else []:
        if isinstance(link, dict) and type(link.get("key_point")) is int and 0 <= link["key_point"] < len(points):
            urls = [seen[url_key(u)] for u in link.get("source_urls", []) if url_key(u) in seen] if isinstance(link.get("source_urls"), list) else []
            if urls:
                support.setdefault(link["key_point"], []).extend(u for u in urls if u not in support.get(link["key_point"], []))
    kept = [i for i in range(len(points)) if i in support]
    if not kept:
        return None, "每个要点都需要有网页支持，模型没有给出"
    draft = clean_answer({**raw, "key_points": [points[i] for i in kept]}, qid)
    if draft.get("skip"):
        return None, draft["reason"]
    cited = {u for i in kept for u in support[i]}
    answer = {**draft, "status": "source_backed", "sources": [c for c in citations if c["url"] in cited],
              "evidence": [{"key_point": n, "source_urls": support[i]} for n, i in enumerate(kept)],
              "checks": [f"web search ({provider}) and page text read by the server on {accessed}",
                         f"{sum('evidence_quote' in c for c in citations if c['url'] in cited)} quotes found verbatim in the page text"]}
    if len(kept) < len(points):
        answer["checks"].append(f"{len(points) - len(kept)} key points without a supporting page were dropped")
    return answer, None


def clean_answer(raw, qid):
    if not isinstance(raw, dict):
        return {"question_id": qid, "skip": True, "reason": "模型没有返回这道题的答案"}
    if raw.get("skip") is True:
        return {"question_id": qid, "skip": True, "reason": _text(raw.get("reason"), 300) or "模型跳过了这道题"}
    short = _text(raw.get("short_answer"), 3000)
    found = raw.get("key_points") if isinstance(raw.get("key_points"), list) else []
    points = list(dict.fromkeys(p for p in (_text(v, 600) for v in found) if p))[:12]
    if not short or not points:
        return {"question_id": qid, "skip": True, "reason": "模型的答案缺少结论或要点"}
    answer = {"question_id": qid, "status": "ai_draft", "short_answer": short, "key_points": points, "sources": []}
    for field in ("spoken_answer", "deep_dive", "interviewer_intent"):
        if _text(raw.get(field), 8000):
            answer[field] = _text(raw[field], 8000)
    for field in ("follow_up_questions", "common_mistakes"):
        if isinstance(raw.get(field), list):
            values = list(dict.fromkeys(v for v in (_text(x, 600) for x in raw[field]) if v))[:10]
            if values:
                answer[field] = values
    if _text(raw.get("code_example"), 12000):
        answer["code_example"] = raw["code_example"].strip()[:12000]
    return answer


class IntakeJobs:
    """Screenshot imports of one bank. Holds the reader's mutation lock around every bank write."""

    def __init__(self, bank, config, mutation_lock, call=ai.call, search=ai.search, fetch=None):
        self.bank, self.config, self.mutation, self.call = bank, config, mutation_lock, call
        self.search, self.fetch = search, fetch
        self.limits = config["limits"]
        self.lock = threading.RLock()
        self.root = bank_file(bank, "cache/web-intake")
        self.root.mkdir(parents=True, exist_ok=True)
        self._recover()

    # ---- storage -------------------------------------------------------------------------------------------
    def _dir(self, job_id):
        require(isinstance(job_id, str) and JOB_ID.fullmatch(job_id), "Unknown import job")
        return self.root / job_id

    def _load(self, job_id):
        path = self._dir(job_id) / "job.json"
        require(path.is_file(), "This import job no longer exists; start a new one")
        return read_json(path)

    def _save(self, job):
        job["updated_at"] = utc_now()
        atomic_write(self._dir(job["id"]) / "job.json", dumps(job) + "\n")
        return job

    def _update(self, job_id, change):
        with self.lock:
            job = self._load(job_id)
            change(job)
            return self._save(job)

    def _jobs(self):
        jobs = []
        for path in self.root.glob("job_*/job.json"):
            try:
                jobs.append(read_json(path))
            except (OSError, ValueError, BankError):
                continue
        return sorted(jobs, key=lambda j: j["created_at"], reverse=True)

    def _committed(self, job):
        """Image intakes carry no completion mark: the import is committed once its sources are in the bank."""
        ids = {s["source_id"] for s in job.get("sources", [])}
        with open_bank(self.bank, shared=True) as (_, _config, data):
            return bool(ids) and any(s["id"] in ids for s in data["sources"])

    def _after_commit_failure(self, job, reason):
        """Saving stopped after the commit: record what was saved and offer the answers again."""
        if not job.get("result"):
            job["result"], targets = self._result(job)
            job["answers"] = {"pending": targets, "done": [], "failed": {}}
        self._interrupt_answers(job, reason)
        job.update(status="done", merge_review=None)

    def _recover(self):
        """A restart stops workers: leave every job in a state the person can act on."""
        for job in self._jobs():
            if job["status"] not in RUNNING:
                continue
            if job["status"] == "extracting":
                for source in job["sources"]:
                    if source["status"] == "pending":
                        source.update(status="failed", error="服务重启，识别中断")
                job["status"] = "review" if job["sources"] else "collecting"
            elif job["status"] == "saving":
                if self._committed(job):
                    self._after_commit_failure(job, "服务重启，答案生成中断")
                else:
                    job.update(status="review", error="服务重启，保存中断，请重新确认")
            else:
                self._interrupt_answers(job, "服务重启，答案生成中断")
                job["status"] = "done"
            job["progress"] = None
            self._save(job)

    @staticmethod
    def _interrupt_answers(job, reason):
        answers = job.get("answers") or {"pending": [], "done": [], "failed": {}}
        answers["failed"].update({qid: reason for qid in answers["pending"]})
        answers["pending"] = []
        job["answers"] = answers

    def _today_images(self):
        """Screenshots sent to the model in the last day, plus the ones waiting in an open upload."""
        since = datetime.now(timezone.utc) - timedelta(days=1)
        return sum(len(j["images"]) for j in self._jobs() if parse_timestamp(j["created_at"]) >= since
                   and (j.get("intake_id") or j["status"] == "collecting"))

    def _prune(self):
        for job in self._jobs()[KEEP_JOBS:]:
            if job["status"] not in ACTIVE:
                for path in sorted(self._dir(job["id"]).glob("*"), reverse=True):
                    path.unlink()
                self._dir(job["id"]).rmdir()

    def _drop_uploads(self, job):
        for path in self._dir(job["id"]).glob("img-*"):
            path.unlink()

    # ---- views ---------------------------------------------------------------------------------------------
    def view(self, job):
        return {"kind": job.get("kind", "import"), **{key: job.get(key) for key in (
            "id", "status", "created_at", "updated_at", "hints", "images", "sources", "progress", "error", "notice",
            "merge_review", "result", "answers")}}

    def overview(self):
        with self.lock:
            jobs = self._jobs()
            active = next((j for j in jobs if j["status"] in ACTIVE), None)
            used = self._today_images()
            searched = self._today_research()
        research = None
        if self.config.get("search"):
            research = {"candidates": len(self._research_candidates()), "per_job": self.limits["max_answers_per_job"],
                        "left_today": max(0, self.limits["daily_research"] - searched)}
        return {"enabled": True, "models": ai.describe(self.config), "limits": {**self.limits, "max_image_bytes": MAX_IMAGE,
                "max_view_bytes": MAX_VIEW, "max_views": MAX_VIEWS, "images_left_today": max(0, self.limits["daily_images"] - used)},
                "research": research, "active": self.view(active) if active else None,
                "recent": [{"id": j["id"], "kind": j.get("kind", "import"), "status": j["status"], "created_at": j["created_at"],
                            "images": len(j["images"]), "result": j.get("result"), "answers": j.get("answers")} for j in jobs[:10]]}

    def job(self, job_id):
        with self.lock:
            return self.view(self._load(job_id))

    # ---- collecting ----------------------------------------------------------------------------------------
    def create(self, payload):
        require(isinstance(payload, dict) and set(payload) <= {"hints"}, "Expected hints")
        hints = clean_hints(payload.get("hints") or {})
        with self.lock:
            active = next((j for j in self._jobs() if j["status"] in ACTIVE), None)
            require(active is None, "还有一个导入任务没有完成：请先完成或取消它")
            require(self._today_images() < self.limits["daily_images"], "今天的截图识别额度已用完，请明天再试")
            job = {"schema_version": 1, "id": "job_" + secrets.token_hex(12), "status": "collecting", "created_at": utc_now(),
                   "hints": hints, "images": [], "sources": [], "progress": None, "error": None, "notice": None,
                   "merge_review": None, "result": None, "answers": None}
            self._dir(job["id"]).mkdir()
            self._prune()
            return self.view(self._save(job))

    def upload(self, job_id, index, view, raw):
        mime = sniff(raw)
        require(mime is not None, "Only PNG, JPEG, WebP or GIF screenshots")
        require(len(raw) <= (MAX_VIEW if view is not None else MAX_IMAGE), "Screenshot is too large")
        with self.lock:
            job = self._load(job_id)
            require(job["status"] == "collecting", "This import has already started")
            require(type(index) is int and 0 <= index < self.limits["max_images_per_job"], f"At most {self.limits['max_images_per_job']} screenshots per import")
            images = {image["index"]: image for image in job["images"]}
            if view is None:
                require(index in images or self._today_images() < self.limits["daily_images"], "今天的截图识别额度已用完，请明天再试")
                for path in self._dir(job_id).glob(f"img-{index}-*"):
                    path.unlink()
                atomic_bytes(self._dir(job_id) / f"img-{index}-original{MIMES[mime]}", raw)
                images[index] = {"index": index, "mime": mime, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "views": []}
            else:
                require(index in images, "Upload the screenshot before its parts")
                require(type(view) is int and 0 <= view < MAX_VIEWS, f"At most {MAX_VIEWS} parts per screenshot")
                atomic_bytes(self._dir(job_id) / f"img-{index}-view{view}{MIMES[mime]}", raw)
                images[index]["views"] = sorted({*images[index]["views"], view})
            job["images"] = [images[i] for i in sorted(images)]
            return self.view(self._save(job))

    def _original(self, job_id, index):
        return next(self._dir(job_id).glob(f"img-{index}-original.*"))

    def _views(self, job_id, image):
        paths = [next(self._dir(job_id).glob(f"img-{image['index']}-view{v}.*")) for v in image["views"]]
        return paths or [self._original(job_id, image["index"])]

    def start(self, payload):
        job_id = payload.get("job") if isinstance(payload, dict) else None
        with self.lock:
            job = self._load(job_id)
            require(job["status"] == "collecting", "This import has already started")
            require(bool(job["images"]), "Add at least one screenshot")
            for image in job["images"]:
                sent = sum(path.stat().st_size for path in self._views(job_id, image))
                require(sent <= MAX_SENT, f"截图 {image['index'] + 1} 太大，请压缩或裁剪后再试")
            job.update(status="extracting", progress={"phase": "extract", "done": 0, "total": len(job["images"])})
            self._save(job)
        self._spawn(job_id, self._extract_new)
        return self.job(job_id)

    def _spawn(self, job_id, work):
        def run():
            try:
                work(job_id)
            except Exception as exc:  # The job records the failure; the reader keeps serving.
                message = str(exc) if isinstance(exc, BankError) else "导入时发生意外错误，请重试"

                def fail(job):
                    if job["status"] == "extracting":
                        for source in job["sources"]:
                            if source["status"] == "pending":
                                source.update(status="failed", error=message)
                        job["status"] = "review" if job["sources"] else "collecting"
                    elif job["status"] == "saving":
                        if self._committed(job):
                            self._after_commit_failure(job, message)
                        else:
                            job["status"] = "review"
                    elif job["status"] == "answering":
                        self._interrupt_answers(job, message)
                        job["status"] = "done"
                    job.update(error=message, progress=None)
                self._update(job_id, fail)
        threading.Thread(target=run, name=f"ibank-intake-{job_id[-6:]}", daemon=True).start()

    # ---- extraction ----------------------------------------------------------------------------------------
    def _extract_new(self, job_id):
        job = self._load(job_id)
        paths = [self._original(job_id, image["index"]) for image in job["images"]]
        with self.mutation:
            intake = intake_images(self.bank, [str(p) for p in paths], retention="copy")
        by_hash = {}
        for image in job["images"]:
            by_hash.setdefault(image["sha256"], image["index"])

        def record(job):
            job["intake_id"] = intake["id"]
            new = {i["source"]["sha256"] for i in intake["items"]}
            for image in job["images"]:
                # Already in the bank, or the same bytes twice in this import: read once, counted once.
                image["duplicate"] = image["sha256"] not in new or by_hash[image["sha256"]] != image["index"]
            job["sources"] = [{"source_id": item["source"]["id"], "index": by_hash[item["source"]["sha256"]], "status": "pending",
                               "reason": None, "metadata": {}, "questions": []} for item in intake["items"]]
            job["progress"] = {"phase": "extract", "done": 0, "total": len(job["sources"])}
            if not job["sources"]:
                job.update(status="done", progress=None, result={"added": [], "merged": [], "related": 0, "nothing_new": True})
        job = self._update(job_id, record)
        if job["status"] == "done":
            self._drop_uploads(job)
            return
        self._extract(job_id)

    def retry_extract(self, payload):
        job_id = payload.get("job") if isinstance(payload, dict) else None
        with self.lock:
            job = self._load(job_id)
            require(job["status"] == "review" and job.get("intake_id"), "Nothing to read again")
            failed = [s for s in job["sources"] if s["status"] == "failed"]
            require(bool(failed), "Every screenshot was read")
            for source in failed:
                source.update(status="pending", error=None)
            job.update(status="extracting", error=None, progress={"phase": "extract", "done": 0, "total": len(failed)})
            self._save(job)
        self._spawn(job_id, self._extract)
        return self.job(job_id)

    def _extensions(self):
        with open_bank(self.bank, shared=True) as (_, config, _data):
            return config.get("taxonomy_extensions", {})

    def _extract(self, job_id):
        extensions = self._extensions()
        system = extraction_prompt(tuple(extensions.get("domains", [])))
        job = self._load(job_id)
        images = {image["index"]: image for image in job["images"]}
        for source in [s for s in job["sources"] if s["status"] == "pending"]:
            image = images[source["index"]]
            parts = [{"text": extraction_request(job["hints"])}]
            views = self._views(job_id, image)
            for n, path in enumerate(views, 1):
                if len(views) > 1:
                    parts.append({"text": f"Part {n} of {len(views)}:"})
                raw = path.read_bytes()
                parts.append({"image": raw, "mime": sniff(raw)})
            try:
                with VISION_SLOTS:
                    reply = self.call(self.config["vision"], system, parts)
                result, error = clean_source(reply, job["hints"], extensions, f"s{source['index'] + 1}"), None
            except ai.AIError as exc:
                result, error = None, str(exc)
            del parts

            def store(job, source_id=source["source_id"], result=result, error=error):
                target = next(s for s in job["sources"] if s["source_id"] == source_id)
                if result:
                    target.update(result, error=None)
                else:
                    target.update(status="failed", error=error)
                job["progress"]["done"] += 1
            self._update(job_id, store)
        self._update(job_id, lambda job: job.update(status="review", progress=None))

    # ---- confirmation, dedupe and commit -------------------------------------------------------------------
    def confirm(self, payload):
        require(isinstance(payload, dict) and set(payload) == {"job", "sources"} and isinstance(payload["sources"], list),
                "Expected job and sources")
        with self.lock:
            job = self._load(payload["job"])
            require(job["status"] == "review", "This import is not waiting for confirmation")
            sources = {s["source_id"]: s for s in job["sources"]}
            for entry in payload["sources"]:
                require(isinstance(entry, dict) and set(entry) <= {"source_id", "metadata", "questions"}, "Invalid source confirmation")
                source = sources.get(entry.get("source_id"))
                require(source is not None and source["status"] == "extracted", "Unknown or unreadable screenshot")
                metadata = copy.deepcopy(source["metadata"])
                edits = entry.get("metadata", {})
                require(isinstance(edits, dict) and set(edits) <= {"company", "round", "event_date"}, "Editable: company, round, event_date")
                if "company" in edits:
                    metadata["company"] = _text(edits["company"], 80)
                if "round" in edits:
                    require(edits["round"] in (None, "", *TAXONOMY["round"]), "Unknown round")
                    metadata["round"] = edits["round"] or None
                if "event_date" in edits:
                    require(edits["event_date"] in (None, "") or _date(edits["event_date"]), "Interview date is YYYY, YYYY-MM or YYYY-MM-DD")
                    metadata["event_date"] = edits["event_date"] or None
                metadata = {k: v for k, v in metadata.items() if v}
                require(not classified_findings(dumps(metadata)), "Leave contact details out of the company name")
                known = {q["id"] for q in source["questions"]}
                questions = []
                for edit in entry.get("questions", []):
                    require(isinstance(edit, dict) and set(edit) <= {"id", "keep", "canonical"} and edit.get("id") in known, "Unknown question")
                    require(type(edit.get("keep", True)) is bool, "keep must be true or false")
                    canonical = edit.get("canonical")
                    require(canonical is None or isinstance(canonical, str) and 0 < len(canonical.strip()) <= 2000, "Question text is 1..2000 characters")
                    questions.append({"id": edit["id"], "keep": edit.get("keep", True), "canonical": canonical.strip() if canonical else None})
                source["confirmed"] = {"metadata": metadata, "questions": questions}
            job.update(status="saving", error=None, notice=None, progress={"phase": "save", "done": 0, "total": 1})
            self._save(job)
        self._spawn(job["id"], self._submit)
        return self.job(job["id"])

    def _stage(self, job):
        """ingest submit for the confirmed extraction; any earlier stage of this job is abandoned first."""
        if job.get("stage_run"):
            run = read_json(run_path(self.bank, job["stage_run"]) / "run.json")
            if run["status"] == "staged":
                abandon_run(self.bank, job["stage_run"])
        result = ingest_submit(self.bank, job["intake_id"], build_extraction(job))
        if result["status"] != "dedupe_pending":
            reasons = "；".join(item.get("reason", "") for item in result.get("review", [])[:3])
            raise ValidationError(f"保存前的检查没有通过：{reasons or result['status']}")
        return result["stage_run"], result["dedupe"]["task_id"]

    def _submit(self, job_id):
        job = self._load(job_id)
        with self.mutation:
            stage_run, task_id = self._stage(job)
        job = self._update(job_id, lambda j: j.update(stage_run=stage_run, task_id=task_id))
        task = read_json(run_path(self.bank, task_id) / "task.json")
        decisions, notice = self._judge(task)
        uncertain = [d for d in decisions if d["action"] == "REVIEW"]
        texts = {i["incoming"]["id"]: i["incoming"]["canonical"] for i in task["items"]}
        texts.update({m["question"]["id"]: m["question"]["canonical"] for i in task["items"] for m in i["matches"]})
        if uncertain:
            with open_bank(self.bank, shared=True) as (_, _config, data):
                texts.update({q["id"]: q["canonical"] for q in data["questions"] if q["id"] in {d["target_id"] for d in uncertain}})

            def ask(job):
                job.update(status="merge_review", decisions=decisions, notice=notice, progress=None,
                           merge_review=[{"question_id": d["question_id"], "question": texts[d["question_id"]],
                                          "target_id": d["target_id"], "target": texts.get(d["target_id"], ""),
                                          "reason": d["reason"], "canonical": d.get("canonical")} for d in uncertain])
            self._update(job_id, ask)
            return
        self._update(job_id, lambda j: j.update(decisions=decisions, notice=notice))
        self._finalize(job_id)

    def _judge(self, task):
        """Dedupe decisions by full IDs: exact matches merge, the model judges the rest, uncertain ones go to the person."""
        aliases = task.get("aliases", {})
        refs = {qid: ref for ref, qid in aliases.items()}
        order = [i["incoming"]["id"] for i in task["items"]]
        decisions = {}
        for item in task["items"]:
            exact = next((m for m in item["matches"] if m["exact"]), None)
            decisions[item["incoming"]["id"]] = (
                {"action": "MERGE_EXACT", "target_id": exact["question"]["id"], "confidence": 1.0, "reason": "规范化后文字完全相同"}
                if exact else {"action": "KEEP_DISTINCT", "confidence": 0.9, "reason": "没有找到重复题"})
        open_items = [i for i in task["items"] if i["matches"] and decisions[i["incoming"]["id"]]["action"] != "MERGE_EXACT"]
        notice = None
        if open_items:
            try:
                proposed = self._ask_model(task, open_items, refs)
            except ai.AIError as exc:
                proposed, notice = {}, f"AI 去重判断没有完成（{exc}），相似度较高的题交给你确认。"
                for item in open_items:
                    best = item["matches"][0]
                    if best["score"] >= 0.55:
                        proposed[item["incoming"]["id"]] = {"action": "REVIEW", "target_id": best["question"]["id"],
                                                            "confidence": best["score"], "reason": f"文字相似度 {best['score']:.2f}"}
            with open_bank(self.bank, shared=True) as (_, _config, data):
                questions = {q["id"]: q for q in data["questions"]}
                latest = {}
                for answer in data["answers"]:
                    if answer["version"] > latest.get(answer["question_id"], {}).get("version", 0):
                        latest[answer["question_id"]] = answer
            for qid, d in proposed.items():
                target = d.get("target_id")
                if target in order and order.index(target) > order.index(qid):
                    # A merge into a later new question would cycle through the stage order; flip it when that one stays.
                    if decisions[target]["action"] == "KEEP_DISTINCT" and target not in proposed:
                        decisions[target] = {**d, "target_id": qid}
                    continue
                existing = questions.get(target)
                if existing and (existing.get("report_exclusion") or exclusion_reason(existing)):
                    continue
                answer = latest.get(existing["merged_into"] or target) if existing else None
                if d.get("canonical") and d["action"] == "MERGE_VARIANT" and answer and answer["status"] in ("source_backed", "reviewed"):
                    # Rewording a question whose answer was researched makes that answer need a recheck: the person decides.
                    d = {**d, "action": "REVIEW", "reason": f"{d['reason']}；合并后题目会改为新的问法，已有的参考答案需要重新核验"}
                decisions[qid] = d
        return [{"question_id": qid, **decisions[qid]} for qid in order], notice

    def _ask_model(self, task, items, refs):
        sheet_path = run_path(self.bank, task["id"]) / "review-sheet.md"
        sheet = sheet_path.read_text(encoding="utf-8") if sheet_path.is_file() else ""
        listing = [{"ref": refs[i["incoming"]["id"]], "question": i["incoming"]["canonical"],
                    "candidates": [{"ref": refs.get(m["question"]["id"], m["question"]["id"]), "question": m["question"]["canonical"],
                                    "score": m["score"]} for m in i["matches"][:8]]} for i in items]
        text = ("New questions and their retrieved candidates:\n" + json.dumps(listing, ensure_ascii=False, indent=1) +
                "\n\nThe review sheet (same-topic questions of the bank, for paraphrases that share few words):\n" + sheet[:40000])
        with TEXT_SLOTS:
            reply = self.call(self.config["text"], dedupe_prompt(), [{"text": text}])
        aliases = task.get("aliases", {})
        incoming = {i["incoming"]["id"] for i in items}
        exact = {i["incoming"]["id"]: {m["question"]["id"] for m in i["matches"] if m["exact"]} for i in items}
        proposed = {}
        for row in reply.get("decisions", []) if isinstance(reply.get("decisions"), list) else []:
            if not isinstance(row, dict):
                continue
            qid = aliases.get(row.get("question_id"), row.get("question_id"))
            target = aliases.get(row.get("target_id"), row.get("target_id"))
            action = row.get("action")
            if qid not in incoming or action not in ("MERGE_EXACT", "MERGE_VARIANT", "KEEP_RELATED", "KEEP_DISTINCT", "REVIEW"):
                continue
            if action == "KEEP_DISTINCT" or target not in aliases.values() or target == qid:
                continue
            confidence = _score(row.get("confidence"), 0.5)
            if action == "MERGE_EXACT" and target not in exact[qid]:
                action = "MERGE_VARIANT"
            if action.startswith("MERGE") and confidence < 0.9:
                action = "REVIEW"
            if action == "KEEP_RELATED" and confidence < 0.8:
                continue
            proposed[qid] = {"action": action, "target_id": target, "confidence": confidence,
                             "reason": _text(row.get("reason"), 300) or "AI 判断"}
            canonical = _text(row.get("canonical"), 2000)
            if canonical and action in ("MERGE_VARIANT", "REVIEW") and not classified_findings(canonical):
                proposed[qid]["canonical"] = canonical
        return proposed

    def merge(self, payload):
        require(isinstance(payload, dict) and set(payload) == {"job", "decisions"} and isinstance(payload["decisions"], list),
                "Expected job and decisions")
        with self.lock:
            job = self._load(payload["job"])
            require(job["status"] == "merge_review", "This import is not waiting for merge decisions")
            asked = {item["question_id"]: item for item in job["merge_review"]}
            chosen = {}
            for row in payload["decisions"]:
                require(isinstance(row, dict) and set(row) == {"question_id", "action"} and row["question_id"] in asked, "Unknown merge item")
                require(row["action"] in HUMAN_ACTIONS, "Choose merge, related or distinct")
                chosen[row["question_id"]] = row["action"]
            require(set(chosen) == set(asked), "Decide every listed question")
            labels = {"MERGE_VARIANT": "是同一题", "KEEP_RELATED": "相关但不同", "KEEP_DISTINCT": "不同的题"}
            for d in job["decisions"]:
                if d["question_id"] in chosen:
                    d.update(action=chosen[d["question_id"]], confidence=1.0,
                             reason=f"网页导入时由本人确认{labels[chosen[d['question_id']]]}（AI：{d['reason']}）")
                    if d["action"] != "MERGE_VARIANT":
                        d.pop("canonical", None)
                    if d["action"] == "KEEP_DISTINCT":
                        d.pop("target_id", None)
            job.update(status="saving", progress={"phase": "save", "done": 0, "total": 1})
            self._save(job)
        self._spawn(job["id"], self._finalize)
        return self.job(job["id"])

    def _finalize(self, job_id):
        job = self._load(job_id)
        with self.mutation:
            with open_bank(self.bank, shared=True) as (_, _config, current):
                fresh = read_json(run_path(self.bank, job["task_id"]) / "task.json")["base_digest"] == fingerprint(current)
            if not fresh:
                # Practice or another write moved the bank on: stage the same confirmed extraction again. Question IDs
                # derive from the intake and candidate IDs, so the decisions still name the right questions.
                stage_run, task_id = self._stage(job)
                job = self._update(job_id, lambda j: j.update(stage_run=stage_run, task_id=task_id))
            staged = stage_decisions(self.bank, {"schema_version": 1, "task_id": job["task_id"], "decisions": job["decisions"]})
            require(not staged["review"], "Merge decisions still need review")
            commit_run(self.bank, staged["run_id"])
        result, targets = self._result(job)

        def done(job):
            job.update(committed_run=staged["run_id"], result=result, merge_review=None,
                       answers={"pending": targets, "done": [], "failed": {}},
                       status="answering" if targets else "done",
                       progress={"phase": "answer", "done": 0, "total": len(targets)} if targets else None)
        job = self._update(job_id, done)
        self._drop_uploads(job)
        if targets:
            self._answer(job_id)

    def _result(self, job):
        with open_bank(self.bank, shared=True) as (_, config, data):
            questions = {q["id"]: q for q in data["questions"]}
            candidates = [q["id"] for s in build_extraction(job)["sources"] for q in s.get("questions", [])]
            added, merged, final = [], [], []
            for cid in candidates:
                qid = stable_id("q", job["intake_id"], cid)
                q = questions[qid]
                target = q["merged_into"] or qid
                if q["merged_into"]:
                    merged.append({"id": target, "canonical": questions[target]["canonical"], "from": q["canonical"]})
                else:
                    added.append({"id": qid, "canonical": q["canonical"]})
                final.append(target)
            final = list(dict.fromkeys(final))
            rows = select(data, config, self.bank, ids=final)
            missing = [q["id"] for q in rows if needs_answer(q)]
        relations = sum(d["action"] == "KEEP_RELATED" for d in job["decisions"])
        limit = self.limits["max_answers_per_job"]
        return {"added": added, "merged": merged, "related": relations, "answers_skipped_for_limit": max(0, len(missing) - limit)}, missing[:limit]

    # ---- answers -------------------------------------------------------------------------------------------
    def retry_answers(self, payload):
        job_id = payload.get("job") if isinstance(payload, dict) else None
        with self.lock:
            job = self._load(job_id)
            require(job["status"] == "done" and job.get("answers") and job["answers"]["failed"], "No answers to generate again")
            job["answers"]["pending"] = list(job["answers"]["failed"])
            job["answers"]["failed"] = {}
            job.update(status="answering", error=None, progress={"phase": "answer", "done": 0, "total": len(job["answers"]["pending"])})
            self._save(job)
        self._spawn(job_id, self._answer)
        return self.job(job_id)

    def _answer(self, job_id):
        size = self.limits["answer_batch"]
        while True:
            job = self._load(job_id)
            pending = job["answers"]["pending"]
            if not pending:
                break
            research_only = job.get("kind") == "research"
            batch = pending[:size]
            with self.mutation:
                with open_bank(self.bank, shared=True) as (_, config, data):
                    wanted = needs_research if research_only else needs_answer
                    still = {q["id"] for q in select(data, config, self.bank, ids=batch) if wanted(q)}
                batch = [qid for qid in batch if qid in still]
                task = research_task(self.bank, question_ids=batch) if batch else None
            answered, sourced, failed, searched = [], [], {}, 0
            if task:
                try:
                    answers, pages, searched, reasons = self._sourced_answers(task, config, job_id)
                    missing = [item for item in task["items"] if item["question"]["id"] not in {a["question_id"] for a in answers}]
                    if missing and not research_only:
                        answers += self._write_answers(missing, config)
                    answers += [{"question_id": item["question"]["id"], "skip": True,
                                 "reason": reasons.get(item["question"]["id"], "没有找到能支撑答案的网页")}
                                for item in missing if research_only]
                    with self.mutation:
                        answered, failed = self._commit_answers(task, answers, pages)
                    sourced = [a["question_id"] for a in answers if a.get("status") == "source_backed" and a["question_id"] in answered]
                except (ai.AIError, ValidationError) as exc:
                    failed = {qid: str(exc) for qid in batch}

            def store(job, done=pending[:size], answered=answered, sourced=sourced, failed=failed, searched=searched):
                answers = job["answers"]
                answers["pending"] = [q for q in answers["pending"] if q not in done]
                answers["done"] += [q for q in answered if q not in answers["done"]]
                answers.setdefault("sourced", [])
                answers["sourced"] += [q for q in sourced if q not in answers["sourced"]]
                answers["searched"] = answers.get("searched", 0) + searched
                answers["failed"].update(failed)
                for qid in answered:
                    answers["failed"].pop(qid, None)
                job["progress"]["done"] += len(done)
            self._update(job_id, store)
        self._update(job_id, lambda job: job.update(status="done", progress=None))

    def _research_candidates(self):
        with open_bank(self.bank, shared=True) as (_, config, data):
            rows = select(data, config, self.bank)
        order = {"ai_draft": 0, "stale": 1, "missing": 2}
        rows = sorted((q for q in rows if needs_research(q)), key=lambda q: (order[q["answer_status"]], -q["frequency"], q["id"]))
        return [(q["id"], q["canonical"]) for q in rows]

    def research(self, payload):
        """Look up sources for the given questions, or for the most-asked drafts, stale and unanswered ones."""
        require(self.config.get("search"), "这个服务器没有配置联网搜索（ai.json 的 search）")
        require(isinstance(payload, dict) and set(payload) <= {"question_ids"}, "Expected question_ids or nothing")
        ids = payload.get("question_ids")
        require(ids is None or isinstance(ids, list) and 1 <= len(ids) <= 200 and all(isinstance(i, str) for i in ids), "question_ids: 1..200 IDs")
        candidates = self._research_candidates()
        if ids is not None:
            with open_bank(self.bank, shared=True) as (_, _config, data):
                targets = {q["id"]: q["merged_into"] or q["id"] for q in data["questions"]}
            require(set(ids) <= targets.keys(), "Unknown question")
            wanted = set(targets[i] for i in ids)
            candidates = [c for c in candidates if c[0] in wanted]
            require(bool(candidates), "这道题已经有来源或已审阅的答案")
        require(bool(candidates), "没有需要补充出处的题目")
        targets = candidates[:max(1, self.limits["max_answers_per_job"])]
        with self.lock:
            require(next((j for j in self._jobs() if j["status"] in ACTIVE), None) is None, "还有一个任务没有完成：请先完成或取消它")
            require(self._today_research() < self.limits["daily_research"], "今天的联网检索额度已用完，请明天再试")
            job = {"schema_version": 1, "id": "job_" + secrets.token_hex(12), "kind": "research", "status": "answering",
                   "created_at": utc_now(), "hints": {}, "images": [], "sources": [], "error": None, "notice": None,
                   "merge_review": None, "result": {"research": True, "more": max(0, len(candidates) - len(targets)),
                                                    "questions": [{"id": qid, "canonical": text} for qid, text in targets]},
                   "answers": {"pending": [qid for qid, _ in targets], "done": [], "failed": {}, "sourced": [], "searched": 0},
                   "progress": {"phase": "research", "done": 0, "total": len(targets)}}
            self._dir(job["id"]).mkdir()
            self._prune()
            self._save(job)
        self._spawn(job["id"], self._answer)
        return self.job(job["id"])

    def _sourced_answers(self, task, config, job_id):
        """Search, read and answer each question from the pages read; (answers, page texts, searches, skip reasons)."""
        if not self.config.get("search"):
            return [], {}, 0, {}
        answers, texts, reasons, searched = [], {}, {}, 0
        for item in task["items"]:
            qid = item["question"]["id"]
            if self._today_research() + searched >= self.limits["daily_research"]:
                reasons[qid] = "今天的联网检索额度已用完"
                continue
            searched += 1
            try:
                pages = self._read_pages(item)
                if not pages:
                    reasons[qid] = "搜索结果里没有能读取正文的网页"
                    continue
                with TEXT_SLOTS:
                    reply = self.call(self.config["text"], research_prompt(), [{"text": research_request(item["question"], pages)}])
            except ai.AIError as exc:
                reasons[qid] = str(exc)
                continue
            answer, reason = clean_sourced(reply, qid, pages, self.config["search"]["provider"])
            if answer:
                try:
                    privacy_check(dumps(answer), config)
                except ValidationError:
                    answer, reason = None, "答案里出现了疑似联系方式，已跳过"
            if answer:
                answers.append(answer)
                texts.update({url: page["text"] for page in pages for url in page["urls"]})
            else:
                reasons[qid] = reason
        return answers, texts, searched, reasons

    def _read_pages(self, item):
        """Up to `pages` readable public pages for a question: official domains first, at most two per site."""
        settings = self.config["search"]
        found = self.search(settings, item["suggested_queries"][0])
        preferred = tuple(item.get("preferred_domains") or ())
        ranked = sorted(found, key=lambda r: not (urlsplit(r["url"]).hostname or "").endswith(preferred) if preferred else False)
        chosen, per_site = [], {}
        for row in ranked:
            host = urlsplit(row["url"]).hostname or ""
            if per_site.get(host, 0) >= 2 or row["url"] in {c["url"] for c in chosen}:
                continue
            per_site[host] = per_site.get(host, 0) + 1
            chosen.append(row)
        chosen = chosen[:settings["pages"] + 2]
        if not chosen:
            return []
        report = fetch_pages(self.bank, [c["url"] for c in chosen], opener=self.fetch)
        saved = {r["url"]: r for r in report["results"] if r["ok"]}
        pages = []
        for row in chosen:
            if row["url"] in saved and len(pages) < settings["pages"]:
                result = saved[row["url"]]
                text = Path(result["path"]).read_text(encoding="utf-8")
                pages.append({"url": row["url"], "urls": list(dict.fromkeys([row["url"], result.get("final_url") or row["url"]])),
                              "title": row.get("title"), "site": row.get("site"), "text": text})
        return pages

    def _today_research(self):
        since = datetime.now(timezone.utc) - timedelta(days=1)
        return sum((j.get("answers") or {}).get("searched", 0) for j in self._jobs() if parse_timestamp(j["created_at"]) >= since)

    def _write_answers(self, items, config):
        questions = [{"question_id": item["question"]["id"], "question": item["question"]["canonical"],
                      "question_type": item["question"]["question_type"], "domains": item["question"]["domains"],
                      "technologies": item["question"]["technologies"]} for item in items]
        with TEXT_SLOTS:
            reply = self.call(self.config["text"], answer_prompt(),
                              [{"text": "Write reference answers for these questions:\n" + json.dumps(questions, ensure_ascii=False, indent=1)}])
        rows = {row.get("question_id"): row for row in reply.get("answers", []) if isinstance(row, dict)} \
            if isinstance(reply.get("answers"), list) else {}
        answers = []
        for q in questions:
            answer = clean_answer(rows.get(q["question_id"]), q["question_id"])
            if not answer.get("skip"):
                try:
                    privacy_check(dumps(answer), config)
                except ValidationError:
                    answer = {"question_id": q["question_id"], "skip": True, "reason": "答案里出现了疑似联系方式，已跳过"}
            answers.append(answer)
        return answers

    def _commit_answers(self, task, answers, pages=None):
        skipped = {a["question_id"]: a["reason"] for a in answers if a.get("skip")}
        if len(skipped) == len(answers):
            return [], skipped
        response = lambda task_id: {"schema_version": 1, "task_id": task_id, "answers": answers}
        try:
            staged = stage_answers(self.bank, response(task["id"]), pages)
        except ValidationError as exc:
            if "stale" not in str(exc).lower():
                raise
            # The bank moved on while the model wrote: a fresh task for the same questions takes the same answers.
            task = research_task(self.bank, question_ids=[a["question_id"] for a in answers])
            staged = stage_answers(self.bank, response(task["id"]), pages)
        commit_run(self.bank, staged["run_id"])
        return ([a["question_id"] for a in answers if not a.get("skip")],
                {a["question_id"]: a["reason"] for a in answers if a.get("skip")})

    # ---- cancel --------------------------------------------------------------------------------------------
    def cancel(self, payload):
        job_id = payload.get("job") if isinstance(payload, dict) else None
        with self.lock:
            job = self._load(job_id)
            require(job["status"] in CANCELLABLE, "This import can no longer be cancelled")
            job.update(status="cancelled", progress=None, merge_review=None)
            self._save(job)
        # Workers take the reader's mutation lock before the job lock; never the other way round.
        with self.mutation:
            if job.get("stage_run"):
                run = read_json(run_path(self.bank, job["stage_run"]) / "run.json")
                if run["status"] == "staged":
                    abandon_run(self.bank, job["stage_run"])
            if job.get("intake_id"):
                self._drop_media(job["intake_id"])
        self._drop_uploads(job)
        return self.view(job)

    def _drop_media(self, intake_id):
        """Screenshot copies this uncommitted intake made and no committed source uses."""
        intake = read_json(run_path(self.bank, intake_id) / "intake.json")
        with open_bank(self.bank) as (_, _config, data):
            kept = {s["path"] for s in data["sources"] if s.get("path")}
            for item in intake["items"]:
                path = item["source"].get("path")
                if path and path.startswith("media/") and path not in kept:
                    target = bank_file(self.bank, path)
                    if target.is_file():
                        target.unlink()
