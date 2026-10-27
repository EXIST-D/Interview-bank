# Optional local Web reader and practice

Use this mode when the user requests a local visual question library, browsing, or browser-based practice. The default intake and two-report workflow stays unchanged.
No npm, build step, CDN or extra Python package is required to use it, and a model key only for the optional screenshot import: the page ships prebuilt in `assets/web`
(built from the repository's `web/` with React and Tailwind; only people changing the page need Node), and Python 3.10+
serves it and the existing bank engine.

## Start and stop

Resolve the installed `scripts/ibank.py` to an absolute path. Resolve the intended existing bank explicitly; never create a new bank just because lookup failed.

```text
python -B <cli> web --bank <existing-bank> --json
python -B <cli> web --bank <existing-bank> --read-only --json
python -B <cli> web --bank <existing-bank> --port 8765 --open
```

The process remains running. The first stdout JSON line contains `result.url`, `result.pid`, `result.version`, and `result.read_only`. Default port 0 chooses a free port;
an explicitly occupied port fails instead of killing another process. The launch URL includes a session token in its fragment.
Open the complete returned URL in the user's local browser; do not publish or copy it to external services.
The page removes the fragment and keeps the token in tab session storage. A restarted process needs its new launch URL.

Keep a long-lived command session or use the host's supported background process mechanism.
On Windows, if launching a background helper with Start-Process, use `-WindowStyle Hidden`, a quoted absolute CLI/bank path, `-PassThru`, and stdout/stderr logs under the permitted user workspace.
Never place logs or runtime state in the installed Skill. Use the stdout readiness line to obtain the actual port instead of guessing.
Stop through Ctrl+C in the owned command session, or stop the exact recorded and verified helper PID; do not kill unrelated Python processes.
Report whether the server is still running and how the user can stop it.

Opening a browser alone does not keep a terminated executor alive. If the host cannot maintain a process, provide the exact command for a user-owned local terminal; do not claim the page is running.

## Visible behavior

- Library navigation: all questions, due for review (including unpractised questions), weak/changed questions, and unseen questions.
- Search original/canonical text; combine domain, source role, technology, company, industry and answer-status filters. Context predicates match the same occurrence.
  Sort by frequency, update date or title; paginate the result. This is text/tag filtering, not vector search.
- Details:
  original wording, occurrence count, company names, years, tags, reference answer with real source links, effective answer status, timestamped excerpt information and recent
  self-rating/response history.
  Source paths and internal identifiers are omitted from the visible reader. The Web UI does not expose local source files or arbitrary directories over HTTP.
- Practice: select 5/10/20 questions in the current filtered order, or practise one question. Hide answers until reveal;
  accept optional written responses and an actual user self-rating. No automatic correctness score or new answer generation.
  Missing/draft/stale answers remain visibly distinguished.
- Personal notes: **笔记 / Notes** in the reader toolbar opens a right-side Markdown panel, independent of
  the original content and its answer visibility. On desktop the original remains interactive with an independent
  scrollbar; on phones it is a modal panel with a close/return-to-item control. The bottom editor is removed.
  Markdown renders in place as you write (headings, emphasis, lists, quotes, code, task lists and tables); Ctrl/⌘ + Enter saves. Opening
  or closing notes preserves the visible paragraph. Each note is bound to the open question or collection entry;
  saved-note badges, My notes cards and `panel=notes` deep links open the correct item and note together.
  Unsaved drafts are local to this browser, scoped by account, bank path and item, and survive closing, item
  switching or reloading. They are not cross-device synchronization; save explicitly to store the note on the server.
  Storage remains `personal/my-answers.json` with the last 10 versions; a stale save is refused and the draft is
  retained while loading the latest version for comparison. Existing saved notes need no migration. Notes outlive
  removed entries and stay listed as missing. The Agent reads personal notes but never writes or rewrites them.
- 我的 (`#/mine`): every own answer and note, newest first, searchable (every space-separated term must appear),
  filterable by section and exported as one Markdown file in the browser. Favourites: the star in the reader puts the
  open question or entry into one or more folders (the first star creates 我的收藏). Folders are renamed, reordered,
  deleted (the items themselves stay) and emptied item by item; 练习其中的面经题 runs a round over the folder's
  interview questions. Stored in `personal/favorites.json` (up to 200 folders, 5000 items each).
- Long text: when an original has three or more headings or bold numbered question lines, 本文目录 in the reader lists
  them, follows the scroll position and jumps; far down, a button returns to the top.
- 今日计划 on the overview: reviews due now, weak/changed and never-practised questions, each opening that list;
  开始复习 opens a practice round on the first non-empty one.
- Learning state: read marks, 待复习/已掌握 states of entries and the source order are kept in the browser and, when
  the server allows personal writes, merged into `personal/learning.json` so another device sees them (read marks
  union; per entry the newest change wins). Without personal writes they stay in the browser as before.
- Human review: below a stored answer, 人工审阅 lets the reader write what they checked and press 人工审阅通过 (or mark it 待重新核验).
  The server stages and commits under one lock and audits `actor: local_web`; it refuses if the answer changed since the page loaded. Read-only mode hides it. Works in V1 and V2.
- V2 saves each submitted response and self-rating through the existing stage/commit machinery. Due dates use the existing review scheduler.
  Network retries carry the same request ID, so a successful but unacknowledged submission is not duplicated. Failed saves keep the response in the current page.
- V1 and `--read-only` allow temporary practice without writing practice events. Explain this before the round; do not silently migrate.
  Saving practice requires an explicitly authorized verified V2 migration.
- Saved events survive server/browser restarts and are shared with CLI review.
  An unfinished Web round is kept in the browser tab's session storage (question IDs and position only, never the written response): reloading the tab offers to resume it;
  closing the tab ends it. The Agent interview workflow remains the durable guided session.
- Merge decisions: when a staged dedupe run has review items, a banner above the personal-interview list opens 合并裁决.
  The person sees both questions and the agent's reason, chooses 是同一题 / 相关但不同 / 不同的题 with a required note, and the choice is saved next to the stage
  (`runs/<run>/human-decisions.json`, actor local_web).
  Nothing canonical changes until the agent runs `dedupe --resolve <run>`, which re-stages the run with those decisions, and commits it.
- Notes: once a collection is imported, personal interviews, knowledge, public interviews and learning materials have primary entries.
  Source cards lead to a source-local knowledge
  directory or its original chapters. Search explicitly scopes to the current topic, current source or all sources;
  tag, content kind, verification and browser-local learning filters supplement key-only and most-asked views.
  Notes show the collection's original answer with its source, and link both ways to interview questions.
  Note search (Web and `notes search`) needs every space-separated term, ranks entries holding all terms in the
  title first, then by relevance (BM25, titles weighted). It uses an SQLite FTS5 trigram index in
  `cache/notes-search.sqlite`, rebuilt when a collection changes and never backed up or synced; where SQLite lacks
  FTS5 the same rules run as a plain scan. A hosted reader builds the index in the background at start.
  Source information separates notices from learning content. Directory maintenance stays with the Agent CLI.
  See [notes](notes.md).
- Learning materials: use `#section=learning` to open the category home. Five cards separate roadmaps, tutorials,
  resource indexes, career/role information and industry news, with entry/source counts and an all-materials entry.
  Browse by category, choose a source, search text and filter local learning state. Source text and citations remain
  in the existing reader. These five kinds do not appear in interview-knowledge lists, source counts or searches.
  Public-interview article membership still takes precedence. Old note links infer their current section; saved
  knowledge filters for these kinds recover to learning. Counts are entries/sections, not unique full documents.
- Layout: a top bar switches 概览 (overview: continue reading, section cards, most-asked questions) and the four
  sections and 我的; settings (appearance, think first, text size, agent actions, refresh, sign out) sit in its menu.
  Phones use a bottom tab bar (overview, interviews, knowledge, more: public, learning, 我的). Hash routes
  (`#/bank?open=q_…`, `#/bank?view=due`, `#/knowledge/<source>?open=note_…`, `#/public`, `#/learning/<kind>`,
  `#/mine?tab=favorites`, `#/bank?open=q_…&panel=notes`) are shareable; the earlier `#question=`,
  `#note=` and `#section=` links still open the same place.
- Knowledge shelf: source cards show title, language, content count, main areas and local reading progress; ⋯ opens
  source information and first/previous/next/last moves. Order is browser-local per account/bank (the same
  `ibank-source-shelf:` key as before) and can be reset. Inside a source: contents (knowledge areas/topics or the
  original chapters), the list and the reader side by side from 1100px; narrower screens open contents as a sheet.
  The page loads each section's source cards once per session and lists with `meta=0`.
- Reading aids: each row can unfold a peek at its answer; opened questions count as read (this browser only), and
  topic or chapter groups fold and show how many were read. 随机一题 (top bar) opens an unread interview question
  first. In the reader, Aa changes the text size and a thin bar shows how far you have read.
- Wide screens (from 900px): the list and the reader sit side by side; L folds the list, F (专注) also hides the top
  bar so the reader fills the window; Esc leaves focus. Phones open the reader full screen; the system back gesture closes it.
- Language and theme: the page follows `config.language` (Chinese or English); the theme follows the operating
  system unless the reader picks light or dark (外观).
- Page security: only the bundled scripts and styles are served (`/`, `/assets/<hashed>.js|css`); each page response
  carries a fresh style nonce for the dialogs' scroll lock, and no inline script is allowed.

The page fetches bank data on navigation, refresh and after practice; it does not automatically poll, research answers or watch directories.
The overview distinguishes stored answers (including draft/stale) from currently valid source-backed/reviewed coverage in its tooltip.
Old migrated answers can be stale until coverage is rechecked. Frequencies count matching collected occurrences.
Domain facet counts may overlap because a question can have multiple labels.

`--read-only` disables every write. On a hosted reader, `--allow-personal` (formerly `--allow-my-answers`, still
accepted) then allows only the person's own layer under `personal/`: answers and notes, favourites and learning
state. `--allow-practice` separately allows saving practice ratings (V2 banks only), which write to `data/` through
the normal stage/commit path; human review and merge decisions stay disabled. Opening a bank still uses the normal lock, recoverable-transaction handling and rebuildable cache;
it is not a promise of zero filesystem activity. Do not open an unrelated or unauthorized bank.

Appending `&question=<question-id>` to the launch URL opens that question directly (useful when pointing the user at one answer).

The server accepts both `http://127.0.0.1:<port>` and `http://localhost:<port>`; any other Host or Origin gets 403 (DNS-rebinding protection).

## Service boundary and validation

Bind exclusively to `127.0.0.1`; no LAN/public binding option.
The custom handler serves only explicitly allowlisted bundled assets and a small authenticated API,
with Host/Origin checks, per-process token, bounded JSON bodies, no CORS grants and a restrictive content policy.
Question/answer HTML is rendered as text, source links accept only HTTP(S), and no remote scripts/fonts are used. The only upload
endpoint belongs to the opt-in screenshot import below; it accepts PNG, JPEG, WebP or GIF bytes and nothing else.
It is a personal helper, not a multi-user service. Never tunnel or expose the port itself; reading on a phone goes
through your own server as below, only when the user asks for it.

## Reading on your own server (optional)

For a person who wants to read and practise on a phone, the reader can sit behind their own HTTPS reverse proxy,
read-only, with the bank copied there. Templates are in the repository's `tools/deploy/`.

- The server still binds to loopback. `web --read-only --token-file <file> --public-origin https://<site>` uses a
  fixed token from a root-readable file (never printed) and accepts that site's Origin. Assets and API calls are
  relative, so the reader works under a path such as `/ibank/`.
- `--login-file` shows the reader's own login page (one account, scrypt hash written by the person with
  `set-login.py` on the server). A login sets a signed HttpOnly, Secure, SameSite=Strict cookie for 14 days; a new
  password signs every device out; five failures per client (thirty overall) lock login for 15 minutes, and the
  proxy also rate-limits the login endpoint. The proxy adds `X-Interview-Token` and the client address; the
  systemd unit runs as an unprivileged user with a read-only filesystem except the bank, and starts only once a
  login exists.
