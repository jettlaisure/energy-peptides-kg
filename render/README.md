# Product renders

Consistent studio shots of every labelled SKU, generated from the real label files (`inbox/labels/`).
Same vial model, lens, rotation and lighting for every product; only the label and vial size (from the graph) change.

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
