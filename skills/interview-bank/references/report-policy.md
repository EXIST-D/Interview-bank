# Question selection and reader report

The deliverable is two Markdown editions (with reference answers, questions only) and one JSON sidecar, rendered
by `export` from the same committed data after research. Other formats or per-category files only on request.

## Selection

- Leave out self-introductions, biography, salary, availability and preference-only questions; do not turn
  “介绍你自己” into a study question.
- Keep reusable project, design, debugging and collaboration questions with real problem-solving content:
  “解释你如何设计缓存” is useful although it says “你”. Never drop a whole category by keyword.
- A block mixing an introduction with a technical question: extract only the technical text, with its own provenance.
- Existing banks: hide a question with `curate` → `report_exclusion` → commit; history stays intact.

## One question per concept

Aim for one focused study question per core concept, merged by meaning with a combined `canonical`
([dedupe](dedupe.md)). Do not collapse independent concepts into chapter-sized questions; keep versions,
constraints, operators, complexity limits and output requirements.

## Layout (rendered by code)

Title, an honest coverage line, a topic overview table, then H2 per topic and H3 per question with
答案（参考） and a metadata line (出现 N 次 · 公司 · 标签).

- Group by the first recognised domain (put the primary topic first); topics are ordered by question count. Number
  from 1 within each group by frequency, ties by wording. Numbers are per report, not IDs; overview counts add up to
  the total.
- Answer edition: every question has 答案（参考）. Only current sourced or reviewed answers with citations show their
  short answer and links; others say 待检索与核验 or that they need a recheck. An honest coverage line opens the report.
- At most six labels per metadata line; years only (面试年份, else 资料年份, never import time); unknown metadata is
  omitted; no internal IDs, round enums or source blocks; code stays fenced; source Markdown is escaped.
- The sidecar keeps IDs, occurrences, source metadata, dates, rounds, relations, answer history and the selection.
- Pending slots are honest interim results, not finished answers.
