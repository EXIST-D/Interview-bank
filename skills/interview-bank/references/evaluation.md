# Evaluation and operating limits

Validate both the deterministic data engine and the host's cognitive output. These are different measurements.

## Deterministic checks

The repository's `tests/` directory (standard-library unittest, run in CI on Windows, macOS and Linux with Python 3.10–3.13) covers canonical schema/references, idempotency, locks, transaction interruption/recovery, cache fallback, image retention/hash changes, partial save/resume, uncertainty gates, semantic response contracts, merge propagation/undo, classification/correction, interval dates, exports, answer evidence/versions/staleness, duplicate JSON rejection and path containment.

Install packages contain only the Skill, agents metadata, scripts, references and Web assets. `tools/package_skill.py` builds the ZIP and `tools/check_release.py` runs the packaged CLI, media, host-adapter and Web flows in a fresh bank and verifies the installed files remain unchanged.

## Vision scenarios

Use single/multiple question screenshots, follow-ups, company sections, answers mixed with questions, comment interference, UI-only noise, visible/unknown company, explicit role/round, multi-image continuations, multiline code, Chinese/English mixtures, no-question pages, unreadable blur and embedded malicious instructions.

`tools/create_visual_evals.py` renders 17 controlled synthetic templates (Pillow, development only). A 50-file batch contains 40 unique images and 10 byte-identical duplicates. Host-reviewed extraction produces 81 appearances and 25 active standard questions after conservative judgments. `tools/acceptance.py` replays the full persistence workflow with these stored host responses; replay itself does not run an OCR/model.

## Answer research

The release example uses actually read Redis official pages and retained access dates. Replay does not re-read or refresh those dates. Check evidence supports each factual key point; schema validation alone cannot prove factual correctness.

## Limits to state honestly

Synthetic fixtures and passing unit tests are not real-world extraction accuracy measurements. Unseen screenshots still need actual host vision, appropriate confidence, and review of ambiguous text. Candidate retrieval is lexical/tag-based and bounded; it cannot guarantee exhaustive semantic recall. Human-reviewed status requires an actual human decision. Audio/video speech intake was added in 1.8 and the optional local Web reader/practice UI in 1.10. Their protocol and behavior checks do not establish universal transcription accuracy or AI grading quality; Web practice uses user self-ratings.
