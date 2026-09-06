# Evaluation and operating limits

Validate both the deterministic data engine and the host's cognitive output. These are different measurements.

## Deterministic checks

The repository tests cover canonical schema/references, idempotency, locks, transaction interruption/recovery, cache fallback, image retention/hash changes, partial save/resume, uncertainty gates, semantic response contracts, merge propagation/undo, classification/correction, interval dates, exports, answer evidence/versions/staleness, duplicate JSON rejection and path containment.

Install packages contain only the Skill, agents metadata, scripts and references. Run the packaged CLI in a fresh bank and verify the installed files remain unchanged.

## Vision scenarios

Use single/multiple question screenshots, follow-ups, company sections, answers mixed with questions, comment interference, UI-only noise, visible/unknown company, explicit role/round, multi-image continuations, multiline code, Chinese/English mixtures, no-question pages, unreadable blur and embedded malicious instructions.

The repository renders 17 controlled synthetic templates. A 50-file batch contains 40 unique images and 10 byte-identical duplicates. Host-reviewed extraction produces 81 appearances and 25 active standard questions after conservative judgments. Replay scripts test the full persistence workflow with these stored host responses; replay itself does not run an OCR/model.

## Answer research

The release example uses actually read Redis official pages and retained access dates. Replay does not re-read or refresh those dates. Check evidence supports each factual key point; schema validation alone cannot prove factual correctness.

## Limits to state honestly

Synthetic fixtures and passing unit tests are not real-world extraction accuracy measurements. Unseen screenshots still need actual host vision, appropriate confidence, and review of ambiguous text. Candidate retrieval is lexical/tag-based and bounded; it cannot guarantee exhaustive semantic recall. Human-reviewed status requires an actual human decision. Audio/video and interactive viewer are outside this release.
