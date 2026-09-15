# Product images

## Primary: photo composites (since 2026-09-13)
Real photos of FSD's bare vials (`inbox/photos/`, one lightbox) with each label file wrapped around the cylinder at
its printed size. The label's top and bottom edges curve with the camera's real perspective (EXIF focal length), the
label is turned so neither end shows, and the lighting is measured from a white paper label in the same box.
```bash
uvx --with pillow --with numpy python render/composite.py            # all labelled SKUs -> web/public/img/products/*.webp
uvx --with pillow --with numpy python render/composite.py --only ghk-cu-50mg --debug /tmp   # plus a 1:1 label close-up
```
Bare base photo by vial type: 3 mL white powder (IMG_2444), 3 mL GHK-Cu blue powder (IMG_2439, also blends containing
GHK-Cu), 5 mL amber NAD+ (IMG_2435), bacteriostatic water (IMG_2448, no label file yet). Per base in `BASES`: glass
edges, base line, body diameter, label height (`label_mm`), label centre height (`mid_mm`) Labels are turned so both ends sit behind the
glass edge (`hidden_front`). The print files carry 12% extra navy before the text (1568×780, since 2026-09-13) so the
text reads cleanly at that angle; `--lead-in F --debug DIR` previews further lengthening without touching the site. Change those to resize or rotate labels; re-run after any label change. The labelled and
seam photos are reference only.

## Download bundle
`uv run python render/pack_photos.py` zips the site's WebP photos (square 1600², portrait 1600×2000) with a manifest of
SKU, status and alt text to `render/out/energy-peptides-product-photos.zip`, plus a copy in ~/Downloads. Re-run after
any re-render.

## Fallback: 3D renders

Consistent studio shots of every labelled SKU, generated from the real label files (`inbox/labels/`).
Same vial model, lens, rotation and lighting for every product; only the label and vial size (from the graph) change.
The vial follows ISO 8362-1 (2R: Ø16 × 35 mm, 13 mm finish; 6R: Ø22 × 40 mm, 20 mm finish) and was matched against the
photos of FSD's real vials on the Freedom certificates: tight shoulder, freeze-drying stopper visible in the neck, satin
silver seal, thin flip-off button. Add `&seal=gold` to the scene URL for a gold seal.

```bash
# 1. render at 2x (needs a Python with Playwright + its Chromium; the harness venv has both)
/Users/jettlaisure/context-catalog-harness/.venv/bin/python render/render.py            # all, off-white
/Users/jettlaisure/context-catalog-harness/.venv/bin/python render/render.py --only bpc-157-10mg --bg navy
# 2. downsample to site WebP (web/public/img/products/<slug>-square.webp, -portrait.webp) + contact sheet
uvx --with pillow python render/finish.py
# 3. rebuild + deploy the site (images are picked up by filename)
cd web && npm run deploy
```

Scene: `render/scene.html` (three.js, vendored in `render/vendor/`; never read it into AI context). Raw PNGs land in
`render/out/` (gitignored). Re-render after any label change. Products without a label file (bacteriostatic water)
keep the drawn vial on the site.
