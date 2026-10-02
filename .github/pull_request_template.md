## Summary

<!-- What changes and why. Link the issue if there is one. -->

## Checklist

- [ ] `python -B -X utf8 -m unittest discover -s tests` passes, and a regression test covers each fix
- [ ] `tools/package_skill.py` and `tools/check_release.py` pass if the Skill package changed
- [ ] `SKILL.md`, `references/` and both READMEs describe the new behaviour
- [ ] `CHANGELOG.md` has an entry
- [ ] Data format: unchanged / changed with an explicit migration and backup (say which)
- [ ] Fixtures and examples are synthetic; no personal data or private screenshots
