"""Photo composites: wrap each real label file onto real photos of the actual vials.
Base photos (inbox/photos, Jett 2026-09-13) were shot in one lightbox. v2 (same day, after Jett's review) uses the
BARE vial photos, so the label can be any real size and nothing of a blank label shows around it.
For each product: pick the bare photo for its vial type, wrap the label around the cylinder at a set physical size
(mm) and height, curve its top and bottom edges with the camera's real perspective (EXIF focal length), apply the
lightbox lighting measured from a white paper label, grade to the off-white studio tone, and frame every vial at
the same millimetre scale on the same floor line.
  uvx --with pillow --with numpy python render/composite.py [--only slug,...] [--debug]"""
import argparse, json, math, pathlib, sqlite3
import numpy as np
from PIL import Image, ImageOps

ROOT = pathlib.Path(__file__).resolve().parent.parent
PHOTOS = ROOT / "inbox" / "photos"
OUT_WEB = ROOT / "web" / "public" / "img" / "products"
OUT_RAW = ROOT / "render" / "out" / "photo"
LABEL_ASPECT = 1400 / 780            # label artwork width / height (wrap length / label height)
OUT_PX_PER_MM = 24.0                 # one scale for every product, so a 5 mL vial reads larger
FLOOR = 0.88                         # vial base sits at this fraction of the frame height
BG_TARGET = np.array([0xF1, 0xF0, 0xEC], np.float32)
SS = 3                               # supersampling per axis for the label (clean small type)

# Bare-vial photos, measured on gridded close-ups (full-resolution px after EXIF rotation).
#   body: glass silhouette x at label height; base: lowest point of the vial base (front); f35: EXIF 35 mm-equiv focal
#   label_mm: printed label height; mid_mm: label centre height above the base; u_max: furthest the label may turn
#   (label x facing the camera, 0..1) while its left end stays in view. Each label turns to centre its own text block.
BASES = {
    "3ml-white":  {"photo": "IMG_2444.jpeg", "body": (1936, 2314), "base": 3752, "body_mm": 16.0, "f35": 35, "label_mm": 16.5, "mid_mm": 13.5, "u_max": 0.36},
    "3ml-blue":   {"photo": "IMG_2439.jpeg", "body": (1801, 2195), "base": 3735, "body_mm": 16.0, "f35": 35, "label_mm": 16.5, "mid_mm": 13.5, "u_max": 0.36},
    "5ml-amber":  {"photo": "IMG_2435.jpeg", "body": (1902, 2264), "base": 3557, "body_mm": 20.1, "f35": 24, "label_mm": 22.0, "mid_mm": 18.5, "u_max": 0.36},
    "10ml-water": {"photo": "IMG_2448.jpeg", "body": (1758, 2325), "base": 4200, "body_mm": 20.0, "f35": 35, "label_mm": 22.0, "mid_mm": 20.0, "u_max": 0.36},
}
# lighting reference: NAD+'s white paper label facing the camera (IMG_2437), rows clear of its curved edges
SHADE_REF = {"photo": "IMG_2437.jpeg", "rows": (2885, 3360), "body": (1811, 2175)}

def srgb_to_lin(c): c = c / 255.0; return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def lin_to_srgb(c): c = np.clip(c, 0, 1); return 255.0 * np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)

def load(name):
    return np.asarray(ImageOps.exif_transpose(Image.open(PHOTOS / name)).convert("RGB")).astype(np.float32)

def grade(img, body, y_ref):
    """Neutral off-white studio tone: per-channel gains from the back wall beside the vial."""
    x0, x1 = body; w = x1 - x0; ya, yb = int(y_ref - 2.4 * w), int(y_ref - 1.6 * w)
    patch = np.concatenate([img[ya:yb, x0 - 3 * w:x0 - 2 * w].reshape(-1, 3), img[ya:yb, x1 + 2 * w:x1 + 3 * w].reshape(-1, 3)])
    return np.clip(img * (BG_TARGET / np.median(patch, axis=0)), 0, 255)

def shading_map():
    """Lighting on a white paper label in this lightbox, linear light, normalised; indexed by (v 0..1, s -1..1)."""
    (t, b), (l, r) = SHADE_REF["rows"], SHADE_REF["body"]
    img = grade(load(SHADE_REF["photo"]), (l, r), t)
    lab = srgb_to_lin(img[t:b, l:r]).mean(2)
    return lab / np.percentile(lab, 99.0)

