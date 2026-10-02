"""Lazy evidence-led answer enrichment and immutable answer versions."""
import copy
from datetime import datetime
from urllib.parse import quote_plus, urlparse

from .dates import effective_answer, latest_calendar_date, today
from .editorial import exclusion_reason
from .ids import new_answer_id, utc_now
from .ingestion import privacy_check
from .runs import stage_snapshot
from .schema import require, string, strings
from .search import select_questions
from .storage import dumps, open_bank
from .tasks import read_task, write_task

ANSWER_CONTENT = {"short_answer", "spoken_answer", "key_points", "deep_dive", "interviewer_intent",
                  "common_mistakes", "follow_up_questions", "code_example", "sources"}
# Only these must be written; the rest is optional practice depth, stored empty when omitted.
ANSWER_REQUIRED = ("short_answer", "key_points", "sources")
ANSWER_OPTIONAL = {"spoken_answer": "", "deep_dive": "", "interviewer_intent": "", "common_mistakes": [],
                   "follow_up_questions": [], "code_example": None}
OFFICIAL_DOMAINS = {"redis": "redis.io", "mysql": "dev.mysql.com", "postgresql": "postgresql.org",
                    "react": "react.dev", "javascript": "developer.mozilla.org", "typescript": "typescriptlang.org",
                    "python": "docs.python.org", "go": "go.dev", "kubernetes": "kubernetes.io", "docker": "docs.docker.com"}


def research_task(bank, question_ids=None, limit=10, **filters):
    require(type(limit) is int and limit > 0, "Research limit must be positive")
    with open_bank(bank) as (_, config, current):
        questions = select_questions(current, stale_days=config.get("answer_stale_days", 180), **filters)
        if question_ids:
            questions = [q for q in questions if q["id"] in question_ids]
            require({q["id"] for q in questions} == set(question_ids), "Unknown/filtered research question ID")
        else:
            questions = [q for q in questions if not exclusion_reason(q)][:limit]
        require(bool(questions), "No questions selected for research")
        items = []
        for q in questions:
            domains = sorted({OFFICIAL_DOMAINS[t] for t in q["technologies"] if t in OFFICIAL_DOMAINS})
            # Full occurrences and answer histories can be large; retrieve with show only when needed.
            context = {field: q[field] for field in ('id', 'canonical', 'question_type', 'language', 'domains', 'technologies',
                                                     'answer_status', 'answer_stale_reason')}
            context['answer'] = ({field: q['answer'][field] for field in ('id', 'version', 'short_answer', 'key_points', 'sources', 'verified_at')}
                                 if q['answer'] else None)
            items.append({"question": context, "suggested_queries": [q["canonical"], *(f"site:{d} {q['canonical']}" for d in domains)],
                          "preferred_domains": domains})
        return write_task(bank, "research", current, config, items,
            instruction="Research every question in this batch using host web tools and references/answer-policy.md. Read primary pages, cross-check key claims and versions, verify examples/algorithm constraints when relevant, record accessed_at and evidence_note, and map every key point to citation URLs via evidence. Write a concise short_answer (usually one conclusion and 3-5 brief points); keep detailed reasoning in deep_dive. Never label an unverified answer source_backed. If verification cannot finish, skip with a specific reason; ai_draft is allowed only when the user accepts unverified drafts. Commit this batch, then generate fresh tasks for the remaining user-selected questions; this batch limit is not the total assignment. Do not invent citations, human review or executable-test results.")


