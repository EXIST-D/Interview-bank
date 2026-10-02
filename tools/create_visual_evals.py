"""Render synthetic social screenshot fixtures; Pillow is development-only.

These fixtures test controlled behavior and are not a real-world accuracy benchmark.
No downloaded media or personal screenshots are included.
"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
# A CJK-capable font; INTERVIEW_BANK_CJK_FONT overrides the per-platform defaults.
FONT_CANDIDATES = [os.environ.get("INTERVIEW_BANK_CJK_FONT", ""), "C:/Windows/Fonts/msyh.ttc",
                   "/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc",
                   "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"]
FONT = next((Path(p) for p in FONT_CANDIDATES if p and Path(p).is_file()), None)
# Templates and their gold answers live in evals/extraction/gold.jsonl (one source of truth for render and score).
CASES = [(row["case_id"], row["template"]["title"], row["template"]["lines"], row["template"]["notes"])
         for row in map(json.loads, (ROOT / "evals/extraction/gold.jsonl").read_text(encoding="utf-8").splitlines()) if row]


def draw_card(case, sequence):
    name, title, lines, notes = case
    font = ImageFont.truetype(str(FONT), 24)
    small = ImageFont.truetype(str(FONT), 20)
    bold = ImageFont.truetype(str(FONT), 26)
    height = max(500, 220 + (len(lines) + len(notes)) * 49)
    im = Image.new("RGB", (820, height), "#f4f5f7")
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle((18, 18, 802, height - 18), 20, fill="white")
    draw.text((42, 32), "面经广场  ·  匿名测试样本", font=small, fill="#7b8392")
    draw.text((42, 83), title, font=bold, fill="#172335")
    y = 146
    for line in lines:
        draw.text((42, y), line, font=font, fill="#202a38")
        y += 49
    for line in notes:
        draw.text((42, y + 20), line, font=small, fill="#788393")
        y += 49
    draw.text((42, height - 63), f"Synthetic QA / {name} / {sequence:02d}", font=small, fill="#8c94a2")
    if name == "blur":
        im = im.filter(ImageFilter.GaussianBlur(16))
    return im


def main():
    output = ROOT / ".work/visual-evals"
    output.mkdir(parents=True, exist_ok=True)
    batch = output / "batch50"
    batch.mkdir(exist_ok=True)
    manifest = []
    for i in range(40):
        case = CASES[i % len(CASES)]
        image = draw_card(case, i)
        path = batch / f"{i:02d}-{case[0]}.png"
        image.save(path)
        manifest.append({"path": str(path), "case": case[0], "index": i})
        if i < len(CASES):
            image.save(output / f"{case[0]}.png")
    for i in range(10):
        original = Path(manifest[i]["path"])
        (batch / f"duplicate-{i:02d}.png").write_bytes(original.read_bytes())
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for start in range(0, len(CASES), 4):
        selected = CASES[start:start + 4]
        canvas = Image.new("RGB", (1640, 1700), "#ddd")
        for j, case in enumerate(selected):
            image = Image.open(output / f"{case[0]}.png")
            image.thumbnail((820, 850))
            canvas.paste(image, ((j % 2) * 820, (j // 2) * 850))
        canvas.save(output / f"contact-{start // 4}.png")
    print(output)


if __name__ == "__main__":
    main()
