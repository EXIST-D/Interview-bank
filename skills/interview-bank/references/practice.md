# Personal review and mock interviews (1.7)

Requires V2; see [maintenance](maintenance.md). Practice data belongs to the user's bank, not the Skill. Never fabricate the user's answers, mastery, project experience or human review. Automated tests may use clearly labeled synthetic responses only in isolated test banks.

## Review queue

Use `study queue --input <selection.json>` with optional question_ids/studyset_id, timezone (default Asia/Shanghai), as_of (aware ISO timestamp), include_future. `study history` optionally filters question_id. Returned IDs identify questions; report numbers are not stable IDs.

Record the user's self-rating with `study record`, then commit. Generate one stable request_id for the logical action and reuse the exact payload after an uncertain response; don't invent a fresh ID on retry.

```json
{"request_id":"practice-unique-action","question_id":"q_ACTUAL","rating":"hard","timezone":"Asia/Shanghai","note":"用户表示还不能解释复杂度"}
```

Ratings: again/hard/good/easy. again schedules 1 day; hard keeps at least 1 day; good begins at 3 days and doubles up to 90; easy begins at 7 and doubles up to 180. These are simple configurable defaults, not scientifically optimized predictions. Explicit interval_days (1–3650) or next_review_at overrides scheduling. User scheduling wins. The CLI accepts UTC and Asia/Shanghai without extra dependencies; other IANA zones require system timezone data, and fail explicitly if unavailable.

Events append and keep original timestamps, user timezone and question revision; summaries derive unseen/needs_practice/mastered. A changed or merged question requires renewed practice instead of inheriting mastery of a smaller old question. Future practice times and out-of-order events are rejected to avoid silently rewriting schedules; next_review_at must follow the recorded practice. Request IDs are idempotent and reject different payload reuse.

This provides an on-demand review queue. It does not run a background scheduler. Create reminders only when the user requests them and the host supports authorized scheduling.

## One-at-a-time interview

Create a session from question_ids or studyset_id, optional limit (default 10), and name:

```text
interview start --input <session.json> --bank <bank> --json
commit --run <returned-run> --bank <bank> --json
interview next --id <session-id> --bank <bank> --json
```

Present only the current prompt to the user. next returns no reference answer in the question state. Ask one question and wait for the user's real response; an interactive interview cannot be “completed” by supplying both sides yourself.

Once the user responds, write `interview answer` input with request_id, question_id, text; commit. next then returns an Agent-only awaiting_feedback packet with the actual response and a currently valid reference answer if available. Preserve the original response exactly; quotes in feedback must be actual substrings of it.

Feedback payload for `interview feedback`, followed by commit:

```json
{
  "response_id":"response_RETURNED",
  "observations":[
    {"dimension":"coverage","quote":"实际回答中的原文","note":"具体说明遗漏及其影响"},
    {"dimension":"constraints","note":"说明需要补充的适用边界"}
  ],
  "review_topics":["需要复习的知识点"],
  "limited_basis":false
}
```

Dimensions: accuracy, coverage, constraints, clarity. Be specific and proportionate; do not infer personality, hiring suitability or a numeric skill rating. Verify your feedback against the reference evidence; reference-source availability alone does not certify your judgment. If no valid answer exists, or the question changed since the frozen session prompt, set limited_basis=true, disclose the limitation and avoid confident correctness judgments. Evidence links and the answer version used are saved with feedback.

After feedback, optionally stage `interview follow-up` with prompt/reason. It asks about the preceding question, and follows the same answer/feedback sequence; choose follow-ups only when they add value. Otherwise next gives the next main question. User-requested early termination uses `interview end`; it becomes completed only if all selected questions have answers and feedback and no follow-up is pending, otherwise cancelled with history retained.

At the end use `interview summary` to report coverage, ungraded responses and weak topics. Summarize in natural language without dumping internal IDs. `interview show/list/next` resumes after interruption. Reference answers may change meanwhile; the original prompt is frozen, changes are disclosed, and previously saved feedback retains its actual source version.

Learning records are separate: only call study record after a real user self-rating, not merely because the Agent gave favorable feedback. No practice operation changes question occurrence frequency.

Retrying the same answer request ID with the same question/text, or identical feedback for the same response, returns the existing receipt even after session end. Different content with a reused ID is rejected. Repeated end is harmless. On missing receipts inspect the session before generating another ID.
