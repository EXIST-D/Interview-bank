"""The Skill's data engine does not depend on the Web reader's product code (one-way: Web -> core)."""
import ast
import unittest
from pathlib import Path

import support  # noqa: F401  (puts the Skill's scripts on sys.path)

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/interview-bank/scripts"
PACKAGE = SCRIPTS / "ibank_core"
# The reader and everything that only the Web's model features use. Core modules must never import these;
# only the command-line entry (ibank.py) starts the reader.
WEB_SIDE = {"web", "web_intake", "web_interview", "web_prepare", "usage_ledger", "ai", "ai_prompts", "weblogin", "public_reader"}


def imported(path):
    """Modules of ibank_core imported by a file, at top level or inside functions."""
    names = {p.stem for p in PACKAGE.glob("*.py")}
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.level == 1:
            found |= {node.module.split(".")[0]} if node.module else {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("ibank_core."):
            found.add(node.module.split(".")[1])
        elif isinstance(node, ast.Import):
            found |= {a.name.split(".")[1] for a in node.names if a.name.startswith("ibank_core.")}
    return found & names


class Boundaries(unittest.TestCase):
    def test_the_web_side_exists(self):
        self.assertEqual(WEB_SIDE - {p.stem for p in PACKAGE.glob("*.py")}, set())

    def test_core_modules_do_not_import_the_web_side(self):
        crossings = {p.stem: sorted(imported(p) & WEB_SIDE) for p in PACKAGE.glob("*.py") if p.stem not in WEB_SIDE and imported(p) & WEB_SIDE}
        self.assertEqual(crossings, {}, "core must not import Web code; move shared logic into core or pass it in")

    def test_only_the_cli_entry_starts_the_reader(self):
        self.assertLessEqual(imported(SCRIPTS / "ibank.py") & WEB_SIDE, {"web", "ai"})


if __name__ == "__main__":
    unittest.main()
