# Interview Bank Skill

English | [简体中文](README.md)

`interview-bank` is an interview-question organization Skill for Codex and other capable agents. It helps users extract questions from screenshots or selected text collected over time, classify them by role, technical domain, technology, company and industry, merge equivalent wording, research sourced reference answers, and produce two reports for reading and self-testing. It turns scattered interview material into a growing personal reference bank.

Suitable for internships, campus recruitment, autumn recruitment and experienced-hire interviews. Current version: **1.4.0**.

## Repository structure

```text
Interview-bank/
├── README.md
├── README.en.md
├── LICENSE
└── skills/
    └── interview-bank/
        ├── SKILL.md
        ├── LICENSE.txt
        ├── agents/
        │   └── openai.yaml
        ├── references/
        └── scripts/
            ├── ibank.py
            └── ibank_core/
```

## Scope

- **Screenshot extraction (M1):** batch intake, byte-identical image detection, questions/code/follow-ups with provenance, partial saves and resume.
- **Semantic classification (M2):** roles, domains, technologies, company aliases, industries, interview types, rounds, dates and difficulty, with corrections and extensions.
- **Deduplication (M3):** candidates from the current batch and existing bank, equivalent-question merging, compatible subquestion consolidation, and preserved original wording and occurrences.
- **Analysis and export (M4):** combined filters, frequency and domain statistics, Markdown, JSON, JSONL, CSV and viewer JSON output.
- **Answer research (M5):** public-source research, claim/version/scope checks, concise reference answers, citations, answer history and verification states.

The catalog includes **67 roles, 186 technical domains, 229 technology tags and 83 industry labels**, with Chinese names, aliases, multiple labels and hierarchical filters. Company profiles can include evidenced organization types, ownership and business models. Unknown metadata stays unconfirmed.

## Agent capabilities and requirements

The host agent supplies image viewing, reasoning and web tools. Python validates and stores its structured responses, then queries and exports the bank. No particular model API is required.

- **Python 3.10+**, using only the standard library for the core runtime.
- An agent able to view local images, execute Python and access user-authorized files.
- Actual web search and page-reading tools for sourced answers.
- Node.js/npm for the optional `npx` installation command; not for the Python runtime.
- A writable bank outside the installed Skill directory and within the user's permitted workspace.

The workflow has been exercised with Windows and Codex. Other hosts need equivalent capabilities. No separate OCR service, model SDK or database server is required. Running the CLI alone does not perform image recognition, semantic judgment or web research.

## Installation

If you are unfamiliar with installation commands, simply ask your agent:

