"""Conservative lexical retrieval, host semantic judgments and audited merges."""
import copy
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher

from .ids import new_relation_id, utc_now
from .runs import load_stage, run_path, stage_snapshot
from .schema import require, confidence, string
from .errors import ValidationError
from .storage import bank_file, fingerprint, open_bank, read_json
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


TASK_FIELDS = ("id", "canonical", "question_type", "domains", "technologies")
MATCH_FIELDS = ("id", "canonical")
PREVIEW = 15
SHEET_GROUP_LIMIT = 150


def _compact(question):
    """Tasks keep only what a judgment needs; full records stay in the bank (a 400-question import was 4.5 MB)."""
    return {key: question[key] for key in TASK_FIELDS}


def _sheet(task, final, lang="zh-CN"):
    """A Markdown review sheet: incoming questions grouped by report topic, each with its candidates by ref, and
    the bank's existing questions of the same topic, so paraphrases that share no wording can still be compared."""
    from .export import report_group
    refs = {qid: ref for ref, qid in task["aliases"].items()}
    active = {q["id"]: q for q in final["questions"] if q["status"] == "active"}
    incoming = {item["incoming"]["id"] for item in task["items"]}
    groups = {}
    for item in task["items"]:
        groups.setdefault(report_group(active[item["incoming"]["id"]]), []).append(item)
    existing = {}
    for q in active.values():
        if q["id"] not in incoming:
            existing.setdefault(report_group(q), []).append(q)
    lines = [f"# Dedupe review sheet — {task['id']}", "",
             "Each incoming question (n…) needs one decision. Candidates follow the arrow with their retrieval score; "
             "the topic's existing questions (e…) are listed after them. Any active question may be a target, "
             "including one that is not a listed candidate. Use refs or full IDs in the decisions file.", ""]
    for title in sorted(groups, key=lambda t: (-len(groups[t]), t)):
        items, others = groups[title], sorted(existing.get(title, []), key=lambda q: q["canonical"])
        lines.append(f"## {title} — {len(items)} incoming, {len(others)} existing")
        lines.append("")
        for item in items:
            candidates = " · ".join(f"{refs[m['question']['id']]} {m['score']:.2f}" + (" exact" if m["exact"] else "")
                                    for m in item["matches"])
            lines.append(f"- {refs[item['incoming']['id']]} {item['incoming']['canonical']}" + (f"  → {candidates}" if candidates else ""))
        if others:
            lines.append("")
            for q in others[:SHEET_GROUP_LIMIT]:
                lines.append(f"- {refs[q['id']]} (existing) {q['canonical']}")
            if len(others) > SHEET_GROUP_LIMIT:
                lines.append(f"- … {len(others) - SHEET_GROUP_LIMIT} more existing questions in this topic: use search to compare")
        lines.append("")
    return "\n".join(lines)


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
                # A shared domain or technology admits a candidate, but the real score still ranks it: flooring every
                # same-topic question to one value made the top-k cut among them arbitrary.
                scored = [{"question": {key: p[key] for key in MATCH_FIELDS}, "score": similarity(q, p), "exact": exact_equivalent(q, p),
                           "shared_tag": any(set(q[k]) & set(p[k]) for k in ("domains", "technologies"))} for p in pool.values()]
                matches = sorted((m for m in scored if m["score"] >= 0.18 or m["shared_tag"]),
                                 key=lambda m: (-m["exact"], -m["score"], m["question"]["id"]))[:top_k]
                for m in matches:
                    del m["shared_tag"]
                items.append({"incoming": _compact(q), "matches": matches})
            for token in grams(retrieval_text(q["normalized"])):
                postings[token].add(len(prior))
            for tag in [*q["domains"], *q["technologies"]]:
                tag_postings[tag].add(len(prior))
            prior.append(q)
        if question_ids:
            require({i["incoming"]["id"] for i in items} == set(question_ids), "Unknown/ineligible dedup question ID")
        # Short refs (n1… incoming, e1… other active questions) keep the sheet and the decisions file small.
        incoming_ids = [i["incoming"]["id"] for i in items]
        others = [q["id"] for q in final["questions"] if q["status"] == "active" and q["id"] not in set(incoming_ids)]
        aliases = {**{f"n{n}": qid for n, qid in enumerate(incoming_ids, 1)}, **{f"e{n}": qid for n, qid in enumerate(others, 1)}}
        task = write_task(bank, "dedupe", current, config, items, input_run=run_id, input_digest=fingerprint(final), aliases=aliases,
                          instruction="Return one decision for every incoming question (or set default_action KEEP_DISTINCT and list "
                                      "only the others). Merge only when a complete correct answer covers both without a new core concept. "
                                      "Similarity is retrieval evidence, not semantic confidence. Read the review sheet: paraphrases with "
                                      "low scores sit in the same topic group.")
        from .storage import atomic_write
        atomic_write(run_path(bank, task["id"]) / "review-sheet.md", _sheet(task, final) + "\n")
        return task


