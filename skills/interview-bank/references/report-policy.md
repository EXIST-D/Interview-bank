# Question selection and reader report

Default deliverable: two concise Markdown editions (questions plus reference answers, and questions only) sharing a structured JSON sidecar. Both use the same included questions, frequency order and numbering; answer research runs once after deduplication, then code renders both editions. Create further formats or many category files only when requested. Keep the audit trail available without copying it into every question.

## Selection

Omit self-introductions, personal biography, salary expectations, availability and personal preference-only questions. Do not turn “介绍你自己” into a generic study question. Preserve reusable technical project architecture, debugging, design choices and collaboration cases with substantive problem-solving content. “解释你如何设计缓存” is useful even though it says “你”. Do not reject an entire behavioral or project category by keyword.

If one block mixes personal introduction and a separately visible technical question, omit the personal clause and extract the exact technical text with its own provenance. Purely personal sources receive no_questions with a reason. Save exclusions in the host's structured observation response. The deterministic self-introduction guard is intentionally narrow; the host still judges broader relevance.

For existing banks, mark irrelevant questions with `curate` → `report_exclusion` → commit. Keep canonical history and original appearances intact. The exporter also hides obvious introductions in legacy banks that have no editorial field.

## Merge by meaning

Aim for one focused study question per core concept. Different wording, “简要/详细介绍”, or “你项目中” without solution-changing context need not create separate questions. Combine compatible explanatory subpoints into a concise canonical question, using the dedupe response's canonical field. See [dedupe protocol](dedupe.md).

Do not collapse independent concepts into chapter-sized questions. Preserve meaningful versions, languages, constraints, operators, complexity limits, exception conditions and output requirements. A compound question may merge with a compatible basic form when the final wording retains every meaningful requirement, but not with an unrelated neighboring topic. Never inflate confidence to force a merge.

## Presentation

Use H1 for the report title, a top overview table listing each domain's question count, H2 for domains (including count), and H3 for numbered questions. Group by the first recognized domain; curate domains with the primary topic first. Within each domain, sort by collected frequency descending, break ties by canonical text, and number from 1. Display numbering is regenerated for the current report/filter; it is not a persistent question ID. Each question appears in one domain so overview counts sum to the report total.

In the answer edition every question includes 答案（参考） before one compact metadata line. The question-only edition omits answers, empty slots, progress and citations. Missing answers say 待检索与核验. Only current source_backed/reviewed answers with citations display their concise short_answer and clickable sources. Drafts, stale answers and uncited human-reviewed content remain in JSON with a clear pending-verification message in Markdown. This avoids presenting an old or unsourced answer as newly verified. Include an honest answer-coverage count at the top.

Example layout (illustrative values only):

```text
# 面试题整理报告

## 领域概览

| 领域 | 题目数 |
|---|---:|
| Agent 架构与工作流 | 1 |

## Agent 架构与工作流（1 题）

### 1. LangChain Chain 与 LangGraph 状态机有何区别？复杂 Agent 场景如何选型？

答案（参考）：待检索与核验。

出现 4 次 · 公司：寒武纪、淘宝闪购 · 标签：智能体工作流 / LangGraph
```

Show at most six labels on a reader metadata line; retain the complete set in JSON. Keep internal IDs, raw round enums, source blocks and original variants out of the reader report. Preserve multiline code in a fenced body rather than flattening it into a heading. Escape source Markdown syntax so source text cannot inject headings or links.

Show known years only; distinguish 面试年份 from 资料年份 and never use import time as interview time. Omit unknown metadata. Counts describe collected appearances, not applicants or hiring probability.

The `.md.details.json` sidecar keeps full IDs, original occurrences, exact source metadata, dates, rounds, relations, answer history, included/excluded report IDs, domain totals and numbering policy. Canonical bank runs retain commit and merge audits. Creating an answer slot does not generate or verify an answer. For the default end-to-end workflow, apply [answer policy](answer-policy.md) to every question in scope before final export. Pending slots are honest interim results or documented unresolved items, not completed answers.
