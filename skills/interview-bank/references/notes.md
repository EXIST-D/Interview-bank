# 八股 notes beside the bank

A collection of published study notes (八股文) lives beside the user's own interview questions. Its questions
and answers are kept exactly as published, with where they came from. Notes never become occurrences: they do
not change frequency, dedupe, sourced answers or reports. Links join a bank question to the notes that answer it,
so the reader shows "相关八股" under a question and "面经里这样问" under a note.

## Import

The source is a folder of Markdown files the user collected, one chapter per file, read in file-name order.
- `# ` is the chapter title.
- Each `## ` heading is a question, and the text under it is the collection's answer.
- When an `## ` only groups several `### ` headings (e.g. 高频面试题), the `### ` headings are the questions.
- 🔴 or ⭐ in a heading marks a key question (重点).
- A chapter opening of 200+ characters becomes a note named `<chapter> · 导读`.

```
notes import --source <folder> --name <id> --title "<display name>" --origin "<where it comes from>" --order <n>
```

- One folder is one collection; `--name` is a short lowercase ID (`agent`, `java`). Ask the user for the origin
  when the folder does not say; never invent an author or a URL.
- The folder is only read. Re-importing the same name replaces the collection: unchanged headings keep their
  note IDs and links, and removed headings drop theirs (`links_dropped`).
- Tell the user the chapter, note and 重点 counts. If a chapter has no `## ` headings, it was imported as one note:
  say so.
- `notes list` shows collections and chapters; `notes search --query <words>`; `notes show <note_id>`;
  `notes remove --name <id>` deletes a collection and its links.

## Organise one source

Keep each upstream source as its own collection, even when another source asks the same question. Within a source,
prefer a small set of knowledge areas, each with topics. Map the original chapter filenames to those topics;
use note overrides for exceptions. Tags are supplementary labels, not another deep directory tree.
Do not infer human mastery, review, author, license or publication date from the title alone.

1. Run `notes catalog --name <id> --bank <bank> --json`. Read the returned chapter/heading inventory and current
   rules. Large catalogs may be capped; read `_page.full_output` when present. Read relevant original notes with
   `notes show` before judging ambiguous headings. This command does not download or rewrite source bodies.
2. Prepare a response using both returned digests. IDs for areas/topics are unique within this source;
   chapter keys are original filenames and note keys are existing note IDs. For example:

```json
{
  "schema_version": 1,
  "collection": "java",
  "source_digest": "<from catalog>",
  "organization_digest": "<from catalog>",
  "metadata": {"description": "Java study notes", "language": "zh-CN"},
  "areas": [{"id": "storage", "title": "数据库与缓存", "topics": [{"id": "redis", "title": "Redis"}]}],
  "chapters": {"08-Redis.md": {"area": "storage", "topic": "redis", "tags": ["Redis"], "kind": "qa"}},
  "notes": {}
}
```

3. Run `notes organize --name <id> --input <response> --preview`, inspect the change counts, then run the same
   command without `--preview`. Supply `--bank <bank> --json` as usual. This command applies one source atomically;
   no separate `commit` is required. If either digest is stale, regenerate the catalog and reconcile the changes.
4. Verify counts, IDs, source bodies and interview links. Repeating an unchanged response with fresh digests is
   a no-op and does not add history. Changes retain the latest 30 organization history summaries.

Optional metadata: `description`, `author`, `homepage`, `license`, `license_url`, `version`, `updated_at`, `language`.
Use the upstream commit/version and date with evidence; unspecified metadata remains unknown. URLs must use
HTTP(S) and contain no credentials. Collection metadata and area lists are display/navigation data, not claims
that every answer has been verified.

Rules support `area`, `topic`, `tags`, `kind`, `question_type`, `verification`, `language`, `evidence`, `locked`, `user_quote`.
Kinds: `material` (default), `qa` (one interview Q&A), `knowledge` (explanations), `case` (system/project design),
`reading`, `roadmap` (learning order/plans), `tutorial` (hands-on instructions), `exercise` (coding problems/solutions),
`resource` (curated links/indexes), `career` (career/role/recruitment information), `news` (releases/industry commentary),
`collection` (several questions in one entry), `info` (source/license/maintenance notices and excluded fragments). Verification:
`reference` (default), `verified`, `needs_review`, `outdated`. Only mark `verified` after actually checking the content
against appropriate sources, supply their URLs in `evidence`, and explain the scope to the user. The CLI validates
the evidence fields, not the truth of a URL's content. Never auto-promote imported public answers to verified.

For a mixed-source cleanup, follow [content cleanup](knowledge-cleanup.md). Classify from actual text and original
article context; the presence of “路线” or “课程” alone does not make an entry a learning roadmap. Exclude pure
promotion, empty answers and maintenance-only fragments from the normal study list with `kind: info`, retaining
their IDs and source text. Meaningful guides and resources stay available through their own content-type filters.
Report entry counts separately from unique questions or full articles. Content classification does not verify answers.

