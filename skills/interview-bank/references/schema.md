# V1/V2 data contract

The executable validator in ../scripts/ibank_core/schema.py is authoritative. UTF-8 records use schema_version=1. Unknown schema versions fail explicitly. V1 remains supported; V2 is enabled only by explicit migrate plan/apply. No read operation silently upgrades a bank.

| File in data/ | Fields beyond id and schema_version |
| --- | --- |
| questions.jsonl | canonical, normalized, language, question_type, role_tracks, domains, technologies, difficulty, status, merged_into, created_at, updated_at |
| occurrences.jsonl | question_id, source_id, original_text, company_id, role_tracks, interview_type, round, event_date, sequence, parent_occurrence_id, extraction_confidence, classification_confidence, created_at |
| sources.jsonl | type, path, sha256, platform, source_url, source_date, imported_at, retention |
| companies.jsonl | name, aliases, industries |
| answers.jsonl | question_id, version, status, short_answer, spoken_answer, key_points, deep_dive, interviewer_intent, common_mistakes, follow_up_questions, code_example, sources, created_at, verified_at |
| relations.jsonl | from_question_id, to_question_id, type, confidence, created_at |

Companies optionally support company_type, ownership, business_models and profile_evidence since 1.1. Profile attributes require evidence; old Company records without them remain valid. These are additive V1 fields that the 1.0 runtime does not understand. No automatic rewrite or migration occurs when reading an old bank.

Unexpected canonical record fields, duplicate JSON keys, nonfinite numbers, duplicate IDs and broken references fail validation. ID prefixes: q_, occ_, src_, company_, ans_, rel_. Generated IDs are UUID-based or content-derived stable hashes depending on the operation. Do not infer behavior from the ID text.

## Invariants

- Dates preserve null/year/month/day precision; timestamps include timezone.
- Labels and bullet fields are arrays of unique strings. Empty role/domain arrays mean unclassified. Known technology aliases from older V1 banks remain valid even if the new catalog recommends another spelling; read-time lookup/statistics normalize both. New host responses use current canonical labels.
- Questions are active or merged. merged_into points directly to an active target; no self-links/chains. Every active Question has an Occurrence.
- Occurrences point to active Questions and existing Sources. Sequence is positive and unique per source. Same-source parents precede children; cross-source parents are allowed. The entire parent graph must be acyclic.
- Confidence is finite in [0,1]. Text-adapter confidence denotes direct copying of already selected text, not independent semantic review.
- Sources have unique byte SHA256 hashes. Types: text/image/web/audio/video; adapters currently cover selected text and images. retention=none requires path=null. copy image bytes are stored under bank/media.
- Company names/aliases cannot identify multiple companies. Industries are extensible strings.
- Answers have unique (question_id,version), statuses ai_draft/source_backed/reviewed/stale. missing is derived. Citations contain title/url/publisher/type/accessed_at and may include evidence_note. The answer workflow enforces evidence coverage more strictly than legacy canonical bundle shape validation.
- Relations connect different active Questions: related, prerequisite, follow_up, contrast, broader, narrower.

## Config and operations

manifest.json records schema_version/bank_version=1 and creation/update timestamps. Counts are derived.

config.json includes bank_version, source_retention, language, default_interview_type, dedupe and privacy. Optional taxonomy_extensions supports role_tracks/domains; answer_stale_days defaults to 180. Read config and taxonomy task payloads instead of hardcoding extensions. Source context explicitly provided by the host takes precedence; missing interview metadata remains unknown.

An intake run contains intake.json and optional extraction.json. A cognitive task contains task.json. A staged mutation contains run.json and six table files. Snapshot stages also contain before.json, optional config snapshots, digests, review items and audit. Commit adds commit.json/report.md. Statuses: staged, committed, superseded, abandoned.

stage --input appends a canonical bundle and does not edit existing records. Other mutation commands create complete validated snapshots bound to current data/config digests. They do not change canonical state until commit. Repeat commit returns the existing receipt. Deduplication can supersede an input extraction stage.

## Durability

Readers/writers acquire an OS lock. Files are flushed and fsynced before same-directory os.replace. A durable .transaction.json journal records multi-file commit intent; the next CLI operation replays it after interruption. Do not manually alter the journal. External readers are not coordinated and should avoid reading during commit.

SQLite includes all six tables and a canonical-data fingerprint; rebuild-index can always regenerate it. No model/provider information is embedded in the data contract. Managed output paths reject traversal and symlink escapes.

Question optional field (1.2): report_exclusion, null or a nonempty string explaining editorial exclusion from reader reports. It does not change active/merged status or delete occurrences. Old banks without this field remain valid.

## V2 personal state (1.5–1.7)

manifest.schema_version and manifest/config.bank_version are 2. The six table records remain schema_version=1; new V2 answers optionally retain question_revision, evidence, checks and version_scope. Migrated answers have null question_revision until an actual new coverage/source check is submitted. Effective staleness includes content revision mismatch, independent of metadata frequency changes.

`data/state.json` is a version=2 object containing policies, workflows, studysets, events, sessions and evidence, each an ID-keyed object. All are loaded and validated under the same lock as the six tables, included in bank/task digests, staged snapshots, before-images, undo and transaction journal. SQLite indexes the six tables; it is still reconstructible. State and private study data are not automatically published by report export.

Workflows bind original scope, occurrence IDs, question revisions and initial answer IDs. Studysets keep selection revisions and matching occurrence IDs; refresh is explicit. Practice uses append-only request-id-deduplicated events; interview responses bind actual prompts, user text and reference-answer versions. Agent tools cannot infer a user's response or self-rating.

Upgrade creates a verified ZIP/hash manifest under backups before activation; restore creates a separate bank under restored and never replaces later changes. See [maintenance](maintenance.md) for commands. The installed V1 runtime rejects a V2 manifest instead of ignoring protections or personal state.