def task_summary(bank, task, preview=PREVIEW):
    """The one result shape of dedupe-candidates and ingest submit: counts, the review sheet path and a preview of
    the first items with their candidates. The sheet is the reading surface; run-show pages the full task."""
    refs = {qid: ref for ref, qid in task.get("aliases", {}).items()}
    texts = {m["question"]["id"]: m["question"]["canonical"] for i in task["items"] for m in i["matches"]}
    items = task["items"] if preview is None else task["items"][:preview]
    shown = {m["question"]["id"] for i in items for m in i["matches"]} - {i["incoming"]["id"] for i in items}
    return {"task_id": task["id"], "incoming": len(task["items"]), "previewed": len(items),
            "full_task": f"run-show --run {task['id']} --offset 0 --limit 20" if len(items) < len(task["items"]) else None,
            "with_candidates": sum(bool(i["matches"]) for i in task["items"]),
            "exact_matches": sum(any(m["exact"] for m in i["matches"]) for i in task["items"]),
            "review_sheet": str(run_path(bank, task["id"]) / "review-sheet.md"),
            "items": [{"ref": refs.get(i["incoming"]["id"], i["incoming"]["id"]), "question_id": i["incoming"]["id"],
                       "canonical": i["incoming"]["canonical"],
                       "candidates": [{"ref": refs.get(m["question"]["id"], m["question"]["id"]), "score": m["score"],
                                       "exact": m["exact"]} for m in i["matches"]]} for i in items],
            "candidates": {refs.get(qid, qid): texts[qid] for qid in sorted(shown, key=lambda q: refs.get(q, q))}}


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


def _resolve_refs(task, decisions):
    """Accept n…/e… refs from the review sheet wherever a question ID is expected."""
    aliases = task.get("aliases", {})
    resolved = []
    for d in decisions:
        if isinstance(d, dict):
            d = {**d, **{k: aliases.get(d[k], d[k]) for k in ("question_id", "target_id") if isinstance(d.get(k), str)}}
        resolved.append(d)
    return resolved


