"""Custom KiCad 7 footprint library (SIB.pretty), generated from package dimensions.

Land patterns follow the nominal IPC-7351-style values used by KiCad's own libraries for these
packages (pad position and size per package below). Courtyards add 0.25 mm around pads and body.
"""
from __future__ import annotations

from pathlib import Path

PITCH = 2.54


def _smd(num, x, y, w, h, rr=0.25):
    return (f'(pad "{num}" smd roundrect (at {x:g} {y:g}) (size {w:g} {h:g}) '
            f'(layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio {rr:g}))')


def _tht(num, x, y, square=False):
    shape = "rect" if square else "circle"
    return (f'(pad "{num}" thru_hole {shape} (at {x:g} {y:g}) (size 1.7 1.7) (drill 1) '
            f'(layers "*.Cu" "*.Mask"))')


def _bbox(pads):
    xs, ys = [], []
    for x, y, w, h in pads:
        xs += [x - w / 2, x + w / 2]
        ys += [y - h / 2, y + h / 2]
    return min(xs), min(ys), max(xs), max(ys)


def _footprint(name, descr, pad_txt, geom, body, attr="smd"):
    x0, y0, x1, y1 = _bbox(geom)
    bx, by = body
    x0, x1 = min(x0, -bx / 2), max(x1, bx / 2)
    y0, y1 = min(y0, -by / 2), max(y1, by / 2)
    m = 0.25
    cx0, cy0, cx1, cy1 = (round(v, 2) for v in (x0 - m, y0 - m, x1 + m, y1 + m))
    t = "(effects (font (size 0.8 0.8) (thickness 0.12)))"
    return f"""(footprint "{name}" (version 20221018) (generator sib_libgen) (layer "F.Cu")
  (descr "{descr}") (attr {attr})
  (fp_text reference "REF**" (at 0 {cy0 - 0.5:g}) (layer "F.SilkS") {t})
  (fp_text value "{name}" (at 0 {cy1 + 0.5:g}) (layer "F.Fab") {t})
  (fp_rect (start {-bx / 2:g} {-by / 2:g}) (end {bx / 2:g} {by / 2:g}) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))
  (fp_rect (start {cx0:g} {cy0:g}) (end {cx1:g} {cy1:g}) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))
  {chr(10).join("  " + p for p in pad_txt)}
)
"""


def chip(name, px, w, h, body):
    geom = [(-px, 0, w, h), (px, 0, w, h)]
    return _footprint(name, f"Chip {name}", [_smd(1, -px, 0, w, h), _smd(2, px, 0, w, h)], geom, body)


def sot23():
    g = [(-1.1375, -0.95, 1.325, 0.6), (-1.1375, 0.95, 1.325, 0.6), (1.1375, 0, 1.325, 0.6)]
    return _footprint("SOT-23", "SOT-23-3", [_smd(i + 1, x, y, w, h) for i, (x, y, w, h) in enumerate(g)], g, (1.4, 3.0))


def sot23_5():
    g = [(-1.1375, -0.95, 1.325, 0.6), (-1.1375, 0, 1.325, 0.6), (-1.1375, 0.95, 1.325, 0.6),
         (1.1375, 0.95, 1.325, 0.6), (1.1375, -0.95, 1.325, 0.6)]
    return _footprint("SOT-23-5", "SOT-23-5", [_smd(i + 1, x, y, w, h) for i, (x, y, w, h) in enumerate(g)], g, (1.6, 3.0))


def sot563():
    g = [(-0.75, -0.5, 0.6, 0.28), (-0.75, 0, 0.6, 0.28), (-0.75, 0.5, 0.6, 0.28),
         (0.75, 0.5, 0.6, 0.28), (0.75, 0, 0.6, 0.28), (0.75, -0.5, 0.6, 0.28)]
    return _footprint("SOT-563", "SOT-563 1.6x1.6 mm, 0.5 mm pitch",
                      [_smd(i + 1, x, y, w, h, 0.1) for i, (x, y, w, h) in enumerate(g)], g, (1.2, 1.6))


