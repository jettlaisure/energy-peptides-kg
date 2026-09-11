"""Downsample render/out/<bg>/*.png (2x) to site-ready WebP in web/public/img/products/ and write a contact sheet.
  uvx --with pillow python render/finish.py [--bg offwhite]"""
import argparse, pathlib
from PIL import Image
ROOT = pathlib.Path(__file__).resolve().parent.parent
SIZES = {"square": (1600, 1600), "portrait": (1600, 2000)}
ap = argparse.ArgumentParser(); ap.add_argument("--bg", default="offwhite"); a = ap.parse_args()
src = ROOT / "render" / "out" / a.bg; dst = ROOT / "web" / "public" / "img" / "products"; dst.mkdir(parents=True, exist_ok=True)
squares = []
for f in sorted(src.glob("*.png")):
    slug, fmt = f.stem.rsplit("-", 1)
    im = Image.open(f).convert("RGB").resize(SIZES[fmt], Image.LANCZOS)
    suffix = "" if a.bg == "offwhite" else f"-{a.bg}"
    im.save(dst / f"{slug}-{fmt}{suffix}.webp", "WEBP", quality=86, method=6)
    if fmt == "square": squares.append((slug, im))
cols = 6; t = 300; rows = (len(squares) + cols - 1) // cols
sheet = Image.new("RGB", (cols * t, rows * t), (255, 255, 255))
for i, (slug, im) in enumerate(squares): sheet.paste(im.resize((t, t), Image.LANCZOS), ((i % cols) * t, (i // cols) * t))
sheet.save(ROOT / "render" / "out" / f"contact-{a.bg}.png")
total = sum(p.stat().st_size for p in dst.glob("*.webp"))
print(f"{len(list(dst.glob('*.webp')))} webp files, {total // 1024} KB total; contact sheet render/out/contact-{a.bg}.png")
