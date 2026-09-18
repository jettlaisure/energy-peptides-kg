"""Open Graph share cards — one per product, plus a default.

Every link to the site currently shares as bare text. The product photos are WebP, which social
scrapers handle unevenly, so this composes proper 1200x630 JPEGs on the brand ground instead:
product photo right, name and amount left, compliance line where it belongs.

    uv run --with pillow --with "fonttools[woff]" python render/og_cards.py

Reads web/src/data/catalog.json (so it follows the graph) and writes web/public/og/.
Re-run after a rename, a new product, or a photo re-render.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
CATALOG = WEB / "src" / "data" / "catalog.json"
FONTS = WEB / "public" / "fonts"
OUT = WEB / "public" / "og"

W, H = 1200, 630
VOID = (6, 12, 31)
NAVY = (13, 27, 62)
GOLD = (212, 175, 95)
TEXT = (238, 242, 249)
DIM = (159, 178, 206)

PAD = 64


def load_font(weight: int, size: int) -> ImageFont.FreeTypeFont:
    """Satoshi ships as woff2; Pillow needs sfnt, so decompress in memory."""
    from fontTools.ttLib import TTFont

    src = FONTS / f"satoshi-{weight}.woff2"
    buf = io.BytesIO()
    f = TTFont(str(src))
    f.flavor = None
    f.save(buf)
    buf.seek(0)
    return ImageFont.truetype(buf, size)


def fit_lines(draw, text, font, max_w, max_lines=2):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines


def card(name: str, amount: str, photo: Path | None, compliance: str, out: Path) -> None:
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)

    # Photo panel on the right, on the darker ground so the vial separates from the card.
    panel_w = 470
    if photo and photo.exists():
        d.rectangle([W - panel_w, 0, W, H], fill=VOID)
        src = Image.open(photo).convert("RGB")
        scale = max(panel_w / src.width, H / src.height)  # cover the panel, no dark seam
        src = src.resize((max(1, round(src.width * scale)), max(1, round(src.height * scale))), Image.LANCZOS)
        left = (src.width - panel_w) // 2
        top = (src.height - H) // 2
        img.paste(src.crop((left, top, left + panel_w, top + H)), (W - panel_w, 0))
        text_w = W - panel_w - PAD * 2
    else:
        text_w = W - PAD * 2

    d.rectangle([0, 0, 6, H], fill=GOLD)  # brand rule down the left edge

    f_eyebrow = load_font(500, 20)
    f_name = load_font(700, 72)
    f_amount = load_font(400, 40)
    f_small = load_font(400, 20)

    y = PAD + 6
    d.text((PAD, y), "ENERGY PEPTIDES", font=f_eyebrow, fill=GOLD)

    lines = fit_lines(d, name, f_name, text_w)
    y = 196 if len(lines) > 1 else 232
    for ln in lines:
        d.text((PAD, y), ln, font=f_name, fill=TEXT)
        y += 84

    if amount:
        d.text((PAD, y + 6), amount, font=f_amount, fill=DIM)

    d.text((PAD, H - PAD - 16), compliance, font=f_small, fill=DIM)

    OUT.mkdir(parents=True, exist_ok=True)
    img.save(out, "JPEG", quality=88, optimize=True, progressive=True)


def main() -> None:
    cat = json.loads(CATALOG.read_text())
    site = cat.get("site", {})
    compliance = site.get("compliance_line", "For Research Use Only — Not for Human Consumption")

    made = 0
    for p in cat["products"]:
        sq = (p.get("images") or {}).get("square")
        photo = WEB / "public" / sq.lstrip("/") if sq else None
        amount = f"{p['size_mg']} mg" if p.get("size_mg") else (f"{p['size_ml']} ml" if p.get("size_ml") else "")
        name = p.get("display_name") or p["name"]
        # Most catalog names already carry the amount ("Retatrutide 20mg"); don't print it twice.
        if amount and amount.replace(" ", "").lower() in name.replace(" ", "").lower():
            name = name.replace(amount, "").replace(amount.replace(" ", ""), "").strip(" ,·-")
        card(name, amount, photo, compliance, OUT / f"{p['slug']}.jpg")
        made += 1

    card(
        "Research-grade peptides",
        "Tested batch by batch to a ≥99% purity specification",
        None,
        compliance,
        OUT / "default.jpg",
    )
    print(f"wrote {made} product cards + default.jpg to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
