# Changelog

All notable changes to the Interview Bank Skill. Versions follow [Semantic Versioning](https://semver.org/); the bank data format is versioned separately (V1/V2) and only changes through an explicit `migrate`.

## [1.15.0] - 2026-10-08

Optional reading on a phone through the user's own server. Data stays V1/V2; no migration is needed.

### Added
- `web --token-file <file> --public-origin https://<site>`: the reader still binds to loopback, takes a fixed token from a
  root-readable file (never printed to logs) and accepts the public site's Origin, for use behind an HTTPS reverse proxy
  that asks for a login and adds the token.
- `tools/deploy/`: a hardened systemd unit (unprivileged user, read-only filesystem except the bank), an nginx location
  with `auth_basic`, `set-password.sh` (the person types the password on the server) and `sync.sh`, which copies only a
  bank's data, config and manifest to the server.
- web.md: “Reading on your own server”.

### Changed
- The Web page loads its assets and calls its API by relative paths, so it also works under a path such as `/ibank/`.

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
