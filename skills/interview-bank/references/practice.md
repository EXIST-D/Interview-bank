# Personal review and mock interviews

Requires V2; see [maintenance](maintenance.md). Practice data belongs to the user's bank, not the Skill.
Never fabricate the user's answers, mastery, project experience or human review. Automated tests may use clearly labeled synthetic responses only in isolated test banks.

## Review queue

Use `study queue --input <selection.json>` with optional question_ids/studyset_id, timezone (default Asia/Shanghai), as_of (aware ISO timestamp), include_future.
`study history` optionally filters question_id. Returned IDs identify questions; report numbers are not stable IDs.

Record the user's self-rating with `study record`, then commit. The payload must include `user_quote`: the user's own words that gave the rating (for example 这题我基本会了).
Events written this way are marked `rating_source: agent_relayed`; ratings clicked in the Web page are `user_self_rating`.
Generate one stable request_id for the logical action and reuse the exact payload after an uncertain response; don't invent a fresh ID on retry.

```json
{"request_id":"practice-unique-action","question_id":"q_ACTUAL","rating":"hard","timezone":"Asia/Shanghai","note":"用户表示还不能解释复杂度"}
```

Ratings: again/hard/good/easy. again schedules 1 day; hard keeps at least 1 day; good begins at 3 days and doubles up to 90; easy begins at 7 and doubles up to 180.
These are simple configurable defaults, not scientifically optimized predictions. Explicit interval_days (1–3650) or next_review_at overrides scheduling. User scheduling wins.
The CLI accepts UTC and Asia/Shanghai without extra dependencies; other IANA zones require system timezone data, and fail explicitly if unavailable.

Events append and keep original timestamps, user timezone and question revision; summaries derive unseen/needs_practice/mastered.
A changed or merged question requires renewed practice instead of inheriting mastery of a smaller old question.
Future practice times and out-of-order events are rejected to avoid silently rewriting schedules; next_review_at must follow the recorded practice.
Request IDs are idempotent and reject different payload reuse.

This provides an on-demand review queue. It does not run a background scheduler. Create reminders only when the user requests them and the host supports authorized scheduling.

### Scheduler

The default schedule doubles the interval on good/easy (1, 3, 6, 12 … days). Set
`config --input '{"review": {"scheduler": "fsrs", "desired_retention": 0.9}}'` (then commit) to use FSRS-4.5 with
its published default parameters: each event then records `fsrs.stability` and `fsrs.difficulty`, and the interval
is the time until predicted recall falls to the desired retention (0.70–0.97). A reworded question starts over.

## One-at-a-time interview

Create a session from question_ids or studyset_id, optional limit (default 10), and name:

```text
interview start --input <session.json> --bank <bank> --json
commit --run <returned-run> --bank <bank> --json
interview next --id <session-id> --bank <bank> --json
```

Present only the current prompt to the user. next returns no reference answer in the question state. Ask one question and wait for the user's real response;
an interactive interview cannot be “completed” by supplying both sides yourself.

Once the user responds, write `interview answer` input with request_id, question_id, text (the user's answer verbatim) and optionally `captured_via` (`chat`, default, or `voice_transcript`);
commit. next then returns an Agent-only awaiting_feedback packet with the actual response and a currently valid reference answer if available.
Preserve the original response exactly; quotes in feedback must be actual substrings of it.

`interview turn --id <session> --input <answer.json>` does answer + commit + next in one call and returns the
feedback packet; `interview review --id <session> --input <feedback.json>` does feedback + commit + next and
returns the next prompt. A 10-question interview then takes about 22 calls instead of 65. `study record --commit`
and `interview start --commit` commit at once; any stage with review items is left staged.

Feedback payload for `interview feedback` (or `interview review`), followed by commit:

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

Dimensions: accuracy, coverage, constraints, clarity. Be specific and proportionate; do not infer personality, hiring suitability or a numeric skill rating.
Verify your feedback against the reference evidence; reference-source availability alone does not certify your judgment.
If no valid answer exists, or the question changed since the frozen session prompt, set limited_basis=true, disclose the limitation and avoid confident correctness judgments.
Evidence links and the answer version used are saved with feedback.

After feedback, optionally stage `interview follow-up` with prompt/reason. It asks about the preceding question, and follows the same answer/feedback sequence;
choose follow-ups only when they add value. Otherwise next gives the next main question. User-requested early termination uses `interview end`;
it becomes completed only if all selected questions have answers and feedback and no follow-up is pending, otherwise cancelled with history retained.

At the end use `interview summary` to report coverage, ungraded responses and weak topics. Summarize in natural language without dumping internal IDs.
`interview show/list/next` resumes after interruption. Reference answers may change meanwhile;
the original prompt is frozen, changes are disclosed, and previously saved feedback retains its actual source version.

Learning records are separate: only call study record after a real user self-rating, not merely because the Agent gave favorable feedback. No practice operation changes question occurrence frequency.

Retrying the same answer request ID with the same question/text, or identical feedback for the same response, returns the existing receipt even after session end.
Different content with a reused ID is rejected. Repeated end is harmless. On missing receipts inspect the session before generating another ID.