def stage_decisions(bank, response=None, task_id=None, defer_review=False):
    """Stage one decision per incoming question.

    defer_review: REVIEW items (and merges below 0.90 confidence) do not block the stage; they are kept as separate
    questions and recorded as deferred_review, so the rest can be committed and the person decides them later in
    the Web reader (dedupe --resolve applies those decisions as a new stage)."""
    with open_bank(bank) as (_, config, current):
        if response is not None:
            require(isinstance(response, dict) and response.get("schema_version", 1) == 1, "Expected v1 dedupe response")
            require(task_id is None or response.get("task_id", task_id) == task_id,
                    f"The decisions file belongs to task {response.get('task_id')}, not {task_id}")
            task_id = response.get("task_id", task_id)
        require(isinstance(task_id, str), "The decisions file needs a task_id (ingest finalize --task supplies it)")
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
                # A REVIEW item names its best candidate so a person can compare the two questions.
                best = exact or (item["matches"][0] if item["matches"] else None)
                decisions.append({"question_id": key, "action": action, "target_id": best["question"]["id"] if best else None,
                                  "confidence": 1.0, "reason": "Deterministic exact match" if exact else "No exact match"})
        else:
            decisions = response.get("decisions")
            require(isinstance(decisions, list), "Invalid decisions")
            decisions = _resolve_refs(task, decisions)
            default = response.get("default_action")
            if default is not None:
                # Large imports are mostly distinct questions; listing only the others keeps the file small.
                require(default == "KEEP_DISTINCT", "default_action may only be KEEP_DISTINCT")
                listed = {d.get("question_id") for d in decisions if isinstance(d, dict)}
                decisions += [{"question_id": key, "action": "KEEP_DISTINCT", "confidence": 0.9,
                               "reason": "default_action: no duplicate among the candidates or the topic group"}
                              for key in items if key not in listed]
        require(isinstance(decisions, list) and all(isinstance(d, dict) and isinstance(d.get("question_id"), str) for d in decisions), "Invalid decisions")
        unknown = sorted({d["question_id"] for d in decisions} - set(items))
        require(not unknown, f"Not an incoming question of this task: {', '.join(unknown[:5])}")
        require(len(decisions) == len(items) and {d["question_id"] for d in decisions} == set(items), "Return each requested dedupe decision exactly once")
        audit, review = list(meta.get("audit", [])), list(meta.get("review", []))
        deferred = []
        actions = {"MERGE_EXACT": 0, "MERGE_VARIANT": 0, "KEEP_RELATED": 0, "KEEP_DISTINCT": 0, "REVIEW": 0}
        by_id = {q["id"]: q for q in final["questions"]}
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
            outside = False
            if action in ("MERGE_EXACT", "MERGE_VARIANT", "KEEP_RELATED") or (action == "REVIEW" and target_id):
                # Any question in the bank or this stage may be the target: lexical retrieval misses paraphrases, so
                # the host may name one it found in the review sheet. Unknown IDs fail loudly instead of degrading.
                require(target_id in by_id, f"{qid}: target {target_id!r} is not a question of this bank or stage")
                require(target_id != qid, f"{qid}: a question cannot target itself")
                outside = target_id not in {m["question"]["id"] for m in item["matches"]}
                target = by_id[target_id]
                if target["status"] == "merged":
                    via = target_id
                    target_id = target["merged_into"]
            if action.startswith("MERGE") and d["confidence"] < 0.9:
                action = "REVIEW"
            actions[action] += 1
            if action == "REVIEW":
                entry = {"question_id": qid, "reason": d["reason"], "target_id": target_id}
                if defer_review:
                    deferred.append(entry)
                    audit.append({**d, "action": "REVIEW", "deferred": True, "target_id": target_id})
                else:
                    review.append(entry)
            elif action.startswith("MERGE"):
                source_exclusion = exclusion_reason(next(q for q in final["questions"] if q["id"] == qid))
                target_exclusion = exclusion_reason(next(q for q in final["questions"] if q["id"] == target_id))
                require(source_exclusion == target_exclusion, "Do not merge excluded and included questions; curate selection first")
                audit.append({**merge_questions(final, qid, target_id, action, d["confidence"], d["reason"], via),
                              **({"outside_candidates": True} if outside else {})})
                if "canonical" in d:
                    audit.extend(apply_changes(final, [{"table":"questions", "id":target_id,
                        "set":{"canonical":d["canonical"]}, "reason":d["reason"]}], config))
            elif action == "KEEP_RELATED":
                require(d["confidence"] >= 0.8, "Related judgment confidence must be >= 0.80")
                final["relations"].append({"schema_version": 1, "id": new_relation_id(), "from_question_id": qid,
                    "to_question_id": target_id, "type": "related", "confidence": d["confidence"], "created_at": utc_now()})
                audit.append({**d, "target_id": target_id, **({"outside_candidates": True} if outside else {})})
            else:
                audit.append(d)
        return stage_snapshot(bank, current, final, config, operation="dedupe", audit=audit, review=review,
                              summary={**meta.get("summary", {}), "dedupe": actions, "task_id": task_id}, intake_id=meta.get("intake_id"),
                              supersedes=[task["input_run"]] if task["input_run"] else [],
                              # Kept so a person's Web decisions on the review items can replace just those items.
                              extra={"decisions": decisions, **({"deferred_review": deferred} if deferred else {})})