- Several people: `--banks-dir <dir>` gives each account its own bank, `<dir>/<bank name of the account>`; an
  account never sees another's questions. Accounts are managed on the server with `set-login.py add|passwd|remove|list`.
- `tools/deploy/sync.sh [--force] <bank> <user@server> <bank name>` copies only `data/`, `collections/`,
  `config.json` and `manifest.json` to that account: no images, runs, caches or exports. It refuses when the
  server's copy changed after the local one (practice saved there, or the agent worked on the server) unless
  `--force`. With `--allow-practice` the server's `data/` becomes the original: bring it back first (latest backup,
  `backup restore` into a new directory) before the agent works locally and syncs again.
- What the person writes on the hosted reader lives in that bank's `personal/`; `sync.sh` never sends or deletes it.
  `backup.sh` with its systemd timer keeps 14 daily verified backups on the server, `personal/` included.
  `tools/deploy/pull-backups.sh <user@server> <local folder> [bank name]` copies the newest backups (NEWEST, default 3)
  to your computer, checks each against its `.sha256`, skips ones already there and keeps the newest KEEP (default 30).
  `nginx-gzip.conf` optionally compresses the page's scripts, styles and JSON.
- Personal data leaves the machine: deploy only when the user asks, to a server they control, with HTTPS and login.