> Please install the [Interview-bank](https://github.com/EXIST-D/Interview-bank) Skill for me and give me a brief introduction.

View the [interview-bank page on skills.sh](https://skills.sh/exist-d/interview-bank/interview-bank). Install for Codex in the current project using the `skills` CLI:

```powershell
npx skills add EXIST-D/Interview-bank --skill interview-bank --agent codex --yes --copy
```

This command was verified in an isolated Windows project: discovery and installation succeeded, the license was retained, and the installed Python CLI passed initialization, health and data-validation checks.

Without `--global`, the Codex project installation path is `.agents/skills/interview-bank`. To list discoverable skills first:

```powershell
npx skills add EXIST-D/Interview-bank --list
```

See the [skills CLI documentation](https://github.com/vercel-labs/skills) for options and agent paths. This repository uses `skills/interview-bank/SKILL.md` with standard name, description, license and author metadata.

Alternatively, copy the complete `skills/interview-bank` folder to a supported skill directory, or ask your agent to read [SKILL.md](skills/interview-bank/SKILL.md) directly. Reload the project or restart the client if its skill list has not refreshed.

According to the [skills.sh FAQ](https://skills.sh/docs/faq), leaderboard inclusion and counts are driven by anonymous CLI installation telemetry. Adding a README or license is not a separate submission process; listing and update timing remain platform-controlled.

## Usage examples

Explicit invocation:

```text
Use $interview-bank to organize these interview screenshots, classify and merge equivalent questions, research concise sourced reference answers, and export answered and question-only reports.
```

Other requests:

```text
Organize this screenshot folder by role, technical domain, technology and company.

Extract questions only; do not research answers. Exclude personal introductions.

Find frequent backend Redis questions in my existing bank and add answers supported by official documentation.

Add answers to the first 30 questions in this report, preserving their numbering and order, and export a test report.

Resume the previous task from saved progress without counting duplicate images again.
```

Complete task template:

```text
Use $interview-bank to process every interview screenshot in <input directory>.
Save the bank and outputs to <output bank directory>.

Read inputs without modifying them. Write new files only under the output bank;
do not modify the installed Skill.

Classify by meaning, merge equivalent questions and compatible subquestions,
and preserve original wording and sources. Exclude purely personal questions.
Do not guess companies, years or unreadable text.

Search and read credible sources for each deduplicated question, check claims
and applicability, and write concise reference answers with citations.

Export an answered report, a question-only report and a structured attachment.
Group by domain, number within each domain by descending occurrence count,
and display dates as years only.

Save and commit in batches. Report actual question and answer coverage,
output locations and unresolved items when finished.
```

## Included content

- [SKILL.md](skills/interview-bank/SKILL.md): triggers, full workflow, operating boundaries and protocol links.
- `references/`: extraction, taxonomy, company metadata, merging, report layout, answer research and schemas.
- `scripts/ibank.py`: CLI entry point for intake, staging, validation, commits, queries, exports and maintenance.
- `scripts/ibank_core/`: JSONL storage, SQLite cache, recovery, audit and report implementation.
- `agents/openai.yaml`: Codex UI metadata and default invocation prompt.
- `LICENSE.txt`: the MIT license included with installed copies of the Skill.

## Processing strategy

The default sequence is **extract → classify → deduplicate → commit → research answers → export both editions**.

Keep reusable knowledge questions and merge equivalent wording while preserving language, version, scenario and complexity constraints. Similarity scores retrieve candidates; the agent decides whether meanings can be merged.

Prefer official documentation, original papers and first-party sources. Check every subquestion against its evidence. Answers are labeled “答案（参考）” and usually use a direct response plus a few short points, roughly 100–250 Chinese characters, with more space for compound questions when needed. Incomplete evidence stays pending. Source checks and actual human review are separate states; personal experience and experimental results must never be invented.

Work in batches of about 5–10 questions. Deduplicate before research and reuse only applicable answers and evidence. Both report editions are rendered from the same data, without answering questions twice. Batching limits context size; initial full-scope research can still consume substantial tokens.

Explicit question-only requests skip research. Query-only, export-only and Skill-editing requests do not initiate research across an existing bank. Export commands only render committed answers.

## Generated bank and reports

The main bank layout is shown below. Report names can be customized; these are example names:

```text
<output bank directory>/
├── manifest.json
├── config.json
├── data/                         # questions, occurrences, sources, companies, answers, relations
├── runs/                         # tasks, stages, commits and audits
├── media/                        # images retained using the copy policy
├── cache/                        # rebuildable query cache
└── exports/
    ├── 面试题整理报告.md
    ├── 面试题整理报告（题目版）.md
    └── 面试题整理报告.md.details.json
```

- **Answered report:** domain totals, level-two domain headings, level-three numbered questions, reference answers, citations and compact occurrence/company/tag/year metadata.
- **Question-only report:** the same questions and order without answers, citations or answer progress.
- **Structured attachment:** IDs, original wording, precise dates, source relationships, classifications and answer history.

JSONL is the source of truth; SQLite is rebuildable. Mutations use staged validation and commits with history and audits. Reimporting identical image bytes does not increase frequency. Counts describe collected occurrences, not interview participants or market probabilities.

## Current status and planned features

Version 1.4 passed 94 automated checks during development, alongside real screenshot organization and sourced-answer exercises for a selected subset. These validate workflow behavior, not universal extraction or answer accuracy.

Planned development will extend collection, practice and management:

- **Audio/video transcription:** transcribe interview-experience videos, lessons or recordings and extract questions into the existing classification, deduplication and answer workflow.
- **Mock interviews and spaced repetition:** practice with the personal bank and use review history to schedule spaced repetition.
- **Social-platform reference collection:** find similar questions and relevant answers on social platforms, retain their sources and verify the content as supplementary reference material.
- **Standalone local web interface:** browse, search and maintain the personal bank in a browser, including classifications, reference answers and processing progress.

These are planned directions and are not included in the current version.

This public repository contains the Skill, introductions and licenses. Personal screenshots, banks, research records, development plans, test projects and local environments are not published.

## Author and maintenance

Created and maintained by [EXIST-D](https://github.com/EXIST-D).

Use [GitHub Issues](https://github.com/EXIST-D/Interview-bank/issues) for bugs, feedback and suggestions. Pull requests for taxonomy, workflow or tooling improvements are welcome. Remove personal information, private screenshots and sensitive bank content before sharing examples.

## License

This repository uses the **MIT License**. See [LICENSE](LICENSE). An installed Skill also includes [skills/interview-bank/LICENSE.txt](skills/interview-bank/LICENSE.txt).

The license covers this repository's code and documentation. User-supplied materials and cited third-party sources remain subject to their respective rights and terms.
