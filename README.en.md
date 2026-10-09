# Interview Bank Skill

English | [简体中文](README.md)

`interview-bank` is an interview-question organization Skill for Claude Code, Codex and other agents that support Agent Skills. It helps users extract questions from screenshots, selected text, web pages, recorded speech in audio/video, or subtitle transcripts collected over time, classify them by role, technical domain, technology, company and industry, merge equivalent wording, research sourced reference answers, and produce two reports for reading and self-testing. It turns scattered interview material into a growing personal reference bank.

Suitable for internships, campus recruitment, autumn recruitment and experienced-hire interviews. Current version: **1.16.0**. See the [CHANGELOG](CHANGELOG.md) and [GitHub Releases](https://github.com/EXIST-D/Interview-bank/releases).

## What's new: 1.16 a 八股 notes section and a better Web reader

- **Notes section (八股):** `notes import` reads a folder of collected public study notes in Markdown (one file per chapter, `##` headings as questions). Their answers are kept verbatim with their source (collection, chapter, file and line); 🔴 / ⭐ marks key questions. Notes never count as interview occurrences and do not touch dedupe or reference answers. See [notes](skills/interview-bank/references/notes.md).
- **Linked to your own questions:** the agent judges which notes answer each interview question (same question / related topic). In the reader a question lists its related notes, and a note lists how interviews asked it and how often, one tap apart; "asked" and "most asked" views put the questions interviewers actually ask first.
- **A better Web reader:** notes grouped by chapter with folding headers (collapse all for a table of contents); a peek at any answer from the list; read marks and chapter progress; a random pick; on a computer the navigation and the list fold away and Focus reads full-window; text size, a reading progress bar, light / dark themes. See [the Web reader](#the-web-reader-study-on-a-computer-or-a-phone).
- Server sync and daily backups include the notes (`collections/`).

## 1.15 reading online, on a phone or a computer

- The Web page was redesigned for short sessions: a list and a full-screen reader on a phone, three columns on a computer; every key point of an answer links to the source behind it.
- The read-only reader can run behind your own HTTPS server with its own login page, one bank per account and daily verified backups; `tools/deploy/` holds every template.

## Interface preview

On a computer: navigation, question list and reader in three columns; a question lists its related notes.

![Interview Bank on a computer: navigation and topics, question list, reference answer with sources and related notes](assets/readme/web-preview.png)

The notes section: chapters that fold, a peek at an answer in the list, and a note with its source and how interviews asked it.

![Interview Bank notes section on a computer: chapter groups, answer peek, the collection's answer and linked interview questions](assets/readme/notes-preview.png)

On a phone: chapters with a peek (left), the full-screen reader with previous/next (right).

![Interview Bank on a phone: notes list and reader](assets/readme/mobile-preview.png)

All come from the `demo` sample bank (synthetic questions, fictional companies, notes written for the demo); anyone can reproduce them with `demo --bank <new dir>` and `web`.

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
├── tools/                        # packaging, release checks, synthetic fixtures, measurements, eval runners, server deployment (deploy/)
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
| Notes (八股) | Import collected Markdown study notes with their answers and sources; agent-judged links to interview questions, both ways in the reader |
| Web reader | Interview and notes sections, peek, read marks, random pick, folding chapters, focus reading; self-rated practice, human review, merge decisions; can run on your own server for a phone |

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

`demo` builds 20 synthetic questions, 8 with reference answers checked against official documentation, and a small notes collection written for the demo (5 notes, linked to the questions).

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

## The Web reader: study on a computer or a phone

The agent organises the bank; the Web page is for reading it. The page runs no AI and searches nothing online; it only reads your bank.

- **Two sections:** *Interviews* holds the real questions you collected, most frequent first, with reference answers whose sources you can check; *Notes* holds the public study notes you collected, in chapter order, with their own answers and sources. The two link to each other.
- **Made for spare minutes:** on a phone, a list and a full-screen reader with previous/next at the bottom or a swipe; a peek at any answer from the list; read marks and chapter progress; a random pick that prefers unread questions; Think first hides answers by default.
- **Three columns on a computer:** navigation, list and reader. The navigation and the list fold away, and Focus lets the reader fill the window at a comfortable line length.
- **Easy on the eyes:** three text sizes, a reading progress bar, light / dark / system themes, highlighted search words; tables, code, quotes and nested lists in long answers render properly. Read marks, folds, text size and theme stay in the browser.
- **Practice and your own decisions** (when run locally): self-rated practice (V2 banks save progress and schedule reviews), **human review** of answers and **merge decisions** on pairs the agent was unsure about; only you can press these.

| Shortcut (computer) | Action |
|---|---|
| ← / → or K / J | Previous / next |
| Space | Show the answer (in Think first) |
| / | Search |
| F | Focus (fold the navigation and the list) |
| L | Fold / unfold the list |
| Esc | Leave focus |

### Three ways to use it

| Way | For | How |
|---|---|---|
| **On your computer** | Reading on the machine where your bank is | `python -B <skill dir>/scripts/ibank.py web --bank <bank> --open`. Loopback only (127.0.0.1), no login; Ctrl+C stops it and `--read-only` disables writes. Or ask the agent to open your bank's Web reader. |
| **On your own server** | Reading on a phone anywhere | The read-only reader sits behind your own HTTPS reverse proxy: its own login page (hashed passwords, lockout after failures), one bank per account, daily verified backups. `tools/deploy/sync.sh` copies the bank text and notes from your computer, never screenshots. Steps: [Web usage](skills/interview-bank/references/web.md) and `tools/deploy/`. |
| **Test it with the author** | Trying the hosted reader first, or when you cannot deploy one yet | Contact the author through [GitHub Issues](https://github.com/EXIST-D/Interview-bank/issues) for an account to test with. Each account sees only its own bank; the server keeps only the bank text (no screenshots), deleted on request. |

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

**v1.16.0** implements everything in the capabilities table above. Existing V1 banks keep extraction, classification, deduplication, answer research and export; saved topics, durable research workflows and review state need a backed-up upgrade to V2. Updating the Skill never migrates a personal bank or marks old answers as re-verified.

**Not implemented yet:**

| Area | Note |
|---|---|
| On-screen text in videos | Only speech is processed; capture silent on-screen questions as screenshots |
| Speaker separation, resuming inside long recordings | Speaker labels from the tool are kept; resume is per file |
| Editing in the Web reader | Question edits and intake stay with the agent; the Web reader reads, practises, reviews and decides merges |
| Reading progress across devices | Read marks and folds stay in one browser; a hosted reader does not yet send practice ratings back |
| MCP server | Planned as a separate optional package; the core stays dependency-free |

**Other limits:** review queues are generated on demand with no background reminders; exact token and cost figures depend on the host; splitting an arbitrary historical merge is not supported, only undoing the latest eligible operation.

**Verification:** v1.16.0 passes 315 automated tests in CI (Windows, macOS and Linux; Python 3.10–3.13), runs them again in the legacy snapshot format, and adds lint and a packaged-install check; run them with `python -B -m unittest discover -s tests`. Evaluation results and host checks are in [evals](evals/README.md): dedupe retrieval recall@10 is 1.00; blind dedupe judgments made 0 % false merges and 3.4 % missed merges (Opus and Sonnet); blind answers scored 1.7 / 2 from a separate judge with no unsupported claims; on Claude Code the trigger suite passes with Sonnet, while Haiku's recall (0.73–0.80) is below the gate. Extracted content and reference answers still need checking against the original material, sources and scope.

The repository contains the Skill, tests, evaluations and development tools, documentation, license and the README image. Personal material, banks, research ledgers and local environments are not published; test and evaluation data are synthetic.

## Author and maintenance

Created and maintained by [EXIST-D](https://github.com/EXIST-D).

Issues, feedback and suggestions are welcome in [GitHub Issues](https://github.com/EXIST-D/Interview-bank/issues); see [CONTRIBUTING](CONTRIBUTING.md), and [SECURITY](SECURITY.md) for vulnerabilities. Remove personal information, private screenshots and sensitive bank content from any example you submit.

## License

This repository uses the **MIT License**; see [LICENSE](LICENSE). The Skill also ships a copy: [skills/interview-bank/LICENSE.txt](skills/interview-bank/LICENSE.txt).

The license covers this repository's code and documentation; screenshots, question material and cited third-party sources remain subject to their own rights and terms.
