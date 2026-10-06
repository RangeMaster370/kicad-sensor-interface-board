"""Checks of the generated SIB-1 hardware: library, netlist, electrical rules, PCB and DRC."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
HW = ROOT / "hardware"

from sib import checks, design, footprints, symbols  # noqa: E402

HAVE_KICAD = shutil.which("kicad-cli") is not None
try:
    import pcbnew  # noqa: F401
    HAVE_PCBNEW = True
except ImportError:
    HAVE_PCBNEW = False


class DesignSource(unittest.TestCase):
    def test_every_part_has_symbol_and_footprint(self):
        syms = symbols.all_symbols()
        for p in design.PARTS:
            self.assertIn(p.symbol, syms, p.ref)
            if not p.ref.startswith("#"):
                self.assertIn(p.footprint, footprints.FOOTPRINTS, p.ref)

    def test_pin_numbers_match_symbol_and_footprint_pads(self):
        syms = symbols.all_symbols()
        for p in design.PARTS:
            sym_pins = set(syms[p.symbol][1])
            self.assertEqual(set(p.pins), sym_pins, p.ref)
            if p.ref.startswith("#"):
                continue
            pads = set(re.findall(r'\(pad "(\d+)"', footprints.FOOTPRINTS[p.footprint]()))
            self.assertEqual(pads, sym_pins, f"{p.ref} pads vs pins")

    def test_every_net_has_two_or_more_pins(self):
        for net, nodes in design.nets().items():
            real = [n for n in nodes if not n[0].startswith("#")]
            self.assertGreaterEqual(len(real), 2, net)

    def test_filter_values_match_spice_project(self):
        values = {p.ref: p.value for p in design.PARTS}
        self.assertEqual((values["R7"], values["R8"], values["C7"], values["C8"]), ("15k", "15k", "1.5u", "680n"))
        self.assertEqual(values["R6"], "10k 1%")

    def test_i2c_addresses_strapped(self):
        u4 = next(p for p in design.PARTS if p.ref == "U4")
        u5 = next(p for p in design.PARTS if p.ref == "U5")
        self.assertEqual(u4.pins["4"], "GND")                      # TMP102 ADD0 -> 0x48
        self.assertEqual([u5.pins[k] for k in "123"], ["GND"] * 3)  # 24LC02 A0-A2 -> 0x50


@unittest.skipUnless(HAVE_KICAD, "kicad-cli not installed")
class KiCadNetlist(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        net = Path(cls.tmp.name) / "sib.net"
        subprocess.run(["kicad-cli", "sch", "export", "netlist", str(HW / "sib.kicad_sch"), "-o", str(net)],
                       check=True, capture_output=True)
        cls.nets = checks.parse(net)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_kicad_netlist_equals_design(self):
        self.assertEqual(checks.compare_with_design(self.nets), [])

    def test_electrical_rules(self):
        self.assertEqual(checks.electrical_rules(self.nets, checks.flagged_nets(HW)), [])

    def test_checker_catches_a_broken_connection(self):
        broken = {n: [x for x in v if x[:2] != ("U2", "23")] for n, v in self.nets.items()}
        self.assertTrue(checks.compare_with_design(broken))

    def test_checker_catches_a_missing_power_flag(self):
        self.assertTrue(checks.electrical_rules(self.nets, flagged=set()))

    def test_adc_channels(self):
        short = {checks.short(n): {(r, p) for r, p, _ in v} for n, v in self.nets.items()}
        self.assertIn(("U2", "23"), short["ADC_NTC"])   # ADC0 <- filtered NTC
        self.assertIn(("U2", "24"), short["VMON"])      # ADC1 <- VIN/3


@unittest.skipUnless(HAVE_PCBNEW, "KiCad pcbnew Python module not installed")
class Board(unittest.TestCase):
    def test_drc_clean_and_fully_routed(self):
        from sib import pcb
        with tempfile.TemporaryDirectory() as tmp:
            r = pcb.drc(HW / "sib.kicad_pcb", Path(tmp) / "drc.txt")
        self.assertEqual(r["errors"], 0, r)
        self.assertEqual(r["unconnected"], 0, r)

    def test_all_parts_inside_outline(self):
        import pcbnew
        from sib import pcb
        b = pcbnew.LoadBoard(str(HW / "sib.kicad_pcb"))
        for fp in b.GetFootprints():
            bb = fp.GetBoundingBox(False, False)
            self.assertGreaterEqual(pcbnew.ToMM(bb.GetLeft()), 0, fp.GetReference())
            self.assertLessEqual(pcbnew.ToMM(bb.GetRight()), pcb.BOARD_W, fp.GetReference())
            self.assertGreaterEqual(pcbnew.ToMM(bb.GetTop()), 0, fp.GetReference())
            self.assertLessEqual(pcbnew.ToMM(bb.GetBottom()), pcb.BOARD_H, fp.GetReference())


class Results(unittest.TestCase):
    def test_summary_consistent(self):
        s = json.loads((ROOT / "results/summary.json").read_text())
        self.assertEqual(s["schematic"]["netlist_vs_design_problems"], 0)
        self.assertEqual(s["pcb"]["drc"]["errors"], 0)
        self.assertEqual(s["pcb"]["drc"]["unconnected"], 0)
        self.assertEqual(s["bom"]["parts"], sum(1 for p in design.PARTS if p.in_bom))
        self.assertIn("sib.drl", s["fabrication_files"])


if __name__ == "__main__":
    unittest.main()