Protocol endpoints for diagnostics: GET `/api/library`, `/api/question?id=...`, `/api/practice`, `/api/my-notes`,
`/api/favorites`, `/api/learning`, `/api/intake`; POST `/api/practice`, `/api/my-answer`, `/api/favorites`, `/api/learning`. All require `X-Interview-Token` from the launch URL;
keep it out of public logs. Use the browser for normal practice instead of submitting synthetic user ratings into a real bank.
Unknown IDs, invalid requests, concurrent modification and locked banks report errors rather than overwrite data.

Validate changes in a separate fixture or a permitted copy.
Verify filtering, answer reveal, saved self-ratings, refresh/restart persistence, empty/V1/read-only banks, mobile layout, and rejected unauthorized writes.
A browser demo against a copy must be labelled as a copy; do not imply those practice records are the user's real learning history.

### Screenshot import with a model (1.31+)

Opt-in. `web --ai-config <file>` adds 截图导入 (`#/import`): the signed-in person uploads screenshots and a configured
model plays the host's part in the usual pipeline, through the same CLI code: `ingest images` (copy retention,
known bytes are not read again), extraction, the person's check, `ingest submit`, dedupe decisions, commit,
`research` task, `ai_draft` answers, commit. A read-only hosted reader also needs `--allow-intake`.

