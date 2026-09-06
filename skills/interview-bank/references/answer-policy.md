# Evidence-led reference answers

Reference-answer research is the default after deduplication for an end-to-end question-organization request. Use research with question IDs or a filtered limit, then answer --input and commit; skip research only when the user explicitly requests questions only or a narrower operation such as exporting existing data. The CLI prepares task packets and validates submitted evidence; the host searches and actually reads pages. Search result snippets and invented links are insufficient. Prefer official docs, standards, original papers and first-party engineering writeups. Note version-sensitive behavior and disagreements. Paraphrase concisely; do not copy articles.

## Complete scope and verification

By default enumerate report.question_ids for the current requested material/filter scope and cover the full set, unless the user has explicitly selected a smaller scope. Do not research hidden personal questions or unrelated existing banks. Keep a structured per-question research ledger outside the installed Skill: pending/researched/verified/blocked, supporting sources, version scope, checks performed and reasons for unresolved items. Work in batches; after each commit regenerate the next task because snapshots become stale. A research limit is not the total assignment. Do not claim completion from a few examples. Default unqualified research excludes report-hidden personal questions; explicit question IDs remain possible for a specifically requested scope.

For EACH question:

1. Break the final merged wording into required subquestions and constraints; identify which claims need evidence. Search using the subject, version and constraints, then actually open the supporting primary pages. Snippets, link availability and model recollection are not verification.
2. Prefer official documentation, standards, original papers and first-party engineering explanations. Cross-check important, disputed or version-dependent claims against a second independent primary source when available; mirror copies do not count as independent. One directly applicable official specification can suffice for a narrow unambiguous fact; record why and identify uncovered claims. Do not add irrelevant citations to reach a quota.
3. Check that the cited text entails the claim and matches the requested version and scenario. Resolve disagreements or state the exact boundary. For algorithms/code, verify complexity and run a minimal example plus relevant edge cases when executable examples are supplied and a runtime is available. Record actual commands/results; do not claim testing from inspection. If execution is unavailable, distinguish source/logic verification from executable validation.
4. Re-read the condensed answer against every subquestion and its citations. Preserve negation, exceptions, tradeoffs, versions and complexity limits. Separate supported facts from design advice or source-based inference. Personal project questions use a general answer framework, never invented personal experience.
5. Mark source_backed only when the content has supporting citations and the checks above have been performed. CLI validation enforces evidence structure, not factual correctness. Agent source verification does not authorize a reviewed/human-reviewed status. If necessary evidence is missing, leave the item pending with a reason rather than inventing a definitive answer.

## Token use and resume

- Deduplicate before research; never research each repeated occurrence or each output edition separately.
- Inspect existing answer summaries. Reuse only current source-backed/reviewed answers whose sources and claims still cover the canonical wording, relevant version and all constraints. A changed/expanded merged question requires coverage review even if verified_at is recent. Cache age alone is not proof of applicability; do not refresh timestamps without new verification.
- Group 5–10 questions by topic. Read a shared primary page once per relevant version and retain a concise source/evidence ledger, URL, actual access date and covered claims. Reuse the evidence only where it supports each question; do not mechanically attach the same citation to unrelated claims.
- Research task packets intentionally omit occurrences and full answer histories. Use show only when provenance, old wording or deeper answer history is necessary. Avoid repeatedly pasting full webpages or the entire bank into context.
- Commit each completed batch and record remaining IDs, blocked reasons and completion counts. Resume those IDs rather than starting over. Fresh task packets are required after commits. A batch size limits context, not the total assignment or a guaranteed token budget.
- Concise reader answers do not require verbose hidden essays: keep deep_dive, spoken answers and other mandatory fields useful and proportionate, not padded. Verify sufficiently before condensing.
- After research, export both editions from the same data using the CLI. The question-only edition requires no second model generation. If a user supplies a budget, honor it and report actual remaining coverage rather than fabricating completion; when usage is unavailable, do not invent precise token or money estimates.

## Concise reader answers

Always label displayed content 答案（参考）. Write short_answer as one direct conclusion plus usually 3–5 short points, approximately 100–250 Chinese characters for ordinary conceptual questions; use fewer points for simple facts, or more space only to retain required constraints. Newline-separated points render as bullets. Do not repeat the question, add promotional introductions, dump retrieved text, or mechanically truncate an answer. Include the essential mechanism, choice/tradeoff and key boundary. Algorithm answers should state approach and complexity; requested runnable code belongs in code_example, with its concise result in short_answer.

Keep long explanations, spoken versions, examples, common mistakes, verification notes and full evidence in the structured records/ledger. Link the sources that support the reader answer. All substantive claims in short_answer must also be represented by the cited key_points. The reference label signals an aid to study, not permission to relax verification.

## Response shape

Return exactly one answer or explicit skip per task question. Example structure below uses placeholder content/IDs/URLs solely to document fields; replace them with actual research, never persist placeholders.

```json
{
  "schema_version": 1,
  "task_id": "run_FROM_TASK",
  "answers": [{
    "question_id": "q_FROM_TASK",
    "status": "source_backed",
    "short_answer": "直接回应问题的简洁答案",
    "spoken_answer": "适合面试口述的连贯回答",
    "key_points": ["一个有来源支持的要点"],
    "deep_dive": "机制、适用条件、版本与边界",
    "interviewer_intent": "这道题考察的能力",
    "common_mistakes": ["容易混淆的说法及纠正"],
    "follow_up_questions": ["进一步追问"],
    "code_example": null,
    "sources": [{
      "title": "实际读取的文档标题",
      "url": "https://example.org/actual-page",
      "publisher": "发布者",
      "type": "official_doc",
      "accessed_at": "2026-09-05",
      "evidence_note": "对支持该要点的原文进行简短概述"
    }],
    "evidence": [{"key_point": 0, "source_urls": ["https://example.org/actual-page"]}]
  }]
}
```

Citation type is a nonempty descriptive string (e.g. official_doc, standard, paper). accessed_at is the actual YYYY-MM-DD reading date and cannot be future. Every key_point (zero-based index) needs an evidence entry containing one or more supplied citation URLs. URLs must be HTTP(S) without embedded credentials; duplicate URLs fail. evidence_note is at most 2000 characters. Evidence mapping is retained in run audit; citation notes are retained on the Answer.

All displayed conclusions should be supported by the sources or clearly described as reasoning, example, or interview advice. Structural validation cannot establish truth or source entailment: that responsibility remains with the researching Agent.

## States and versions

- ai_draft: model-generated answer without web research; sources and evidence must be empty.
- source_backed: researched answer with citations and complete key-point mapping. It does not mean a human has approved it.
- reviewed: actual human review; only answer-review --status reviewed --human-reviewed --reason can create it through the normal workflow.
- stale: explicitly outdated, or effectively older than the configured age threshold.
- missing: no answer yet.

Each write appends a version. Existing answer content is not overwritten. Source-backed verified_at uses the oldest cited accessed_at; replaying old evidence does not refresh it. Human review appends a copy with review timestamp. Merging questions retains answers and audits any version renumbering.

When research cannot be completed, return {"question_id":"q_ID","skip":true,"reason":"..."} for that item, or an honest ai_draft if useful and consistent with the user's request. Do not silently substitute unsourced answers when the user specifically requires verified sources.
