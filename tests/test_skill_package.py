"""Skill-package lint: frontmatter limits, version consistency and links an agent will follow."""
import re
import unittest

from support import REPO, SKILL

from ibank_core import __version__


def frontmatter(text):
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert match, "SKILL.md must start with YAML frontmatter"
    fields, parent = {}, None
    for line in match.group(1).splitlines():
        if re.match(r"^\s{2,}\w", line) and parent:
            key, _, value = line.strip().partition(":")
            fields[f"{parent}.{key}"] = value.strip().strip('"')
        else:
            key, _, value = line.partition(":")
            parent, fields[key] = key, value.strip().strip('"')
    return fields, text[match.end():]


class SkillPackage(unittest.TestCase):
    def setUp(self):
        self.text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.fields, self.body = frontmatter(self.text)

    def test_frontmatter_respects_agent_skill_limits(self):
        self.assertRegex(self.fields["name"], r"^[a-z0-9-]{1,64}$")
        self.assertEqual(self.fields["name"], SKILL.name)
        self.assertTrue(0 < len(self.fields["description"]) <= 1024)
        self.assertLess(len(self.body.splitlines()), 500, "keep SKILL.md body under 500 lines")

    def test_versions_agree_everywhere(self):
        self.assertEqual(self.fields["metadata.version"], __version__)
        for readme in ("README.md", "README.en.md"):
            with self.subTest(readme=readme):
                self.assertIn(f"**{__version__}**", (REPO / readme).read_text(encoding="utf-8"))

    def test_relative_links_in_skill_docs_resolve(self):
        for doc in [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))]:
            for target in re.findall(r"\]\(([^)#\s]+)\)", doc.read_text(encoding="utf-8")):
                if re.match(r"[a-z]+://", target):
                    continue
                with self.subTest(doc=doc.name, target=target):
                    self.assertTrue((doc.parent / target).exists())


    def test_skill_body_is_short_and_scannable(self):
        self.assertLessEqual(len(self.body), 9000, "SKILL.md body: keep detail in references")
        self.assertEqual([len(l) for l in self.body.splitlines() if len(l) > 200], [])

    def test_end_to_end_reading_set_stays_small(self):
        """What an agent reads for screenshots -> answers -> report, beside SKILL.md."""
        names = ("extraction", "report-policy", "dedupe", "answer-policy", "query-export")
        total = len(self.body) + sum(len((SKILL / "references" / f"{n}.md").read_text(encoding="utf-8")) for n in names)
        self.assertLessEqual(total, 30000)

    def test_references_wrap_prose_and_carry_no_version_history(self):
        for doc in sorted((SKILL / "references").glob("*.md")):
            fence = False
            for line in doc.read_text(encoding="utf-8").splitlines():
                if line.lstrip().startswith("```"):
                    fence = not fence
                    continue
                if not fence and not line.lstrip().startswith("|"):
                    self.assertLessEqual(len(line), 200, (doc.name, line[:60]))
            self.assertIsNone(re.search(r"^#.*\(1\.\d+\)", doc.read_text(encoding="utf-8"), re.M), doc.name)

    def test_commands_named_in_skill_md_exist(self):
        """Every command in the routing table's last column is a real CLI subcommand."""
        import argparse
        import ibank
        sub = next(a for a in ibank.parser()._actions if isinstance(a, argparse._SubParsersAction))
        rows = [line for line in self.body.splitlines() if line.startswith("| ") and "Main commands" not in line and "---" not in line]
        named = {cell.split()[0] for row in rows for cell in re.findall(r"`([^`]+)`", row.rsplit("|", 2)[-2])}
        self.assertGreater(len(named), 20)
        self.assertEqual(sorted(named - set(sub.choices)), [])

    def test_sources_compile_without_warnings(self):
        """A SyntaxWarning goes to stderr and breaks every --json consumer reading it."""
        import warnings
        for path in sorted((SKILL / "scripts").rglob("*.py")):
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                compile(path.read_text(encoding="utf-8"), str(path), "exec")


if __name__ == "__main__":
    unittest.main()