HUMAN_ACTIONS = ("MERGE_VARIANT", "KEEP_RELATED", "KEEP_DISTINCT")


def human_decisions_path(bank, run_id):
    return run_path(bank, run_id) / "human-decisions.json"


def _human_file(bank, run_id):
    path = human_decisions_path(bank, run_id)
    return read_json(path) if path.is_file() else {"schema_version": 1, "decisions": {}}


def _resolution_state(bank, stored, question_id):
    """committed / staged / None for the latest resolution stage that covered a deferred item."""
    state = None
    for resolution in stored.get("resolutions", []):
        if question_id in resolution["question_ids"]:
            path = run_path(bank, resolution["run_id"]) / "run.json"
            status = read_json(path)["status"] if path.is_file() else None
            if status == "committed":
                return "committed"
            if status == "staged":
                state = "staged"
    return state


def _deferred_open(bank, run, current, stored):
    """Deferred items of a committed dedupe run that are still decidable: both questions active, not yet resolved."""
    active = {q["id"]: q for q in current["questions"] if q["status"] == "active"}
    for item in run.get("deferred_review", []):
        if item.get("question_id") in active and item.get("target_id") in active \
                and _resolution_state(bank, stored, item["question_id"]) != "committed":
            yield item, active


def review_queue(bank):
    """Questions waiting for a person's merge decision, with both wordings: review items of staged dedupe runs and
    deferred items of committed ones."""
    from .runs import load_stage
    with open_bank(bank, shared=True) as (_, _, current):
        items = []
        for path in sorted(bank_file(bank, "runs").glob("run_*/run.json")):
            run = read_json(path)
            if run.get("operation") != "dedupe":
                continue
            stored = _human_file(bank, run["id"])
            decided = stored["decisions"]
            if run.get("status") == "staged" and run.get("review"):
                try:
                    final = load_stage(bank, run["id"], run, current)
                except ValidationError:
                    continue  # stale stage: the agent must regenerate it
                questions = {q["id"]: q for q in final["questions"]}
                for item in run["review"]:
                    if "question_id" not in item or item.get("target_id") not in questions:
                        continue
                    incoming, target = questions[item["question_id"]], questions[item["target_id"]]
                    items.append({"run_id": run["id"], "question_id": incoming["id"], "question": incoming["canonical"],
                                  "target_id": target["id"], "target": target["canonical"], "reason": item["reason"],
                                  "decision": decided.get(incoming["id"])})
            elif run.get("status") == "committed" and run.get("deferred_review"):
                for item, active in _deferred_open(bank, run, current, stored):
                    incoming, target = active[item["question_id"]], active[item["target_id"]]
                    items.append({"run_id": run["id"], "question_id": incoming["id"], "question": incoming["canonical"],
                                  "target_id": target["id"], "target": target["canonical"], "reason": item["reason"],
                                  "decision": decided.get(incoming["id"]), "deferred": True,
                                  "resolution": _resolution_state(bank, stored, incoming["id"])})
        return items


