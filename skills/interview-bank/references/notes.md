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

## Link questions to notes

1. `notes link-candidates [--question <id> …] [--unlinked] [--top-k 6]` writes a task. Each active question gets
   its lexically closest notes, and `catalog` lists every note (ID, collection › chapter, title). Read `task_file`;
   with many questions, judge in batches. Candidates only share words: scan the catalog for paraphrases too.
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

A link task is stale after a re-import, as dedupe tasks are after commits; create a new one.

## Reader and server

- The Web reader shows a 面经 / 八股 switch once a collection exists. In the notes view:
  - chapters in order, with 重点, 面经考过 and 按考频 (most asked first);
  - Markdown answers (lists, tables, quotes, code);
  - the source line under every answer.
- A hosted reader gets notes through `tools/deploy/sync.sh`, which sends `collections/` with `data/`.
- Backups include `collections/`.
- Collections are the user's private material: never copy them into the Skill, a repository or a public page.
