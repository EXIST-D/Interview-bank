# Query, analysis and export

## Filters

`search`, `stats` and `export` share: `--query --company --industry --company-type --ownership --business-model
--role --domain --technology --round --interview-type --difficulty --question-type --date-from --date-to
--recent-days --as-of --answer-status`.

- Labels accept catalog IDs, Chinese labels and aliases; a parent role, domain or industry includes its children.
  Several query words must all appear in one wording (the question's or one occurrence's).
- Company, industry, profile, role, round, type and date conditions must hold for the **same occurrence**.
- `frequency` counts matching occurrences, `total_frequency` all of them. Counts describe the collected
  material, not interview participants or hiring odds; say so when you report them.
- Dates keep their precision (YYYY, YYYY-MM); filters match overlapping intervals and drop unknown dates only
  when a date filter is set. `--recent-days N` covers today and N−1 earlier UTC days; `--as-of` fixes "today".

## Search, show, stats

- `search` returns question cards (id, canonical, type, difficulty, labels, frequency, top companies,
  answer_status, answer_stale_reason, answer_version), 20 per page with `next_offset`; `--detail` returns full
  records with matching occurrences and answer history. `--limit` / `--offset` page.
- `show <id>`: occurrences, sources, relations, merged variants and answer history; merged IDs resolve.
- `stats`: distributions by company, role, domain, technology, month, round, type and answer status, with
  explicit unknown and imprecise date counts. Multi-label totals can exceed the number of occurrences.
- The latest version decides the answer status; `missing` is derived. Age past `answer_stale_days` (180)
  makes an answer stale without rewriting history.

## Export

`export --format markdown|json|jsonl|csv|viewer|anki --output <name>` writes under bank/exports only (traversal
and symlink escapes are refused) and always covers the full selection, not one search page.

| Format | Content |
|---|---|
| markdown | Two reader editions plus `<output>.details.json` (below) |
| json / viewer | Snapshot: questions with occurrences and answer history, referenced sources, companies, relations |
| jsonl | One question envelope per line with its related records |
| csv | UTF-8 BOM, formula-safe cells, JSON columns for occurrences, citations and companies |
| anki | Tab-separated notes for Anki's File → Import (front, back, tags) |

- Local source paths are left out unless `--include-paths`; citation and source URLs stay (they are evidence).
- Exports are for reading and exchange, not `stage --input` bundles; backups are `backup create`.
- The reader report leaves out self-introductions and questions with a `report_exclusion`; the result lists
  `report_questions` and `excluded_questions`, and structured exports keep every selected record.

## Two Markdown editions

- `--answers both` (default) writes `<output>` with 答案（参考）, `<stem>（题目版）<suffix>` with questions only, and
  one shared `<output>.details.json`. `--answers with|without` writes one edition at `<output>`.
- Layout: title, topic overview, H2 per topic, H3 questions numbered from 1 by frequency; years only; no internal
  IDs; code stays fenced. Both editions share selection, totals and numbering.
- The answer edition shows a current sourced short answer with its links; missing, draft, stale or uncited
  answers get an explicit pending line (full content stays in the sidecar). `--answer-extras folded|inline|none`
  controls the 口述版 · 常见追问 · 易错点 block. The question edition shows no answers at all.
- `answered_questions` / `pending_answers` in the result give real coverage. Export never browses or calls a model:
  in the default flow, research and commit answers first.

## Anki

Front: the question. Back: the current sourced short answer with source links (and the problem link when set).
Questions without one get an empty back and the tag 待核验. Tags are domain and technology IDs. Report-excluded
questions are left out.

## Report language

`config.language` `zh-CN` (default) or `en` (`config --input '{"language": "en"}'`, then commit) switches headings,
answer states, the practice block, topic names, tags and Anki cards; question wording is never translated.
The Web reader follows the same setting.
