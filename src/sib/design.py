"""SIB-1 sensor-interface board: parts, pin maps and connectivity, split by functional stage.

This file is the single design source. The schematic, the PCB and the BOM are generated from it,
and the tests compare KiCad's exported netlist back to it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

NC = None  # pin intentionally not connected (gets a no-connect marker)

# Sheets = functional stages
SHEETS = [
    ("power", "1 Power input and 3.3 V regulation"),
    ("mcu", "2 Microcontroller, programming and status"),
    ("analog", "3 NTC front end and anti-alias filter"),
    ("interfaces", "4 I2C sensor, EEPROM and connectors"),
]

# Nets that cross stages become global labels; all others stay local to their sheet.
GLOBAL_NETS = {"GND", "+3V3", "VIN", "VMON", "ADC_NTC", "SDA", "SCL", "UART_TX", "UART_RX"}


@dataclass
class Part:
    ref: str
    symbol: str
    value: str
    footprint: str
    sheet: str
    pins: dict            # pin number -> net name (or NC)
    mpn: str = ""
    role: str = ""
    in_bom: bool = True
    selection: dict = field(default_factory=dict)  # requirement / choice / key data (assumption) / alternatives


PARTS: list[Part] = [
    # ---------------- 1 power ----------------
    Part("J1", "Conn_01x02", "VIN 5 V", "PinHeader_1x02_P2.54mm", "power", {"1": "VIN_RAW", "2": "GND"},
         "2.54 mm header", "Supply input"),
    Part("D1", "D_Schottky", "SS14", "D_SMA", "power", {"1": "VIN", "2": "VIN_RAW"}, "SS14",
         "Reverse-polarity protection",
         selection={"requirement": "Block reverse input; low drop so the LDO keeps headroom at 4.75 V",
                    "choice": "SS14 1 A 40 V Schottky, SMA",
                    "key_data": "Vf about 0.2-0.35 V at 15-250 mA (SPICE project, 1N5819-class model)",
                    "alternatives": "P-MOSFET ideal diode (lower drop, more parts); silicon diode (0.7 V drop)"}),
    Part("C1", "C", "1u", "C_0603", "power", {"1": "VIN", "2": "GND"}, "GRM188R61E105KA12", "LDO input capacitor"),
    Part("U1", "MCP1700-3302", "MCP1700-3302E/TT", "SOT-23", "power", {"1": "GND", "2": "+3V3", "3": "VIN"},
         "MCP1700T-3302E/TT", "3.3 V LDO",
         selection={"requirement": "3.3 V for MCU and sensors, about 15 mA budget, regulation from 4.75 V USB minimum",
                    "choice": "MCP1700-3302, 250 mA, SOT-23",
                    "key_data": "dropout up to 350 mV at 250 mA, quiescent current a few µA (datasheet class); "
                                "0.77 V headroom at 4.75 V, 250 mA in SPICE",
                    "alternatives": "AP2112K-3.3 (600 mA, higher quiescent current); buck converter (not needed at 15 mA)"}),
    Part("C2", "C", "1u", "C_0603", "power", {"1": "+3V3", "2": "GND"}, "GRM188R61E105KA12", "LDO output capacitor"),
    Part("R1", "R", "20k", "R_0603", "power", {"1": "VIN", "2": "VMON"}, "RC0603FR-0720KL", "Supply monitor divider top"),
    Part("R2", "R", "10k", "R_0603", "power", {"1": "VMON", "2": "GND"}, "RC0603FR-0710KL",
         "Supply monitor divider bottom (VIN/3 to ADC1)"),
    Part("R3", "R", "1k", "R_0603", "power", {"1": "+3V3", "2": "PWR_LED_A"}, "RC0603FR-071KL", "Power LED resistor"),
    Part("D2", "LED", "green", "LED_0603", "power", {"1": "GND", "2": "PWR_LED_A"}, "LTST-C191KGKT", "Power LED"),
    Part("#FLG01", "PWR_FLAG", "PWR_FLAG", "", "power", {"1": "VIN_RAW"}, in_bom=False),
    Part("#FLG02", "PWR_FLAG", "PWR_FLAG", "", "power", {"1": "GND"}, in_bom=False),
    Part("#FLG03", "PWR_FLAG", "PWR_FLAG", "", "power", {"1": "VIN"}, in_bom=False),

    # ---------------- 2 mcu ----------------
    Part("U2", "ATmega328P-AU", "ATmega328P-AU", "TQFP-32_7x7mm_P0.8mm", "mcu", {
        "1": NC, "2": NC, "3": "GND", "4": "+3V3", "5": "GND", "6": "+3V3", "7": NC, "8": NC,
        "9": NC, "10": NC, "11": NC, "12": "STATUS_LED", "13": NC, "14": NC, "15": "MOSI", "16": "MISO",
        "17": "SCK", "18": "+3V3", "19": NC, "20": "AREF", "21": "GND", "22": NC, "23": "ADC_NTC", "24": "VMON",
        "25": NC, "26": NC, "27": "SDA", "28": "SCL", "29": "RESET", "30": "UART_RX", "31": "UART_TX", "32": NC},
        "ATMEGA328P-AU", "Microcontroller (internal 8 MHz RC oscillator)",
        selection={"requirement": "10-bit ADC with AVCC reference, I2C, UART, 3.3 V operation, free toolchain",
                   "choice": "ATmega328P-AU, TQFP-32",
                   "key_data": "6 ADC channels on TQFP, TWI and USART, 1.8-5.5 V; avr-gcc and simavr for firmware tests",
                   "alternatives": "STM32G031 (more capable, 12-bit ADC); ATtiny1616 (fewer pins)"}),
    Part("C3", "C", "100n", "C_0603", "mcu", {"1": "+3V3", "2": "GND"}, "GRM188R71H104KA93", "VCC decoupling (pin 4)"),
    Part("C4", "C", "100n", "C_0603", "mcu", {"1": "+3V3", "2": "GND"}, "GRM188R71H104KA93", "VCC decoupling (pin 6)"),
    Part("C5", "C", "100n", "C_0603", "mcu", {"1": "+3V3", "2": "GND"}, "GRM188R71H104KA93", "AVCC decoupling (pin 18)"),
    Part("C6", "C", "100n", "C_0603", "mcu", {"1": "AREF", "2": "GND"}, "GRM188R71H104KA93", "AREF capacitor"),
    Part("R4", "R", "10k", "R_0603", "mcu", {"1": "+3V3", "2": "RESET"}, "RC0603FR-0710KL", "Reset pull-up"),
    Part("J3", "Conn_02x03_ISP", "AVR-ISP", "PinHeader_2x03_P2.54mm", "mcu",
         {"1": "MISO", "2": "+3V3", "3": "SCK", "4": "MOSI", "5": "RESET", "6": "GND"}, "2x3 header", "ISP programming"),
    Part("R5", "R", "1k", "R_0603", "mcu", {"1": "STATUS_LED", "2": "STAT_LED_A"}, "RC0603FR-071KL", "Status LED resistor"),
    Part("D3", "LED", "yellow", "LED_0603", "mcu", {"1": "GND", "2": "STAT_LED_A"}, "LTST-C191KSKT", "Status LED"),

    # ---------------- 3 analog ----------------
    Part("R6", "R", "10k 1%", "R_0603", "analog", {"1": "+3V3", "2": "NTC_MID"}, "RC0603FR-0710KL", "NTC divider top",
         selection={"requirement": "Divider resistor whose tolerance does not dominate the temperature error",
                    "choice": "10 kΩ 1 % thin-film-class 0603",
                    "key_data": "Monte Carlo: 0.1 % improves the 25 °C p95 error only from 0.41 to 0.31 °C",
                    "alternatives": "0.1 % resistor (cost for little gain)"}),
    Part("RT1", "Thermistor_NTC", "10k B3380", "R_0603", "analog", {"1": "NTC_MID", "2": "GND"},
         "NCP18XH103F03RB", "Board temperature sensor",
         selection={"requirement": "Board temperature 0-85 °C with about 0.1-0.3 °C per ADC count",
                    "choice": "10 kΩ NTC, B25/85 = 3380 K, ±1 %, 0603",
                    "key_data": "R25 and B tolerance dominate the error at the range ends (Monte Carlo)",
                    "alternatives": "Digital sensor only (TMP102 is also fitted as a cross-check)"}),
    Part("R7", "R", "15k", "R_0603", "analog", {"1": "NTC_MID", "2": "SK_A"}, "RC0603FR-0715KL", "Sallen-Key R1"),
    Part("R8", "R", "15k", "R_0603", "analog", {"1": "SK_A", "2": "SK_B"}, "RC0603FR-0715KL", "Sallen-Key R2"),
    Part("C7", "C", "1.5u", "C_0805", "analog", {"1": "SK_A", "2": "OPA_OUT"}, "GRM21BR71C155KA01", "Sallen-Key C1 (feedback)"),
    Part("C8", "C", "680n", "C_0603", "analog", {"1": "SK_B", "2": "GND"}, "GRM188R71C684KA01", "Sallen-Key C2",
         selection={"requirement": "Low-pass about 10 Hz, Q about 0.7, -25 dB or better at 50 Hz",
                    "choice": "15 kΩ / 15 kΩ / 1.5 µF / 680 nF unity-gain Sallen-Key",
                    "key_data": "f-3dB 8.5-10.7 Hz over temperature, -29.6 dB at 50 Hz (25 °C) in SPICE",
                    "alternatives": "Single RC (only -20 dB/decade); digital filter only (aliasing not removed)"}),
    Part("U3", "MCP6001", "MCP6001T-I/OT", "SOT-23-5", "analog",
         {"1": "OPA_OUT", "2": "GND", "3": "SK_B", "4": "OPA_OUT", "5": "+3V3"}, "MCP6001T-I/OT",
         "Buffer op-amp (unity gain)",
         selection={"requirement": "Rail-to-rail buffer at 3.3 V, low input bias for 15 kΩ filter resistors",
                    "choice": "MCP6001, 1 MHz GBW, SOT-23-5",
                    "key_data": "input offset up to 4.5 mV (datasheet class) adds about 0.2 °C at 85 °C (Monte Carlo)",
                    "alternatives": "MCP6V01 zero-drift (removes offset error, higher cost); one-point calibration"}),
    Part("C9", "C", "100n", "C_0603", "analog", {"1": "+3V3", "2": "GND"}, "GRM188R71H104KA93", "Op-amp decoupling"),
    Part("R9", "R", "100", "R_0603", "analog", {"1": "OPA_OUT", "2": "ADC_NTC"}, "RC0603FR-07100RL", "Isolation resistor"),
    Part("C10", "C", "10n", "C_0603", "analog", {"1": "ADC_NTC", "2": "GND"}, "GRM188R71H103KA01", "ADC charge reservoir"),

    # ---------------- 4 interfaces ----------------
    Part("U4", "TMP102", "TMP102AIDRLR", "SOT-563", "interfaces",
         {"1": "SCL", "2": "GND", "3": NC, "4": "GND", "5": "+3V3", "6": "SDA"}, "TMP102AIDRLR",
         "Digital temperature sensor, address 0x48",
         selection={"requirement": "Independent digital temperature reading to cross-check the NTC channel",
                    "choice": "TMP102, I2C, ADD0 to GND (0x48)",
                    "key_data": "12-bit, 0.0625 °C per LSB, ±0.5 °C (datasheet class)",
                    "alternatives": "LM75 (coarser, larger package)"}),
    Part("C11", "C", "100n", "C_0603", "interfaces", {"1": "+3V3", "2": "GND"}, "GRM188R71H104KA93", "TMP102 decoupling"),
    Part("U5", "24LC02", "24LC02B", "SOIC-8_3.9x4.9mm_P1.27mm", "interfaces",
         {"1": "GND", "2": "GND", "3": "GND", "4": "GND", "5": "SDA", "6": "SCL", "7": "GND", "8": "+3V3"},
         "24LC02BT-I/SN", "Calibration EEPROM, address 0x50",
         selection={"requirement": "Store calibration offset and board ID outside the MCU",
                    "choice": "24LC02B 2 kbit I2C EEPROM, WP to GND",
                    "key_data": "8-byte page write, address 0x50 with A0-A2 to GND",
                    "alternatives": "MCU internal EEPROM (lost on chip replacement)"}),
    Part("C12", "C", "100n", "C_0603", "interfaces", {"1": "+3V3", "2": "GND"}, "GRM188R71H104KA93", "EEPROM decoupling"),
    Part("R10", "R", "4.7k", "R_0603", "interfaces", {"1": "+3V3", "2": "SDA"}, "RC0603FR-074K7L", "SDA pull-up"),
    Part("R11", "R", "4.7k", "R_0603", "interfaces", {"1": "+3V3", "2": "SCL"}, "RC0603FR-074K7L", "SCL pull-up"),
    Part("J4", "Conn_01x04", "I2C", "PinHeader_1x04_P2.54mm", "interfaces",
         {"1": "+3V3", "2": "GND", "3": "SDA", "4": "SCL"}, "2.54 mm header", "I2C expansion"),
    Part("J5", "Conn_01x03", "UART", "PinHeader_1x03_P2.54mm", "interfaces",
         {"1": "UART_TX", "2": "UART_RX", "3": "GND"}, "2.54 mm header", "UART debug port (3.3 V)"),
]


def nets() -> dict[str, list[tuple[str, str]]]:
    out: dict[str, list[tuple[str, str]]] = {}
    for p in PARTS:
        for pin, net in p.pins.items():
            if net is not None:
                out.setdefault(net, []).append((p.ref, pin))
    return out
