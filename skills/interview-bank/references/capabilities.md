# Capabilities and requirements

Who does what. Version history lives in the repository CHANGELOG, not here.

## Division of work

| Capability | Host agent | Python CLI |
|---|---|---|
| See screenshots (M1) | Required: actual image viewing | Hashes, deduplicates and stores sources; never reads pixels |
| Understand meaning (M2/M3, JD mapping, feedback) | Required: reasoning | Validates labels, decisions and confidence gates; no semantic inference |
| Research answers (M5) | Required: actual search and page reading | Validates citations, key-point evidence and quotes against supplied page text; never browses |
| Check cited links | — | `verify-citations`, only on request: the one CLI command that makes network requests |
| Transcribe audio/video | Optional host tool, or local faster-whisper | `media-transcribe` runs the optional local model; supplied SRT/VTT/TXT/JSON need nothing |
| Store, query, export, recover | — | Transactions, change-set runs, audit, undo, search, statistics, reports, `gc`, `backup` |
| Local Web reader and practice | User's browser | Loopback-only server; self-ratings saved only in V2 banks |
| Human decisions (review, merges, ratings) | Relays the user's words only | Web buttons and an interactive-terminal confirmation; agents cannot mark answers reviewed |

When the host lacks a capability, report the specific limitation and use selected text, a supplied transcript or an explicitly labelled draft where appropriate.
See [portability](portability.md) to check a new host.

## Runtime

- Python 3.10+ standard library; the CLI refuses older interpreters. No model SDK, embeddings, API key, database server or OCR installation.
- A writable bank outside the installed skill. Queries read the JSONL tables directly; cache/ only holds spilled outputs.
- Optional: `faster-whisper==1.2.1` in a workspace virtual environment for raw audio/video.

## Supported today

- Try it: `demo --bank <new dir> [--v2]` builds a sample bank of 20 synthetic questions, 8 with answers checked against the cited
  official pages, the rest pending.
- Intake: images (files, directories, recursive), selected text lines, web page bodies the host read (`web-intake`), local audio/video speech,
  SRT/VTT/TXT/JSON transcripts (including Bilibili JSON and rolling auto-captions) and sidecars, host transcription results.
  Byte-identical sources never add frequency. Composite `ingest images|media|submit|finalize` commands cover the usual sequence.
- Organisation: hierarchical roles/domains/industries with Chinese labels and aliases, evidenced company profiles, conservative merges with
  audited canonical rewrites, user decisions on uncertain merges in the Web reader, reversible report exclusions, problem links.
- Answers: source-backed versions with per-key-point evidence and optional verified quotes, age- and revision-based staleness with
  `answer-recheck`, optional practice depth (spoken answer, follow-ups, pitfalls), optional link checks.
- Output: two Markdown editions (Chinese or English) with a JSON sidecar, JSON/JSONL/CSV/viewer/Anki exports, compact size-bounded
  `--json` output with question cards and paging, `error_type` and `hint` on errors.
- Personal state (V2): verified backup migration, field protection and never-merge rules, durable research workflows, saved topics and JD
  mappings with daily .ics plans, review queues (doubling schedule or FSRS), one-question-at-a-time mock interviews.
- Housekeeping: doctor, validate, undo of the latest snapshot change, `gc`, `backup create|verify|restore`, shared read locks.

## Not implemented

Video frame OCR, automatic speaker diarization, mid-file ASR resume, platform scraping (the CLI never fetches pages; `web-intake` takes
text the host read), editing questions in the Web reader, background reminders, and splitting arbitrary historical merges.
