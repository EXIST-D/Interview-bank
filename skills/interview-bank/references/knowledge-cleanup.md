# Mixed knowledge-source cleanup

> Scope: this protocol belongs to the Web reader project. It is not on the Skill's routing table; read it only when the user asks for this feature by name.

Use this after a broad repository import or when the user finds roadmaps, news or unrelated material among 八股.
Read [notes](notes.md) for the atomic organization protocol and [knowledge taxonomy](knowledge-taxonomy.md) for
subject classification. A content kind describes the entry's purpose; an area/topic describes its technical subject.

1. Start with the current bank and fresh source/organization digests. Inventory the knowledge projection separately
   from public-experience article members and source notices. Work from an authorized public-only snapshot if private
   questions must stay on another machine. Never download a whole personal bank merely to audit public notes.
2. Read ambiguous headings with their bodies and original article context. Imported chapter files may combine many
   unrelated upstream articles. Use the saved original citation as context, not the generated filename alone.
3. Use explicit content kinds:
   - `qa`: one focused interview question with its answer; technical route comparisons remain here.
   - `knowledge`: concepts, explanatory sections and book summaries.
   - `exercise`: programming problems, solutions, handwritten implementations and practice notebooks.
   - `case`: system design and project cases; retain assumptions and related steps.
   - `tutorial`: installation, configuration and hands-on walkthroughs.
   - `roadmap`: learning plans, preparation sequences and staged objectives.
   - `resource`: resource lists, linked question selections and topic indexes.
   - `career`: role descriptions, job-search guidance, recruitment or salary information.
   - `news`: product announcements, pricing and industry commentary.
   - `collection`: a single imported entry contains several questions; do not count it as one unique question.
   - `reading` and `material`: existing general-purpose kinds remain compatible.
   - `info`: source/license notices, pure adverts, maintenance instructions, redirects or empty fragments.
4. Keep useful supporting material in its explicit kind. Do not reject a short but meaningful answer, code, citations
   or a technical “路线” question merely because it matches a keyword. A LeetCode “课程表” is a coding exercise.
   An outline without explanations is not a complete answer. Partial technical material with substantive content
   remains available and may receive `needs_review`; do not discard it just because one section says TODO.
5. Preserve original records, IDs and citations. Classify excluded fragments as `info` instead of deleting raw source.
   Record each changed ID, old/new kind, reason and supporting excerpt in the user's ignored workspace. If checking
   duplicates, require the same source/context and actual equivalent content; shared headings or case steps are not enough.
6. Inspect existing personal/public associations before exclusions. A retained reference is not proof of a complete answer.
   Public-study links cannot target notices; reconcile affected edges with source evidence, or retain and flag ambiguous
   content for review. Never change private questions, occurrence counts or user learning marks for this cleanup.
7. Preview then apply through `notes organize`, source by source. Preserve protected user rules and evidence states.
   Refresh digests and confirm idempotence, original source hashes, links, public-article membership and count totals.
   New kinds need version 1.22+; update every reader before applying them on a shared bank. No V1/V2 migration is needed.
   From 1.23, the five learning kinds project into their own section; inventory `all` remains available for a
   complete cleanup audit. Do not misreport a presentation split as removed questions or deleted source text.
8. Check reading continuity separately from subject classification. Recover original article order from saved
   citation line numbers, not the concatenated import order. Use the 1.24+ reading-group protocol in [notes](notes.md)
   for successive introductions, steps, explanations and code; retain source URL/content digests and editorial reasons.
   Keep standalone Q&A separate. Attach topic context to orphan display titles; do not rewrite source headings.
   Preserve paired problem/solution context in practice sheets and label multi-question units as `collection`.
   Similar template steps across different cases are not duplicates. Review questionable question/answer pairs
   against their bodies, quarantine clear mismatches as `info` and retain the original records for repair.

Report: current active entry counts per kind/source, newly excluded fragments and reasons, examples with provenance,
remaining ambiguities and what was actually checked. Separate source/license records from newly excluded items.
Do not turn a cleanup audit into a claim that every technical answer, release, price or recruitment offer is current.