- The configuration names a `vision` model (reads images) and optionally a `text` model (dedupe and answers), each
  `openai` (any OpenAI-compatible `/chat/completions`) or `anthropic`, plus `limits` (screenshots per import and
  per day, answers per import, answers per request). Keys come from `api_key_file` (not world-readable) or
  `api_key_env` (default `INTERVIEW_BANK_AI_KEY`), never the command line; plain http only for a model on loopback.
  `extra_body` adds provider switches to each request (DeepSeek and Zhipu default to thinking: turn it off for reading);
  `image_encoding: "base64"` sends bare base64 where a provider rejects data URLs. `ai-check --ai-config <file>`
  sends one tiny request per model. Example (DeepSeek `deepseek-flash` reads, `deepseek-v4-pro` answers):
  `tools/deploy/ai.example.json`.
- Model instructions are cut at run time from this Skill's references (extraction, report policy, dedupe,
  answer policy), so the Web and an agent follow one protocol. Model output is reduced to the extraction schema:
  unknown labels are dropped, self-introductions removed, confidence and follow-up links checked.
- The person sees every screenshot's questions before anything is saved: untick, edit wording, set company, round
  and date. Unsure readings (confidence < 0.80) and possible contact details are highlighted; keeping them is the
  person's review. Unreadable or failed screenshots are skipped (`skip`, reviewed) when confirmed, or read again.
