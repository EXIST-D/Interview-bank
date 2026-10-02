"""Build a reproducible, self-contained Skill ZIP; all artifacts stay in repo."""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/interview-bank"
sys.path.insert(0, str(SKILL / "scripts"))
from ibank_core import __version__


def main():
    output = (ROOT / "dist").resolve()
    if not output.is_relative_to(ROOT):
        raise ValueError("Build output must remain inside the repository")
    output.mkdir(exist_ok=True)
    archive = output / f"interview-bank-{__version__}.zip"
    files = sorted(p for p in SKILL.rglob("*") if p.is_file() and "__pycache__" not in p.parts
                   and (p.suffix in (".md", ".py", ".json", ".yaml", ".html", ".css", ".js") or p.name == "LICENSE.txt"))
    for path in files:
        if not path.resolve().is_relative_to(SKILL):
            raise ValueError(f"External linked file cannot be packaged: {path}")
        relative = path.relative_to(SKILL)
        if relative.parts[0] not in ("SKILL.md", "LICENSE.txt", "agents", "references", "scripts", "assets"):
            raise ValueError(f"Unexpected skill artifact: {relative}")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipout:
        for path in files:
            name = "interview-bank/" + path.relative_to(SKILL).as_posix()
            entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            zipout.writestr(entry, path.read_bytes())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    print(json.dumps({"archive": str(archive), "files": len(files), "bytes": archive.stat().st_size, "sha256": digest}, indent=2))


if __name__ == "__main__":
    main()