def soic8():
    g = [(-2.475, -1.905 + 1.27 * i, 1.95, 0.6) for i in range(4)] + \
        [(2.475, 1.905 - 1.27 * i, 1.95, 0.6) for i in range(4)]
    return _footprint("SOIC-8_3.9x4.9mm_P1.27mm", "SOIC-8 3.9 mm body",
                      [_smd(i + 1, x, y, w, h) for i, (x, y, w, h) in enumerate(g)], g, (3.9, 4.9))


def tqfp32():
    p, c, w, h = 0.8, 4.1625, 1.475, 0.55
    g = []
    for i in range(8):
        g.append((-c, -2.8 + p * i, w, h))      # pins 1-8, left, top to bottom
    for i in range(8):
        g.append((-2.8 + p * i, c, h, w))       # 9-16, bottom, left to right
    for i in range(8):
        g.append((c, 2.8 - p * i, w, h))        # 17-24, right, bottom to top
    for i in range(8):
        g.append((2.8 - p * i, -c, h, w))       # 25-32, top, right to left
    return _footprint("TQFP-32_7x7mm_P0.8mm", "TQFP-32 7x7 mm, 0.8 mm pitch",
                      [_smd(i + 1, x, y, ww, hh) for i, (x, y, ww, hh) in enumerate(g)], g, (7.0, 7.0))


def header(cols, rows, name):
    pads, geom, n = [], [], 1
    for r in range(rows):
        for col in range(cols):
            x, y = col * PITCH, r * PITCH
            pads.append(_tht(n, x, y, square=(n == 1)))
            geom.append((x, y, 1.7, 1.7))
            n += 1
    x0, y0, x1, y1 = _bbox(geom)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    # centre-referenced body for the outline helpers, pads stay at pin 1 = origin (KiCad convention)
    fp = _footprint(name, f"Pin header {cols}x{rows}, 2.54 mm", pads, geom, (0, 0), attr="through_hole")
    body = f'(fp_rect (start {x0 + 0.6:g} {y0 + 0.6:g}) (end {x1 - 0.6:g} {y1 - 0.6:g}) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))'
    return fp.replace('(fp_rect (start 0 0) (end 0 0) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))', body)


FOOTPRINTS = {
    "R_0603": lambda: chip("R_0603", 0.825, 0.8, 0.95, (1.6, 0.8)),
    "C_0603": lambda: chip("C_0603", 0.775, 0.9, 0.95, (1.6, 0.8)),
    "C_0805": lambda: chip("C_0805", 0.95, 1.0, 1.45, (2.0, 1.25)),
    "LED_0603": lambda: chip("LED_0603", 0.7875, 0.875, 0.95, (1.6, 0.8)),
    "D_SMA": lambda: chip("D_SMA", 2.0, 2.5, 1.7, (4.3, 2.6)),
    "SOT-23": sot23,
    "SOT-23-5": sot23_5,
    "SOT-563": sot563,
    "SOIC-8_3.9x4.9mm_P1.27mm": soic8,
    "TQFP-32_7x7mm_P0.8mm": tqfp32,
    "PinHeader_1x02_P2.54mm": lambda: header(1, 2, "PinHeader_1x02_P2.54mm"),
    "PinHeader_1x03_P2.54mm": lambda: header(1, 3, "PinHeader_1x03_P2.54mm"),
    "PinHeader_1x04_P2.54mm": lambda: header(1, 4, "PinHeader_1x04_P2.54mm"),
    "PinHeader_2x03_P2.54mm": lambda: header(2, 3, "PinHeader_2x03_P2.54mm"),
}


def write_library(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    for name, fn in FOOTPRINTS.items():
        (folder / f"{name}.kicad_mod").write_text(fn())
    return sorted(FOOTPRINTS)