def stage_answers(bank, response):
    require(isinstance(response, dict) and response.get("schema_version") == 1, "Expected v1 answer response")
    with open_bank(bank) as (_, config, current):
        task = read_task(bank, response.get("task_id"), "research", current, config)
        answers = response.get("answers")
        require(isinstance(answers, list) and bool(answers), "answers must be nonempty array")
        expected = {i["question"]["id"] for i in task["items"]}
        require(all(isinstance(a, dict) and isinstance(a.get("question_id"), str) for a in answers), "Invalid answer response record")
        require(len(answers) == len(expected) and {a["question_id"] for a in answers} == expected, "Return each requested answer exactly once; use skip with reason if research cannot finish")
        final, audit = copy.deepcopy(current), []
        for item in answers:
            qid = item["question_id"]
            if item.get("skip") is True:
                string(item.get("reason"), "skip.reason")
                if task.get("workflow_id") and "_state" in final:
                    flow = final["_state"]["workflows"][task["workflow_id"]]
                    old = flow["items"].get(qid, {})
                    flow["items"][qid] = {"reason": item["reason"], "attempts": old.get("attempts", 0)+1}
                audit.append({"action": "SKIP_ANSWER", "question_id": qid, "reason": item["reason"]})
                continue
            status = item.get("status")
            require(status in ("ai_draft", "source_backed"), "New answers must be ai_draft or source_backed; human review uses answer-review")
            require(set(ANSWER_REQUIRED) <= item.keys(), "Answer needs short_answer, key_points and sources")
            require(set(item) <= ANSWER_CONTENT | {"question_id", "status", "evidence", "checks", "version_scope"}, "Unknown answer response fields")
            item = {**ANSWER_OPTIONAL, **item}
            string(item["short_answer"], "answer.short_answer")
            require(isinstance(item["key_points"], list) and bool(item["key_points"]), "answer.key_points needs at least one item")
            for field in ("spoken_answer", "deep_dive", "interviewer_intent"):
                string(item[field], f"answer.{field}", empty=True)
            for field in ("key_points", "common_mistakes", "follow_up_questions"):
                strings(item[field], f"answer.{field}")
            string(item["code_example"], "answer.code_example", nullable=True, empty=True)
            require(isinstance(item["sources"], list), "Answer sources must be array")
            privacy_check(dumps(item), config)
            evidence = item.get("evidence", [])
            if status == "source_backed":
                require(bool(item["sources"]), "Source-backed answer requires citations")
                urls = set()
                for citation in item["sources"]:
                    require(isinstance(citation, dict), "Invalid citation")
                    string(citation.get("url"), "citation.url")
                    parsed = urlparse(citation["url"])
                    require(parsed.scheme in ("http", "https") and bool(parsed.netloc) and not parsed.username, "Citation must be public HTTP(S) URL without credentials")
                    string(citation.get("evidence_note"), "citation.evidence_note")
                    require(len(citation["evidence_note"]) <= 2000, "Use concise evidence notes, not whole articles")
                    accessed = citation.get("accessed_at")
                    require(isinstance(accessed, str) and len(accessed) == 10, "Citation accessed_at requires YYYY-MM-DD")
                    require(today(accessed) <= latest_calendar_date(), "Citation access date cannot be in the future")
                    urls.add(citation["url"])
                require(len(urls) == len(item["sources"]), "Duplicate citation URL")
                require(isinstance(evidence, list), "Evidence must be array")
                coverage = set()
                for link in evidence:
                    require(isinstance(link, dict) and type(link.get("key_point")) is int, "Evidence key_point must be zero-based integer")
                    index = link["key_point"]
                    require(0 <= index < len(item["key_points"]), "Evidence key point index out of range")
                    require(isinstance(link.get("source_urls"), list) and bool(link["source_urls"]), "Evidence needs citation URLs")
                    require(all(isinstance(u, str) and u in urls for u in link["source_urls"]), "Evidence URL is not a supplied citation")
                    coverage.add(index)
                require(coverage == set(range(len(item["key_points"]))), "Every key point must have supporting evidence")
            else:
                require(not item["sources"] and not evidence, "AI draft without research must not claim citations")
            now = utc_now()
            version = max((a["version"] for a in final["answers"] if a["question_id"] == qid), default=0) + 1
            record = {"schema_version": 1, "id": new_answer_id(), "question_id": qid, "version": version,
                      "status": status, **{k: item[k] for k in ANSWER_CONTENT}, "created_at": now,
                      "verified_at": min(s["accessed_at"] for s in item["sources"]) + "T00:00:00+00:00" if status == "source_backed" else None}
            if "_state" in final:
                from .state import revision, question
                record.update(question_revision=revision(question(current, qid)), evidence=copy.deepcopy(evidence),
                              checks=item.get("checks", []), version_scope=item.get("version_scope", "unspecified"))
                from .storage import fingerprint
                for source in item["sources"]:
                    eid = "evidence_" + fingerprint(source)[:32]
                    final["_state"]["evidence"][eid] = {"id": eid, "created_at": now, **copy.deepcopy(source)}
            final["answers"].append(record)
            audit.append({"action": "ANSWER_VERSION", "question_id": qid, "answer_id": record["id"], "version": version,
                          "status": status, "evidence": evidence, "task_id": task["id"]})
        return stage_snapshot(bank, current, final, config, operation="answer-enrichment", audit=audit,
                              summary={"answer_versions_added": len(final["answers"]) - len(current["answers"]), "task_id": task["id"]})


