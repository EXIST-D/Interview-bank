# Optional local Web reader and practice

Use this mode when the user requests a local visual question library, browsing, or browser-based practice. The default intake and two-report workflow stays unchanged.
No npm, build step, CDN, model key or extra Python package is required. HTML/CSS/JS ship in `assets/web`; Python 3.10+ serves the UI and the existing bank engine.

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
- Human review: below a stored answer, 人工审阅 lets the reader write what they checked and press 人工审阅通过 (or mark it 待重新核验).
  The server stages and commits under one lock and audits `actor: local_web`; it refuses if the answer changed since the page loaded. Read-only mode hides it. Works in V1 and V2.
- V2 saves each submitted response and self-rating through the existing stage/commit machinery. Due dates use the existing review scheduler.
  Network retries carry the same request ID, so a successful but unacknowledged submission is not duplicated. Failed saves keep the response in the current page.
- V1 and `--read-only` allow temporary practice without writing practice events. Explain this before the round; do not silently migrate.
  Saving practice requires an explicitly authorized verified V2 migration.
- Saved events survive server/browser restarts and are shared with CLI review.
  An unfinished Web round is kept in the browser tab's session storage (question IDs and position only, never the written response): reloading the tab offers to resume it;
  closing the tab ends it. The Agent interview workflow remains the durable guided session.
- Merge decisions: when a staged dedupe run has review items, the header shows 合并裁决.
  The person sees both questions and the agent's reason, chooses 是同一题 / 相关但不同 / 不同的题 with a required note, and the choice is saved next to the stage
  (`runs/<run>/human-decisions.json`, actor local_web).
  Nothing canonical changes until the agent runs `dedupe --resolve <run>`, which re-stages the run with those decisions, and commits it.
- 八股 notes: once a collection is imported, a 面经 / 八股 switch appears. Notes read in chapter order (key-only, asked-only,
  most-asked views), show the collection's answer with its source, and link both ways to interview questions.
  See [notes](notes.md).
- Reading aids: each row can unfold a peek at its answer; opened questions count as read (this browser only), and
  chapter headers in the notes list fold and show how many were read (全部折叠 turns the list into a table of contents).
  随机一题 opens a random question of the current list, unread ones first. In the reader, Aa changes the text size
  and a thin bar shows how far you have read. Sidebar sections fold; the choices are remembered on the device.
- Wide screens: « folds the navigation (its section switch, chips and menu move above the list; » brings it back),
  收起列表 (L) folds the list while a question is open, and 专注 (F) folds both so the reader fills the window;
  Esc leaves focus. Phones keep the list and the full-screen reader.
- Language and theme: the page follows `config.language` (Chinese or English); the theme follows the operating
  system unless the reader picks light or dark (外观).

The page fetches bank data on navigation, refresh and after practice; it does not automatically poll, research answers or watch directories.
The overview distinguishes stored answers (including draft/stale) from currently valid source-backed/reviewed coverage in its tooltip.
Old migrated answers can be stale until coverage is rechecked. Frequencies count matching collected occurrences.
Domain facet counts may overlap because a question can have multiple labels.

`--read-only` disables practice writes. Opening a bank still uses the normal lock, recoverable-transaction handling and rebuildable cache;
it is not a promise of zero filesystem activity. Do not open an unrelated or unauthorized bank.

Appending `&question=<question-id>` to the launch URL opens that question directly (useful when pointing the user at one answer).

The server accepts both `http://127.0.0.1:<port>` and `http://localhost:<port>`; any other Host or Origin gets 403 (DNS-rebinding protection).

## Service boundary and validation

Bind exclusively to `127.0.0.1`; no LAN/public binding option.
The custom handler serves only three bundled assets and a small authenticated API, with Host/Origin checks, per-process token, bounded JSON bodies, no CORS grants and a restrictive content policy.
Question/answer HTML is rendered as text, source links accept only HTTP(S), and no remote scripts/fonts or file-upload endpoints are used.
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
- The agent keeps working on the local bank, which stays the original. `tools/deploy/sync.sh <bank> <user@server>
  <bank name>` copies only `data/`, `config.json` and `manifest.json` to that account: no images, runs, caches or
  exports. Practice ratings are not saved there. `backup.sh` with its systemd timer keeps 14 daily verified backups.
- Personal data leaves the machine: deploy only when the user asks, to a server they control, with HTTPS and login.

Protocol endpoints for diagnostics: GET `/api/library`, `/api/question?id=...`, `/api/practice`; POST `/api/practice`. All require `X-Interview-Token` from the launch URL;
keep it out of public logs. Use the browser for normal practice instead of submitting synthetic user ratings into a real bank.
Unknown IDs, invalid requests, concurrent modification and locked banks report errors rather than overwrite data.

Validate changes in a separate fixture or a permitted copy.
Verify filtering, answer reveal, saved self-ratings, refresh/restart persistence, empty/V1/read-only banks, mobile layout, and rejected unauthorized writes.
A browser demo against a copy must be labelled as a copy; do not imply those practice records are the user's real learning history.
