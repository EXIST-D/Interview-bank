"""Conservative lexical retrieval, host semantic judgments and audited merges."""
import copy
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher

from .ids import new_relation_id, utc_now
from .runs import load_stage, run_path, stage_snapshot
from .schema import require, confidence, string
from .storage import fingerprint, open_bank, read_json
from .tasks import read_task, write_task
from .curation import apply_changes
from .editorial import exclusion_reason

ACTIONS = {"MERGE_EXACT", "MERGE_VARIANT", "KEEP_RELATED", "KEEP_DISTINCT", "REVIEW"}


def exact_equivalent(a, b):
    if a["question_type"] != b["question_type"]:
        return False
    if a["question_type"] == "coding":
        return a["canonical"].strip() == b["canonical"].strip()
    return a["normalized"] == b["normalized"]


# Retrieval-only text: question boilerplate carries no topic, and common English terms are mapped to the
# Chinese term most banks use, so "什么是闭包" finds "JavaScript 中闭包是什么" and "event loop" finds "事件循环".
# The glossary only widens candidate retrieval; the host still judges every merge.
GLOSSARY = {
    "three-way handshake": "三次握手", "four-way handshake": "四次挥手", "handshake": "握手", "event loop": "事件循环",
    "closure": "闭包", "process": "进程", "thread": "线程", "coroutine": "协程", "deadlock": "死锁", "lock": "锁",
    "garbage collection": "垃圾回收", "virtual memory": "虚拟内存", "index": "索引", "transaction": "事务",
    "isolation level": "隔离级别", "cache": "缓存", "message queue": "消息队列", "distributed lock": "分布式锁",
    "idempotent": "幂等", "idempotency": "幂等", "consistency": "一致性", "url shortener": "短链接", "short link": "短链接",
    "rate limit": "限流", "load balancing": "负载均衡", "retrieval-augmented generation": "检索增强生成",
    "tool calling": "工具调用", "tool call": "工具调用", "fine-tuning": "微调", "self-attention": "自注意力",
    "attention": "注意力", "evaluate": "评估", "evaluation": "评估", "design": "设计", "difference": "区别",
    "container": "容器", "virtual machine": "虚拟机", "cross-origin": "跨域", "rendering": "渲染",
}
FILLERS = re.compile(r"什么是|是什么意思|是什么|是怎样的|是怎么样的|怎么样|有哪些|有什么|是如何|如何|怎么|讲一下|说一下|说说|"
                     r"介绍一下|请问|一下|的|了|吗|呢|(?<![a-z])(?:what|is|are|the|a|an|how|do|does|you|would|explain|of|in|and)(?![a-z])")


def retrieval_text(normalized):
    text = normalized
    for english, chinese in sorted(GLOSSARY.items(), key=lambda item: -len(item[0])):
        # ASCII boundaries, not \b: Chinese characters count as word characters ("的event loop").
        text = re.sub(rf"(?<![a-z]){re.escape(english)}s?(?![a-z])", chinese, text)
    text = FILLERS.sub("", text)
    return re.sub(r"[\s.,;:!?，。；：！？、（）()]+", "", text) or normalized


def grams(text):
    return {text[i:i + 2] for i in range(max(1, len(text) - 1))}


def similarity(a, b):
    if exact_equivalent(a, b):
        return 1.0
    ta, tb = retrieval_text(a["normalized"]), retrieval_text(b["normalized"])
    left, right = grams(ta), grams(tb)
    lexical = len(left & right) / max(1, len(left | right))
    sequence = SequenceMatcher(None, ta, tb, autojunk=False).ratio()
    tags = sum(bool(set(a[k]) & set(b[k])) for k in ("technologies", "domains")) / 2
    return round(0.5 * lexical + 0.4 * sequence + 0.1 * tags, 6)


