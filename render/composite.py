"""Photo composites: wrap each real label file onto real photos of the actual vials.
Base photos (inbox/photos, Jett 2026-09-13) were shot in one lightbox with a blank label facing the camera.
For each product: pick the base photo for its vial type, map the label onto the blank label's area with
cylindrical geometry, apply the real lighting measured from a white paper label, grade to the off-white studio
tone, and frame every vial at the same millimetre scale.
  uvx --with pillow --with numpy python render/composite.py [--only slug,...]"""
import argparse, json, pathlib, sqlite3
import numpy as np
from PIL import Image, ImageOps, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parent.parent
PHOTOS = ROOT / "inbox" / "photos"
OUT_WEB = ROOT / "web" / "public" / "img" / "products"
OUT_RAW = ROOT / "render" / "out" / "photo"
U_CENTER = 0.315                    # label u facing the camera: name block front, label ends hidden behind the silhouette
LABEL_ASPECT = 1400 / 780
OUT_PX_PER_MM = 24.0                # one scale for every product, so a 5 mL vial reads larger
FLOOR = 0.88                        # vial base sits at this fraction of the frame height
BG_TARGET = np.array([0xF1, 0xF0, 0xEC], np.float32)

# measured on gridded close-ups (full-resolution pixels, after EXIF rotation); cap mm = seal finish size
BASES = {
    "3ml-white": {"photo": "IMG_2446.jpeg", "label": (3252, 3846), "body": (1794, 2233), "cap_px": 397, "cap_mm": 13, "body_mm": 16, "white_label": False},
    "3ml-blue":  {"photo": "IMG_2440.jpeg", "label": (2661, 3149), "body": (1818, 2193), "cap_px": 328, "cap_mm": 13, "body_mm": 16, "white_label": False},
    "5ml-amber": {"photo": "IMG_2437.jpeg", "label": (2869, 3378), "body": (1811, 2175), "cap_px": 362, "cap_mm": 20, "white_label": True},
    "10ml-water": {"photo": "IMG_2449.jpeg", "label": (3520, 4258), "body": (1849, 2401), "cap_px": 552, "cap_mm": 20, "white_label": True},
}
BASE_BOTTOM = {"3ml-white": 3902, "3ml-blue": 3220, "5ml-amber": 3495, "10ml-water": 4456}   # vial base line (px)

def srgb_to_lin(c): c = c / 255.0; return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def lin_to_srgb(c): c = np.clip(c, 0, 1); return 255.0 * np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)

def load(name):
    return np.asarray(ImageOps.exif_transpose(Image.open(PHOTOS / name)).convert("RGB")).astype(np.float32)

def grade(img, base):
    """Neutral off-white studio tone: per-channel gains from the back wall beside the vial."""
    b = BASES[base]; x0, x1 = b["body"]; y0 = b["label"][0]; w = x1 - x0
    patch = np.concatenate([img[y0 - 400:y0 - 100, x0 - 3 * w:x0 - 2 * w].reshape(-1, 3), img[y0 - 400:y0 - 100, x1 + 2 * w:x1 + 3 * w].reshape(-1, 3)])
    gains = BG_TARGET / np.median(patch, axis=0)
    return np.clip(img * gains, 0, 255)

def shading_map(base_img, base):
    """Lighting on a white paper label, normalised; indexed by (v in 0..1, s in -1..1)."""
    b = BASES[base]; (t, bt), (l, r) = b["label"], b["body"]
    lab = srgb_to_lin(base_img[t:bt, l:r]).mean(2)
    return lab / np.percentile(lab, 99.0)

def bilinear(img, xs, ys):
    h, w = img.shape[:2]
    xs = np.clip(xs, 0, w - 1.001); ys = np.clip(ys, 0, h - 1.001)
    x0 = np.floor(xs).astype(int); y0 = np.floor(ys).astype(int); fx = xs - x0; fy = ys - y0
    if img.ndim == 3: fx = fx[..., None]; fy = fy[..., None]
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy) + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)

