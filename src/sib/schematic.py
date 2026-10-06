"""Generate the hierarchical KiCad 7 schematic: a root sheet plus one sheet per functional stage.

Each pin gets a short wire stub ending in a net label (local within a stage, global between
stages) or a no-connect marker. KiCad's own netlist export is then compared with design.py.
"""
from __future__ import annotations

import math
import uuid
from pathlib import Path

from . import design, symbols

NS = uuid.UUID("5b1a1d1e-0000-4000-8000-0000000051b1")
PROJECT = "sib"
G = 1.27
STUB = 2.54
FONT = "(effects (font (size 1.27 1.27)))"
HIDE = "(effects (font (size 1.27 1.27)) hide)"


def uid(*key) -> str:
    return str(uuid.uuid5(NS, "/".join(map(str, key))))


def snap(v: float) -> float:
    return round(round(v / G) * G, 4)


ROOT_UUID = uid("root")
SHEET_UUID = {name: uid("sheet", name) for name, _ in design.SHEETS}


class SheetWriter:
    def __init__(self, sheet: str, syms: dict):
        self.sheet, self.syms, self.items, self.used = sheet, syms, [], {}

    def wire(self, a, b):
        self.items.append(f'(wire (pts (xy {a[0]:g} {a[1]:g}) (xy {b[0]:g} {b[1]:g})) '
                          f'(stroke (width 0) (type default)) (uuid {uid(self.sheet, "w", a, b)}))')

    def label(self, net, at, out):
        ang, just = {(-1, 0): (180, "right"), (1, 0): (0, "left"), (0, -1): (90, "left"), (0, 1): (270, "right")}[out]
        if net in design.GLOBAL_NETS:
            self.items.append(
                f'(global_label "{net}" (shape bidirectional) (at {at[0]:g} {at[1]:g} {ang}) (fields_autoplaced) '
                f'(effects (font (size 1.27 1.27)) (justify {just})) (uuid {uid(self.sheet, "gl", net, at)}) '
                f'(property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {at[0]:g} {at[1]:g} 0) {HIDE}))')
        else:
            self.items.append(f'(label "{net}" (at {at[0]:g} {at[1]:g} {ang}) (fields_autoplaced) '
                              f'(effects (font (size 1.27 1.27)) (justify {just} bottom)) '
                              f'(uuid {uid(self.sheet, "l", net, at)}))')

    def no_connect(self, at):
        self.items.append(f'(no_connect (at {at[0]:g} {at[1]:g}) (uuid {uid(self.sheet, "nc", at)}))')

    def place(self, part: design.Part, sx: float, sy: float):
        _, pin_pos = self.syms[part.symbol]
        self.used[part.symbol] = True
        ys = [-p[1] for p in pin_pos.values()]
        top = sy + min(ys) - 2 * G
        props = [("Reference", part.ref, (sx, snap(top - G)), part.ref.startswith("#")),
                 ("Value", part.value, (sx, snap(sy + max(ys) + 2 * G)), False),
                 ("Footprint", f"SIB:{part.footprint}" if part.footprint else "", (sx, sy), True),
                 ("Datasheet", "", (sx, sy), True),
                 ("MPN", part.mpn, (sx, sy), True)]
        if len(pin_pos) == 2 and part.symbol != "Conn_01x02":
            props[0] = ("Reference", part.ref, (snap(sx + 2.54), snap(sy - G)), part.ref.startswith("#"))
            props[1] = ("Value", part.value, (snap(sx + 2.54), snap(sy + G)), False)
        ptxt = " ".join(
            f'(property "{k}" "{v}" (at {x:g} {y:g} 0) '
            f'{HIDE if hidden else ("(effects (font (size 1.27 1.27)) (justify left))" if len(pin_pos) == 2 and k in ("Reference", "Value") and part.symbol != "Conn_01x02" else FONT)})'
            for k, v, (x, y), hidden in props)
        pins = " ".join(f'(pin "{n}" (uuid {uid(self.sheet, part.ref, "pin", n)}))' for n in pin_pos)
        in_bom = "yes" if part.in_bom else "no"
        on_board = "no" if part.ref.startswith("#") else "yes"
        self.items.append(
            f'(symbol (lib_id "SIB:{part.symbol}") (at {sx:g} {sy:g} 0) (unit 1) (in_bom {in_bom}) '
            f'(on_board {on_board}) (dnp no) (fields_autoplaced) (uuid {uid(self.sheet, part.ref)}) {ptxt} {pins} '
            f'(instances (project "{PROJECT}" (path "/{ROOT_UUID}/{SHEET_UUID[self.sheet]}" '
            f'(reference "{part.ref}") (unit 1)))))')
        for num, (px, py, ang) in pin_pos.items():
            end = (snap(sx + px), snap(sy - py))
            out = (-round(math.cos(math.radians(ang))), round(math.sin(math.radians(ang))))
            net = part.pins.get(num)
            if net is None:
                self.no_connect(end)
                continue
            tip = (snap(end[0] + out[0] * STUB), snap(end[1] + out[1] * STUB))
            self.wire(end, tip)
            self.label(net, tip, out)

    def text(self, s, at, size=2.0):
        self.items.append(f'(text "{s}" (at {at[0]:g} {at[1]:g} 0) '
                          f'(effects (font (size {size:g} {size:g}) bold) (justify left bottom)) '
                          f'(uuid {uid(self.sheet, "t", s)}))')

    def render(self, title: str) -> str:
        lib = "\n    ".join(symbols.all_symbols(prefix="SIB:")[n][0] for n in sorted(self.used))
        return (f'(kicad_sch (version 20230121) (generator sib_schgen)\n  (uuid {SHEET_UUID[self.sheet]})\n'
                f'  (paper "A4")\n  (title_block (title "SIB-1 sensor-interface board") (comment 1 "{title}"))\n'
                f'  (lib_symbols\n    {lib}\n  )\n  ' + "\n  ".join(self.items) + "\n)\n")