- Exact matches merge; the model judges the rest from the candidates and the review sheet. Merges below 0.90 are
  asked on the page (same / related / different) before the commit. If the bank changed meanwhile (practice on
  another device), the same confirmation is staged again; question IDs do not change.
  A merge may reword its target to keep the new sub-points (dedupe `canonical`); rewording a question that has a
  researched answer is asked first, because that answer then needs a recheck. AI drafts are written again.
- New questions without an answer get `ai_draft` answers with no sources: the model cannot browse and may not
  cite. The reader labels them AI 草稿. Research them later as usual (`research --answer-status ai_draft`).
- Long phone screenshots are cut in the browser into up to eight overlapping parts that are read together; the
  original bytes stay the source. Jobs live in `cache/web-intake/` (not backed up); one import at a time per bank.
  A restart leaves interrupted jobs to confirm again or to retry their answers. Cancel abandons the stage and the
  screenshot copies. Endpoints: GET `/api/intake`, `/api/intake/job`; POST `/api/intake/jobs`, `upload`, `start`,
  `confirm`, `merge`, `answers`, `retry`, `cancel`. Behind nginx the upload path needs a larger body limit
  (`tools/deploy/nginx-location.conf`).
- Screenshots leave the server for the model provider the person configured. Enable it only when they ask.

### Hosted public reading (1.30+)

Keep the existing HTTPS proxy, token file, login file and account banks. Add
`--public-bank /absolute/path/to/the/explicitly-published-bank` to `web`. Only the collections in this selected
bank are published. Review them for private material before enabling; never infer publication from a folder name
or publish another person's bank. Personal question tables, reference answers attached to them and `personal/`
remain protected. With no `--public-bank`, the original local/private-hosted behaviour stays unchanged.

Guests receive GET-only `/api/library` (empty personal summary), `/api/notes` and `/api/note`. Collection views
omit personal interview links, frequency counts, personal note flags/content and organization audit history;
non-public source origins are hidden. Public-to-public study links and citations remain readable. All other
account endpoints and mutations require login, including guessed interview IDs. Host/origin and proxy-token
checks still apply. The reverse proxy must overwrite, never trust, the incoming `X-Interview-Token` header.
The allowlist follows the [OWASP authorization guidance](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)
to deny access by default and check each request.

The main URL opens public reading; `?login=1` opens sign-in. The browser retains its hash route across sign-in
and back-to-public links without accepting third-party return URLs. Personal interviews and My Space show
a login gate; notes/favourites/learning controls offer sign-in. Guest local read marks are separate from the
account's existing browser marks and are never queued for server synchronization. Signing in restores normal
per-account permissions; this release does not add registration or grant access to somebody else's bank.

### Live Markdown notes (1.29+)

Notes use a single editing surface. The active line reveals Markdown syntax; other lines render in place.
Clicking a rendered table reveals its source for editing. Formatting tools and Ctrl/Command+B, I, E are
available; undo/redo uses the editor history. HTML stays literal and images are not fetched automatically.
Stored text is the Markdown source, including syntax the preview does not recognize. No rich-text conversion
or personal-data migration is performed. Ctrl/Command+Enter or Save still explicitly saves to the server;
live rendering is local and does not mean autosave. The account/item-scoped draft and stale-save protections
continue to apply. CodeMirror is prebuilt and lazily loaded; the server requires no Node installation.

Bundled editor library notices: [web-editor-licenses.md](web-editor-licenses.md).
