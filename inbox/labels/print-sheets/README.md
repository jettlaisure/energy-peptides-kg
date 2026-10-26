# Letter-size label print sheets (home printing)

Imposed from the approved masters in `../current-print/` for printing on 8.5 x 11 in full-sheet label paper.
Each sheet is 4 x 11 = 44 labels at 42 x 22 mm pitch; the master's 1 mm bleed fills the gutters, so cutting
on the grey hairlines gives a finished 40 x 20 mm label with navy to the edge.

Print at 100% / actual size (never "fit to page"), check the 40 mm scale bar with a ruler, then cut along the
hairlines with a guillotine or rotary cutter. Crop marks in the margins mark every cut line.

Regenerate or add a SKU:

    uv run --with pypdf --with reportlab python inbox/labels/print-sheets/make_sheet.py \
        inbox/labels/current-print/navy/<SKU>_navy.pdf inbox/labels/print-sheets/<SKU>_navy_letter-sheet.pdf "<title>"

Standard 40 x 20 mm labels only; NAD+ (44.2 x 22 mm) needs a different pitch.
