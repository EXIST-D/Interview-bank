"""Static checks of the built Web reader shipped in the skill: self-contained, CSP-compatible and in step with its source."""
import re
import unittest
from html.parser import HTMLParser

from support import REPO, SKILL

WEB = SKILL / "assets" / "web"
SOURCE = REPO / "web" / "src"


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts, self.styles, self.inline = [], [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script":
            (self.scripts if attrs.get("src") else self.inline).append(attrs.get("src") or "inline script")
        if tag == "link" and attrs.get("rel") in ("stylesheet", "modulepreload"):
            self.styles.append(attrs["href"])
        if tag == "style" or "style" in attrs:
            self.inline.append(f"<{tag} style>")


def page(name):
    parser = Page()
    parser.feed((WEB / name).read_text(encoding="utf-8"))
    return parser


class WebAssets(unittest.TestCase):
    def test_only_built_pages_and_assets_ship(self):
        self.assertEqual(sorted(p.name for p in WEB.iterdir()), ["assets", "index.html", "login.html"])
        for asset in (WEB / "assets").iterdir():
            self.assertRegex(asset.name, r"^[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\.(js|css)$")

    def test_pages_reference_existing_relative_assets_without_inline_code(self):
        # The server's Content-Security-Policy allows only same-origin scripts and styles.
        for name in ("index.html", "login.html"):
            parsed = page(name)
            self.assertEqual(parsed.inline, [], name)
            self.assertTrue(parsed.scripts, name)
            for ref in parsed.scripts + parsed.styles:
                self.assertTrue(ref.startswith("./assets/"), ref)
                self.assertTrue((WEB / ref).is_file(), ref)

    def test_bundle_has_no_remote_resources_or_eval(self):
        for asset in (WEB / "assets").iterdir():
            text = asset.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"""(?:src|href)=["']https?://(?!github\.com/EXIST-D)""", asset.name)
            self.assertNotIn("@import url(http", text, asset.name)
            if asset.suffix == ".js":
                self.assertNotRegex(text, r"\beval\(|new Function\(", asset.name)

    def test_both_languages_cover_every_key(self):
        source = (SOURCE / "lib" / "i18n.tsx").read_text(encoding="utf-8")
        zh = source[source.index("const baseZh = {"):source.index("const baseEn")]
        en = source[source.index("const baseEn"):source.index("export type TextKey")]
        keys = re.compile(r"^\s+([a-z_0-9]+):", re.M)
        self.assertEqual(sorted(set(keys.findall(zh)) ^ set(keys.findall(en))), [])
        notes = (SOURCE / "lib" / "notes-text.ts").read_text(encoding="utf-8")
        half = notes.index("export const notesEn")
        quoted = re.compile(r'^\s+"([a-z_0-9]+)":', re.M)
        self.assertEqual(sorted(set(quoted.findall(notes[:half])) ^ set(quoted.findall(notes[half:]))), [])


if __name__ == "__main__":
    unittest.main()
