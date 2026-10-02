# Capabilities and requirements

Who does what. Version history lives in the repository CHANGELOG, not here.

## Division of work

| Capability | Host agent | Python CLI |
|---|---|---|
| See screenshots (M1) | Required: actual image viewing | Hashes, deduplicates and stores sources; never reads pixels |
| Understand meaning (M2/M3, JD mapping, feedback) | Required: reasoning | Validates labels, decisions and confidence gates; no semantic inference |
| Research answers (M5) | Required: actual search and page reading | Validates citations and key-point evidence; never browses |
| Transcribe audio/video | Optional host tool, or local faster-whisper | `media-transcribe` runs the optional local model; supplied SRT/VTT/TXT/JSON need nothing |
| Store, query, export, recover | — | Transactions, audit, undo, search, statistics, reports, `gc` |
| Local Web reader and practice | User's browser | Loopback-only server; self-ratings are saved only in V2 banks |

When the host lacks a capability, report the specific limitation and use selected text, a supplied transcript or an explicitly labelled draft where appropriate. See [portability](portability.md) to check a new host.

## Runtime

- Python 3.10+ standard library; the CLI refuses older interpreters. No model SDK, embeddings, API key, database server or OCR installation.
- A writable bank outside the installed skill. SQLite under cache/ is disposable and rebuilt from JSONL.
- Optional: `faster-whisper==1.2.1` in a workspace virtual environment for raw audio/video.

## Supported today

- Intake: images (files, directories, recursive), selected text lines, local audio/video speech, SRT/VTT/TXT/JSON transcripts and sidecars, host transcription results. Byte-identical sources never add frequency.
- Organisation: hierarchical roles/domains/industries with Chinese labels and aliases, evidenced company profiles, conservative merges with audited canonical rewrites, reversible report exclusions.
- Answers: source-backed versions with per-key-point evidence, age- and revision-based staleness, optional practice depth (spoken answer, follow-ups, pitfalls).
- Output: two Markdown editions with a JSON sidecar, JSON/JSONL/CSV/viewer exports, compact size-bounded `--json` output with paging.
- Personal state (V2): verified backup migration, field protection and never-merge rules, durable research workflows, saved topics and JD mappings, self-rated review queues, one-question-at-a-time mock interviews.
- Housekeeping: doctor, validate, undo of the latest snapshot change, gc compaction of old run snapshots.

## Not implemented

Video frame OCR, automatic speaker diarization, mid-file ASR resume, social-platform scraping (the web Source type only records provenance), Web editing and merge review, background reminders, and splitting arbitrary historical merges.
