# Contributing

Thanks for helping improve Interview Bank. Issues and pull requests are welcome in Chinese or English.

## Development setup

- Python 3.10 or newer. The CLI and the test suite use only the standard library.
- Optional development tools: `pip install -r requirements-dev.txt` (Pillow renders synthetic screenshot fixtures; PyYAML validates frontmatter).
- The installable Skill is `skills/interview-bank/`. `tests/`, `tools/` and `examples/` are development-only and are not packaged.

## Checks before a pull request

```bash
python -B -X utf8 -m unittest discover -s tests -v
python -B -X utf8 tools/package_skill.py
python -B -X utf8 tools/check_release.py
```

`-B` keeps bytecode out of the Skill directory: the installed Skill must stay read-only, and CI fails if `skills/` gains `__pycache__` or changes during the tests. CI runs the same commands on Windows, macOS and Linux with Python 3.10–3.13.

## Conventions

- **Data integrity first.** Keep the provenance chain (Question → Occurrence → Source), staged commits and audit records intact. A change that rewrites canonical data needs a migration, a verified backup and tests.
- **Tests with every fix.** Add a regression test that fails before the fix. Tests create temporary banks; never point them at a personal bank.
- **Synthetic data only.** Fixtures, examples and screenshots in issues must not contain real names, contact details, private screenshots or personal bank content.
- **Bounded output.** New commands should return compact results; large lists must page (see `ibank_core/output.py`).
- **Docs follow behaviour.** When a command or rule changes, update `SKILL.md`, the matching file in `references/`, both READMEs where relevant and `CHANGELOG.md`.
- **Versions.** `ibank_core.__version__`, `SKILL.md` `metadata.version` and both READMEs must agree; `tests/test_skill_package.py` checks this.
- **Commits.** Conventional style: `feat:`, `fix:`, `test:`, `docs:`, `ci:`, `refactor:`, with a body that explains why.

## Reporting bugs

Use the bug report template. Include the host agent and version, OS, Python version, the command, and `doctor --json` output with local paths removed.
