"""Static checks of the Web reader: markup, element IDs and both UI languages stay consistent."""
import re
import unittest
from html.parser import HTMLParser

from support import SKILL

WEB = SKILL / "assets" / "web"
VOID = {"meta", "link", "input", "br", "img", "hr", "source", "area", "base", "col", "embed", "param", "track", "wbr"}


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.ids, self.keys, self.errors = [], [], set(), []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        for name in ("data-i18n", "data-i18n-html", "data-i18n-placeholder", "data-i18n-title", "data-i18n-aria"):
            if name in attrs:
                self.keys.add(attrs[name])
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"unexpected </{tag}> (open: {self.stack[-3:]})")
        else:
            self.stack.pop()


def text_tables(script):
    """Keys of the zh-CN and en tables in app.js."""
    body = script[script.index("const TEXT = {"):script.index("const RATINGS")]
    zh = body[body.index("'zh-CN': {"):body.index("\n  en: {")]
    en = body[body.index("\n  en: {"):]
    keys = re.compile(r"(?:^|[\s{,])([a-z_0-9]+):\s*['`]", re.M)
    return set(keys.findall(zh)), set(keys.findall(en))


class WebAssets(unittest.TestCase):
    def setUp(self):
        self.html = (WEB / "index.html").read_text(encoding="utf-8")
        self.script = (WEB / "app.js").read_text(encoding="utf-8")
        self.markup = Markup()
        self.markup.feed(self.html)

    def test_tags_balance_and_ids_are_unique(self):
        self.assertEqual(self.markup.errors, [])
        self.assertEqual(self.markup.stack, [])
        self.assertEqual(len(self.markup.ids), len(set(self.markup.ids)))

    def test_every_id_the_script_uses_exists(self):
        used = set(re.findall(r"\$\('([\w-]+)'\)", self.script)) - {"nav-" + k for k in ("all", "due", "weak", "unseen")} - {"practice-response"}
        filters = set(re.search(r"const filters = \[([^\]]+)\]", self.script).group(1).replace("'", "").replace(" ", "").split(","))
        self.assertEqual(sorted(used - set(self.markup.ids)), [])
        self.assertTrue(filters <= set(self.markup.ids))

    def test_both_languages_cover_every_key(self):
        zh, en = text_tables(self.script)
        self.assertEqual(sorted(zh ^ en), [])
        used = set(re.findall(r"\bt\('([a-z_0-9]+)'", self.script)) | self.markup.keys
        dynamic = {"status_", "rating_", "titles_", "all_"}
        self.assertEqual(sorted(k for k in used - zh if not k.startswith(tuple(dynamic))), [])

    def test_stylesheet_is_readable_and_has_dark_mode(self):
        css = (WEB / "app.css").read_text(encoding="utf-8")
        self.assertLess(max(len(line) for line in css.splitlines()), 200)
        self.assertIn("@media (prefers-color-scheme: dark)", css)
        self.assertEqual(css.count("{"), css.count("}"))


if __name__ == "__main__":
    unittest.main()
