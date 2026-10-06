# Results report

Generated from src/sib/design.py with KiCad 7.0.11 (pcbnew Python API, kicad-cli) and Freerouting; not fabricated or bench-tested.

| Check | Result |
|---|---|
| Functional stages (schematic sheets) | 4 + root |
| Custom library | 15 symbols, 14 footprints |
| Components on board / nets | 36 / 22 |
| KiCad netlist vs design source | 0 differences |
| ERC-style netlist rules | 0 problems |
| PCB | 54 x 42 mm, 2 layers, 296 track segments, 35 vias, 698.4 mm routed |
| KiCad DRC | 0 errors, 0 warnings, 0 unconnected pads |
| BOM | 25 lines, 36 parts |

## Component selection

| Ref | Requirement | Choice | Evidence | Alternatives |
|---|---|---|---|---|
| D1 | Block reverse input; low drop so the LDO keeps headroom at 4.75 V | SS14 1 A 40 V Schottky, SMA | Vf about 0.2-0.35 V at 15-250 mA (SPICE project, 1N5819-class model) | P-MOSFET ideal diode (lower drop, more parts); silicon diode (0.7 V drop) |
| U1 | 3.3 V for MCU and sensors, about 15 mA budget, regulation from 4.75 V USB minimum | MCP1700-3302, 250 mA, SOT-23 | dropout up to 350 mV at 250 mA, quiescent current a few µA (datasheet class); 0.77 V headroom at 4.75 V, 250 mA in SPICE | AP2112K-3.3 (600 mA, higher quiescent current); buck converter (not needed at 15 mA) |
| U2 | 10-bit ADC with AVCC reference, I2C, UART, 3.3 V operation, free toolchain | ATmega328P-AU, TQFP-32 | 6 ADC channels on TQFP, TWI and USART, 1.8-5.5 V; avr-gcc and simavr for firmware tests | STM32G031 (more capable, 12-bit ADC); ATtiny1616 (fewer pins) |
| R6 | Divider resistor whose tolerance does not dominate the temperature error | 10 kΩ 1 % thin-film-class 0603 | Monte Carlo: 0.1 % improves the 25 °C p95 error only from 0.41 to 0.31 °C | 0.1 % resistor (cost for little gain) |
| RT1 | Board temperature 0-85 °C with about 0.1-0.3 °C per ADC count | 10 kΩ NTC, B25/85 = 3380 K, ±1 %, 0603 | R25 and B tolerance dominate the error at the range ends (Monte Carlo) | Digital sensor only (TMP102 is also fitted as a cross-check) |
| C8 | Low-pass about 10 Hz, Q about 0.7, -25 dB or better at 50 Hz | 15 kΩ / 15 kΩ / 1.5 µF / 680 nF unity-gain Sallen-Key | f-3dB 8.5-10.7 Hz over temperature, -29.6 dB at 50 Hz (25 °C) in SPICE | Single RC (only -20 dB/decade); digital filter only (aliasing not removed) |
| U3 | Rail-to-rail buffer at 3.3 V, low input bias for 15 kΩ filter resistors | MCP6001, 1 MHz GBW, SOT-23-5 | input offset up to 4.5 mV (datasheet class) adds about 0.2 °C at 85 °C (Monte Carlo) | MCP6V01 zero-drift (removes offset error, higher cost); one-point calibration |
| U4 | Independent digital temperature reading to cross-check the NTC channel | TMP102, I2C, ADD0 to GND (0x48) | 12-bit, 0.0625 °C per LSB, ±0.5 °C (datasheet class) | LM75 (coarser, larger package) |
| U5 | Store calibration offset and board ID outside the MCU | 24LC02B 2 kbit I2C EEPROM, WP to GND | 8-byte page write, address 0x50 with A0-A2 to GND | MCU internal EEPROM (lost on chip replacement) |