def review_answer(bank, question_id, status, reason, human_reviewed=False):
    require(status in ("reviewed", "stale"), "Review status must be reviewed or stale")
    string(reason, "review.reason")
    require(status != "reviewed" or human_reviewed is True, "reviewed requires explicit human confirmation via --human-reviewed")
    with open_bank(bank) as (_, config, current):
        versions = [a for a in current["answers"] if a["question_id"] == question_id]
        require(bool(versions), "Question has no answer to review")
        final = copy.deepcopy(current)
        latest = max(versions, key=lambda a: a["version"])
        record = {**copy.deepcopy(latest), "id": new_answer_id(), "version": latest["version"] + 1, "status": status,
                  "created_at": utc_now(), "verified_at": utc_now() if status == "reviewed" else latest["verified_at"]}
        final["answers"].append(record)
        return stage_snapshot(bank, current, final, config, operation="answer-review",
            audit=[{"action": "ANSWER_REVIEW", "previous_answer_id": latest["id"], "answer_id": record["id"], "reason": reason, "human_reviewed": human_reviewed}],
            summary={"question_id": question_id, "version": record["version"], "status": status})


def recheck_answers(bank, payload):
    """Rebind still-valid answers to reworded questions without new research.

    Only for answers whose evidence is current but whose question wording changed since they were
    written (answer_stale_reason "wording_changed"). Content, sources and verified_at are copied
    unchanged; the new version records the agent's coverage checks. A reworded question that now
    asks something new needs research, not a recheck.
    """
    require(isinstance(payload, dict) and payload.get("schema_version") == 1, "Expected v1 recheck input")
    items = payload.get("rechecks")
    require(isinstance(items, list) and bool(items), "rechecks must be a nonempty array")
    with open_bank(bank) as (_, config, current):
        from .state import question, require_v2, revision
        require_v2(current)
        privacy_check(dumps(payload), config)
        final, audit, seen = copy.deepcopy(current), [], set()
        stale_days = config.get("answer_stale_days", 180)
        for item in items:
            require(isinstance(item, dict) and set(item) <= {"question_id", "reason", "checks", "covers_current_wording"},
                    "Recheck fields: question_id, reason, checks, covers_current_wording")
            qid = item.get("question_id")
            require(isinstance(qid, str) and qid not in seen, "Each recheck needs a distinct question_id")
            seen.add(qid)
            string(item.get("reason"), "recheck.reason")
            strings(item.get("checks"), "recheck.checks")
            require(bool(item["checks"]), "recheck.checks: list what was compared, e.g. each sub-question against key points")
            require(item.get("covers_current_wording") is True,
                    "covers_current_wording must be true; if the new wording asks for more, research the question instead")
            q = question(current, qid)
            versions = [a for a in current["answers"] if a["question_id"] == q["id"]]
            require(bool(versions), f"{qid}: no answer to recheck; research it")
            latest = max(versions, key=lambda a: a["version"])
            require(latest["status"] in ("source_backed", "reviewed") and bool(latest["sources"]),
                    f"{qid}: only source-backed or reviewed answers with citations can be rechecked")
            require(effective_answer(latest, None, stale_days) != "stale",
                    f"{qid}: evidence is older than answer_stale_days; research it again instead of rechecking")
            require(latest.get("question_revision") != revision(q), f"{qid}: answer already matches the current wording")
            record = {**copy.deepcopy(latest), "id": new_answer_id(), "version": latest["version"] + 1,
                      # A human review covered the old wording only; the agent's recheck is not a human review.
                      "status": "source_backed", "created_at": utc_now(), "question_revision": revision(q),
                      "checks": [*latest.get("checks", []), *item["checks"]]}
            final["answers"].append(record)
            audit.append({"action": "ANSWER_RECHECK", "actor": "agent", "question_id": q["id"], "previous_answer_id": latest["id"],
                          "answer_id": record["id"], "reason": item["reason"], "checks": item["checks"],
                          "previous_revision": latest.get("question_revision"), "was_reviewed": latest["status"] == "reviewed"})
        return stage_snapshot(bank, current, final, config, operation="answer-recheck", audit=audit,
                              summary={"answers_rechecked": len(audit)})
