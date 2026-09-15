"""Bundle the site's product photos for download: WebP at the exact files the site serves, plus a manifest.
  uv run python render/pack_photos.py      -> render/out/energy-peptides-product-photos.zip (and a copy in ~/Downloads)"""
import csv, io, json, pathlib, re, shutil, sqlite3, zipfile
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parent.parent
IMG = ROOT / "web" / "public" / "img" / "products"
OUT = ROOT / "render" / "out" / "energy-peptides-product-photos.zip"
TOP = "energy-peptides-product-photos"

README = """Energy Peptides product photos ({today})

Format: WebP, sRGB, the same files energypeptides.us serves. WebP is the best web format here: about a quarter the size
of an equivalent JPEG or PNG at the same quality, and supported by every current browser.

square/    1600 x 1600 (1:1)  catalog grids, product cards, marketplace and payment-page thumbnails
portrait/  1600 x 2000 (4:5)  product page hero image

1600 px wide keeps them sharp on high-density (Retina) screens up to 800 px wide on the page.
Every vial is shot at the same millimetre scale on the same floor line, so a 5 mL vial reads larger than a 3 mL one.
manifest.csv gives each photo's SKU, product, status and alt text (use it as the image's alt attribute).
Bacteriostatic water has no photo yet (no label file). GLOW and Retatrutide 15 mg are drafts, not yet on the site.
If a platform refuses WebP, ask Claude for JPEG copies.
"""

def family(name, display):
    base = re.sub(r"\s+\d+(\.\d+)?\s*(mg|ml)$", "", name, flags=re.I)
    if display and "/" in base: return f"{display} ({base})"      # nicknames always travel with their components
    return display or base

def main():
    db = sqlite3.connect(ROOT / "data" / "graph.db")
    rows = []
    for name, attrs in db.execute("SELECT name, attrs FROM nodes WHERE type='Product' ORDER BY name"):
        a = json.loads(attrs); slug = a.get("slug")
        sq, pt = IMG / f"{slug}-square.webp", IMG / f"{slug}-portrait.webp"
        if not (sq.exists() and pt.exists()): continue
        size = f"{a['size_mg']} mg" if a.get("size_mg") else (f"{a['size_ml']} ml" if a.get("size_ml") else "")
        alt = f"{family(name, a.get('display_name'))} {size} vial with the Energy Peptides label. For research use only.".replace("  ", " ")
        rows.append({"sku": a.get("sku"), "product": name, "status": a.get("status"), "square": f"square/{sq.name}",
                     "portrait": f"portrait/{pt.name}", "alt_text": alt, "_files": (sq, pt)})
    order = {"active": 0, "coming_soon": 1, "draft": 2}
    rows.sort(key=lambda r: (order.get(r["status"], 3), r["product"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_STORED) as z:                  # WebP is already compressed
        z.writestr(f"{TOP}/README.txt", README.format(today=date.today().isoformat()))
        buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=["sku", "product", "status", "square", "portrait", "alt_text"])
        w.writeheader(); [w.writerow({k: v for k, v in r.items() if k != "_files"}) for r in rows]
        z.writestr(f"{TOP}/manifest.csv", buf.getvalue())
        for r in rows:
            sq, pt = r["_files"]; z.write(sq, f"{TOP}/{r['square']}"); z.write(pt, f"{TOP}/{r['portrait']}")
    dl = pathlib.Path.home() / "Downloads"
    if dl.is_dir(): shutil.copy2(OUT, dl / OUT.name)
    print(f"{len(rows)} products, {2 * len(rows)} photos, {OUT.stat().st_size / 1e6:.1f} MB -> {OUT}" + (f" (copy in {dl})" if dl.is_dir() else ""))

if __name__ == "__main__":
    main()