def candidate_task(bank, run_id=None, top_k=None, question_ids=None):
    with open_bank(bank) as (_, config, current):
        top_k = config["dedupe"]["top_k"] if top_k is None else top_k
        require(type(top_k) is int and 1 <= top_k <= 100, "top_k must be 1..100")
        final = current
        source_run = None
        if run_id:
            source_run = read_json(run_path(bank, run_id) / "run.json")
            require(source_run["status"] == "staged", "Use an uncommitted staging run")
            require(source_run.get("config_digest", fingerprint(config)) == fingerprint(config), "Staged configuration is stale; regenerate")
            if source_run.get("mode") == "snapshot":
                require(source_run["base_digest"] == fingerprint(current), "Staged data is stale; regenerate")
            final = load_stage(bank, run_id, source_run, current)
        current_ids = {q["id"] for q in current["questions"]}
        prior, items, postings, tag_postings = [], [], defaultdict(set), defaultdict(set)
        for q in final["questions"]:
            if q["status"] != "active":
                continue
            selected = (not run_id or q["id"] not in current_ids) and (not question_ids or q["id"] in question_ids)
            if selected:
                hits = Counter()
                for token in grams(retrieval_text(q["normalized"])):
                    hits.update(postings[token])
                # Semantic bilingual pairs may share no characters but share a domain.
                for tag in [*q["domains"], *q["technologies"]]:
                    hits.update(tag_postings[tag])
                shortlist = [prior[index] for index, _ in hits.most_common(max(200, top_k * 20))]
                # Exact matches always survive bounded lexical candidate retrieval.
                exacts = [p for p in prior if exact_equivalent(q, p)]
                pool = {p["id"]: p for p in [*exacts, *shortlist]}
                scored = [{"question": p, "score": max(similarity(q, p), 0.18 if any(set(q[k]) & set(p[k]) for k in ("domains", "technologies")) else 0),
                           "exact": exact_equivalent(q, p)} for p in pool.values()]
                matches = sorted((m for m in scored if m["score"] >= 0.18), key=lambda m: (-m["score"], m["question"]["id"]))[:top_k]
                items.append({"incoming": q, "matches": matches})
            for token in grams(retrieval_text(q["normalized"])):
                postings[token].add(len(prior))
            for tag in [*q["domains"], *q["technologies"]]:
                tag_postings[tag].add(len(prior))
            prior.append(q)
        if question_ids:
            require({i["incoming"]["id"] for i in items} == set(question_ids), "Unknown/ineligible dedup question ID")
        return write_task(bank, "dedupe", current, config, items, input_run=run_id, input_digest=fingerprint(final),
                          instruction="Return one decision for every incoming question. Merge only when a complete correct answer covers both without a new core concept. Similarity is retrieval evidence, not semantic confidence.")


def merge_questions(data, source_id, target_id, action, score, reason, via=None):
    by_id = {q["id"]: q for q in data["questions"]}
    require(source_id in by_id and target_id in by_id and source_id != target_id, "Invalid merge IDs")
    source, target = by_id[source_id], by_id[target_id]
    require(source["status"] == "active" and target["status"] == "active", "Merge IDs must be active")
    if action == "MERGE_EXACT":
        alias = by_id.get(via) if via else None
        require(exact_equivalent(source, target) or (alias and alias["merged_into"] == target_id and exact_equivalent(source, alias)),
                "MERGE_EXACT requires identical normalized text and question type; coding text is case-sensitive")
    require(score >= 0.9, "Semantic merge confidence must be >= 0.90")
    before = {"source": copy.deepcopy(source), "target": copy.deepcopy(target)}
    source.update(status="merged", merged_into=target_id, updated_at=utc_now())
    for q in data["questions"]:
        if q["merged_into"] == source_id:
            q["merged_into"] = target_id
            q["updated_at"] = utc_now()
    for field in ("role_tracks", "domains", "technologies"):
        target[field] = list(dict.fromkeys(target[field] + source[field]))
    target["updated_at"] = utc_now()
    transferred = []
    for occ in data["occurrences"]:
        if occ["question_id"] == source_id:
            transferred.append(occ["id"])
            occ["question_id"] = target_id
    # Keep answer content/history; append migrated versions after target versions.
    version = max((a["version"] for a in data["answers"] if a["question_id"] == target_id), default=0)
    versions = []
    for answer in sorted((a for a in data["answers"] if a["question_id"] == source_id), key=lambda a: a["version"]):
        version += 1
        versions.append({"answer_id": answer["id"], "old_question_id": source_id, "old_version": answer["version"], "new_version": version})
        answer.update(question_id=target_id, version=version)
    relations, seen, removed = [], set(), []
    for rel in data["relations"]:
        for field in ("from_question_id", "to_question_id"):
            if rel[field] == source_id:
                rel[field] = target_id
        key = (rel["type"], rel["from_question_id"], rel["to_question_id"])
        if rel["from_question_id"] == rel["to_question_id"] or key in seen:
            removed.append(copy.deepcopy(rel))
        else:
            seen.add(key)
            relations.append(rel)
    data["relations"] = relations
    return {"action": action, "source_id": source_id, "target_id": target_id, "via": via, "confidence": score, "reason": reason,
            "before": before, "occurrences_transferred": transferred, "answer_versions": versions, "redundant_relations": removed}