def bilinear(img, xs, ys):
    h, w = img.shape[:2]
    xs = np.clip(xs, 0, w - 1.001); ys = np.clip(ys, 0, h - 1.001)
    x0 = np.floor(xs).astype(int); y0 = np.floor(ys).astype(int); fx = xs - x0; fy = ys - y0
    if img.ndim == 3: fx = fx[..., None]; fy = fy[..., None]
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy) + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)

def text_front(lab):
    """Label x (0..1) to face the camera: the centre of the text block, from its left margin to the end of the
    longer of the product name (white type) and the compliance line (ends at ~0.51 of the width in label v2)."""
    a = lab.astype(int); H, W, _ = a.shape; mx, mn = a.max(2), a.min(2)
    white = (mn > 205) & (mx - mn < 30); white[:, int(.8 * W):] = False
    cols = np.where(white.any(0))[0]
    if not len(cols): return 0.30
    return (cols[0] / W + max(cols[-1] / W, 0.51)) / 2

def geometry(base, img_h, u_front):
    """Label placement in photo pixels. A horizontal circle on the vial at image row y projects to an ellipse whose
    front point sits b(y) = R (y - yc) / f below its side points (camera level, optical centre mid-frame)."""
    g = BASES[base]; l, r = g["body"]; k = (r - l) / g["body_mm"]
    f = g["f35"] * math.hypot(4284, 5712) / 43.27; yc = img_h / 2; R = (r - l) / 2 + 1.0
    bow = lambda y: R * (y - yc) / f
    side0 = g["base"] - bow(g["base"])                       # base circle at the silhouette sides
    top = side0 - (g["mid_mm"] + g["label_mm"] / 2) * k
    bot = side0 - (g["mid_mm"] - g["label_mm"] / 2) * k
    arc = LABEL_ASPECT * g["label_mm"] / (g["body_mm"] / 2) # wrap angle of the label (radians)
    return {"cx": (l + r) / 2, "R": R, "top": top, "bot": bot, "bt": bow(top), "bb": bow(bot), "arc": arc, "u0": min(u_front, g["u_max"]), "k": k}

def composite(base, label_png, shade, debug=False):
    g = BASES[base]; img = load(g["photo"]); img = grade(img, g["body"], g["base"])
    lab = np.asarray(Image.open(label_png).convert("RGB")).astype(np.float32)
    G = geometry(base, img.shape[0], text_front(lab)); cx, R, arc, u0 = G["cx"], G["R"], G["arc"], G["u0"]
    X0, X1 = int(cx - R - 4), int(cx + R + 5); Y0 = int(G["top"] + min(G["bt"], 0) - 4); Y1 = int(G["bot"] + max(G["bb"], 0) + 5)
    # pre-filter the artwork to ~2 artwork px per photo px at the front of the vial
    lw = int(max(64, min(lab.shape[1], 2 * arc * R))); lab_img = Image.fromarray(lab.astype(np.uint8)).resize((lw, int(lw / LABEL_ASPECT)), Image.LANCZOS)
    lab = srgb_to_lin(np.asarray(lab_img).astype(np.float32))
    # supersampled pixel grid
    o = (np.arange(SS) + 0.5) / SS - 0.5
    yy, xx = np.mgrid[Y0:Y1, X0:X1].astype(np.float32)
    ys = (yy[..., None, None] + o[:, None]); xs = (xx[..., None, None] + o[None, :])
    ys, xs = np.broadcast_arrays(ys, xs)
    s = (xs - cx) / R; inside = np.abs(s) < 1
    sc = np.clip(s, -0.99999, 0.99999); c = np.sqrt(1 - sc ** 2)
    ytop = G["top"] + G["bt"] * c; ybot = G["bot"] + G["bb"] * c
    v = (ys - ytop) / (ybot - ytop)
    u = u0 + np.arcsin(sc) / arc
    cov = inside & (v >= 0) & (v <= 1) & (u >= 0) & (u <= 1)
    col = bilinear(lab, u * (lab.shape[1] - 1), np.clip(v, 0, 1) * (lab.shape[0] - 1))
    sh = bilinear(shade, (sc * 0.5 + 0.5) * (shade.shape[1] - 1), np.clip(v, 0, 1) * (shade.shape[0] - 1))
    sh = np.clip(sh, 0.25, 1.05) * 0.93                    # printed stock reflects a little less than bare paper
    lin = col * sh[..., None]
    prof = shade.mean(0); sx = (np.argmax(prof) / (shade.shape[1] - 1)) * 2 - 1
    spec = (0.07 * np.exp(-((sc - sx) / 0.12) ** 2) * (1 - 0.6 * np.abs(sc)))[..., None]
    lin = 1 - (1 - lin) * (1 - spec)
    # die-cut edge: the paper core catches a little light along the label's outline (~0.06 mm)
    d_edge = np.minimum.reduce([v * (ybot - ytop), (1 - v) * (ybot - ytop), u * arc * R * c + 9e9 * (u0 * arc > math.pi / 2)])
    lin = np.where((d_edge < 0.7)[..., None], lin * 0.8 + 0.12, lin)
    m = cov.mean((2, 3)); out = (lin * cov[..., None]).sum((2, 3)) / np.maximum(cov.sum((2, 3)), 1)[..., None]
    region = img[Y0:Y1, X0:X1]
    # the label's thickness leaves a faint contact shadow on the glass just past its visible end
    x_end = cx + R * math.sin(-u0 * arc) if u0 * arc < math.pi / 2 else None
    if x_end is not None:
        xr = np.arange(X0, X1, dtype=np.float32)[None, :]; rows = (yy >= G["top"] + G["bt"]) & (yy <= G["bot"] + G["bb"])
        shadow = 1 - 0.18 * np.exp(-np.clip(x_end - xr, 0, None) / 1.2) * (xr < x_end) * rows
        region = region * shadow[..., None]
    img[Y0:Y1, X0:X1] = region * (1 - m[..., None]) + lin_to_srgb(out) * m[..., None]
    return img, (X0, X1, Y0, Y1)