def composite(base, label_png, shade_src):
    b = BASES[base]; img = grade(load(b["photo"]), base)
    (t, bt), (l, r) = b["label"], b["body"]
    pv, ph = 7, 2                                             # cover the blank label's own edge line (top/bottom)
    T, B, L, Rr = t - pv, bt + pv, l - ph, r + ph
    H, W = B - T, Rr - L; cx = (l + r) / 2; R = (r - l) / 2 + 1.0
    yy, xx = np.mgrid[T:B, L:Rr].astype(np.float32)
    s = np.clip((xx - cx) / R, -0.9999, 0.9999); theta = np.arcsin(s)
    arc = LABEL_ASPECT * (bt - t) / R                         # label wrap angle (radians)
    u = U_CENTER + theta / arc; v = (yy - t) / (bt - t)
    lab = np.asarray(Image.open(label_png).convert("RGB")).astype(np.float32)
    col = bilinear(lab, u * (lab.shape[1] - 1), v * (lab.shape[0] - 1))
    # real lighting from a white paper label (same lightbox), resampled into this label's box
    sh = shade_src; shh, shw = sh.shape
    shade = bilinear(sh, (s * 0.5 + 0.5) * (shw - 1), np.clip(v, 0, 1) * (shh - 1))
    shade = np.clip(shade, 0.25, 1.05) * 0.93                 # printed stock reflects a little less than bare paper
    lin = srgb_to_lin(col) * shade[..., None]
    # soft satin highlight where the lightbox is brightest on the label
    prof = sh.mean(0); sx = (np.argmax(prof) / (shw - 1)) * 2 - 1
    spec = 0.07 * np.exp(-((s - sx) / 0.12) ** 2)[..., None] * (1 - 0.6 * np.abs(s[..., None]))
    lin = 1 - (1 - lin) * (1 - spec)
    out = lin_to_srgb(lin)
    # feathered mask: full inside the blank label, soft 1.5 px edge
    ramp = lambda d: np.clip(d / 1.5, 0, 1)
    edge = (r - l) / 2 + 0.5                                  # never paint outside the glass silhouette
    m = ramp(yy - T) * ramp(B - 1 - yy) * ramp(edge - np.abs(xx - cx) + 0.5)
    v = np.clip(v, 0, 1)
    region = img[T:B, L:Rr]
    img[T:B, L:Rr] = region * (1 - m[..., None]) + out * m[..., None]
    return img

def frame(img, base, size):
    b = BASES[base]
    src_px_per_mm = (b["body"][1] - b["body"][0]) / b["body_mm"] if b.get("body_mm") else b["cap_px"] / b["cap_mm"]   # ISO 2R body is 16.0 mm
    k = OUT_PX_PER_MM / src_px_per_mm                                  # output px per source px
    W, H = size; sw, sh = W / k, H / k
    cx = (b["body"][0] + b["body"][1]) / 2; floor_y = BASE_BOTTOM[base]
    x0 = cx - sw / 2; y0 = floor_y - FLOOR * sh
    crop = Image.fromarray(img.astype(np.uint8)).crop((int(x0), int(y0), int(x0 + sw), int(y0 + sh)))
    return crop.resize(size, Image.LANCZOS)

def products():
    db = sqlite3.connect(ROOT / "data" / "graph.db"); db.row_factory = sqlite3.Row
    out = []
    for p in db.execute("SELECT id, attrs FROM nodes WHERE type='Product'"):
        a = json.loads(p["attrs"])
        label = next((db.execute("SELECT name FROM nodes WHERE id=?", (e["dst"],)).fetchone()["name"] for e in db.execute("SELECT dst FROM edges WHERE src=? AND rel='USES'", (p["id"],))
                      if db.execute("SELECT name FROM nodes WHERE id=?", (e["dst"],)).fetchone()["name"].startswith("inbox/labels/")), None)
        if not label: continue
        comps = [json.loads(db.execute("SELECT attrs FROM nodes WHERE id=?", (c["dst"],)).fetchone()["attrs"]) for c in db.execute("SELECT dst FROM edges WHERE src=? AND rel='CONTAINS'", (p["id"],))]
        blue = any("blue" in (c.get("appearance") or "") for c in comps)
        base = "5ml-amber" if a.get("vial_glass") == "amber" else ("3ml-blue" if blue else "3ml-white")
        out.append({"slug": a["slug"], "label": ROOT / label, "base": base})
    return sorted(out, key=lambda x: x["slug"])

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--only"); a = ap.parse_args()
    OUT_RAW.mkdir(parents=True, exist_ok=True); OUT_WEB.mkdir(parents=True, exist_ok=True)
    shade_src = shading_map(grade(load(BASES["5ml-amber"]["photo"]), "5ml-amber"), "5ml-amber")
    for p in products():
        if a.only and p["slug"] not in a.only.split(","): continue
        img = composite(p["base"], p["label"], shade_src if not BASES[p["base"]]["white_label"] or p["base"] != "5ml-amber" else shade_src)
        for fmt, size in (("square", (1600, 1600)), ("portrait", (1600, 2000))):
            im = frame(img, p["base"], size)
            im.save(OUT_RAW / f"{p['slug']}-{fmt}.png"); im.save(OUT_WEB / f"{p['slug']}-{fmt}.webp", "WEBP", quality=88, method=6)
        print("composited", p["slug"], "on", p["base"])

if __name__ == "__main__":
    main()