def stage_decisions(bank, response=None, task_id=None):
    with open_bank(bank) as (_, config, current):
        if response is not None:
            require(isinstance(response, dict) and response.get("schema_version") == 1, "Expected v1 dedupe response")
            task_id = response.get("task_id")
        task = read_task(bank, task_id, "dedupe", current, config)
        final, meta = copy.deepcopy(current), {}
        if task["input_run"]:
            meta = read_json(run_path(bank, task["input_run"]) / "run.json")
            require(meta["status"] == "staged", "Input stage is no longer staged")
            require(meta.get("config_digest", fingerprint(config)) == fingerprint(config), "Input configuration is stale")
            final = copy.deepcopy(load_stage(bank, task["input_run"], meta, current))
        require(fingerprint(final) == task["input_digest"], "Task input changed")
        items = {i["incoming"]["id"]: i for i in task["items"]}
        if response is None:
            decisions = []
            for key, item in items.items():
                exact = next((m for m in item["matches"] if m["exact"]), None)
                action = "MERGE_EXACT" if exact and config["dedupe"]["auto_merge_exact"] else "REVIEW" if item["matches"] else "KEEP_DISTINCT"
                decisions.append({"question_id": key, "action": action, "target_id": exact["question"]["id"] if exact else None,
                                  "confidence": 1.0, "reason": "Deterministic exact match" if exact else "No exact match"})
        else:
            decisions = response.get("decisions")
        require(isinstance(decisions, list) and all(isinstance(d, dict) and isinstance(d.get("question_id"), str) for d in decisions), "Invalid decisions")
        require(len(decisions) == len(items) and {d["question_id"] for d in decisions} == set(items), "Return each requested dedupe decision exactly once")
        audit, review = list(meta.get("audit", [])), list(meta.get("review", []))
        actions = {"MERGE_EXACT": 0, "MERGE_VARIANT": 0, "KEEP_RELATED": 0, "KEEP_DISTINCT": 0, "REVIEW": 0}
        # Input order creates an acyclic merge graph even when the response is reordered.
        ordered = {d["question_id"]: d for d in decisions}
        for qid, item in items.items():
            d = ordered[qid]
            action = d.get("action")
            require(isinstance(action, str) and action in ACTIONS, "Invalid dedupe action")
            confidence(d.get("confidence"), "decision.confidence")
            string(d.get("reason"), "decision.reason")
            if "canonical" in d:
                require(action == "MERGE_VARIANT", "canonical rewrite is only allowed for MERGE_VARIANT")
                string(d["canonical"], "decision.canonical")
            target_id = d.get("target_id")
            via = None
            if action in ("MERGE_EXACT", "MERGE_VARIANT", "KEEP_RELATED"):
                require(target_id in {m["question"]["id"] for m in item["matches"]}, "Target must be a retrieved candidate")
                target = next(q for q in final["questions"] if q["id"] == target_id)
                if target["status"] == "merged":
                    via = target_id
                    target_id = target["merged_into"]
            if action.startswith("MERGE") and d["confidence"] < 0.9:
                action = "REVIEW"
            actions[action] += 1
            if action == "REVIEW":
                review.append({"question_id": qid, "reason": d["reason"], "target_id": target_id})
            elif action.startswith("MERGE"):
                source_exclusion = exclusion_reason(next(q for q in final["questions"] if q["id"] == qid))
                target_exclusion = exclusion_reason(next(q for q in final["questions"] if q["id"] == target_id))
                require(source_exclusion == target_exclusion, "Do not merge excluded and included questions; curate selection first")
                audit.append(merge_questions(final, qid, target_id, action, d["confidence"], d["reason"], via))
                if "canonical" in d:
                    audit.extend(apply_changes(final, [{"table":"questions", "id":target_id,
                        "set":{"canonical":d["canonical"]}, "reason":d["reason"]}], config))
            elif action == "KEEP_RELATED":
                require(d["confidence"] >= 0.8, "Related judgment confidence must be >= 0.80")
                final["relations"].append({"schema_version": 1, "id": new_relation_id(), "from_question_id": qid,
                    "to_question_id": target_id, "type": "related", "confidence": d["confidence"], "created_at": utc_now()})
                audit.append({**d, "target_id": target_id})
            else:
                audit.append(d)
        return stage_snapshot(bank, current, final, config, operation="dedupe", audit=audit, review=review,
                              summary={**meta.get("summary", {}), "dedupe": actions, "task_id": task_id}, intake_id=meta.get("intake_id"),
                              supersedes=[task["input_run"]] if task["input_run"] else [])
