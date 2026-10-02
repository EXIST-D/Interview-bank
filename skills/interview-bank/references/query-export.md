# Query, analysis and export

search, stats and export share filters: --query, --company, --industry, --company-type, --ownership, --business-model, --role, --domain, --technology, --round, --interview-type, --difficulty, --question-type, --date-from, --date-to, --recent-days, --as-of, --answer-status. Role/domain/technology/industry/profile filters accept catalog codes, Chinese labels and known aliases. Company matches IDs/names/aliases; parent role/domain/industry matches descendants. Multiple query tokens use AND within one question wording or one occurrence wording.

Company/industry/company-type/ownership/business-model/role/round/interview-type/date conditions must match the same occurrence. They cannot be satisfied by unrelated appearances of the same standard question. Questions remain unique; frequency is matching occurrence count, total_frequency is all appearances. Statistics describe the collected material, not interview participants or market probabilities. Industry, organization type, ownership and business-model distributions count occurrences; multilabel totals can exceed the number of appearances. Existing legacy aliases are normalized for statistics without rewriting stored data.

Dates retain original precision. YYYY represents that year, YYYY-MM that month; filters include intersecting intervals. Unknown dates are excluded only when a date filter exists. --recent-days N includes today and N−1 preceding UTC dates; --as-of YYYY-MM-DD makes the calculation reproducible. Do not describe partial-date matches as proven exact-day events.

search returns question cards (id, canonical, type, difficulty, labels, frequency, top companies, answer_status, answer_stale_reason, answer_version), 20 per page by default, with `next_offset`; `--detail` returns full records with matching occurrences and answer history. search supports --limit and --offset. With --json every result is compact and bounded (32 KB, INTERVIEW_BANK_MAX_OUTPUT); an oversized result carries `_page` (field, returned, total, next_offset, full_output) and its complete version is saved under cache/outputs. show <id> returns occurrences, source metadata, relations, merged variants and answer history; merged IDs resolve to active targets. stats includes question/company/role/domain/technology/month/round/type/answer-status distributions and source counts. Year-only dates remain year buckets; unknown/imprecise date counts are explicit.

## Answers in results

Latest version determines answer status. missing is a derived state, not a stored Answer. Age past answer_stale_days (default 180) makes an answer effectively stale without rewriting its history; source-backed freshness starts from the oldest citation access date. Original status/history remain accessible.

## Export

export --format markdown|json|jsonl|csv|viewer --output <name> writes under bank/exports only. Relative paths resolve there; absolute paths must still remain there. Symlink/traversal escapes are rejected. Export processes the full selected result rather than search's default first page.

- markdown: concise reader report grouped by knowledge topic; H1 report title, top domain-count overview, H2 domains and frequency-sorted H3 questions numbered from 1 within each domain; no internal IDs, source index or round enums. Every question includes 答案（参考） with sourced content or an explicit pending-verification slot. Known dates display years only (event year, otherwise clearly labeled source year). An adjacent `<output>.details.json` preserves full provenance, metadata, answers and report selection. Original code remains fenced.
- json: structured snapshot with question/occurrences/answer history, referenced sources/companies and relations.
- jsonl: one question envelope per line with its related records.
- csv: UTF-8 BOM for Excel, formula-safe cells, structured occurrence/citation/company JSON columns.
- viewer: portable JSON snapshot for downstream tools. For the optional local Web reader/practice UI, use `web --bank <bank>`; it reads the existing bank directly, not the viewer export. See [Web usage](web.md).

Local source paths are omitted by default; --include-paths explicitly includes them. Citation URLs and source URLs remain because they are evidence. Exported snapshots are reading/interchange formats, not stage --input canonical import bundles. Canonical backup consists of manifest/config/data and retained media; operate while no outside writer is modifying it.

The reader report excludes obvious self-introductions and questions with a nonempty report_exclusion. Legacy records remain retrievable; stats/search describe the canonical bank, while export returns report_questions and excluded_questions separately. Structured JSON/viewer exports retain all selected records plus a report object listing included IDs and exclusion reasons; CSV/JSONL also preserve the canonical data. Unknown metadata is omitted. Missing, draft, stale or uncited answers have an explicit pending-verification slot; full content and versions remain in the sidecar. Current sourced short answers keep their verification status and clickable citations in Markdown. `--include-paths` affects structured provenance only, never adds paths to the reader report.

## Two report editions (1.4)

Markdown defaults to `--answers both`: `<output>` is the reference-answer edition, `<stem>（题目版）<suffix>` is the question-only edition, and `<output>.details.json` is their shared full attachment. `--answers with` or `--answers without` writes only the selected edition at `<output>`. `--answer-extras folded` (default), `inline` or `none` controls the 口述版 · 常见追问 · 易错点 block that follows a current sourced answer when those optional fields were written; the question-only edition never shows it. These options apply only to Markdown; structured exports always retain full data.

Both editions use exactly the same question selection, domain totals, frequency order and numbering. The question-only Markdown has no answer text, pending slots, answer progress or answer citations; its shared structured attachment may still contain answers and history. Result fields answer_output/question_output identify the files; answered_questions/pending_answers distinguish actual coverage from empty slots. The exporter never calls a model or a website. The default Skill workflow researches and commits answers before final export; an explicit export-only request renders existing data without starting research.

## Anki

`export --format anki --output cards.txt` writes tab-separated notes for Anki's File → Import (`#separator:Tab`,
`#html:true`, tags in column 3). Front: the question. Back: the current sourced short answer with its source links
(and the problem link when set). Questions without a current sourced answer get an empty back and the tag 待核验.
Tags are the domain and technology IDs. Report-excluded questions are left out.
