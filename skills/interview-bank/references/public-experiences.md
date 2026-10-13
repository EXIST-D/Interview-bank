# Public interview accounts inside 八股

Read this when organising public sources that mix technical knowledge, interview accounts and career advice.
Keep the source collections separate. These articles never become private question occurrences or inflate
frequency. The Web notes section has **知识资料** and **公开面经**; the existing reader handles both.

## Decide the content type

- `interview`: an explicit account of an interview or written test, including its questions and author commentary.
- `company_questions`: questions attributed by the source to a company, without a clear single interview event.
- `career`: job-search methods, personal retrospectives or career advice. Do not turn general advice into an event.

Generic “big-company interview questions” belong in the knowledge directory unless the actual content identifies
an account or company-specific question list. A directory name, technology vendor or company mentioned in a
comparison is insufficient. For user-uploaded material whose public/private identity is unclear, clarify it;
continue processing known public repositories in the meantime.

Group the original sections of one event or article, preserving order and code. An interview with thirty
sections should be one article, not thirty apparent interview events. Split a file containing several explicit
events at their original boundaries; first preview the prepared Markdown in an isolated bank, record each
original span and check no substantive questions disappeared. Exclude navigation, promotion, empty placeholders
and clearly obsolete link-only indexes with reasons. Individual self-introduction templates are not bank
questions; a requested complete interview account may retain them as original narrative context.

## Company and dates are separate source facts

Use the original company name, role, round and interview date only when supported by text. Preserve partial
dates; “6.29” has no known year. Keep `published_time` separate from `interview_time`. Never use a filename,
image timestamp, upstream commit date, import date, cohort year or model-release year as an interview date.
Unknown values stay empty and the reader labels them as unspecified.

For each populated fact field, record a short source quote and either a member note ID or an actual public
source URL. The value must occur in the quote. A quote with a note ID and no URL must occur in that note or
its chapter. For facts found in the original document outside the imported segment, read the document and
provide its public URL and actual excerpt. Validation establishes structure, not historical truth; do not call
a source account independently verified merely because its fields passed.

## Apply an article overlay

Use `notes catalog --name <source> --bank <bank> --json` and both fresh digests from its full output. Add an
`experiences` patch to the `notes organize` response; it is stored beside the source's directory metadata.

```json
{
  "schema_version": 1,
  "collection": "example",
  "source_digest": "<from catalog>",
  "organization_digest": "<from catalog>",
  "experiences": {
    "backend-first-round": {
      "title": "示例公司后端一面与复盘",
      "kind": "interview",
      "note_ids": ["<existing source-local note ID>", "<another section ID>"],
      "company": "示例公司",
      "interview_time": "2026-02-10",
      "summary": "原文中的面试提问与作者复盘。",
      "facts": [
        {"field": "company", "quote": "示例公司 后端一面（2026-02-10）", "note_id": "<existing source-local note ID>"},
        {"field": "interview_time", "quote": "示例公司 后端一面（2026-02-10）", "note_id": "<existing source-local note ID>"}
      ]
    }
  }
}
```

Fields: `title`, `kind`, ordered `note_ids`, optional `summary`, `company`, `role`, `round`, `interview_time`,
`published_time`, `facts`. Article keys use lowercase letters/digits/hyphens/underscores, at most 80 characters.
Each article has 1–500 existing notes, from its own source only; a note belongs to one article. Source-local
article IDs remain stable when the same key is reused. Replacing an article replaces its complete object;
`"backend-first-round": null` removes it. Other article keys remain unchanged. No private-question IDs belong here.

Run `notes organize --name <source> --input <response> --preview`, inspect counts, then apply without
`--preview`. The operation is atomic and digest-checked. Original notes, IDs and links are unchanged by the
overlay. The knowledge view excludes article members; public accounts are counted by article, not section.
Raw notes remain queryable for existing links. Article links deduplicate the same private question and retain
its original frequency. Reading progress belongs to the article ID in the current browser.

`notes search --query <words> --section experiences` searches whole accounts. `--section knowledge` searches
the knowledge subset; the default `all` preserves legacy raw-note search. `notes show <article-id>` displays
the complete account with provenance and its existing private-question links. `notes catalog` includes the
source's `experiences` mapping. The Web API uses `/api/notes?section=experiences` with optional `collection`,
`kind`, `company`, `year`, `query` and `sort=recent`; `year=unknown` filters unspecified interview years.

After re-importing a changed source, inspect and reconcile member IDs using a fresh catalog. Missing sections
make an account incomplete and needing review, not silently complete. Before retiring notes, remove affected
chapter/note overrides while their keys still exist; update or remove their article groups too. Keep a verified
backup and compare private canonical data and link hashes in a multi-computer server workflow.

## Multilingual sources

When the user requests Chinese-only editions, choose the simplified Chinese edition of a multilingual source
and remove other same-source language editions, including a duplicate traditional edition. Retain code and
original links. Audit removed paths against retained Chinese paths; heading counts can differ between editions,
so do not assert question-by-question equality without checking. A source with only English content is not a
multilingual duplicate: preserve it and label its actual language unless the user also asks to exclude it.
Do not claim an English-only answer is a Chinese translation.

Keep source description, language and knowledge directory consistent after cleanup. Empty directories should
not clutter navigation. The bundled Skill contains the protocol, not imported public or personal datasets.
