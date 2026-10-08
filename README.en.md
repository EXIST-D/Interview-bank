# Interview Bank Skill

English | [简体中文](README.md)

`interview-bank` is an interview-question organization Skill for Claude Code, Codex and other agents that support Agent Skills. It helps users extract questions from screenshots, selected text, web pages, recorded speech in audio/video, or subtitle transcripts collected over time, classify them by role, technical domain, technology, company and industry, merge equivalent wording, research sourced reference answers, and produce two reports for reading and self-testing. It turns scattered interview material into a growing personal reference bank.

Suitable for internships, campus recruitment, autumn recruitment and experienced-hire interviews. Current version: **1.15.0**. See the [CHANGELOG](CHANGELOG.md) and [GitHub Releases](https://github.com/EXIST-D/Interview-bank/releases).

## What's new: 1.14 fixes from a real-environment evaluation

1.14 comes from the first real-environment evaluation: the Skill installed in Claude Code, screenshots organised end to end by fresh Opus and Sonnet agents that read only the Skill, and the trigger, dedupe-judgment and answer suites run in real `claude -p` sessions (results under "Verification" below).

- **Dedupe review sheet:** every dedupe task writes a topic-grouped `review-sheet.md` with incoming questions, their candidates and the bank's questions of the same topic, so paraphrases with no shared wording are compared. Any active question may be a merge target (audited as `outside_candidates`); decisions accept `n3`/`e7` refs and a `default_action`.
- **Uncertain merges no longer block an import:** `ingest finalize --defer-review` commits what is decided and leaves the uncertain merges to the user under "Merge decisions" in the Web reader; `dedupe --resolve` applies them.
- **Quotes that can be checked verbatim:** `page-text` saves the text of cited pages for `answer --page-texts`, and flags redirects to other pages.
- **Phone screenshots:** rules for overlapping scrolls, questions cut across images, very tall images, the same interview posted twice, and evidence for abbreviated company names and platforms.
- **Also:** large imports stay within the 32 KB output cap with smaller task files; a role for AI application development and tags such as Claude Code and Codex; report topics ordered by size; a rule for ties among the most frequent questions.

Details are in the [CHANGELOG](CHANGELOG.md). The local Web interface is described in [local Web usage](skills/interview-bank/references/web.md).

## Interface preview

![Interview Bank local Web interface: filters, question list and reference answer](assets/readme/web-preview.png)

The screenshot comes from the `demo` sample bank (synthetic questions, fictional companies); anyone can reproduce it with `demo --bank <new dir>` and `web`.

## Repository layout

```text
Interview-bank/
├── README.md / README.en.md
├── CHANGELOG.md                  # version history
├── CONTRIBUTING.md / SECURITY.md
├── LICENSE
├── .github/workflows/ci.yml      # tests on Windows/macOS/Linux × Python 3.10–3.13, lint, legacy-format run, package check
├── tests/                        # standard-library unittest suite (not installed with the Skill)
├── evals/                        # evaluation datasets, scorer, recorded runs, host verification
├── tools/                        # packaging, release checks, synthetic fixtures, measurements, eval runners
├── examples/                     # sample structured answer
├── assets/readme/                # README images, not installed
└── skills/
    └── interview-bank/           # the installable Skill
        ├── SKILL.md
        ├── LICENSE.txt
        ├── agents/openai.yaml
        ├── assets/web/           # local Web reader (HTML/CSS/JS, no build step)
        ├── references/           # protocols for each step
        └── scripts/
            ├── ibank.py          # CLI entry point
            └── ibank_core/       # data engine
```

## Capabilities

| Step | What it does |
|---|---|
| Intake | Screenshots, selected text, web page bodies, audio and video speech, SRT/VTT/TXT/JSON subtitles (including Bilibili and YouTube auto-captions); identical files never add frequency |
| Extraction | The agent reads images or transcripts, keeping original wording, follow-up links, company/round/date; low confidence and contact details become review items |
| Classification | 67 roles, 186 domains, 229 technologies, 83 industries; Chinese labels, aliases, multiple labels, hierarchical filters |
| Deduplication | Candidate retrieval (boilerplate removed, common English terms mapped) plus the agent's semantic judgment; uncertain pairs can go to the user in the Web reader |
| Reference answers | Primary sources read and mapped per key point; optional verified quotes; `answer-recheck` for wording-only changes |
| Reports | Two Markdown editions plus a JSON sidecar; JSON/JSONL/CSV/Anki exports; English or Chinese |
| Maintenance | V2 personal state, field protection, never-merge rules, research workflows, undo, change-set runs, `gc`, standalone backup and restore |
| Preparation | JD topics with coverage gaps, daily plan calendars, review queues (simple or FSRS), one-question-at-a-time mock interviews |
| Local Web | Browse, filter, self-rated practice, human review, merge decisions; English and Chinese, dark mode |

## Agent capabilities and requirements

The Skill uses the agent's vision, reasoning and web tools and is not tied to one model API. The agent understands material and researches answers; the Python CLI validates, stores transactionally, queries and exports.

- Python **3.10 or newer**; the core and subtitle parsing use only the standard library. Local transcription of raw audio/video optionally uses `faster-whisper==1.2.1`.
- The agent must view local images, read and write the files the user allows, and run Python; sourced answers need web search and page reading.
- Installing with `npx` needs Node.js/npm; the Python core does not.
- Keep banks and outputs outside the installed Skill directory.
- The CLI does not go online by default; only `verify-citations` (link checks, on request) and `page-text` (saving cited pages while researching answers) make network requests.

## Installation

If you are not familiar with installation commands, tell your agent:

> Please install this Skill for me: [https://github.com/EXIST-D/Interview-bank](https://github.com/EXIST-D/Interview-bank), and give me a short introduction.

The Skill is listed on [skills.sh](https://skills.sh/exist-d/interview-bank/interview-bank). Install with the `skills` CLI (Codex shown):

```powershell
npx skills add EXIST-D/Interview-bank --skill interview-bank --agent codex --yes --copy
```

Other agents use the same command with their `--agent` value (paths from the [skills CLI](https://github.com/vercel-labs/skills); add `-g` for a user-wide install):

| Agent | `--agent` | Project path | Global path | How to invoke |
|---|---|---|---|---|
| Claude Code | `claude-code` | `.claude/skills/` | `~/.claude/skills/` | Natural language; matched by the Skill description |
| Codex | `codex` | `.agents/skills/` | `~/.codex/skills/` | `$interview-bank …` or natural language |
| Cursor | `cursor` | `.agents/skills/` | `~/.cursor/skills/` | Natural language |
| Trae / Trae CN | `trae` / `trae-cn` | `.trae/skills/` | `~/.trae/skills/` / `~/.trae-cn/skills/` | Natural language |
| Qwen Code | `qwen-code` | `.qwen/skills/` | `~/.qwen/skills/` | Natural language |
| Gemini CLI | `gemini-cli` | `.agents/skills/` | `~/.gemini/skills/` | Natural language |

What has actually been verified on each host is recorded in [host verification](evals/host-verification.md). You can also copy `skills/interview-bank` into your agent's skills directory, or download the checksummed ZIP from [Releases](https://github.com/EXIST-D/Interview-bank/releases). Reload the project or restart the client if the skill list does not refresh.

## Try it

```text
python -B <skill dir>/scripts/ibank.py demo --bank <new dir>
python -B <skill dir>/scripts/ibank.py web --bank <new dir> --open
```

`demo` builds 20 synthetic questions, 8 with reference answers checked against official documentation.

## Examples

```text
Use interview-bank to organize these interview screenshots, classify and merge equivalent questions, add sourced reference answers, and produce both reports.

Organize the questions only; no answers. Leave out self-introductions.

Add this interview write-up page to my bank (I have it open).

Find the most frequent Redis backend questions in my bank and add answers backed by official documentation.

From this job description, pick 30 questions from my bank, explain coverage and gaps, export both reports and plan 10 a day.

Ask me 10 questions from this topic one at a time, give feedback after each answer and summarize weak areas at the end.

Export my bank as Anki cards.

Open the local Web reader; I want to review answers myself and settle the uncertain merges.
```

## Local Web reader and practice

> Use interview-bank to open the local Web reader for my bank so I can browse and practise.

```text
python -B <skill dir>/scripts/ibank.py web --bank <existing bank> --open
```

The server listens on the loopback interface only (`127.0.0.1` or `localhost`); use the full launch URL it prints, stop it with Ctrl+C, and add `--read-only` to disable all writes. The page offers filters and search, answers and original wording, self-rated practice (saved in V2 banks; a round survives a reload), **human review** (only you can press it), **merge decisions** (you settle the merges the agent was unsure about), English or Chinese and dark mode. It runs no AI and does not grade answers.

**Reading on a phone (optional):** the read-only reader can sit behind your own HTTPS server and a login; `tools/deploy/sync.sh` copies the bank data there (no screenshots). Steps and templates: [local Web usage](skills/interview-bank/references/web.md) and `tools/deploy/`.

## Processing policy

Default flow: **extract → classify → deduplicate → commit → research reference answers → export both reports**.

- Similarity only finds candidates; the agent decides merges from the full meaning and hands uncertain ones to the user. Languages, versions, scenarios and complexity constraints are never dropped to shrink the count.
- Answers prefer official documentation, original papers and first-party sources, with every key point mapped to a citation. "Verified against sources" and "human-reviewed" are different states; only the user can create the latter.
- Before researching more than 20 questions the agent tells you the count and batches and lets you choose all, only the most frequent, or the question edition first.
- Work runs in batches of 5–10, deduplicated before research; both editions render from the same data.
- A questions-only request skips research; queries, exports or Skill changes never start a bank-wide research run.

## Generated bank and reports

```text
<bank directory>/
├── manifest.json / config.json
├── data/                         # questions, occurrences, sources, companies, answers, relations; V2 adds state.json
├── runs/                         # task packets, stages (change sets), commit receipts and audit
├── media/                        # retained source copies when chosen
├── backups/                      # verified backups from backup create and migrations
└── exports/
    ├── 面试题整理报告.md
    ├── 面试题整理报告（题目版）.md
    └── 面试题整理报告.md.details.json
```

- **Answer edition:** topic overview at the top; each question has its reference answer, source links, frequency, companies, labels and evidenced years; spoken version, follow-ups and pitfalls are folded.
- **Question edition:** the same questions and order without answers, for self-testing.
- **Structured sidecar:** internal IDs, original wording, exact dates, source links, full classification and answer history.

The JSONL files in `data/` are the only source of truth and are queried directly; every change goes through stage, validation and commit with history and audit. Frequency counts collected occurrences, not interview participants or market probabilities.

## Status and plans

**v1.15.0** implements everything in the capabilities table above. Existing V1 banks keep extraction, classification, deduplication, answer research and export; saved topics, durable research workflows and review state need a backed-up upgrade to V2. Updating the Skill never migrates a personal bank or marks old answers as re-verified.

**Not implemented yet:**

| Area | Note |
|---|---|
| On-screen text in videos | Only speech is processed; capture silent on-screen questions as screenshots |
| Speaker separation, resuming inside long recordings | Speaker labels from the tool are kept; resume is per file |
| Editing in the Web reader | Question edits and intake stay with the agent; the Web reader reads, practises, reviews and decides merges |
| MCP server | Planned as a separate optional package; the core stays dependency-free |

**Other limits:** review queues are generated on demand with no background reminders; exact token and cost figures depend on the host; splitting an arbitrary historical merge is not supported, only undoing the latest eligible operation.

**Verification:** v1.15.0 passes 300 automated tests in CI (Windows, macOS and Linux; Python 3.10–3.13), runs them again in the legacy snapshot format, and adds lint and a packaged-install check; run them with `python -B -m unittest discover -s tests`. Evaluation results and host checks are in [evals](evals/README.md): dedupe retrieval recall@10 is 1.00; blind dedupe judgments made 0 % false merges and 3.4 % missed merges (Opus and Sonnet); blind answers scored 1.7 / 2 from a separate judge with no unsupported claims; on Claude Code the trigger suite passes with Sonnet, while Haiku's recall (0.73–0.80) is below the gate. Extracted content and reference answers still need checking against the original material, sources and scope.

The repository contains the Skill, tests, evaluations and development tools, documentation, license and the README image. Personal material, banks, research ledgers and local environments are not published; test and evaluation data are synthetic.

## Author and maintenance

Created and maintained by [EXIST-D](https://github.com/EXIST-D).

Issues, feedback and suggestions are welcome in [GitHub Issues](https://github.com/EXIST-D/Interview-bank/issues); see [CONTRIBUTING](CONTRIBUTING.md), and [SECURITY](SECURITY.md) for vulnerabilities. Remove personal information, private screenshots and sensitive bank content from any example you submit.

## License

This repository uses the **MIT License**; see [LICENSE](LICENSE). The Skill also ships a copy: [skills/interview-bank/LICENSE.txt](skills/interview-bank/LICENSE.txt).

The license covers this repository's code and documentation; screenshots, question material and cited third-party sources remain subject to their own rights and terms.