Metadata keys merge with the existing source; `areas` replaces the directory list. Chapter/note rules are partial
patches, with note rules overriding chapter rules. A `null` rule removes an unprotected override. If specifying a
topic on an override, include its area. Every retained rule must still reference a valid area/topic. To protect a
classification, use `locked: true` and the user's actual `user_quote`; further changes to effective protected rules
require explicit user words, including attempts to override a protected chapter on a single note.

The overlay lives in `collections/_organization.json`, separate from original collections and `links.jsonl`.
Backups include it. Re-import keeps the overlay but signals a changed source digest: inspect new/removed headings
and reconcile mappings. A new chapter with no rule remains available in the original view. Older collections
without an overlay retain their original chapter navigation. Do not write this file or canonical data by hand.
Whole-bank sync can overwrite it; in a multi-computer setup use the current server copy before syncing a whole bank.

## Link questions to notes

For question-level taxonomy, typed filters and evidence-backed links from **public interviews** to same-source
knowledge, read [knowledge taxonomy and study links](knowledge-taxonomy.md). Personal question links below are a
separate relation: public articles never contribute private occurrence frequency. When augmenting existing personal
links, include all current links for every task question in the response; `notes link` replaces that question's set.

1. `notes link-candidates [--question <id> …] [--unlinked] [--top-k 6]` writes a task. Each active question gets
   its lexically closest notes, and `catalog` lists every note (ID, collection › chapter, title). Read `task_file`;
   with many questions, judge in batches. Candidates only share words: scan the catalog for paraphrases too.
   Large-source retrieval first shortlists titles, then rescores excerpts with a bounded cache. Body-only matches can
   be missed: use `notes search` beyond candidates, including when `catalog_in_task` is false. On a small server, use
   repeated `--question` batches to bound work per job. Computation releases the bank lock; the CLI rechecks both
   bank and note snapshots before writing the task and rejects concurrent changes instead of overwriting them.
2. For each question, keep only the notes someone should study to answer it:
   - `answers`: the same question or its core.
   - `covers`: a core part of the answer, such as one sub-question.
   Sharing a word or a broad topic is not enough. Most questions get 0–3 links; 自我介绍 and project walkthroughs
   usually none. Any note ID is allowed: look beyond the candidates with `notes search`.
   Avoid notes that are whole interview records (a company and round as the title) unless nothing else fits.
3. Write `{"task_id": "<task id>", "links": [{"question_id", "note_id", "relation", "reason"}]}` and run
   `notes link --input <file>`.
   The task's questions get exactly these links. Questions without links are recorded as judged,
   so `--unlinked` later offers only new questions.
4. Report linked questions, links, and how many came from outside the candidates.

A link task is stale after source contents, headings or interview links change, as dedupe tasks are after commits;
create a new one. Organization-only edits retain the source revision. Older task packets keep their legacy ID check.
An identical already-applied response is a no-op. When task questions have absorbed merged aliases, replacement
reconciles the old alias links with the active IDs; it must not retain a duplicate association under both IDs.

## Reader and server

For public interview records and career articles, read [public experiences](public-experiences.md).
`notes organize` also accepts source-local `experiences` groups with quoted company/date facts. They appear
under 八股 → 公开面经, separate from knowledge and private interview occurrences. Multilingual Chinese-only
cleanup must preserve code, citations and an exclusion audit; original single-language English sources stay
labelled as such unless the user asks to remove them too.

- The Web reader offers personal interviews, interview knowledge, public interviews and learning materials:
  - learning materials have five category cards: roadmaps, tutorials, resources, career material and industry news;
    these are omitted from the interview-knowledge section, without moving or duplicating original records;
  - category/source filters, search and local learning progress work within the learning section;
  - knowledge materials and public interview articles, with independent source shelves and counts;
  - public articles distinguish interview accounts, company question lists and career advice, with company and
    explicit interview-year filters; unknown dates never inherit publication/import dates;
  - an overview of separate source cards; learning content and source/license notices count separately;
  - knowledge areas/topics or original chapters, with 重点, 面经考过 and 按考频 (most asked first);
  - explicit current-topic/current-source/all-source search; tags, content kinds, question types, personal/public
    interview-link scopes and verification filters;
  - source metadata and organization history, including links to full source/license notices;
  - read/review/mastered learning marks and filters, kept only in this browser/account namespace; reading never
    implies verification, and the Agent must not manufacture these marks;
  - Markdown answers (lists, tables, quotes, code);
  - the source line under every answer.
- Source cards show linked **note** counts, not distinct interview-question counts. A note can link to several questions.
- Original answers stay verbatim and marked as reference; unverified material displays its verification status.
- Hosted readers remain read-only. Editing directories, importing sources and setting evidence-backed verification
  use the Agent CLI. Cross-device progress sync and direct Web editing are not implemented.
- A hosted reader gets notes through `tools/deploy/sync.sh`, which sends `collections/` with `data/`.
- Backups include `collections/`.
- Collections are the user's private material: never copy them into the Skill, a repository or a public page.

From 1.23, use `notes search --section learning` for those five kinds and `--section knowledge` for interview
knowledge. The default `all` query preserves the original inventory, including notices and article members.
Public-article members take precedence over their original kind: a career article never leaks into learning.
Section-aware Web deep links keep original note IDs and learning marks; no bank migration is required.
