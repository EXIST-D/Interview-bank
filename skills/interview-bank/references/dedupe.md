# Conservative deduplication

Use dedupe-candidates --run <uncommitted-import-stage> for new material, or omit --run for the existing bank. --question can select incoming IDs. Candidates are retrieved from earlier active records in canonical order, avoiding cyclic plans. Selecting only an earlier question will not search later records: select the later ID or run the full-bank task.

Retrieval uses normalized character bigrams, sequence similarity and shared semantic labels. Top-k defaults to 10, maximum 100. Cross-language equivalents are more likely to be retrieved after classification. This is bounded candidate recall, not exhaustive semantic equivalence; increase top-k or curate classification if a pair is missing.

## Decision response

```json
{
  "schema_version": 1,
  "task_id": "run_FROM_TASK",
  "decisions": [{
    "question_id": "q_INCOMING",
    "action": "MERGE_VARIANT",
    "target_id": "q_CANDIDATE",
    "confidence": 0.96,
    "reason": "两题都要求解释 Redis 快的主要原因，完整答案可以共同覆盖"
  }]
}
```

Every incoming ID must appear exactly once. For merge/related decisions, target_id must be one of its returned candidates.

| Action | Meaning |
| --- | --- |
| MERGE_EXACT | Same normalized text and question type; coding questions additionally require case-sensitive canonical text equality |
| MERGE_VARIANT | Same core concept with synonymous wording or compatible explanatory subpoints; requires semantic judgment |
| KEEP_RELATED | Shared topic but different required knowledge; keep both and add related relation |
| KEEP_DISTINCT | Different question, or no viable candidate; target_id may be omitted |
| REVIEW | Unresolved ambiguity; blocks the entire commit |

Merges require confidence ≥0.90; lower merge confidence becomes REVIEW. KEEP_RELATED requires ≥0.80. Exact deterministic automation via dedupe --task merges only exact pairs when auto_merge_exact is enabled, keeps no-candidate items, and marks other candidates REVIEW.

Ask: can a complete correct answer cover both without adding a new core concept? “Redis 为什么快” and “Redis 单线程为什么能处理高并发” overlap but may demand different scope; do not equate on one keyword. “索引原理” and “索引失效条件” stay separate. Versions, languages, negation, operators and code case matter. Missing evidence means REVIEW or distinct, not guessed merging.

## Commit and audit

dedupe --input stages the complete final state. For an input stage, its extraction review blockers carry forward. Correct those at the extraction response; do not erase them in a dedupe response. Commit only the returned final stage, which marks its predecessor superseded.

All occurrences move to the active target; original text, sequence, parents and sources stay intact. The merged Question remains with status=merged and merged_into set directly to the active target. Prior aliases are redirected; an exact match through an already merged variant records via in audit. Answer content and IDs are retained, versions are appended after target versions. Relations are redirected and redundant/self-relations removed with audit.

Merges can be undone immediately if no later data/config change exists. For an import-plus-merge, undo verifies and restores the original import staging snapshot, keeping all imported questions/sources and reversing only deduplication. Its summary records dedupe_only_preserve_import. Existing-bank merge undo restores the prior complete state. Never delete canonical lines to reverse a merge.

## Consolidated canonical wording

For MERGE_VARIANT the response may include `canonical`, a concise complete question replacing the active target after merging. It is validated and audited within the same stage. Original occurrences and merged IDs are unchanged. No second curate operation is required. Other actions cannot carry this field.

Example: “介绍 LangGraph 的核心概念” and “LangGraph 中 State、Node、Edge 如何实现流程控制” may become “LangGraph 的核心概念有哪些？State、Node 与条件边如何实现状态流转、分支和循环？” when the actual source questions cover those concepts. A generic request for explanation and its concrete explanatory subpoints need not become separate study items. “项目里怎么用” alone is not proof of a distinct knowledge point. Compare the actual required technical answer; keep business-specific constraints that change the solution.

Keep distinct algorithms, incompatible requirements and independent concepts separate: LRU vs LFU, TCP handshake vs disconnect, cache penetration vs breakdown, Redis versions, mandatory language and complexity constraints. Do not merge all LangGraph questions into a single huge topic. A cluster should support one focused answer and a concise canonical question. State which common concept and which retained subpoints justify each merge; similarity scores never make that decision.

When merging a cluster over several decisions, each later canonical must include the already consolidated target's meaningful subpoints. Inspect the merged cluster, not just the original candidate pair. Increase candidate coverage up to 100 and perform a final thematic pass. Questions with different report_exclusion values cannot merge; settle inclusion first using curate. Rewriting the wording does not verify or refresh existing answers; recheck answer applicability when subpoints change.