def record_human_decision(bank, run_id, question_id, action, note):
    """Store one person's decision next to the run; nothing canonical changes until dedupe --resolve and commit."""
    require(action in HUMAN_ACTIONS, "action must be MERGE_VARIANT, KEEP_RELATED or KEEP_DISTINCT")
    string(note, "note")
    with open_bank(bank) as (_, _, current):
        run = read_json(run_path(bank, run_id) / "run.json")
        require(run.get("operation") == "dedupe", "Not a dedupe run")
        stored = _human_file(bank, run_id)
        if run.get("status") == "staged":
            pending = run.get("review", [])
        else:
            require(run.get("status") == "committed" and run.get("deferred_review"), "This dedupe run has nothing waiting for a decision")
            pending = [item for item, _ in _deferred_open(bank, run, current, stored)]
        item = next((i for i in pending if i.get("question_id") == question_id), None)
        require(item is not None, "Not an open review item of this run")
        stored["decisions"][question_id] = {"action": action, "target_id": item.get("target_id"), "note": note.strip(),
                                            "actor": "local_web", "decided_at": utc_now()}
        from .storage import atomic_write, dumps
        atomic_write(human_decisions_path(bank, run_id), dumps(stored) + "\n")
        return {"run_id": run_id, "question_id": question_id, "action": action,
                "remaining": sum(i.get("question_id") not in stored["decisions"] for i in pending)}


def _human_choice(question_id, choice):
    return {"question_id": question_id, "action": choice["action"], "confidence": 1.0,
            "reason": "User decision in the Web reader: " + choice["note"],
            **({"target_id": choice["target_id"]} if choice["action"] != "KEEP_DISTINCT" else {})}


def resolve_with_human_decisions(bank, run_id):
    """Apply the person's decisions as a new stage.

    Staged run: re-stage it with the decisions on its review items (all must be decided); the old stage is abandoned.
    Committed run with deferred items: stage the decided items over the committed questions; undecided ones stay
    in the queue for later."""
    from .runs import abandon_run
    run = read_json(run_path(bank, run_id) / "run.json")
    require(run.get("operation") == "dedupe", "Expected a dedupe run")
    stored = _human_file(bank, run_id)
    human = stored["decisions"]
    if run.get("status") == "committed":
        require(run.get("deferred_review"), "This committed run has no deferred review items")
        with open_bank(bank, shared=True) as (_, _, current):
            open_items = [item for item, _ in _deferred_open(bank, run, current, stored)]
        chosen = [item for item in open_items if item["question_id"] in human
                  and _resolution_state(bank, stored, item["question_id"]) is None]
        require(chosen, "No new decisions to apply; ask the user to decide the deferred items in the Web reader")
        task = candidate_task(bank, question_ids=[item["question_id"] for item in chosen])
        staged = stage_decisions(bank, {"schema_version": 1, "task_id": task["id"],
                                        "decisions": [_human_choice(item["question_id"], human[item["question_id"]]) for item in chosen]})
        stored.setdefault("resolutions", []).append({"run_id": staged["run_id"], "question_ids": [item["question_id"] for item in chosen]})
        from .storage import atomic_write, dumps
        atomic_write(human_decisions_path(bank, run_id), dumps(stored) + "\n")
        return {**staged, "resolves": run_id, "human_decisions": len(chosen), "still_open": len(open_items) - len(chosen)}
    require(run.get("status") == "staged", "Expected a staged dedupe run or a committed one with deferred items")
    require("decisions" in run, "This stage predates recorded decisions; stage dedupe again with full decisions")
    require(human, "No decisions recorded yet; ask the user to decide the review items in the Web reader")
    missing = [i["question_id"] for i in run.get("review", []) if i.get("question_id") not in human]
    require(not missing, f"{len(missing)} review items still need the user's decision")
    decisions = [_human_choice(d["question_id"], human[d["question_id"]]) if d["question_id"] in human else d for d in run["decisions"]]
    staged = stage_decisions(bank, {"schema_version": 1, "task_id": run["summary"]["task_id"], "decisions": decisions})
    abandon_run(bank, run_id)
    return {**staged, "replaces": run_id, "human_decisions": len(human)}