def frame(img, base, size):
    g = BASES[base]; k = OUT_PX_PER_MM / ((g["body"][1] - g["body"][0]) / g["body_mm"])   # output px per source px
    W, H = size; sw, sh = W / k, H / k; cx = (g["body"][0] + g["body"][1]) / 2
    x0 = cx - sw / 2; y0 = g["base"] - FLOOR * sh
    return Image.fromarray(img.astype(np.uint8)).crop((int(x0), int(y0), int(x0 + sw), int(y0 + sh))).resize(size, Image.LANCZOS)

def products():
    db = sqlite3.connect(ROOT / "data" / "graph.db"); db.row_factory = sqlite3.Row
    name = lambda nid: db.execute("SELECT name FROM nodes WHERE id=?", (nid,)).fetchone()["name"]
    out = []
    for p in db.execute("SELECT id, attrs FROM nodes WHERE type='Product'"):
        a = json.loads(p["attrs"])
        label = next((name(e["dst"]) for e in db.execute("SELECT dst FROM edges WHERE src=? AND rel='USES'", (p["id"],)) if name(e["dst"]).startswith("inbox/labels/")), None)
        if not label: continue
        comps = [json.loads(db.execute("SELECT attrs FROM nodes WHERE id=?", (c["dst"],)).fetchone()["attrs"]) for c in db.execute("SELECT dst FROM edges WHERE src=? AND rel='CONTAINS'", (p["id"],))]
        blue = any("blue" in (c.get("appearance") or "") for c in comps)
        base = "5ml-amber" if a.get("vial_glass") == "amber" else ("3ml-blue" if blue else "3ml-white")
        out.append({"slug": a["slug"], "label": ROOT / label, "base": base})
    return sorted(out, key=lambda x: x["slug"])

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--only"); ap.add_argument("--debug", help="write a 1:1 label close-up to this dir"); a = ap.parse_args()
    OUT_RAW.mkdir(parents=True, exist_ok=True); OUT_WEB.mkdir(parents=True, exist_ok=True)
    shade = shading_map()
    for p in products():
        if a.only and p["slug"] not in a.only.split(","): continue
        img, (X0, X1, Y0, Y1) = composite(p["base"], p["label"], shade)
        if a.debug:
            pad = 120; Image.fromarray(img[Y0 - pad:Y1 + pad, X0 - pad:X1 + pad].astype(np.uint8)).save(pathlib.Path(a.debug) / f"{p['slug']}-close.png")
        for fmt, size in (("square", (1600, 1600)), ("portrait", (1600, 2000))):
            im = frame(img, p["base"], size)
            im.save(OUT_RAW / f"{p['slug']}-{fmt}.png"); im.save(OUT_WEB / f"{p['slug']}-{fmt}.webp", "WEBP", quality=88, method=6)
        print("composited", p["slug"], "on", p["base"])

if __name__ == "__main__":
    main()
