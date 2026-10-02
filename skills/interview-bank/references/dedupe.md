# Conservative deduplication

`dedupe-candidates --run <uncommitted import stage>` for new material (`ingest submit` does this), or without
`--run` for the existing bank (`--question` selects incoming IDs). Candidates come from earlier active records,
so selecting only an early question does not search later ones. Retrieval combines character bigrams (question
boilerplate removed, common English terms mapped to Chinese), sequence similarity and shared labels; top-k is 10
by default, up to 100. It is bounded recall: raise top-k or fix labels when a pair is missing.

## Decisions

```json
{"schema_version": 1, "task_id": "run_FROM_TASK", "decisions": [{
  "question_id": "q_INCOMING", "action": "MERGE_VARIANT", "target_id": "q_CANDIDATE", "confidence": 0.96,
  "reason": "两题都要求解释 Redis 快的主要原因，完整答案可以共同覆盖"}]}
```

Every incoming ID appears exactly once; a merge or related target must be one of its returned candidates.

| Action | Meaning |
|---|---|
| MERGE_EXACT | Same normalized text and type (coding: identical canonical text, case-sensitive) |
| MERGE_VARIANT | Same core concept, synonymous wording or compatible sub-points; may carry a new `canonical` |
| KEEP_RELATED | Shared topic, different required knowledge; both stay, linked as related (confidence ≥ 0.80) |
| KEEP_DISTINCT | Different question, or no viable candidate |
| REVIEW | Unresolved; blocks the commit |

- Merges need confidence ≥ 0.90, otherwise they become REVIEW. `dedupe --task <id>` decides only exact pairs.
- A REVIEW item names its best candidate. The user can decide it in the Web reader (合并裁决); then
  `dedupe --resolve <stage-run>` re-stages with their decisions and abandons the old stage. Commit the new run.

## Judging a pair

Ask: can one complete, correct answer cover both without adding a core concept?

- Merge synonymous wording, “简要/详细介绍” and “你项目中” without solution-changing context.
- Keep apart: different algorithms, versions, constraints or concepts. LRU vs LFU, TCP handshake vs teardown,
  cache penetration vs breakdown, 索引原理 vs 索引失效条件, different Redis versions, required languages or complexity.
- A shared keyword is not a merge. Missing evidence means REVIEW or distinct.
- Do not build chapter-sized clusters: one cluster supports one focused answer.

## Canonical wording for a merge

MERGE_VARIANT may include `canonical`: a concise question that keeps every meaningful sub-point of the cluster,
for example “LangGraph 的核心概念有哪些？State、Node 与条件边如何实现状态流转、分支和循环？”. It is validated and
audited in the same stage; occurrences and merged IDs are unchanged. When a cluster grows over several decisions,
each new canonical must keep what earlier merges added. Questions with different `report_exclusion` cannot merge.
A rewrite does not refresh answers: recheck them (answer-policy).

## Commit, audit and undo

- The dedupe stage contains the whole final state; commit only it (its import stage becomes superseded).
  Review items of the import carry forward: fix them in the extraction, not in the decisions.
- Occurrences move to the target with original text, sequence, parents and sources intact. The merged question
  stays (status merged, `merged_into` the active target); aliases are redirected; answers keep content and IDs and
  get versions after the target's; relations are redirected and self-relations removed, all audited.
- `undo --run <latest dedupe>` works while nothing changed afterwards. For an import plus merge it restores the
  import (summary `dedupe_only_preserve_import`), keeping every imported question and source. Never delete lines.
