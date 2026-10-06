# Method and assumptions

## Functional stages
| Stage | Function | Main parts |
|---|---|---|
| 1 Power | 5 V input, Schottky reverse-polarity protection, 3.3 V LDO, supply monitor divider (VIN/3 to ADC1), power LED | J1, D1 (SS14), U1 (MCP1700-3302), R1/R2 |
| 2 MCU | ATmega328P-AU on the internal 8 MHz oscillator, decoupling on each supply pin, reset pull-up, ISP header, status LED | U2, C3–C6, R4, J3, D3 |
| 3 Analog | 10 kΩ NTC divider referenced to AVCC, unity-gain Sallen–Key low-pass (15 k/15 k/1.5 µ/680 n), 100 Ω + 10 nF at ADC0 | RT1, R6–R9, C7, C8, C10, U3 (MCP6001) |
| 4 Interfaces | TMP102 at I²C 0x48, 24LC02 EEPROM at 0x50 (WP to GND), 4.7 kΩ pull-ups, I²C and UART headers | U4, U5, R10, R11, J4, J5 |

Stages are separate schematic sheets joined by global labels (GND, +3V3, VIN, VMON, ADC_NTC, SDA, SCL, UART_TX, UART_RX); nets inside a stage use local labels.

## Library
- **Symbols (15)**: rectangular IC and connector symbols with typed pins (power_in, power_out, input, output, bidirectional, open collector); compact two-pin symbols for passives, diodes and the NTC; a PWR_FLAG symbol.
- **Footprints (14)**: 0603/0805 chips, SMA, SOT-23, SOT-23-5, SOT-563, SOIC-8, TQFP-32 (0.8 mm) and 2.54 mm headers. Pad positions and sizes follow the nominal values KiCad's standard libraries use for these packages; courtyards add 0.25 mm.

## Checks
1. **Netlist vs design**: KiCad's exported netlist must contain exactly the nets and pins of `design.py`, and only the intended no-connect pins.
2. **ERC-style rules** (KiCad 7's command line has no ERC): every net with power-input pins has a power output or PWR_FLAG; no single-pin nets; at most one output pin per net; inputs driven. Two tests confirm the checker catches a removed connection and a missing power flag.
3. **Symbol/footprint consistency**: pin numbers equal pad numbers for every part.
4. **DRC**: KiCad DRC with 0.2 mm clearance and track width minimum, 0.6/0.3 mm vias, 0.5 mm edge clearance, courtyard overlap and solder-mask checks; the board must have no errors and no unconnected pads.

## Layout
54 × 42 mm, 2 layers. Connectors and the MCU are fixed; other parts are placed by a first-fit search inside each stage's region so courtyards never overlap. Freerouting routes the board through a Specctra DSN/SES round trip (the session is imported with a small parser because KiCad 7's importer needs the GUI). A GND pour on the bottom layer is filled after routing.

## Engineering decisions
- Ratiometric NTC measurement (divider and ADC both on AVCC) and a 1 % divider resistor, from the SPICE project's Monte Carlo.
- Separate decoupling capacitor for each MCU supply pin and for AVCC/AREF.
- Supply monitor on ADC1 lets firmware detect a low input before readings drift.
- EEPROM write protect tied low and both I²C addresses strapped, so firmware can probe fixed addresses (0x48, 0x50).

## Limits and next steps
Autorouted, not hand-optimised: the analog path is not routed with special care, decoupling capacitors are within the MCU region rather than at each pin, and the power traces use the default 0.25 mm width (enough for the 15 mA budget). The schematic uses label connections rather than drawn wires. No 3D model check, no fabrication or bench test. Next: hand-route the analog stage and decoupling, move to KiCad 8 for command-line ERC, and order prototype boards.
