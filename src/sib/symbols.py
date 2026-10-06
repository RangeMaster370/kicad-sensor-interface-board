"""Custom KiCad 7 symbol library (SIB.kicad_sym).

Two-pin parts get compact vertical symbols; ICs and connectors get rectangular bodies with pins
on the left and right. All pin ends sit on the 1.27 mm grid.
"""
from __future__ import annotations

G = 1.27
FONT = "(effects (font (size 1.27 1.27)))"
HIDE = "(effects (font (size 1.27 1.27)) hide)"

# name -> (pins [(number, name, type, side)], ref prefix, description)
# side: L/R for rectangular symbols; T/B for two-pin vertical symbols
IC = {
    "MCP1700-3302": ([("3", "VIN", "power_in", "L"), ("1", "GND", "power_in", "L"), ("2", "VOUT", "power_out", "R")],
                     "U", "3.3 V 250 mA LDO regulator, SOT-23"),
    "MCP6001": ([("3", "+", "input", "L"), ("4", "-", "input", "L"), ("5", "V+", "power_in", "L"),
                 ("2", "V-", "power_in", "L"), ("1", "OUT", "output", "R")], "U", "1 MHz rail-to-rail op-amp, SOT-23-5"),
    "TMP102": ([("5", "V+", "power_in", "L"), ("2", "GND", "power_in", "L"), ("4", "ADD0", "input", "L"),
                ("6", "SDA", "bidirectional", "R"), ("1", "SCL", "input", "R"), ("3", "ALERT", "open_collector", "R")],
               "U", "I2C digital temperature sensor, SOT-563"),
    "24LC02": ([("8", "VCC", "power_in", "L"), ("4", "VSS", "power_in", "L"), ("1", "A0", "input", "L"),
                ("2", "A1", "input", "L"), ("3", "A2", "input", "L"), ("7", "WP", "input", "L"),
                ("5", "SDA", "bidirectional", "R"), ("6", "SCL", "input", "R")], "U", "2 kbit I2C EEPROM, SOIC-8"),
    "ATmega328P-AU": ([
        ("4", "VCC", "power_in", "L"), ("6", "VCC", "power_in", "L"), ("18", "AVCC", "power_in", "L"),
        ("20", "AREF", "passive", "L"), ("3", "GND", "power_in", "L"), ("5", "GND", "power_in", "L"),
        ("21", "GND", "power_in", "L"), ("29", "PC6/~{RESET}", "input", "L"), ("7", "PB6/XTAL1", "bidirectional", "L"),
        ("8", "PB7/XTAL2", "bidirectional", "L"), ("19", "ADC6", "input", "L"), ("22", "ADC7", "input", "L"),
        ("12", "PB0", "bidirectional", "L"), ("13", "PB1", "bidirectional", "L"), ("14", "PB2", "bidirectional", "L"),
        ("15", "PB3/MOSI", "bidirectional", "L"),
        ("16", "PB4/MISO", "bidirectional", "R"), ("17", "PB5/SCK", "bidirectional", "R"),
        ("23", "PC0/ADC0", "bidirectional", "R"), ("24", "PC1/ADC1", "bidirectional", "R"),
        ("25", "PC2/ADC2", "bidirectional", "R"), ("26", "PC3/ADC3", "bidirectional", "R"),
        ("27", "PC4/SDA", "bidirectional", "R"), ("28", "PC5/SCL", "bidirectional", "R"),
        ("30", "PD0/RXD", "bidirectional", "R"), ("31", "PD1/TXD", "bidirectional", "R"),
        ("32", "PD2", "bidirectional", "R"), ("1", "PD3", "bidirectional", "R"), ("2", "PD4", "bidirectional", "R"),
        ("9", "PD5", "bidirectional", "R"), ("10", "PD6", "bidirectional", "R"), ("11", "PD7", "bidirectional", "R")],
        "U", "8-bit AVR microcontroller, 32 KB flash, TQFP-32"),
    "Conn_01x02": ([("1", "Pin_1", "passive", "L"), ("2", "Pin_2", "passive", "L")], "J", "1x02 connector"),
    "Conn_01x03": ([("1", "Pin_1", "passive", "L"), ("2", "Pin_2", "passive", "L"), ("3", "Pin_3", "passive", "L")],
                   "J", "1x03 connector"),
    "Conn_01x04": ([(str(i), f"Pin_{i}", "passive", "L") for i in range(1, 5)], "J", "1x04 connector"),
    "Conn_02x03_ISP": ([("1", "MISO", "passive", "L"), ("3", "SCK", "passive", "L"), ("5", "~{RST}", "passive", "L"),
                        ("2", "VCC", "passive", "R"), ("4", "MOSI", "passive", "R"), ("6", "GND", "passive", "R")],
                       "J", "AVR ISP 2x03 header"),
}

TWO_PIN = {  # name -> (ref prefix, pin1 name, pin2 name, description, body)
    "R": ("R", "~", "~", "Resistor", "rect"),
    "C": ("C", "~", "~", "Capacitor", "cap"),
    "Thermistor_NTC": ("RT", "~", "~", "NTC thermistor", "rect"),
    "LED": ("D", "K", "A", "Light-emitting diode (pin 1 cathode)", "diode"),
    "D_Schottky": ("D", "K", "A", "Schottky diode (pin 1 cathode)", "diode"),
}


def _pin(num, name, typ, x, y, angle, length=2.54, hide_name=False):
    nm = f'(name "{name}" {HIDE if hide_name else FONT})'
    return (f'(pin {typ} line (at {x:g} {y:g} {angle}) (length {length:g}) {nm} '
            f'(number "{num}" {FONT}))')


