# Semantic classification and curation

The host classifies by meaning and source context. Scripts enforce schemas and vocabularies; there is no fake keyword-only semantic classifier. Read [taxonomy.md](taxonomy.md) and task taxonomy/extensions. Use taxonomy CLI search for Chinese labels, aliases and deeper categories. Roles/domains/technologies supplied through classify, extraction and curate are normalized; a justified leaf is enough because parent filters include it.

## Classification task response

Run classify with selected --question IDs or all active questions. Use the returned task ID and occurrence IDs. Each task item must appear once; skip=true plus reason is allowed when there is nothing to change.

```json
{
  "schema_version": 1,
  "task_id": "run_FROM_TASK",
  "items": [{
    "question_id": "q_FROM_TASK",
    "confidence": 0.95,
    "reason": "题目考查缓存实现，原图明确后端实习一面",
    "question": {
      "role_tracks": ["backend"],
      "domains": ["backend.cache"],
      "technologies": ["redis"],
      "difficulty": "medium"
    },
    "occurrences": [{
      "id": "occ_FROM_TASK",
      "set": {"company": "字节跳动", "role_tracks": ["backend"], "interview_type": "intern", "round": "technical-1", "event_date": "2026-08"}
    }]
  }]
}
```

Run classify --input <response>, then commit returned stage. Confidence below 0.80 requires review; reviewed=true only represents actual reinspection. Question labels describe the concept; occurrence labels describe where it appeared. A company alias is resolved to one company entity; ambiguous aliases fail. A company object may include name, aliases, industries and optional evidenced profile fields; see [company classification](company-classification.md).

## Corrections

curate accepts the following response. Original source wording and identities are immutable; corrections change canonical presentation or metadata, not source history.

```json
{
  "schema_version": 1,
  "changes": [{
    "table": "questions",
    "id": "q_EXISTING",
    "set": {"canonical": "Redis 慢命令有哪些影响？", "difficulty": "medium"},
    "reason": "规范标准题表述，保留来源原文"
  }]
}
```

Editable fields:
- questions: canonical, language, question_type, role_tracks, domains, technologies, difficulty, report_exclusion.
- occurrences: company_id, role_tracks, interview_type, round, event_date, classification_confidence.
- companies: name, aliases, industries, company_type, ownership, business_models, profile_evidence. Profile attribute corrections require fresh profile_evidence.
- sources: platform, source_url, source_date.

All changes record before/after and reason. Full-bank validation prevents broken aliases, invalid taxonomy and dangling references. Commit explicitly applies the stage.

## Configuration

config displays current configuration. config --input reads a merge patch, stages it, and commit applies it transactionally. Allowed settings include source_retention, language, default_interview_type, dedupe, privacy, taxonomy_extensions, answer_stale_days.

```json
{
  "taxonomy_extensions": {"role_tracks": ["data-engineering"], "domains": ["data.pipeline"]},
  "answer_stale_days": 120
}
```

Use configured extended labels only after committing the configuration. Taxonomy extensions are lists of strings; do not silently edit taxonomy.json. Changing config invalidates already issued cognitive tasks.

For a legacy personal-only question, curate questions.report_exclusion to a nonempty reason, then commit. The question, occurrences and IDs remain in the bank for audit but are omitted from reader reports. Set null to remove an editorial exclusion (the automatic self-introduction guard still applies). Never delete provenance to clean presentation.
