# Capabilities and requirements

Version 1.4.0 covers M1 image intake/extraction workflow, M2 semantic classification, M3 conservative deduplication, M4 query/analysis/export and M5 evidence-led answers. The expanded taxonomy adds Chinese/alias lookup, hierarchical roles/domains/industries, evidenced employer profiles, company discovery and profile-aware filtering/export. See [taxonomy](taxonomy.md).

The host needs image viewing for M1, reasoning for M2/M3, and actual browsing for researched M5 answers. The Python CLI alone does not see pixels, understand semantics or fetch websites. It validates host responses and persists data with recoverable transactions. When a host lacks a capability, report the specific limitation and use selected text or an explicitly labeled draft if appropriate.

Runtime: Python 3.10+ standard library; writable bank separate from the installed skill. No model SDK, embeddings, API key, database server or OCR installation is required. SQLite is disposable and rebuilt from JSONL; keyword search has a fallback when FTS5 is unavailable.

M1 supports individual files, directories and recursive intake, SHA256 duplicate suppression, three retention policies, partial response save/resume, explicit empty/unreadable/skip dispositions and follow-up relationships. Structured canonical bundles and selected plain text remain supported.

M2 supports host labels with controlled vocabulary/extensions and audited metadata correction. M3 preserves historical occurrences and merged Question records. M4 exports files or viewer JSON data; there is no separate interactive viewer application. M5 retains structured answers, source evidence and versions, with derived age-based staleness.

Audio/video transcription, automatic social-platform scraping, spaced repetition, mock interview and Web management UI are outside M1–M5. Source schema reserves audio/video/web types for structured provenance; this does not mean those ingestion adapters exist.

Version 1.2 adds reusable-question selection, reversible report exclusions, audited canonical rewrites during semantic merges, and a concise default Markdown report with a complete JSON sidecar. Reports hide internal IDs, source/round details and personal-only prompts; dated metadata shows years only.

Version 1.3 adds a heading outline, per-domain totals and frequency-based numbering, mandatory reference-answer slots, and full-scope research/verification guidance. Draft or stale answers are retained in structured history and do not appear as verified reader answers.

Version 1.4 makes verified reference-answer research the default in an end-to-end organization task, followed by two Markdown editions from shared committed data. Explicit question-only/export-only requests retain their scope. Compact research packets and reusable source/answer evidence reduce repeated context; the CLI still does not perform model inference or browsing.
