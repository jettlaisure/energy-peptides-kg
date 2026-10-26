"""Impose a 40 x 20 mm vial label (42 x 22 mm with bleed) on US Letter for home printing.

Usage:  uv run --with pypdf --with reportlab python make_sheet.py navy/BPC-157-10mg_navy.pdf out.pdf

Grid: 4 columns x 11 rows = 44 labels, pitch 42 x 22 mm so each label's 1 mm bleed
fills the gutter. Cut on the grey hairlines (gutter centres); the trim is 40 x 20 mm.
Print at 100% / actual size, never "fit to page".
"""
import io, sys
from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import letter

src, out = sys.argv[1], sys.argv[2]
label_name = sys.argv[3] if len(sys.argv) > 3 else src

PW, PH = letter                      # 612 x 792 pt
COLS, ROWS = 4, 11
PITCH_W, PITCH_H = 42 * mm, 22 * mm  # bleed-to-bleed pitch
GRID_W, GRID_H = COLS * PITCH_W, ROWS * PITCH_H
X0 = (PW - GRID_W) / 2
Y0 = (PH - GRID_H) / 2 - 2 * mm      # nudge down to leave room for the header
BLEED = 1 * mm

lab = PdfReader(src).pages[0]
assert abs(float(lab.mediabox.width) - 42 * mm) < 0.5 and abs(float(lab.mediabox.height) - 22 * mm) < 0.5, "expected 42 x 22 mm bleed page"

# --- base layer: header, scale check, crop marks ------------------------------
buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=letter)
c.setFont("Helvetica-Bold", 9)
c.drawString(X0, PH - 10 * mm, f"Energy Peptides — {label_name}")
c.setFont("Helvetica", 7)
c.drawString(X0, PH - 14 * mm, "Print at 100% (actual size), not 'fit to page'. Cut on the grey hairlines; finished label 40 x 20 mm. "
             f"{COLS * ROWS} per sheet.")
# 40 mm scale check, top right
sx = X0 + GRID_W - 40 * mm; sy = PH - 11.5 * mm
c.setLineWidth(0.4); c.line(sx, sy, sx + 40 * mm, sy)
c.line(sx, sy - 1.5 * mm, sx, sy + 1.5 * mm); c.line(sx + 40 * mm, sy - 1.5 * mm, sx + 40 * mm, sy + 1.5 * mm)
c.setFont("Helvetica", 6); c.drawCentredString(sx + 20 * mm, sy + 2 * mm, "40 mm scale check")

# crop marks in the margins at every cut line
c.setLineWidth(0.25); c.setStrokeGray(0)
GAP, LEN = 1.5 * mm, 4 * mm
xcuts = [X0 + BLEED] + [X0 + i * PITCH_W for i in range(1, COLS)] + [X0 + GRID_W - BLEED]
ycuts = [Y0 + BLEED] + [Y0 + j * PITCH_H for j in range(1, ROWS)] + [Y0 + GRID_H - BLEED]
for x in xcuts:
    c.line(x, Y0 - GAP, x, Y0 - GAP - LEN); c.line(x, Y0 + GRID_H + GAP, x, Y0 + GRID_H + GAP + LEN)
for y in ycuts:
    c.line(X0 - GAP, y, X0 - GAP - LEN, y); c.line(X0 + GRID_W + GAP, y, X0 + GRID_W + GAP + LEN, y)
c.showPage(); c.save()
base = PdfReader(io.BytesIO(buf.getvalue())).pages[0]

# --- labels -------------------------------------------------------------------
for j in range(ROWS):
    for i in range(COLS):
        base.merge_transformed_page(lab, Transformation().translate(X0 + i * PITCH_W, Y0 + j * PITCH_H))

# --- overlay: hairline cut guides through the gutters (inside the bleed only) --
buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=letter)
c.setLineWidth(0.2); c.setStrokeGray(0.65)
for x in xcuts:
    c.line(x, Y0, x, Y0 + GRID_H)
for y in ycuts:
    c.line(X0, y, X0 + GRID_W, y)
c.showPage(); c.save()
base.merge_page(PdfReader(io.BytesIO(buf.getvalue())).pages[0])

w = PdfWriter(); w.add_page(base); w.write(out)
print(f"wrote {out}: {COLS}x{ROWS} = {COLS*ROWS} labels, grid origin ({X0/mm:.1f}, {Y0/mm:.1f}) mm")
