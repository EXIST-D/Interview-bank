# Evidence-led reference answers

Research answers after deduplication unless the user asked for questions only or another narrow operation
(core rule 6). The CLI prepares task packets and validates evidence; you search and actually read the pages.
Snippets, link titles and recollection are not verification (core rule 4).

## Commands

```text
python -B <cli> research --question <id> [--question <id> …] --bank <bank> --json   # or a filter plus --limit
python -B <cli> answer --input <answers.json> [--page-texts <pages.json>] --commit --bank <bank> --json
```

`research` packets omit occurrences and answer history (use `show` when you need them). A batch limit is a
context size, not the assignment: commit, then request a fresh task for the remaining IDs. `--commit` commits a
clean batch at once; a batch with review items stays staged.

## Scope and ledger

- Cover every question in the agreed scope (normally `report.question_ids` of the requested filter).
  Skip report-hidden personal questions unless named explicitly; never research unrelated banks.
- Keep a ledger outside the Skill: per question pending / verified / blocked, sources, version scope,
  checks done and why anything is unresolved. Resume from it instead of starting over.
- Group 5–10 questions by topic. Read a shared primary page once and reuse it only where it supports each claim.
- Reuse an existing answer only when it is current (source_backed or reviewed) and still covers the wording,
  version and every constraint. Age alone does not prove applicability; never refresh dates without new reading.
- With a user budget, honour it and report real coverage. Do not invent token or cost figures.

## Verifying one question

1. Split the merged wording into sub-questions and constraints; note which claims need evidence.
2. Open primary pages: official docs, standards, original papers, first-party engineering write-ups.
   Cross-check disputed or version-dependent claims against a second independent source (mirrors do not count).
   One directly applicable specification is enough for a narrow fact; say so in the ledger.
3. Check that each cited passage supports the claim for the asked version and scenario; state boundaries.
   For algorithms or code, check complexity and run a minimal example plus edge cases when a runtime exists.
   Record what you ran; never claim a test you did not run.
4. Re-read the condensed answer against every sub-question. Keep negations, exceptions, trade-offs and versions.
   Separate sourced facts from advice. Project questions get a general framework, never invented experience.
5. Mark `source_backed` only after these checks. The CLI checks structure, not truth.
   If evidence is missing, skip with a reason rather than guessing.

## Writing the answer

- `short_answer`: one conclusion plus 3–5 short points, about 100–250 Chinese characters for a concept question.
  Newlines render as bullets. No restating the question, no filler, no pasted page text.
  Algorithm answers give the approach and complexity; runnable code goes in `code_example`.
- Every claim in `short_answer` must also be a cited key point. Reports label the content 答案（参考）.
- Required: `short_answer`, `key_points`, `sources` (and `evidence` when source_backed).
  Optional, only when they help practice: `spoken_answer`, `follow_up_questions`, `common_mistakes`,
  `deep_dive`, `interviewer_intent`, `code_example`. Reports fold them (`export --answer-extras`) and the Web
  reader shows them as collapsible sections.

## Response shape

One answer or one skip per task question. Placeholders below document fields only; never store them.

```json
{
  "schema_version": 1,
  "task_id": "run_FROM_TASK",
  "answers": [{
    "question_id": "q_FROM_TASK",
    "status": "source_backed",
    "short_answer": "直接回应问题的简洁答案",
    "key_points": ["一个有来源支持的要点"],
    "spoken_answer": "适合面试口述的连贯回答",
    "follow_up_questions": ["进一步追问"],
    "common_mistakes": ["容易混淆的说法及纠正"],
    "sources": [{
      "title": "实际读取的文档标题",
      "url": "https://example.org/actual-page",
      "publisher": "发布者",
      "type": "official_doc",
      "accessed_at": "2026-09-05",
      "evidence_note": "对支持该要点的原文进行简短概述",
      "evidence_quote": "页面中支持该要点的一句原文（可选，≤300 字）"
    }],
    "evidence": [{"key_point": 0, "source_urls": ["https://example.org/actual-page"]}]
  }]
}
```

- `type` is descriptive (official_doc, standard, paper …). `accessed_at` is the real reading date, never future.
- Every key point index needs an evidence entry naming supplied citation URLs. URLs are http(s) without
  credentials; duplicates fail. `evidence_note` ≤ 2000 characters.
- Cannot finish? `{"question_id": "q_ID", "skip": true, "reason": "…"}`. An `ai_draft` (no sources) only when
  the user accepts unverified drafts.

## Quotes and link checks

- `evidence_quote` (≤ 300 characters) is a verbatim excerpt. Save the page text you read and pass
  `--page-texts pages.json` (`{"https://…": "redis-faq.txt"}`, paths relative to the file). A quote found in its
  page (case, width and whitespace folded) is stored with `quote_verified: true`; without page text it is kept
  as `false`; a quote missing from its page is refused. This proves you read the page, not that it supports the claim.
- `verify-citations [--question <id>]… [--workflow <id>] [--limit 50]` is the only online command, run only when
  the user asks. HEAD (GET fallback), 3 redirects, 10 s timeout, private and loopback addresses refused.
  It reports status, final URL and time, logs to logs/ and changes no data. A broken link means re-check, not wrong.

## States and versions

| State | Meaning |
|---|---|
| ai_draft | Written without research; no sources or evidence |
| source_backed | Researched, cited, every key point mapped; not human-approved |
| reviewed | A person checked it: the Web 人工审阅通过 button, or `answer-review --status reviewed` typed by the user in an interactive terminal (piped input is refused) |
| stale | Marked outdated, evidence older than `answer_stale_days`, or (V2) written for other wording |
| missing | No answer yet |

- Every write appends a version; content is never overwritten. `verified_at` is the oldest cited access date.
- You may mark an answer stale: `answer-review --status stale --reason …`. You can never mark it reviewed.
- `search` and `research` give `answer_stale_reason`: `marked_stale`, `evidence_age` or `wording_changed`.

## Recheck instead of research

When the reason is `wording_changed` and the new wording asks nothing the answer does not cover:

```json
{"schema_version": 1, "rechecks": [{"question_id": "q_ID", "reason": "only the wording changed",
  "checks": ["compared sub-questions A and B with key_points 0-3"], "covers_current_wording": true}]}
```

`answer-recheck --input <file>` stages a version with the same content, sources and `verified_at`, bound to the
current wording, with your checks appended. A reviewed answer returns as source_backed. Refused for drafts,
uncited answers, evidence older than `answer_stale_days` and V1 banks. New sub-question or scope: research it.
