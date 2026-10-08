# Conservative deduplication

`dedupe-candidates --run <import stage>` for new material (`ingest submit` does this), or `--question <id>`
(repeatable) for questions already in the bank. Retrieval uses character bigrams, sequence similarity and shared
labels; top-k 10 by default, up to 100 (`--top-k` on both commands).

Lexical retrieval misses paraphrases that share few characters (“线上 CPU 飙高怎么排查” vs “服务器 CPU 100% 你怎么定位”). So every
task also writes a **review sheet** (`review_sheet` in the result): incoming questions grouped by report topic, each
with its candidates, followed by the bank's existing questions of the same topic. Read the sheet group by group;
that is how low-scoring paraphrases are found. Results preview 15 items; the sheet has all.

## Decisions

Refs from the sheet (`n3` = third incoming question in submission order, `e7` existing) or full IDs both work:

```json
{"task_id": "run_FROM_TASK", "default_action": "KEEP_DISTINCT", "decisions": [
  {"question_id": "n3", "action": "MERGE_VARIANT", "target_id": "n1", "confidence": 0.95,
   "reason": "两题都问线上 CPU 飙高的定位步骤，完整答案可以共同覆盖"},
  {"question_id": "n8", "action": "KEEP_RELATED", "target_id": "e12", "confidence": 0.85, "reason": "倒排索引是 Elasticsearch 查询快的机制之一"}]}
```

- `ingest finalize --task` supplies `task_id`; a file naming another task is refused.
- `default_action: "KEEP_DISTINCT"` covers every incoming question not listed; list all others explicitly.
- A merge or related target may be any active question of the bank or the stage, not only a listed candidate.
  Targets outside the candidate list are marked `outside_candidates` in the audit; unknown IDs are refused.

| Action | Meaning |
|---|---|
| MERGE_EXACT | Same normalized text and type (coding: identical canonical text, case-sensitive) |
| MERGE_VARIANT | Same core question, synonymous wording or compatible sub-points; may carry a new `canonical` |
| KEEP_RELATED | One leads into the other (follow-up, mechanism, part); both stay, linked (confidence ≥ 0.80) |
| KEEP_DISTINCT | A different question, including parallel siblings that interviews contrast |
| REVIEW | You cannot decide; the user decides (see below). Confidence = how likely a duplicate |

- Merges need confidence ≥ 0.90, otherwise they become REVIEW. `dedupe --task <id>` decides only exact pairs.
- Without `--defer-review`, one REVIEW item stops the whole stage. With it (`ingest finalize --defer-review` or
  `dedupe --decisions <file> --defer-review`), REVIEW items stay separate questions and everything else commits.
- The user decides REVIEW items in the Web reader (合并裁决); `dedupe --resolve <run>` then stages their decisions
  (for a committed run, only the decided items; others wait). Commit the new run.
- Committed questions are linked or merged the same way: `dedupe-candidates --question <id>`, then decisions.

## Judging a pair

Ask: can one complete, correct answer cover both without adding a core concept?

| Situation | Decision | Example (not from the evaluation set) |
|---|---|---|
| Synonymous wording, “简要/详细介绍”, “你项目中” without solution-changing context | MERGE | “数据库连接池有什么用？” / “为什么要用连接池？” |
| Generic question and its usual implementation | MERGE, keep the technology in `canonical` | “延迟队列怎么实现？” / “如何用 Redis 实现延迟队列？” |
| Same problem: definition and the standard countermeasure | MERGE | “什么是 SSRF？” / “SSRF 怎么防？” |
| One is a superset of the other's sub-points | MERGE, canonical keeps every sub-point | “什么是 CDN？” / “什么是 CDN，它怎么加速？” |
| Same question in two languages | MERGE | “What is a goroutine?” / “什么是 goroutine？” |
| Your-project questions asking the same thing (overall architecture, end-to-end path) | MERGE | “介绍项目架构” / “讲讲项目从请求到返回的完整链路” |
| Your-project questions asking different aspects (architecture vs hardest problem vs evaluation) | DISTINCT | “项目架构” / “项目最大的难点” |
| Follow-up, cause, mechanism or part of the other | RELATED | “Elasticsearch 为什么查询快？” / “什么是倒排索引？” |
| Parallel siblings interviews contrast | DISTINCT | “Saga 是什么？” / “本地消息表是什么？” |
| Different algorithms, versions, constraints, required language or complexity | DISTINCT | “Python 2 的字符串模型” / “Python 3 的字符串模型” |

- When an implementation is one of several the material contrasts (“分别用 Redis 和 ZooKeeper 实现”), keep apart.
- A shared keyword is not a merge. RELATED only when studying one leads into the other (DISTINCT also keeps both).
  Unsure about a merge: REVIEW.
- Do not build chapter-sized clusters: one cluster supports one focused answer.

## Canonical wording for a merge

MERGE_VARIANT may include `canonical`: a concise question keeping every meaningful sub-point of the cluster, e.g.
“LangGraph 的核心概念有哪些？State、Node 与条件边如何实现状态流转、分支和循环？”; later merges must keep what earlier
ones added. It is audited in the same stage. Different `report_exclusion` values cannot merge. Recheck answers after
a rewrite (answer-policy).

## Commit, audit and undo

Commit only the dedupe stage (its import stage becomes superseded). Merged questions are never deleted and
`undo --run <latest dedupe>` restores the import: details in [maintenance](maintenance.md#merge-audit-and-undo).
