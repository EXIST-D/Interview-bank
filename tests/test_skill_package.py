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


if __name__ == "__main__":
    unittest.main()
