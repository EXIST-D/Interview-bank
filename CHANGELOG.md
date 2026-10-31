# Changelog

All notable changes to the Interview Bank Skill. Versions follow [Semantic Versioning](https://semver.org/); the bank data format is versioned separately (V1/V2) and only changes through an explicit `migrate`.

## [1.39.0] - 2026-10-31

### Added
- Web import of pasted text and links (`粘贴文字`, `贴链接` on the import page), through the screenshot pipeline: the text model reads the
  post as numbered paragraphs and returns for each question the paragraphs it is written in; the server takes the original wording
  from those paragraphs (a question that cites none is dropped), so a question stays tied to real text (`locator.segment_ids`) and the
  person confirms, dedupe commits and answers follow as for screenshots. Pasted text is a `text` source, a link a `web` source with the
  address and the platform named from the host. A link is read with the research page reader (public addresses only); a page that
  cannot be read is refused at once with the way out, and a page over 30,000 characters is cut there and the person is told.
- The interview date is only what the person enters (the hint or the confirmation page); the model is not asked for one and a date it
  gives is dropped. A real run read the "面经10.28" in a post's title as the interview date, and a rule that the model must quote the
  post's words would not have caught it. The posting date (`source_date`) is only what the person typed.
- `intake_page` in the engine (the CLI's `web-intake` now goes through it) also takes text without an address.

### Evaluated
- DeepSeek Fetch API (`/v1/tools/fetch`, ¥5 per 1,000 successful calls) against the built-in reader on one post of each platform from a real
  bundle: a cleaner article for 牛客 (about a third of the characters) and nothing usable for 知乎, 小红书, 抖音 or a Bilibili video page,
  where the built-in reader fares no better. Not integrated; `references/web.md` lists which sites give text.

## [1.38.0] - 2026-10-31

Dedupe retrieval for paraphrases and for a short question inside a longer one. Measured on a real import (76 pairs decided by
reading the whole review sheet of a 462-question bundle), pairs that are the same question were already offered 16 of 16
times; the gaps were pairs that lead into each other (52 of 60 offered) and their rank.

### Added
- Concept keys: an optional `concept` on a question names the one knowledge point it asks about, 2 to 4 lowercase segments
  joined by dots (`rag.chunking.strategy`). Questions about the same point share a key whatever their wording. Set it on an
  extraction candidate, with `curate` (`null` clears it) or through `export-bundle` / `import-bundle` (a key that does not
  fit is dropped on import). `stats` lists the keys in use and how many questions have none; `search --concept` takes a key
  or its leading segments.
- In the Web import the model gives each new question a key; its prompt lists the bank's most used keys so it reuses them
  instead of inventing variants, and the dedupe step sees the key and which candidates share it.
- AI-domain evaluation set `evals/dedupe/pairs-ai.jsonl` (66 pairs of Agent, RAG, MCP, LangGraph and LLM questions: paraphrases,
  project-style questions, one question inside a longer combined one, mixed languages, near-miss negatives). The retrieval
  report now also gives RELATED pairs, the AI pairs from wording alone and with their concept keys, and `offered` (anywhere in
  the list the reviewer sees) beside `recall@k`.

### Changed
- Candidate similarity also measures overlap and sequence against the shorter text, scaled by how much the two differ in length and
  damped, so a part of a combined question is found ("岛屿数量" against the long "LeetCode 200 岛屿数量…" went from 0.13 to 0.47)
  while two questions of similar length score exactly as before.
- Candidate lists: the top-k of the bank as before, plus up to 5 earlier questions of the same import (a batch of related new
  questions used to fill the list and push the bank's own question out); questions of the bank with the incoming key are always
  offered, up to 5, and rank as if they scored 0.25 higher. The review sheet shows keys in brackets and marks `key` candidates;
  a task marks them `same_concept`.

### Measured
- Real import, with the model's keys on all 775 questions: same-question pairs rank 1 in 11 of 16 (was 9) and within the top 3
  in 16 (was 13); related pairs offered 57 of 60 (was 52), 46 of them through the key. The cost is a longer list: 12.2 candidates
  per new question on average, 15 at most (was 8.8 and 10). The model's keys matched for all 16 same-question pairs and 46 of
  the 60 related ones (50 shared the first two segments).
- Suite (CI): the old pairs score as with 1.37 on the same pool; AI-domain MERGE pairs 0.91 from wording alone, 1.00 with keys;
  AI-domain RELATED 0.69 → 0.75, 0.88 with keys. The keys in the suite are written by its author, so that figure shows what the
  mechanism does when keys agree, not how well a model agrees.

## [1.37.0] - 2026-10-30

### Added
- `export-bundle` and `import-bundle`: carry the questions of one bank into another as text only (questions, occurrences
  with company, role, round, interview type and dates, one text source per post; no media, answers or transcripts).
  The import fits ids, companies, sources and taxonomy to the target, stages the questions as new ones and returns the
  usual dedupe task; `--dry-run` reports and validates without writing, and importing the same file twice adds nothing.
  `--fill-event-date year|month|day` gives occurrences without an interview date the date their post was published, at
  that precision (an approximation, to file questions under a period; the exact date stays on the source).
  The bundle also carries the wordings merged into each question, so the reader still lists them as its other phrasings.

## [1.36.1] - 2026-10-30

### Fixed
- A failed mock-interview feedback or job-description pick could show as failed before its model call was on the usage
  ledger; the ledger is now written first, so a poll never sees an outcome whose cost is missing.
- Test runs no longer race background import and feedback tasks while their temporary bank folder is deleted.

## [1.36.0] - 2026-10-30

### Added
- Preparation board in the Web reader (`#/prepare`, 备考), for any bank (the list tab needs V2):
  - **Most asked**: questions ranked by how often they were asked, weighted by how recently (each occurrence halves
    its weight every 180, 365 or 730 days; an occurrence with no recorded date counts 0.3), with the library's
    domain, technology and company filters, a time window (all, 3 years, 1 year) and an order by heat or by count.
    Practise or start a mock interview on what is shown, weak and unseen questions first.
  - **Companies**: every company with its questions, occurrences, years and main domains; a company page lists what it
    asked by round and year, with practice and mock interview on that company's questions.
  - **Study lists**: the job-description selection of the mock interview can be saved as a list (a snapshot
    `studyset` with the JD mapping, so `studyset show/export/plan` read it too). A list shows each requirement with the
    words of the job description, its priority (must or nice) and whether the bank covers it directly, partly or not at
    all, the questions with the person's progress, a warning when a question was reworded since, and practice and mock
    interview on the list. Coverage is about the bank's questions only, never about the person or the job.
- A bank whose occurrences carry no interview date (a bank imported without dates has none) ranks by count: the page
  says so and hides the time window and half-life controls, which would have nothing to work on. Publication and import
  dates are never used in place of the interview date.
- The job-description selection now also returns each pick's coverage (direct or partial) and priority.
- Endpoints: GET `/api/prepare/top`, `companies`, `company`, `lists`, `list`; POST `/api/prepare/save` (needs practice).

## [1.35.0] - 2026-10-30

The Skill is narrowed to what an Agent does with a bank: collect, extract, classify, deduplicate, write answers in the
answer format, export, and read the bank in the Web reader. Review, mock interviews, saved topics and 八股 notes
belong to the Web reader project; their commands and data format stay in the engine, only the Skill no longer routes to them.

### Changed
- `SKILL.md`: description and routing table no longer mention JD practice, spaced review, mock interviews, saved topics
  or notes; the reader row is "read the bank in a browser"; `sources` is listed beside search and export. This frees
  about 1 KB of the reading budget of the end-to-end path.
- References of the Web reader project (`practice`, `studysets`, `notes`, `public-experiences`, `knowledge-cleanup`,
  `knowledge-taxonomy`, and the model sections of `web`) carry a scope note.
- Trigger evaluation: six cases about review, mock interviews and JD practice now expect no trigger, and six cases about
  web pages, recordings and imported sources were added (86 cases).

### Added
- `tests/test_boundaries.py`: engine modules may not import the Web reader's code (one-way, Web → engine); only the
  command-line entry starts the reader.
- The `sources` output fields are pinned by a test as a contract with outside collectors: within 1.x they are only added to.

## [1.34.0] - 2026-10-30

### Added
- AI mock interview and answer feedback in the Web reader (`#/interview`; needs `web --ai-config` and, on a read-only
  reader, `--allow-practice`; V2 banks). The questions come from the person's own bank, never invented: by direction
  (the library's filters, questions with a sourced or reviewed answer first, optionally random) or from a pasted job
  description, where the model picks bank questions and the server keeps only real IDs and excerpts that occur in the
  text; the person ticks what to ask, and the session records why each was chosen. *AI 批改我的答案* below a question
  starts a one-question session.
- The person's answer is saved verbatim before anything else (idempotent by request ID); a background task then has
  the text model compare it with the reference answer's key points, following the new *Writing feedback* rules in
  `practice.md`. The server keeps only known dimensions, quotes found word for word in the answer and key-point checks
  that exist in the reference; feedback has no score. Without a sourced or reviewed reference, or when the wording
  changed, feedback is `limited_basis` (no verdicts, no key-point checks). One suggested follow-up, two per question.
  A failed feedback keeps the answer and can be asked for again. Mastery stays the person's own rating.
- Sessions are the CLI's `interview` records (same stage-and-commit steps), so an agent can read and continue them:
  `interview start` takes `meta` and `keep_order`, `interview feedback` takes `generated_by`, `key_point_checks` and
  `follow_up_suggestion`.
- `limits.daily_feedback` (default 200) caps feedbacks per 24 hours; feedback and job-description picking share the
  usage ledger and the daily budget of the import (`usage_ledger.py`).
- `sources` lists the committed sources (screenshots, pages, recordings) with platform, URL, date, transcription
  engine and model and the occurrences and questions extracted from each; `--url`, `--query`, `--platform`, `--type`
  filter and `--limit`/`--offset` page. Read-only and without stored file paths, so a collector can tell which posts
  the bank already holds.

## [1.33.0] - 2026-10-28

### Added
- Usage and cost of the Web import and web research: every model call (cached and uncached input, output tokens) and
  every search is recorded per job and per Beijing day (`cache/web-intake/usage.json`, 120 days). The import page shows
  today's usage and the last 30 days; each finished job shows its own. Works with the usage fields of DeepSeek,
  OpenAI-compatible and Anthropic replies.
- Optional `prices` in the AI configuration (per million tokens, with `peak` / `off_peak` for DeepSeek's Beijing
  weekday 9–12 and 14–18 rates, or `call` for a search provider) and `limits.daily_budget`, which refuses new jobs and
  further searches once today's cost reaches it. The example carries DeepSeek's and Bocha's list prices of 2026-10-28.

### Changed
- Page texts saved for web research (`cache/pages`) are deleted after 30 days.

## [1.32.1] - 2026-10-27

Fixes from the first web research with real Bocha search.

### Fixed
- Anti-bot stubs (for example `var arg1=…`) and pages under 300 characters counted as readable, so a question could
  reach the model with no usable text. They now count as failed and the next results are read, up to 12 pages a question.
- Many Chinese results are JavaScript-only for a server: when none is readable, a second query adds the question's
  technologies (for 缓存穿透: 3 of 3 sample questions sourced, against 2 of 3 before).
- A desktop and a mobile copy of the same page (`www.` / `m.`) both cited; now one page per site, so sources are
  independent. Answer farms and document-sharing sites are read only when nothing better is readable.

## [1.32.0] - 2026-10-27

### Added
- Web research for sourced answers in the reader (optional `search` in the AI configuration: Bocha or Tavily). New
  imported questions are researched before anything is written; 补充出处 on the import page (most-asked drafts, stale and
  unanswered questions first) and 联网补充出处 below an answer do the same for existing questions. For each question the
  `research` task's query is searched, up to `pages` results are read with `page-text`, the model answers only from
  those texts (instructions cut from answer-policy), and the server keeps only citations of pages it read, drops
  quotes not found verbatim and key points without a supporting page, records its checks and stages the answer as
  `source_backed` with the page texts so quotes are verified. Unsupported questions keep their answer; a new import
  falls back to an AI draft. `limits.daily_research` caps searches per day; `ai-check` also checks the search service.
- README screenshot of the import review page; the reader and phone screenshots retaken from the demo bank.

### Fixed
- Security: `page-text` and `verify-citations` refused private targets but followed redirects without checking them; a
  redirect to a loopback, private, link-local or carrier-grade NAT address (cloud metadata) is now refused.
- nginx templates: nginx refuses `client_max_body_size` twice in one location, so the shared proxy snippet no longer
  sets it and each location does (64k; 11m for import). `location /ibank/api/intake` has no trailing slash, so
  `GET …/api/intake` reaches the reader instead of an nginx redirect.
- Documentation that no longer matched: SECURITY.md (network paths, hosted mode), web.md (polling, accounts),
  capabilities, README requirements, status and verification figures, outdated screenshots.

### Changed
- `page-text` leaves out `<nav>` and `<aside>` blocks, so menus no longer fill the start of a page's text.
- `ai.example.json` uses `deepseek-flash` with thinking off for dedupe and answers too: on the same screenshot a batch
  took 42 s against 276 s with `deepseek-v4-pro`, with the same dedupe decisions and comparable answers.

### Removed
- 21 unused interface strings left from the 1.28/1.29 editor changes and an unused storage alias.

## [1.31.1] - 2026-10-27

Fixes from the first import with a real model (DeepSeek `deepseek-flash` / `deepseek-v4-pro`).

### Fixed
- A merge kept the existing wording and lost the new question's sub-points. The dedupe step now also follows
  dedupe.md's merged-wording rules: the model proposes a `canonical`, applied directly when the target has no answer or
  only an AI draft (the draft is written again), and asked on the page when the target has a researched answer,
  since rewording makes that answer need a recheck. Choosing related or different drops the proposed wording.
- `deepseek-flash` with thinking off breaks off plain-text JSON; the example configuration turns on `json_mode` for reading.
- Study wording drops labels such as “手撕：” (extraction.md).

### Added
- The review page opens each screenshot full size for checking; the merge page shows the wording a merge would produce.
- The saving step says that judging duplicates takes a minute or two and the page can be left.

## [1.31.0] - 2026-10-27

### Added
- Screenshot import in the Web reader (`#/import`, opt-in with `web --ai-config <file>`; a read-only reader also needs `--allow-intake`): upload, paste or drop screenshots; a configured vision model reads them; the person checks every question (untick, reword, company/round/date) before anything is saved; new questions get `ai_draft` reference answers.
- The model plays the host's part in the Skill's own pipeline: `ingest images` (copy retention; known bytes are not read again), extraction, `ingest submit` with dedupe candidates and the review sheet, dedupe decisions, commit, `research` task and answer staging. Instructions are cut at run time from `references/` (extraction, report policy, dedupe, answer policy); model output is reduced to the extraction schema.
- Exact duplicates merge; merges below 0.90 confidence are asked on the page before the commit. Low-confidence readings and possible contact details are highlighted, unreadable screenshots are skipped on confirmation or read again.
- Long screenshots are cut in the browser into up to eight overlapping parts read in one request; HEIC (Safari) and oversized files are re-encoded as JPEG. Thumbnails are data URLs, so the content policy is unchanged.
- `ai.py`: OpenAI-compatible `/chat/completions` and Anthropic Messages via the standard library, retries for 429/5xx/timeouts, keys only from `api_key_file` (refused when world-readable) or an environment variable, plain HTTP only on loopback; `extra_body` for provider switches such as DeepSeek's thinking mode, `image_encoding` for providers that want bare base64. `ai-check --ai-config <file>` sends one tiny request per model.
- Per-bank limits (screenshots per import and per day, answers per import and per request), one import at a time, recovery of interrupted jobs after a restart, cancel that abandons the stage and removes the screenshot copies.
- Tests for the whole pipeline with a stand-in model (merges, retries, bank changes during judging, cancel, limits, restart, both protocols) and a browser journey (`e2e/import.mjs`) against a loopback stand-in model.

### Changed
- `tools/deploy/`: `ai.example.json` (DeepSeek: `deepseek-flash` reads with thinking off, `deepseek-v4-pro` answers); nginx location for `/api/intake/` with an 11 MiB body limit; service notes for `--allow-intake` and `MemoryMax=512M`.
- The settings menu's 导入题目 opens the import page when the server allows it; 个人面经 shows 上传截图.

## [1.30.0] - 2026-10-24

### Added
- Opt-in hosted guest reading via `web --public-bank <bank>`: GET-only public bootstrap, collection search and articles; knowledge, public interviews and learning resources are accessible without an account.
- Login gates for personal interviews, notes, favourites and practice; same-page login returns to the original hash route. Public reading can resume from the login page.
- Visible GitHub entry beside account controls, with responsive navigation and reader height tracking.
- Authorization regression tests for anonymous private-ID guesses, write attempts, private association counts, account isolation, invalid cookies and unchanged personal data.

### Security
- Public projections never load personal notes and omit interview questions, private links/counts and organization audit history; local source origins are hidden. Guest browser reading state is separate and never synced to an account.
- Publishing is explicit and requires hosted login configuration. Existing local readers and private hosted instances retain their defaults; proxy token, origin validation and secure session cookies are preserved.

## [1.29.0] - 2026-10-23

### Added
- Live Markdown notes using CodeMirror 6: in-place headings, emphasis, lists, quotes, code, task checkboxes and table widgets; reveal source at the cursor without switching modes. Click a table to edit its Markdown.
- Formatting tools and shortcuts with undo/redo; native composition handling, soft wrapping, a visible 20,000-character limit, and independently scrolling notes on desktop and phone.
- Browser checks for live rendering, exact Markdown round trips, format undo/redo, table editing, inert HTML/links/images, Chinese composition and keyboard saving.

### Changed
- Replace the note edit/preview tabs with a single editor surface. Existing Markdown/API, scoped drafts, optimistic concurrency and version history remain compatible; no bank migration or automatic server saving.
- Lazy-load the prebuilt editor only when the note panel opens. Retain nonce-bound styles and the existing CSP; no CDN, remote image loading or AI calls.

## [1.28.0] - 2026-10-21

### Added
- A Notes toolbar entry and an independent right-side Markdown editor shared by interview questions, knowledge, public interviews and learning materials. Desktop reading stays interactive; phones use an accessible modal panel.
- Account/item-scoped local drafts, Markdown preview, keyboard save, and linked-item context. My-notes cards, saved-note list badges and copyable `panel=notes` links open the correct item's note.
- Browser regression journeys for draft restoration, item isolation, note deep links, mobile dismissal, Markdown preview and real stale-save conflict reconciliation.

### Changed
- Remove the bottom personal editor and unify visible labels as notes; keep `personal/my-answers.json`, the API, version history and permissions compatible. No bank migration.
- Preserve the visible paragraph when opening or closing the panel; late saves cannot replace another open item's details. Conflicting saves retain the local draft and require loading the latest version before saving.

## [1.27.0] - 2026-10-21

### Added
- Learning categories open a collapsible source directory with courses/topics and separate entry counts, instead of a flat chapter list. Directory-name search and full-text search have distinct scopes; a complete list remains available.
- Source-local course/topic deep links and a selector in the learning list. Existing reader, note IDs, original text, personal notes and learning marks are retained.
- Learning source cards expose per-kind area/topic counts so resource indexes or announcements do not inflate tutorial directory counts. No bank migration is needed.

## [1.26.0] - 2026-10-19

### Added
- My notes: an own note below the original of every knowledge, public-interview and learning entry, stored with own answers in `personal/my-answers.json` (same versions and stale-page protection). `notes show` returns it; notes whose collection was removed stay listed and are flagged.
- 我的 page (`#/mine`): all own answers and notes, newest first, with section filter, multi-term search and a Markdown export; favourite folders for questions and entries (`personal/favorites.json`): create, rename, reorder, delete, add/remove items, and a practice round over a folder's interview questions. `GET /api/my-notes`, `GET|POST /api/favorites`.
- A star in the reader to save the open question or entry into folders; the first star creates a default folder.
- 本文目录 in the reader: headings and bold numbered question lines of long originals, with scroll position, jumps and back-to-top.
- 今日计划 on the overview: reviews due, weak/changed and never-practised counts with a start-review shortcut (`#/bank?view=due&practice=1`).
- Learning state on the server: read marks, entry states and source order merge into `personal/learning.json` (`GET|POST /api/learning`) when the reader allows personal writes; browsers still work alone otherwise.
- `web --allow-practice` lets a read-only hosted reader save practice ratings (V2 only); `--allow-personal` is the new name of `--allow-my-answers`, which still works.
- `tools/deploy/pull-backups.sh` copies the newest server backups to a local folder, verifies each `.sha256` and keeps the newest 30.
- `notes describe --name <id> [--title …] [--origin …]` changes a collection's display name or origin line (author · licence · pinned URL) without re-importing; IDs, links and organization digests stay.
- `web/e2e/reader.mjs` (`pnpm e2e`): browser checks on a demo bank in hosted mode, run in CI.

### Changed
- Note search (Web and `notes search`) needs every space-separated term and ranks title matches first, then BM25, using an SQLite FTS5 trigram index in `cache/notes-search.sqlite` that is rebuilt when collections change, built in the background when a reader starts, and never backed up; a plain scan applies the same rules where FTS5 is missing. My-notes search also takes several terms.
- `tools/deploy/sync.sh` refuses to overwrite a server bank that changed after the local one unless `--force`.
- The deploy unit template uses `--allow-personal --allow-practice` and `MemoryMax=384M`.
- Backups skip `personal/.bank.lock`.

## [1.25.0] - 2026-10-17

### Added
- "My answer": the person's own answer to each interview question, written in the Web reader below the reference answer, independent of it and allowed to stay empty. Stored in `personal/my-answers.json` (never `data/`) with the last 10 versions per question; a save from a stale page is refused instead of overwriting another device; answers written before a merge show on the surviving question. `POST /api/my-answer`; `web --read-only --allow-my-answers` lets a hosted reader save only these. Backups include `personal/`; `show`, the answers edition of `export` (quoted, plus `my_answers` in the details JSON) and mock-interview feedback packets read it; the agent never writes it.
- An overview page (continue reading, section cards, most-asked questions), a top navigation bar, a phone tab bar and one settings menu.
- `GET /api/notes?meta=0` omits source cards so lists stay small; the page loads each section's cards once per session.

### Changed
- The Web reader is rebuilt with React, Vite and Tailwind from `web/` and ships prebuilt in `assets/web/`; using it still needs Python only. The question and note reading area keeps its typography; personal interviews, notes (contents/list/reader side by side), public interviews, learning materials, practice rounds, human review and merge decisions are all available. Earlier `#question=`, `#note=` and `#section=` links still open.
- The server serves `/` (reader or login page) and hashed `/assets/*.js|css` only, with long-lived caching for the hashed files and a fresh per-page style nonce for dialog scroll locks; inline scripts stay disallowed.
- Source-card order now moves through a menu (first/previous/next/last) instead of dragging; the saved order key is unchanged.
- CI rebuilds the page and requires the committed bundle to match.

## [1.24.0] - 2026-10-15

### Added
- Source-local reading groups with original-article URL, ordered member IDs, content digests and editorial reasons. Preview, concurrency checks, idempotence, history and backup use the existing organization protocol.
- Contextual display titles and CLI `notes show --original` access. Legacy catalogs preserve every original record; changed, missing, protected or conflicting group members fail open instead of hiding content.
- Aggregate personal/public interview associations and browser-local progress at reading-unit level while keeping original evidence edges, question frequencies and member learning records.

### Changed
- Rename the Chinese knowledge navigation to 八股资料. Cleanup guidance distinguishes standalone Q&A, coherent articles, practice sets, career material, notices and mismatched fragments.
- Preserve weakest member verification, original Markdown/code and reader CSS. No V1/V2 migration; shared readers need 1.24+ for grouped presentation.

## [1.23.0] - 2026-10-15

### Added
- A disjoint learning-material section for roadmaps, tutorials, resources, career material and industry news, available through the Web API and CLI notes search.
- Five category cards with entry/source counts, category/source navigation, search and local learning-state filters.
- Primary navigation and direct links for the new section on desktop/phone, with original-note routing and recovery of older saved filters.

### Changed
- Interview-knowledge shelves exclude learning-material kinds while the legacy all-notes query and raw records remain available.
- Preserve public-article membership, citations, note IDs, study associations and browser-local learning marks. No bank migration or reader CSS change.

## [1.22.0] - 2026-10-15

### Added
- Explicit organization kinds for learning roadmaps, hands-on tutorials, coding exercises/solutions, resource indexes, career material, industry news and multi-question collections. Existing kinds and V1/V2 banks remain readable.
- A reusable mixed-source cleanup protocol covering original-article context, honest entry counts, provenance-preserving exclusions, association review and evidence limits.

### Changed
- Show content kinds in the left knowledge list and entry counts in type filters; keep the reader CSS/layout unchanged.
- Use one source-information entry per source for all notices instead of duplicating the same button for every excluded fragment.
- Content overlays remain source-local, digest-checked and atomic. Public-source datasets and per-user cleanup audits are not part of the Skill package.

## [1.21.0] - 2026-10-15

### Added
- Compact collapsible knowledge-source cards with persistent per-account browser preferences, reading progress, expand/collapse-all and default-order restoration.
- Pointer-based handle reordering with a constrained preview, insertion markers, edge scrolling and cancellation. Move-action menus support keyboard and phone interactions without dragging.
- Source-order preference validation and reconciliation for added/retired sources; local memory fallback when browser storage is unavailable. No source, note, learning or personal-question IDs change.

### Fixed
- Make notes UI listener installation idempotent across language/metadata initialization, preventing duplicate navigation handlers.
- Serve and verify the packaged shelf asset. Add independent reorder/state-model and JavaScript syntax checks to CI; preserve reader CSS and all stored bank data.

## [1.20.0] - 2026-10-14

### Added
- A global public-interview catalogue grouped by content topic or interview year, with combined topic/company/year filters, recent-first ordering and per-article source labels. Knowledge shelves remain source-separated.
- Content-derived browsing topics with conservative unknown handling, exposed through public API facets and filters. Source facts, article IDs, learning IDs and stored data are unchanged.

### Fixed
- Full-width vertical desktop navigation and single-line mobile entries prevent squeezed three-tab labels. Keyboard navigation follows each layout's orientation.
- Reset old source-scoped public navigation once and retain global browsing on study-link/deep-link jumps. Preserve the original reader CSS and collapse/focus layout.

## [1.19.1] - 2026-10-14

### Fixed
- Promote public interviews to a primary entry beside personal interviews and knowledge sources on desktop and mobile. Hide the redundant secondary switch; preserve source groups and the reader layout.
- Match the selected primary tab to the knowledge/public section even though they share the notes engine; reset stale filters when changing entries. Add direct section links and keyboard navigation.

## [1.19.0] - 2026-10-14

### Added
- Optional source-local question types, independent of content kind and verification, with Web facets and filters.
- Evidence-bearing public-interview → knowledge links in `notes organize`: same-source direction checks, exact excerpts, reasons, duplicate checks and atomic patches. Reads exclude stale links and flag surviving affected entries.
- Bidirectional study navigation and separate personal/public association filters and source-card counts. Public links never increase personal occurrence frequency; legacy summary fields and raw note IDs remain available.
- A reusable protocol for per-question taxonomy review, ambiguous headings, project context and conservative association decisions. No personal-bank migration or external dependencies.

### Changed
- Large personal-link candidate tasks shortlist titles and rescore bodies with a bounded cache, reducing memory use. Scores remain retrieval aids; agents must search beyond the shortlist and review actual explanations.
- Candidate computation releases the bank lock and checks source/bank revisions before publishing a task. Link writes reject stale personal-link snapshots, reconcile merged question IDs without duplicate associations, and make identical retries a no-op.
- The reader retains its layout and original text; related public questions and study evidence appear in collapsible sections.

## [1.18.0] - 2026-10-14

### Added
- A public-interview shelf inside notes, separate from knowledge and private interview occurrences. Source-owned articles project ordered existing note sections into interview accounts, company question lists or career advice.
- Quoted source facts for company, role, round, interview time and publication time. Interview years are derived only from explicit interview dates; incomplete source groups are flagged for review.
- Company/year filters, recent-interview ordering and source-preserving search. Existing private-question links are deduplicated within an article without changing frequency or original links.
- `experiences` in digest-checked `notes organize` overlays and `--section` in `notes search`; article IDs work with `notes show`. Existing collections require no V1/V2 migration.

### Changed
- Knowledge directories omit public-article fragments while original note IDs remain available. Source cards distinguish knowledge and article counts; topics expand for the selected area in the existing left navigation.
- Bookmarks to retired entries recover to the current list with a readable notice; metadata remains visible when starting directly in notes mode.
- Documented Chinese-edition cleanup, event-boundary/provenance checks and exclusions for mixed public repositories. Imported datasets remain outside the repository and Skill package; imported answers are references, not automatically fact-verified.

## [1.17.1] - 2026-10-13

### Changed
- Refined only the existing sidebar and question list: study icons, collapsible source groups, a list-local count/collapse control and initially folded directory/filter panels.
- Retained the original reader HTML, app.js, app.css and notes-ui.js, including independent panel folding, focus, typography and phone full-screen reading.
- Bundled the extra local CSS/JavaScript in the static asset allowlist; no external assets, framework, build step or bank migration. New labels support Chinese and English; desktop filters also recover their open state after a viewport resize.

## [1.17.0] - 2026-10-11

### Added
- Source overview cards in the notes reader, with content counts, language, linked interview questions and browser-local reading progress.
- Source-local knowledge areas and topics, an alternative original chapter view, explicit current-topic/current-source/all-source search, and tag, content-kind, verification and learning filters.
- Source information with author, license, upstream version/date, import date, organization history and a separate view for source/license notices.
- `notes catalog --name` and `notes organize --name --input [--preview]`: an atomic, digest-checked metadata overlay in `collections/_organization.json`. Original collection files, note IDs, bodies, frequency and interview links stay unchanged. Protected classifications require explicit user words; a verified label requires evidence URLs.
- Manual read/review/mastered learning marks kept in the current browser. They do not certify a source or sync across devices. Hosted readers stay read-only.

### Changed
- Backups and the existing collection sync include organization metadata. Existing collections work without it; no V1/V2 migration is required. A re-import that changes the source marks its organization mapping for review.
- Noninteractive test subprocesses explicitly close stdin, so tests do not wait for a human confirmation when run from an interactive terminal.

## [1.16.1] - 2026-10-10

### Added
- A link to the project on GitHub in the Web reader: an icon at the top of the sidebar, a link at the foot of the
  sidebar and in the phone menu, and one under the login card of a hosted reader.

## [1.16.0] - 2026-10-09

A 八股 notes section beside the bank's own questions. Data stays V1/V2; no migration is needed.

### Added
- `notes import|list|search|show|remove`: import a folder of Markdown study notes as a collection (one file per chapter,
  `##` headings as questions, `###` under a grouping `##`, 🔴/⭐ as key marks, long chapter openings as 导读 notes).
  Answers are kept verbatim with their source; notes never become occurrences. Re-imports keep the IDs of unchanged
  headings. Stored in `collections/<name>.json`.
- `notes link-candidates` and `notes link`: the agent judges which notes answer or cover each interview question
  (`answers` / `covers`); links live in `collections/links.jsonl`, and judged questions without links are remembered
  for `--unlinked`.
- Web reader: a 面经 / 八股 switch; collections and chapters (chips on a phone, the sidebar on wide screens); key-only,
  asked-only and most-asked views; Markdown answers with lists, tables, quotes and code; the source under every
  answer; "相关八股" under a question and "面经里这样问" under a note, jumping both ways. API: `/api/notes`, `/api/note`.
- Web reading aids, on a phone and a computer: chapter headers in the notes list that fold (全部折叠 / 全部展开, a table
  of contents on a phone) and count what was read; a peek at each answer from the list; read marks; 随机一题 (unread
  first); search words highlighted in titles; text size (Aa) and a reading progress bar in the reader; foldable
  sidebar sections; a light / dark / system theme choice; a back-to-top button. Read marks, folds, theme and text size
  stay in the browser.
- Wide screens: the navigation and the list fold away (« / », 收起列表 or L, 专注 or F for both, Esc to leave), so the
  reader can fill the window at a comfortable line length; the choice is remembered on the device.
- references/notes.md.

### Changed
- Backups and `tools/deploy/sync.sh` include `collections/`.
- README: the Web reader section rewritten (two sections, reading aids, shortcuts, and three ways to use it: locally,
  on your own server, or testing with the author); new screenshots from the demo bank, including the notes section.

## [1.15.0] - 2026-10-08

Optional reading on a phone through the user's own server. Data stays V1/V2; no migration is needed.

### Added
- `web --token-file <file> --public-origin https://<site>`: the reader still binds to loopback, takes a fixed token from a
  root-readable file (never printed to logs) and accepts the public site's Origin, for use behind an HTTPS reverse proxy
  that asks for a login and adds the token.
- `web --login-file`: a login page for the hosted reader (one account, scrypt hash, signed HttpOnly/Secure/SameSite=Strict
  session cookie for 14 days, sign-out button, lockout after repeated failures; a new password signs every device out).
- `web --banks-dir <dir>`: several people on one server, each account reading only its own bank; login files hold
  several accounts (format 2; the single-account format still loads).
- Reading-first Web design: phone list and full-screen reader with previous/next, swipe and back gesture; three columns
  on wide screens (sidebar with overview, study views, topics and tools, inline filters, reader); key points with
  their sources; optional think-first mode; placeholders that explain how to import, answer and export via the agent.
- `tools/deploy/`: a hardened systemd unit (unprivileged user, read-only filesystem except the bank, starts only once a
  login exists), nginx snippets that add the token and client address and rate-limit logins, `set-login.py` (accounts:
  add, passwd, remove, list; passwords typed on the server), `sync.sh` (a bank's data, config and manifest to one
  account) and `backup.sh` with a daily systemd timer (14 verified backups per bank).
- web.md: “Reading on your own server”.

### Changed
- The Web page loads its assets and calls its API by relative paths, so it also works under a path such as `/ibank/`;
  the brand link stays inside the reader, and a read-only notice takes precedence over the V1 notice.

## [1.14.0] - 2026-10-08

Fixes from the first real-environment evaluation: the Skill installed in Claude Code, screenshots organised end to end
by fresh Opus and Sonnet agents that read only the Skill, blind dedupe and answer suites, and the trigger suite in real
`claude -p` sessions. Data stays V1/V2; no migration is needed.

Evaluation results: dedupe retrieval recall@10 1.00; blind dedupe judgments 0 % false merges and 3.4 % missed merges
(Opus, Sonnet); blind answers 1.7 / 2 from a separate judge with no unsupported claims; triggers pass with Sonnet
(recall 1.00), while Haiku's recall (0.73–0.80) stays below the gate. See evals/README.md.

### Added
- Dedupe review sheet: every dedupe task writes `review-sheet.md`, incoming questions grouped by report topic with their
  candidates and the bank's existing questions of the same topic, so paraphrases with no shared wording are compared.
- Short refs (`n1`… incoming, `e1`… existing) accepted in decisions; `default_action: "KEEP_DISTINCT"` covers unlisted
  questions; `ingest submit --top-k`; `dedupe --decisions` (alias of `--input`).
- `--defer-review` on `ingest finalize` and `dedupe`: REVIEW items no longer block the whole stage; they stay separate
  questions and wait for the user in the Web reader (合并裁决). `dedupe --resolve` applies decisions on a committed run's
  deferred items as a new stage; undecided items stay queued.
- `page-text <url>…`: saves the readable text of cited pages under cache/pages/ and returns a file for
  `answer --page-texts`, for hosts whose web tool returns summaries (the second command that goes online); pages that
  redirected elsewhere are flagged.
- Extraction rules for phone screenshots: overlapping scrolls, questions cut across images, very tall images, the same
  interview posted twice, abbreviations as company evidence and platform evidence.
- Dedupe judgment table (generic vs implementation, definition vs countermeasure, supersets, languages, project questions,
  follow-ups vs siblings) with examples that are not in the evaluation set.
- Role track `ai-agent.application` (AI 应用开发); technologies `agent-skills`, `claude-code`, `codex`, `cursor`,
  `github-copilot`, `ragas` (catalog 1.2.0).
- Rule for “the N most frequent” when place N is tied.
- `tools/run_trigger_eval.py --max-turns`; run directories record the Skill version.

### Changed
- A merge or related target may be any active question of the bank or stage, not only a retrieved candidate; such
  targets are audited as `outside_candidates`, and unknown targets fail with the ID named. Committed questions can be
  linked or merged later with `dedupe-candidates --question`.
- `dedupe-candidates` returns the same compact shape as `ingest submit` (counts, review sheet path, a 15-item preview with
  refs and scores), not the task file; `run-show` pages the full task. Output trimming also reaches lists nested one
  level down, so a 400-question `ingest submit` no longer prints 456 KB.
- Dedupe tasks store only ID and wording for candidates (a 400-question import wrote 4.5 MB of task files).
- Candidate ranking keeps the real score for same-topic questions instead of flooring them to one value, so the top-k
  cut among them is no longer arbitrary.
- `ingest finalize --task` refuses a decisions file that names another task.
- Report topics are ordered by question count.
- SKILL.md description lists more Chinese trigger phrases and excludes self-introductions, salary negotiation and
  post-interview emails. Rarely needed detail moved out of the end-to-end reading set (export formats, answer recheck,
  merge audit), which stays under 30K characters.
- The Python version error explains how to find a newer interpreter.

### Fixed
- `tools/run_trigger_eval.py` counted API errors (for example an unresolvable model alias) as “not triggered” and aborted
  on harmless CLI warnings; it now judges each case by the session's own result events.

## [1.13.0] - 2026-10-02

Stages 3 and 4 of the improvement plan: the Skill text, evaluations, human-only actions, composite commands,
new sources, the learning loop and the Web reader. Data stays V1/V2; no migration is needed.

### Added
- Composite commands: `ingest images|media`, `ingest submit` (extract-save + stage + dedupe candidates), `ingest finalize`
  (dedupe + commit, optional `--workflow`), `answer --commit`, `--commit` on workflow/studyset/study/interview actions,
  `interview turn` and `interview review`. Calls: screenshot batch 6 → 3, interview question 6 → 2, practice rating 2 → 1.
- Human-only actions: `answer-review --status reviewed` needs an interactive terminal and a typed confirmation
  (`--human-reviewed` is ignored); the Web reader's 人工审阅 box (`POST /api/review`, actor local_web); CLI practice ratings need
  `user_quote` and are stored as `agent_relayed`; policies keep `user_quote`; interview answers record `captured_via`;
  remote transcription consent records `granted_via`.
- Merge decisions in the Web reader (`GET /api/dedupe-reviews`, `POST /api/dedupe-decision`) and `dedupe --resolve <run>`.
- Citations: `evidence_quote` checked against `answer --page-texts`; `verify-citations` link check (only online command).
- Evaluations under `evals/`: 80 trigger queries, gold for 17 screenshot templates, 121 + 24 held-out dedupe pairs,
  10 answer cases, `evals/score.py` with release gates, recorded runs and `evals/host-verification.md`;
  `tools/run_trigger_eval.py` for Claude Code. Retrieval recall runs in CI.
- `web-intake --url --text` for page bodies the host read, with paragraph provenance; Bilibili subtitle JSON;
  rolling auto-captions merged with `source_cues`.
- `export --format anki`; optional FSRS scheduler (`config.review`); `questions.problem_url`; `studyset plan` (.ics).
- `demo --bank <new dir> [--v2]`: 20 synthetic questions, 8 answers checked against the cited official pages.
- English reports and Web UI from `config.language`; Web dark mode, resumable practice rounds, `localhost` access,
  `#question=` deep links.
- CI: ruff lint (pyflakes rules).

### Changed
- SKILL.md rewritten: 6.9K characters (was 19.5K) around eight core rules and a routing table; the end-to-end reading set
  (SKILL.md plus five references) is 29.4K characters; references wrapped to 200-character lines without version history.
- Dedupe retrieval ignores question boilerplate and maps common English terms to Chinese: recall@10 0.948 → 1.00
  (held-out pairs 0.917 → 1.00). Automatic REVIEW items name their best candidate; dedupe stages record their decisions.
- `app.js` rewritten as readable, sectioned code; `app.css` reformatted with a derived dark palette.
- `tools/acceptance.py` no longer submits a self-introduction candidate (refused by policy since it was added).

### Fixed
- A SyntaxWarning in new code would have broken `--json` consumers; a test now compiles every source with warnings as errors.

## [1.12.0] - 2026-10-02

### Added
- Run format 2: snapshot stages store a change set (`changes.jsonl`) of inserted, updated and deleted records with before-images; commit replays it, undo replays it inverted, and both check the recorded fingerprint. A stage the change set cannot reproduce (reordered records, duplicate IDs) falls back to a full snapshot. `INTERVIEW_BANK_RUN_FORMAT=1` forces full snapshots; CI runs the whole suite in both formats.
- `backup create [--include-runs] / verify / restore --destination <new dir>`: hash manifest, `.sha256` sidecar, re-verified on write; restore validates before renaming into a directory that must not exist.
- `answer-recheck`: rebinds a source-backed answer to reworded question wording with recorded checks, keeping content, sources and `verified_at`.
- `search` and `research` report `answer_stale_reason` (`marked_stale`, `evidence_age`, `wording_changed`).
- JSON errors carry `error_type` and `hint`.
- Shared (reader) locks: search, show, stats, export, doctor, validate, companies, taxonomy, run-show and Web pages run side by side; writers stay exclusive (LockFileEx on Windows).

### Changed
- CLI `search` returns question cards, 20 per page with `next_offset`; `--detail` returns the previous full records.
- Queries filter the loaded JSONL in memory. init and commit no longer build `cache/bank.sqlite`; `rebuild-index` is a deprecated no-op that removes a leftover cache, and gc removes it too. doctor drops `sqlite`, `fts5_available` and `index` and reports `legacy_index_cache`.
- Commits rewrite only the data files that changed.
- Contact details inside an extracted image/media candidate become a review item (`pii_reviewed` + `pii_reason` to keep an example address); other paths still refuse, naming the kind of match with the value masked.
- `migrate apply` and the legacy `migrate restore` use the shared backup engine.

### Measured
- 1,000-question bank: `runs/` growth per 10-answer batch 1.9 MB → 17 KB; every measured command stays within 32 KB of stdout.

## [1.11.0] - 2026-10-02

### Added
- Public test suite (196 standard-library unittest cases), synthetic fixtures and release tools in `tests/` and `tools/`.
- GitHub Actions CI: Windows, macOS and Linux with Python 3.10–3.13, plus a job that installs the packaged Skill read-only and exercises CLI, media, host adapters and the Web server.
- Compact, size-bounded `--json` output (32 KB per result, `INTERVIEW_BANK_MAX_OUTPUT`). Oversized results are saved whole under `cache/outputs/`; stdout carries a `_page` block. `--pretty` restores indentation.
- `run-show --offset/--limit` pages the items of a task or intake packet.
- `gc` (dry-run unless `--apply`) compacts old run snapshots while keeping run audit records, commit receipts, the latest undo point and every intake; `doctor` reports `runs_bytes`/`data_bytes`.
- `export --answer-extras folded|inline|none`: the answer edition shows a folded 口述版 · 常见追问 · 易错点 block when those fields were written; the Web reader shows them as collapsible sections.
- `tools/measure_outputs.py` reports stdout size per command and `runs/` growth per write.
- `migrate apply` reports `answers_bound` and `answers_need_recheck`.

### Changed
- Answers require only `short_answer`, `key_points` and `sources` (plus evidence when source-backed); the other six content fields are optional.
- Commands wait up to 10 s for the bank lock (`INTERVIEW_BANK_LOCK_TIMEOUT`, 0 = fail fast) instead of failing at once; exit code 4 now means "still busy after waiting".
- V2 migration binds a legacy answer to its question when the question was not edited after the answer was written; only edited questions need a coverage recheck.
- The privacy guard also checks `stage --text`, allows RFC 2606/6761 documentation domains (example.com, *.test …) and requires an ID-like token after 微信/QQ labels.
- SKILL.md: Chinese trigger terms (面经, 八股文, 模拟面试, JD 备考), a budget checkpoint before researching more than 20 questions, a quick/full path choice and a routing table. `capabilities.md` is now a capability matrix; version history moved here.
- README: installation for Claude Code, Codex, Cursor, Trae, Qwen Code and Gemini CLI.

### Fixed
- Concurrent Web requests (and Web plus CLI) conflicted on an exclusive non-blocking lock: 7 of 8 simultaneous reads returned 409.
- Saving a Web self-rating could leave an orphan staged run that later blocked `migrate apply`.
- The practice dialog lost its default "10 题" option because of a malformed `</option>` tag.
- Reports grouped 10 of the 18 top-level domains (mobile, data, security, …) into a single 其他知识题 section.
- Random generated IDs occasionally matched the phone-number pattern (about 1 in 700), failing staging with a false privacy error.
- Citation reading dates in UTC+8 between 00:00 and 08:00 were rejected as "in the future".
- Timestamps ending in `Z` were rejected on Python 3.10; the CLI now also refuses Python older than 3.10 with a clear message.
- `web` could stall for tens of seconds on hosts with slow reverse DNS.
- `media-transcribe` failed every file when faster-whisper package metadata was unavailable.

## [1.10.0] - 2026-09-28

### Added
- Optional loopback-only local Web reader with search, multi-dimensional filters, sorting and pagination, answer and source reading, and self-rated practice (persisted in V2 banks).

## [1.9.0] - 2026-09-09

Includes the unreleased 1.8 work.

### Added
- Audio/video speech intake with optional local faster-whisper; SRT/VTT/TXT/JSON transcripts and sidecars with timestamps, paginated reading, reviewed corrections and per-file resume.
- Host capability probes separated from host declarations, transcription route planning and source-bound import of host or cloud tool results.

## [1.7.0] - 2026-09-08

Includes the unreleased 1.5 and 1.6 work.

### Added
- 1.5: explicit V2 migration with verified backups and isolated restore, field protection and never-merge rules, durable research workflows with batches, budgets, blockers and receipt-derived progress.
- 1.6: saved snapshot/dynamic study sets with AND/OR/NOT filters and JD requirement mapping with coverage and gaps.
- 1.7: self-rated review queues and one-question-at-a-time mock interviews with feedback, follow-ups and resume.

## [1.4.0] - 2026-09-06

First public release.

### Added
- M1–M5: screenshot and selected-text extraction with provenance, semantic classification with an extensible catalog and company profiles, conservative audited deduplication, filtered search, statistics and exports, and source-verified reference answers.
- Two Markdown report editions (with answers and questions only) from the same data, with a JSON sidecar.
