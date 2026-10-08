# Evaluations

Unit tests show the data engine works. These suites measure what tests cannot: whether a host loads the Skill
when it should, reads screenshots correctly, judges duplicates, and writes supported answers. All data here is
synthetic or written for the suite; nothing comes from a personal bank.

| Suite | Data | Needs a host? | Metric and release gate |
|---|---|---|---|
| Retrieval recall | `dedupe/pairs.jsonl` (121 pairs), `dedupe/holdout.jsonl` (24) | No, runs in CI | recall@10 of MERGE pairs ≥ 0.95; held-out ≥ 0.90 |
| Triggers | `triggers/cases.jsonl` (80: zh/en × trigger/no-trigger) | Yes | precision ≥ 0.9 and recall ≥ 0.9 |
| Extraction | `extraction/gold.jsonl` (17 rendered templates) | Yes (vision) | precision ≥ 0.95, recall ≥ 0.95, injection followed = 0 |
| Dedupe judgments | `dedupe/pairs.jsonl` | Yes | false-merge rate ≤ 2 %, missed-merge rate ≤ 10 % |
| Answers | `answers/cases.jsonl` (10) | Yes (web research) | mean judged score ≥ 1.6 / 2, unsupported claims = 0 |

Each release runs at least retrieval (CI), triggers, extraction and dedupe judgments, on one host with two model
tiers. The answer suite runs once per minor version. Run the same suites once without the Skill installed as a
baseline.

## Running and scoring

Every host run gets its own directory, `runs/<date>-<host>-<model>/`, holding the host's raw outputs and a
`meta.json` (date, host and version, model, OS, how the run was done, caveats). `score.py` reads only those
files, so anyone can recompute a score:

```text
python -B evals/score.py retrieval
python -B evals/score.py all --run evals/runs/<dir> --gate
```

`--gate` exits 1 when a release threshold is missed. The result is also written to `<dir>/score.json`.

### Retrieval recall (deterministic)

For each MERGE pair, the bank holds every other text in the suite and the pair's `a` arrives as a new stage;
the pair counts when `b` is among `dedupe-candidates` (top 10 / top 5). Cross-language pairs and the held-out set
are reported separately. The held-out pairs were written after the retrieval glossary was tuned on
`pairs.jsonl`, so they are the honest generalisation figure. CI runs this through `tests/test_evals.py`.

### Triggers

Every case runs in a fresh session with the Skill installed. A case is triggered when the host loads the Skill
for that query (tool call, log or UI, whatever the host shows). Save one line per case:

```json
{"id": "t-zh-01", "triggered": true}
```

to `triggers.jsonl`. For Claude Code, `python -B tools/run_trigger_eval.py --model <model>` does this with
`claude -p` and needs a logged-in CLI.

### Extraction

Render the templates with `python -B tools/create_visual_evals.py` (Pillow, development only). Give the host each
image with the extraction protocol and save, per template, `extraction/<case_id>.json`:

```json
{"case_id": "chain", "status": "extracted",
 "questions": [{"text": "Redis 为什么快？", "parent": null, "company": null, "round": "technical-1"},
               {"text": "为什么采用单线程？", "parent": 0, "company": null, "round": "technical-1"}]}
```

`parent` is the index of the question it follows up within the same image. A question matches gold when the
normalised texts are at least 85 % similar. The scorer reports precision, recall, parent and metadata accuracy
(company aliases are accepted), hallucinated questions, extracted noise (`must_not_extract`) and injected
instructions that were followed.

### Dedupe judgments

Give the host each pair (both texts and the domain) with the dedupe protocol and save one line per pair:

```json
{"id": "d001", "decision": "MERGE"}
```

using MERGE, RELATED or DISTINCT. False merges, which lose a distinct question, cost the most.

### Answers

Research each case with the answer protocol and save `answers.json` as `{"answers": [{"case_id": "a01", ...answer
fields...}]}`. Automatic checks: short answer 100–250 characters, every key point mapped to evidence, no
duplicate URL, at least one citation on a reference domain. A person or a judge model then scores each answer 0–2
on coverage, correctness, support (the page really says it) and concision, plus a count of unsupported claims,
in `answer_scores.jsonl`:

```json
{"case_id": "a01", "coverage": 2, "correctness": 2, "support": 2, "concision": 1, "unsupported_claims": 0}
```

`verify-citations` can add a link check.

## Recorded runs

| Run | Suites | Result | Caveat |
|---|---|---|---|
| CI, every commit | retrieval | recall@10 1.00 (holdout 1.00, cross-language 1.00); before the 1.13 retrieval glossary: 0.948 (holdout 0.917) | — |
| [2026-10-02, Claude Code, Opus 5.5](runs/2026-10-02-claude-code-claude-opus-5-5/meta.json) | extraction | precision 1.00, recall 1.00, parents 1.00, metadata 1.00, injection 0 | Same session wrote the gold, so not blind |
| [2026-10-08, Claude Code, Sonnet 5.5, Skill 1.13](runs/2026-10-08-claude-code-claude-sonnet-5-5-skill-1.13.0/meta.json) | triggers | precision 0.93, recall 1.00 (3 turns: 0.89 / 1.00) | One run per case |
| [2026-10-08, Claude Code, Haiku 5.5, Skill 1.13](runs/2026-10-08-claude-code-claude-haiku-5-5-skill-1.13.0/meta.json) | triggers | precision 1.00, recall 0.775, zh 0.65 (3 turns: recall 0.80) | **Below gate.** Haiku looks for the files first and asks the user when none exist |
| [2026-10-08, Claude Code, Sonnet 5.5, Skill 1.14](runs/2026-10-08-claude-code-claude-sonnet-5-5-skill-1.14.0/meta.json) | triggers | precision 0.87, recall 1.00 | Repeated runs of the disagreeing cases show the 1.13 and 1.14 descriptions behave the same; the gap is run-to-run noise |
| [2026-10-08, Claude Code, Haiku 5.5, Skill 1.14](runs/2026-10-08-claude-code-claude-haiku-5-5-skill-1.14.0/meta.json) | triggers | precision 1.00, recall 0.725 | **Below gate**, same behaviour; description wording does not change it |
| [2026-10-08, subagent, Opus 5.5](runs/2026-10-08-claude-code-subagent-claude-opus-5-5/meta.json) | dedupe judgments, answers | false merges 0 %, missed merges 3.4 % (holdout 0 %); answers 1.7 / 2, unsupported claims 0, 96/96 quotes verbatim | Blind to labels; gold written by the Skill author. Two answers cite Oracle's mirror of the MySQL manual (dev.mysql.com returned 403) |
| [2026-10-08, subagent, Sonnet 5.5](runs/2026-10-08-claude-code-subagent-claude-sonnet-5-5/meta.json) | dedupe judgments | false merges 0 %, missed merges 3.4 % (holdout 4.2 %) | Both models label ~33 DISTINCT pairs RELATED (harmless: both keep the questions) |

These synthetic templates are easy and controlled. They do not measure accuracy on real, messy screenshots.

Trigger runs use `tools/run_trigger_eval.py`: one fresh `claude -p` session per case, project settings only.
