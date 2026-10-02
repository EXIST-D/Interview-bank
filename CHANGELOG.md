# Changelog

All notable changes to the Interview Bank Skill. Versions follow [Semantic Versioning](https://semver.org/); the bank data format is versioned separately (V1/V2) and only changes through an explicit `migrate`.

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
