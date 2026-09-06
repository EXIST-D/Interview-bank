# Screenshot extraction protocol

Run images first, then actually view every unique item's view_path. The script checks file size/hash and supported suffix; the host must verify the image decodes and is readable. Maximum input size is 50 MiB per image. Intake copies or references source bytes before semantic work.

## Response

A complete response accounts for exactly every intake source. source_id comes from intake; candidate id is a unique stable label within this batch.

```json
{
  "schema_version": 1,
  "sources": [{
    "source_id": "src_FROM_INTAKE",
    "status": "extracted",
    "metadata": {
      "platform": "小红书",
      "company": {"name": "字节跳动", "aliases": ["ByteDance"], "industries": ["互联网"]},
      "role_tracks": ["backend"],
      "interview_type": "intern",
      "round": "technical-1",
      "event_date": "2026-08"
    },
    "questions": [
      {
        "id": "image1-q1",
        "original_text": "Redis 为什么快？",
        "canonical_suggestion": "Redis 为什么快？",
        "sequence": 1,
        "question_type": "concept",
        "domains": ["backend.cache"],
        "technologies": ["redis"],
        "difficulty": "unknown",
        "confidence": {"is_question": 0.99, "classification": 0.95}
      },
      {
        "id": "image1-q2",
        "parent_id": "image1-q1",
        "original_text": "那执行慢命令会有什么影响？",
        "canonical_suggestion": "Redis 执行慢命令会有什么影响？",
        "sequence": 2,
        "question_type": "concept",
        "domains": ["backend.cache"],
        "technologies": ["redis"],
        "confidence": {"is_question": 0.99, "classification": 0.95}
      }
    ]
  }]
}
```

Metadata may include platform, source_url, source_date, company, role_tracks, interview_type, round, event_date. Question-level metadata overrides source-level context. Company/industry labels need evidence; do not infer them from filenames alone. Optional confidence.company/round/event_date are validated and participate in low-confidence review.

Required candidate fields: id, original_text, sequence, confidence.is_question, confidence.classification. Defaults: canonical_suggestion=original_text, question_type=concept, empty labels, unknown difficulty/round/type, null date/company. Use taxonomy values exactly. Language defaults to bank config.language; explicitly label en or mixed-language content when appropriate.

Each source status:
- extracted: nonempty questions.
- no_questions: empty questions plus reason, e.g. only daily-life text or an answer without a recoverable question.
- unreadable: empty questions plus reason; blocks commit.
- skip: empty questions, reason and reviewed=true; records a conscious exclusion. Never use this to silently hide extraction failure.

For candidate confidence below 0.80, staging produces review items. Reinspect the image, correct the response, and restage; reviewed=true is allowed only after actual review, never as a routine bypass. Keep unknown labels when the image lacks evidence.

## Segmentation and continuity

Preserve verbatim wording in original_text, including multiline code. canonical_suggestion may resolve a pronoun using visible context, but cannot add a new question. Keep question-plus-follow-ups as separate candidates with parent_id referencing an earlier candidate, including across images. Sequence is positive and unique per source. Multi-company sections require per-question context overrides. Ignore comments unless the user's selected material clearly makes them part of the interview record.

## Save and resume

extract-save --run <intake> --input <partial.json> merges by source_id into runs/<intake>/extraction.json and returns remaining source IDs. It may replace a corrected source response. Use the same batch-stable candidate IDs. stage --from-intake <intake> performs full validation; incomplete source coverage fails. Partial saves do not mutate canonical data.

Images are rehashed before staging and before commit. If bytes change, create a new intake. Repeated bytes in a batch or already committed bank are skipped without inflating frequency. --reprocess only retries a known source with zero occurrences. Preserve non-extracted dispositions in run audit and show them in the final user report.

reference keeps an absolute source path; copy keeps hash-named bank/media bytes; none stores no canonical source path and removes the temporary view_path after successful commit. Do not put unrelated identifying information in responses, source metadata or filenames you invent.

## Select reusable questions

Follow [report policy](report-policy.md). Do not extract “自我介绍”, “介绍一下你自己”, salary/availability or purely personal biography prompts. Technical project architecture, tradeoffs and failure analysis remain useful. Record omitted text/reasons in a separate structured observation file, not as Questions. If the whole source is personal introductions use no_questions plus reason. The CLI rejects obvious self-introduction candidates; correct the response rather than rewording it to bypass selection. If a retained technical follow-up follows an excluded introduction, resolve its pronoun from visible context and omit the excluded parent link; never fabricate a parent.
