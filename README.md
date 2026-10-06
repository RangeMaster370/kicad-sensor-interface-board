# SIB-1 sensor-interface board in KiCad

A small 2-layer board, designed in KiCad 7 and broken into four functional stages: (1) reverse-polarity protected 5 V input and 3.3 V LDO, (2) ATmega328P microcontroller with ISP and status LED, (3) ratiometric NTC front end with a Sallen–Key anti-alias filter, (4) I²C temperature sensor, calibration EEPROM, I²C and UART connectors. All symbols and footprints come from a custom library built for the board. The design is described once in `src/sib/design.py`; Python scripts generate the schematic, library, PCB and outputs with KiCad's own tools, and the tests check KiCad's exported netlist back against that description.

| Question | Method | Result (see `results/REPORT.md`) |
|---|---|---|
| Does the schematic say what the design says? | KiCad netlist export compared net-by-net with `design.py` | 0 differences over 22 nets and 15 no-connect pins |
| Would ERC flag anything? | ERC-style rules on the netlist (undriven power, single-pin nets, output conflicts) | 0 problems |
| Do symbols and footprints agree? | pin numbers vs pad numbers for all 36 placed parts | all match |
| Is the board manufacturable as drawn? | KiCad DRC (clearance 0.2 mm, edge 0.5 mm, courtyards, solder mask) | 0 errors, 0 warnings, 0 unconnected pads |
| How much routing? | Freerouting autorouter, GND pour on the bottom layer | 296 track segments, 35 vias, 698 mm of track |
| Why these parts? | component-selection table with requirement, choice, evidence, alternatives | 9 key parts, linked to the SPICE project results |

## Run

```sh
pip install -r requirements.txt   # plus KiCad 7, Java and Freerouting (see requirements.txt)
python3 -m unittest discover -s tests -v
python3 src/run_all.py            # regenerates hardware/ and results/ (about 40 s)
```

Open `hardware/sib.kicad_pro` in KiCad 7 or later to inspect or edit the schematic and PCB interactively.

## Structure

```
src/sib/design.py      parts, pin-to-net maps, stages, component-selection notes (single design source)
src/sib/symbols.py     custom symbol library (SIB.kicad_sym)
src/sib/footprints.py  custom footprint library (SIB.pretty) from package land-pattern dimensions
src/sib/schematic.py   hierarchical schematic: root + one sheet per functional stage
src/sib/checks.py      netlist comparison and ERC-style rules
src/sib/pcb.py         pcbnew placement by stage, Freerouting round trip, GND pour, DRC
src/run_all.py         full rebuild, Gerber/drill zip, BOM, renders, summary.json, REPORT.md
hardware/              KiCad project (schematic, PCB, library tables, library)
results/               schematic.pdf, BOM, component selection, DRC report, fabrication zip, plots
tests/                 13 checks
```

## Scope

Design and verification in KiCad only: the board has not been fabricated, assembled or bench-tested. Land patterns use nominal IPC-style dimensions for each package, and the autorouted layout favours completeness over hand-routed quality (see `docs/METHOD.md`). Companion projects: `sensor-frontend-spice-verification` (ngspice stage verification) and `avr-bringup-firmware-sim` (C bring-up firmware, simulated).
