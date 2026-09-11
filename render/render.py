"""Render consistent studio product shots from the real label files.
Run with a Python that has Playwright (Chromium already installed), e.g. the harness venv:
  /Users/jettlaisure/context-catalog-harness/.venv/bin/python render/render.py [--bg offwhite|navy] [--only slug,slug] [--scale 2]
Writes full-resolution PNGs to render/out/<bg>/<slug>-<square|portrait>.png; finish.py downsamples to site WebP."""
import argparse, base64, json, mimetypes, pathlib, sqlite3, sys
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
FORMATS = {"square": (1600, 1600), "portrait": (1600, 2000)}

def products():
    db = sqlite3.connect(ROOT / "data" / "graph.db"); db.row_factory = sqlite3.Row
    out = []
    for p in db.execute("SELECT id, name, attrs FROM nodes WHERE type='Product'"):
        a = json.loads(p["attrs"])
        for e in db.execute("SELECT dst FROM edges WHERE src=? AND rel='USES'", (p["id"],)):
            asset = db.execute("SELECT name FROM nodes WHERE id=?", (e["dst"],)).fetchone()["name"]
            if asset.startswith("inbox/labels/"):
                out.append({"slug": a["slug"], "label": asset, "vial": a.get("vial_ml", 3), "status": a.get("status")})
    return sorted(out, key=lambda x: x["slug"])

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--bg", default="offwhite"); ap.add_argument("--only"); ap.add_argument("--scale", type=float, default=2.0)
    a = ap.parse_args()
    items = [p for p in products() if not a.only or p["slug"] in a.only.split(",")]
    outdir = ROOT / "render" / "out" / a.bg; outdir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist"])
        page = browser.new_page(viewport={"width": 800, "height": 800})
        def serve(route):
            rel = route.request.url.split("https://render.local/", 1)[1].split("?", 1)[0]
            f = ROOT / rel
            if not f.is_file(): return route.fulfill(status=404, body="")
            route.fulfill(status=200, body=f.read_bytes(), headers={"content-type": mimetypes.guess_type(f.name)[0] or "application/octet-stream"})
        page.route("https://render.local/**", serve)
        page.on("console", lambda m: print("  [browser]", m.text) if m.type in ("error", "warning") else None)
        for p in items:
            for fmt, (w, h) in FORMATS.items():
                W, H = int(w * a.scale), int(h * a.scale)
                page.set_viewport_size({"width": W, "height": H})
                page.goto(f"https://render.local/render/scene.html?label=/{p['label']}&vial={p['vial']}&w={W}&h={H}&bg={a.bg}")
                page.wait_for_function("window.__done === true", timeout=120000)
                data = page.evaluate("window.__png").split(",", 1)[1]
                (outdir / f"{p['slug']}-{fmt}.png").write_bytes(base64.b64decode(data))
            print(f"rendered {p['slug']} ({p['status']})")
        browser.close()

if __name__ == "__main__":
    main()
