# Persistent maintenance and research (1.5–1.7)

Use this protocol for repeated intake, durable research scope, user corrections and recovery. The Agent writes response JSON from the user's request; never ask users to author JSON. `<cli>` and all bank/input paths must be resolved within the user's allowed workspace. Never write into the installed Skill.

## Format and commit contract

New banks initialized with `init` start in V1 for compatibility. Existing M1–M5 commands work on V1. Persistent personal features require explicit `migrate plan`, then `migrate apply`; a request to enable these features authorizes the necessary upgrade within the selected bank. Explain the backup location in the result. Do not upgrade unrelated banks or upgrade on read-only lookup.

```text
python -B <cli> migrate plan --bank <bank> --json
python -B <cli> migrate apply --bank <bank> --json
```

Plan reports backup file count, uncompressed size and a conservative free-space estimate. Apply checks free space, refuses pending stages, saves a ZIP under bank/backups, verifies every archived hash and journal-commits V2 manifest/config/state. Six original tables remain; `data/state.json` stores protected policies, workflows, study sets, practice events, interview sessions and shared evidence. It is canonical, not cache. New answers bind to a content revision. Legacy answers retain content/history but are marked for coverage recheck; upgrading alone cannot certify them.

Old runtimes reject V2. `migrate restore --archive <backup-filename.zip> --destination <new-name>` restores to a new `bank/restored/<new-name>` after checking the manifest. It never overwrites the live bank or later work. Switch to that explicit restored bank only when intended. All normal state mutations return run_id and require the usual `commit --run`; do not forget to commit workflow creation before requesting a batch. Migration is the explicit journaled exception that applies directly. `next` writes an inspectable task packet, not answers.

## Durable research

After committing intake plus classification/merging, create a workflow scoped to the final committed run using `from_run`. It derives new occurrences and their active canonical targets. Repeat-byte intake with zero new occurrences yields an empty scope, not the whole bank.

Create payload (IDs shown below are examples; use returned IDs):

```json
{
  "name": "本批面试题答案整理",
  "from_run": "run_RETURNED_BY_COMMIT",
  "batch_size": 5
}
```

Alternatively choose **one** of `question_ids`, `studyset_id`, `from_run`, `expression`. A question_ids list may be empty; `{ "expression": {} }` explicitly means all visible knowledge questions. Explain scope before starting broad research. Never research report-hidden personal questions. Company, year and other matched-source context is frozen as occurrence IDs, so later imports do not change the selected frequency/context.

```text
workflow create --input <scope.json> --bank <bank> --json
commit --run <returned-run> --bank <bank> --json
workflow next --id <workflow-id> --bank <bank> --json
answer --input <researched-response.json> --bank <bank> --json
commit --run <answer-run> --bank <bank> --json
workflow next --id <workflow-id> --bank <bank> --json
workflow show --id <workflow-id> --bank <bank> --json
workflow export --id <workflow-id> --output review.md --bank <bank> --json
workflow summary --id <workflow-id> --output update.md --bank <bank> --json
```

Repeat next/research/answer/commit until the requested scope is covered or an actual budget/tool blocker is reached. A 5–10 item batch is not the whole assignment. next reuses a still-valid task packet; otherwise generates a fresh digest-bound packet. Never replay a task after unrelated bank/config changes. Progress is derived from committed answer IDs and current coverage, so a crash between answer commit and progress inspection does not generate duplicate answers. `workflow reconcile` stages a durable progress snapshot when useful; show is sufficient for inspection.

Read [answer-policy.md](answer-policy.md) for every batch. Actually search/read pages, verify all subquestions and condense. Task questions are under `items[].question`; previous_answer is a compact summary, not proof of validity. `answer` response uses the existing schema with task_id. On V2 it additionally accepts `checks` (list of actual checks) and `version_scope` (text). Do not claim code execution unless executed. Evidence mappings persist with the answer. `evidence list --input <query.json>` accepts query/limit and retrieves previously read page notes; independently check applicability before reuse.

Explicit skips record blockers in the workflow on answer commit. `workflow block --id ... --input ...` also accepts question_id/reason. Do not retry the same unsupported claim indefinitely; save the reason. Resume after the cause changes using `workflow resume` and input `{"retry_blocked": true}`, then commit. It does not mark the item verified. pause/resume/cancel all return staged mutations. Cancelled tasks remain history.

To intentionally change scope, use `workflow revise` with question_ids or expression plus reason, commit, and report the new scope revision. It preserves scope history. Removing an unresolved item changes the assignment and is not a successful answer. Excluded-since-creation items keep the workflow blocked until scope is explicitly revised.

## Budget and output

Optional limits: positive max_questions (new answer completions in this workflow), max_batches (created task packets, including regenerated stale packets), and deadline (ISO timestamp with timezone). Limits pause further batches without shrinking scope. `workflow resume` can replace limits with an explicitly user-requested revision; empty limits removes previous caps. Native CLI has no token meter: it rejects unsupported token/cost keys, and the host must enforce any observable user token allowance itself. Never invent exact usage.

Answers with an old content revision are effectively stale even if the reading date is recent. Metadata-only changes such as frequency/company/difficulty do not change content revision. A merge that expands wording triggers recheck. Preserve answer history; do not reset dates just to make an answer look fresh.

workflow summary distinguishes the attached intake receipt from bank changes since workflow creation; the latter may include other operations and is not attributed solely to this intake. Detailed counts, frequency differences, reasons and IDs stay in its JSON sibling. Export uses the frozen question/source scope and creates both report editions by default. Explicit `--answers without` honors question-only use.

## User protection

First make the user's desired correction with curate. Then `policy add --input ...`, commit, using either:

```json
{"kind":"protect","question_id":"q_ACTUAL","field":"canonical","reason":"用户要求保留此题干","user_requested":true}
```

```json
{"kind":"never_merge","question_ids":["q_FIRST","q_SECOND"],"reason":"用户确认考点不同","user_requested":true}
```

Supported protected fields: canonical, domains, role_tracks, technologies, difficulty, report_exclusion. A missing field must first be set via curate. Do not set user_requested for a model preference. Automatic classification and merges cannot override protections; forbidden pairs remain effective across transitive merges. Conflict errors identify the rule/reason. Keep the current state and resolve with evidence or an explicit user correction.

When the user explicitly changes a protected value, curate input may include `override_protection: true` and `user_requested: true`; the same audited snapshot updates the protection. `policy disable --id ... --input ...` requires reason and then commit. `policy list` shows active and inactive history. Free-form “以后这类题” should be narrowed to evidenced labels/explicit targets, not silently converted into a global keyword rule.

Existing undo remains restricted to the latest unchanged snapshot; arbitrary historical unmerge is not supported. Explain the affected records and preserve later changes instead of rolling back the whole bank. Review [schema.md](schema.md) for durable recovery and invariants.

`workflow next` and `workflow list` return compact progress cards, not the entire scope ledger. Read only `task` items for each research batch. `workflow show` explicitly returns full details; for large banks prefer `workflow summary` and the saved JSON unless item-level diagnosis is needed. This keeps ordinary batch tool output proportional to batch size.