def _extent(pin_pos):
    xs = [p[0] for p in pin_pos.values()]
    ys = [-p[1] for p in pin_pos.values()]
    return min(xs), max(xs), min(ys), max(ys)


def layout_sheet(sheet: str, title: str, syms) -> str:
    w = SheetWriter(sheet, syms)
    w.text(title, (15.24, 22.86), 2.5)
    x, y, row_h = 15.24, 30.48, 0.0
    x_max = 270.0
    for part in [p for p in design.PARTS if p.sheet == sheet]:
        x0, x1, y0, y1 = _extent(syms[part.symbol][1])
        width = (x1 - x0) + 2 * 22.86            # room for labels on both sides
        height = (y1 - y0) + 43.18              # stubs plus vertical labels above and below
        if x + width > x_max:
            x, y, row_h = 15.24, y + row_h, 0.0
        sx, sy = snap(x - x0 + 22.86), snap(y - y0 + 20.32)
        w.place(part, sx, sy)
        x += width
        row_h = max(row_h, height)
    return w.render(title)


def root_sheet() -> str:
    items = []
    for i, (name, title) in enumerate(design.SHEETS):
        x, y = 50.8 + (i % 2) * 127.0, 63.5 + (i // 2) * 76.2
        items.append(
            f'(sheet (at {x:g} {y:g}) (size 101.6 50.8) (fields_autoplaced) (stroke (width 0.1524) (type solid)) '
            f'(fill (color 0 0 0 0.0000)) (uuid {SHEET_UUID[name]}) '
            f'(property "Sheetname" "{title}" (at {x:g} {y - 0.7:g} 0) (effects (font (size 1.27 1.27)) (justify left bottom))) '
            f'(property "Sheetfile" "{name}.kicad_sch" (at {x:g} {y + 51.4:g} 0) (effects (font (size 1.27 1.27)) (justify left top))) '
            f'(instances (project "{PROJECT}" (path "/{ROOT_UUID}" (page "{i + 2}")))))')
    note = ("(text \"Functional stages: power -> MCU -> analog front end -> interfaces. Stages connect through global "
            f"labels (GND, +3V3, VIN, VMON, ADC_NTC, SDA, SCL, UART_TX, UART_RX).\" (at 50.8 40.64 0) "
            f"(effects (font (size 1.778 1.778)) (justify left bottom)) (uuid {uid('root', 'note')}))")
    return (f'(kicad_sch (version 20230121) (generator sib_schgen)\n  (uuid {ROOT_UUID})\n  (paper "A4")\n'
            f'  (title_block (title "SIB-1 sensor-interface board") (date "2026-10-06") (rev "A") '
            f'(comment 1 "Generated from src/sib/design.py"))\n  (lib_symbols)\n  {note}\n  '
            + "\n  ".join(items) + '\n  (sheet_instances (path "/" (page "1")))\n)\n')


def write(folder: Path):
    syms = symbols.all_symbols()
    (folder / f"{PROJECT}.kicad_sch").write_text(root_sheet())
    for name, title in design.SHEETS:
        (folder / f"{name}.kicad_sch").write_text(layout_sheet(name, title, syms))
    (folder / "sym-lib-table").write_text(
        '(sym_lib_table\n  (lib (name "SIB")(type "KiCad")(uri "${KIPRJMOD}/lib/SIB.kicad_sym")(options "")(descr "SIB-1 custom symbols"))\n)\n')
    (folder / "fp-lib-table").write_text(
        '(fp_lib_table\n  (lib (name "SIB")(type "KiCad")(uri "${KIPRJMOD}/lib/SIB.pretty")(options "")(descr "SIB-1 custom footprints"))\n)\n')