def _props(name, ref, value, desc, fp, y_top, y_bot, power=False):
    vis = HIDE if power else FONT
    return (f'(property "Reference" "{ref}" (at 0 {y_top + 2 * G:g} 0) {vis})'
            f'(property "Value" "{value}" (at 0 {y_bot - 2 * G:g} 0) {FONT})'
            f'(property "Footprint" "{fp}" (at 0 0 0) {HIDE})'
            f'(property "Datasheet" "" (at 0 0 0) {HIDE})'
            f'(property "Description" "{desc}" (at 0 0 0) {HIDE})')


def ic_symbol(name, prefix="") -> tuple[str, dict]:
    pins, ref, desc = IC[name]
    left = [p for p in pins if p[3] == "L"]
    right = [p for p in pins if p[3] == "R"]
    rows = max(len(left), len(right))
    half_w = 10.16 if name.startswith("ATmega") else (7.62 if not name.startswith("Conn") else 3.81)
    y0 = ((rows - 1) // 2) * 2 * G
    body_top, body_bot = y0 + 2 * G, y0 - (rows - 1) * 2 * G - 2 * G
    graphics = (f'(rectangle (start {-half_w:g} {body_top:g}) (end {half_w:g} {body_bot:g}) '
                f'(stroke (width 0.254) (type default)) (fill (type background)))')
    pin_txt, pin_pos = [], {}
    for i, (num, pname, typ, _) in enumerate(left):
        y = round(y0 - i * 2 * G, 2)
        x = -half_w - 2.54
        pin_txt.append(_pin(num, pname, typ, x, y, 0))
        pin_pos.setdefault(num, (x, y, 0))
    for i, (num, pname, typ, _) in enumerate(right):
        y = round(y0 - i * 2 * G, 2)
        x = half_w + 2.54
        pin_txt.append(_pin(num, pname, typ, x, y, 180))
        pin_pos.setdefault(num, (x, y, 180))
    sym = (f'(symbol "{prefix}{name}" (in_bom yes) (on_board yes) '
           f'{_props(name, ref, name, desc, "", body_top, body_bot)}'
           f'(symbol "{name}_0_1" {graphics})(symbol "{name}_1_1" {" ".join(pin_txt)}))')
    return sym, pin_pos


def two_pin_symbol(name, prefix="") -> tuple[str, dict]:
    ref, n1, n2, desc, body = TWO_PIN[name]
    if body == "rect":
        g = '(rectangle (start -1.016 2.54) (end 1.016 -2.54) (stroke (width 0.254) (type default)) (fill (type none)))'
        if name.startswith("Thermistor"):
            g += '(polyline (pts (xy -2.032 -2.032) (xy 2.032 2.032)) (stroke (width 0.2) (type default)) (fill (type none)))'
    elif body == "cap":
        g = ('(polyline (pts (xy -2.032 0.762) (xy 2.032 0.762)) (stroke (width 0.508) (type default)) (fill (type none)))'
             '(polyline (pts (xy -2.032 -0.762) (xy 2.032 -0.762)) (stroke (width 0.508) (type default)) (fill (type none)))')
    else:  # diode, cathode (pin 1) at the top
        g = ('(polyline (pts (xy -1.27 1.27) (xy 1.27 1.27)) (stroke (width 0.254) (type default)) (fill (type none)))'
             '(polyline (pts (xy -1.27 -1.27) (xy 1.27 -1.27) (xy 0 1.27) (xy -1.27 -1.27)) '
             '(stroke (width 0.254) (type default)) (fill (type none)))')
    ln = {"rect": 1.27, "cap": 3.048, "diode": 2.54}[body]
    pins = [_pin("1", n1, "passive", 0, 3.81, 270, ln, hide_name=True),
            _pin("2", n2, "passive", 0, -3.81, 90, ln, hide_name=True)]
    sym = (f'(symbol "{prefix}{name}" (pin_numbers hide) (pin_names (offset 0) hide) (in_bom yes) (on_board yes) '
           f'{_props(name, ref, name, desc, "", 1.27, -1.27)}'
           f'(symbol "{name}_0_1" {g})(symbol "{name}_1_1" {" ".join(pins)}))')
    return sym, {"1": (0, 3.81, 270), "2": (0, -3.81, 90)}


def pwr_flag_symbol(prefix="") -> tuple[str, dict]:
    g = ('(polyline (pts (xy 0 0) (xy 0 1.27) (xy -1.016 1.905) (xy 0 2.54) (xy 1.016 1.905) (xy 0 1.27)) '
         '(stroke (width 0) (type default)) (fill (type none)))')
    sym = (f'(symbol "{prefix}PWR_FLAG" (power) (pin_numbers hide) (pin_names (offset 0) hide) (in_bom no) (on_board yes) '
           f'(property "Reference" "#FLG" (at 0 1.905 0) {HIDE})(property "Value" "PWR_FLAG" (at 0 3.81 0) {FONT})'
           f'(property "Footprint" "" (at 0 0 0) {HIDE})(property "Datasheet" "" (at 0 0 0) {HIDE})'
           f'(symbol "PWR_FLAG_0_0" {_pin("1", "pwr", "power_out", 0, 0, 90, 0)})(symbol "PWR_FLAG_0_1" {g}))')
    return sym, {"1": (0, 0, 90)}


def all_symbols(prefix=""):
    out = {}
    for n in IC:
        out[n] = ic_symbol(n, prefix)
    for n in TWO_PIN:
        out[n] = two_pin_symbol(n, prefix)
    out["PWR_FLAG"] = pwr_flag_symbol(prefix)
    return out


def write_library(path):
    syms = all_symbols()
    body = "\n  ".join(s for s, _ in syms.values())
    path.write_text(f"(kicad_symbol_lib (version 20220914) (generator sib_libgen)\n  {body}\n)\n")
    return sorted(syms)
