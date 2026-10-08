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
- “The N most frequent”: `search` and `stats` order by frequency, then wording. When place N is tied, include the
  tie if that adds at most N more (say why there are more than N); otherwise take it in order and name those left out.
- Dates keep their precision (YYYY, YYYY-MM); filters match overlapping intervals and drop unknown dates only
  when a date filter is set. `--recent-days N` covers today and N−1 earlier UTC days; `--as-of` fixes "today".

## Search, show, stats

- `search` returns question cards (id, canonical, type, difficulty, labels, frequency, top companies,
  answer_status, answer_stale_reason, answer_version), 20 per page with `next_offset`; `--detail` returns full
  records with matching occurrences and answer history. `--limit` / `--offset` page.
- `show <id>`: occurrences, sources, relations, merged variants and answer history; merged IDs resolve.
- `stats`: distributions by company, role, domain, technology, month, round, type and answer status, with
  unknown and imprecise date counts (multi-label totals can exceed the occurrences).

## Export

`export --format markdown|json|jsonl|csv|viewer|anki --output <name>` writes under bank/exports only (traversal
and symlink escapes are refused) and always covers the full selection, not one search page.

Formats beyond Markdown (json, viewer, jsonl, csv, anki) and the report language: [export formats](export-formats.md).

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
