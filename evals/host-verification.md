# Host verification

Each host gets the same checklist. Record the date, host version, model and OS. The verdict is **pass**
(every item), **partial** (some items, listed) or **not verified**. Protocol tests in `tests/` do not count
as host verification.

Checklist:

1. Discovery: after installing (`npx skills add EXIST-D/Interview-bank --skill interview-bank -a <agent>`), the host lists or loads the Skill.
2. `doctor` runs with the host's Python (3.10+).
3. Quick path on the demo bank (`demo --bank <new dir>`): search, then export both editions.
4. Both Markdown editions open and render, including the folded 口述版 · 常见追问 · 易错点 block.
5. `web` starts and stays available in the background while the user reads.
6. Screenshot extraction with the host's own vision (the extraction suite in [README](README.md)).
7. Answer research with the host's own web tools, citations included.

| Date | Host and version | Model | OS | Verdict | Notes |
|---|---|---|---|---|---|
| 2026-10-02 | Claude Code 2.1.263 (desktop app, Code tab) | claude-opus-5-5 | macOS 26 (Darwin 25.6.0) | partial: 1, 2, 4, 5, 6 | 1: a headless `claude -p` session listed `interview-bank` among its skills, but could not authenticate, so the trigger suite is not run. 6: extraction suite scored 1.00 (not blind, see the run's meta.json). 3 waits for the demo command; 7 not run in this session. |
| — | Codex | — | — | not verified | — |
| — | Cursor | — | — | not verified | — |
| — | Trae / Trae CN | — | — | not verified | — |
| — | Qwen Code | — | — | not verified | — |
| — | Gemini CLI | — | — | not verified | — |

The author's earlier releases were used with Codex on Windows (screenshots, real speech transcription and
reports). That predates this checklist and is not recorded here as a verification.
