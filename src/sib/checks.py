"""Netlist checks: KiCad's exported netlist against design.py, plus ERC-style electrical rules.

KiCad 7's command line has no ERC, so the electrical rules a schematic ERC would flag for this
design are checked here from the exported netlist (pin types come from the symbol library).
"""
from __future__ import annotations

import re
from pathlib import Path

from . import design


def parse(netlist: Path):
    text = netlist.read_text()
    nets = {}
    for chunk in text[text.index("(nets"):].split("(net (code")[1:]:
        name = re.search(r'\(name "([^"]+)"\)', chunk)[1]
        nets[name] = re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)(?: \(pinfunction "[^"]*"\))? \(pintype "([^"]+)"\)', chunk)
    return nets


def short(name: str) -> str:
    return name.rsplit("/", 1)[-1]


def compare_with_design(nets) -> list[str]:
    problems = []
    exported = {short(n): {(r, p) for r, p, _ in nodes} for n, nodes in nets.items() if not n.startswith("unconnected-")}
    # power-flag symbols are not exported to the netlist; they are checked in electrical_rules
    intended = {n: {(r, p) for r, p in nodes if not r.startswith("#")} for n, nodes in design.nets().items()}
    for n in sorted(set(intended) | set(exported)):
        if intended.get(n) != exported.get(n):
            problems.append(f"net {n}: design {sorted(intended.get(n, []))} vs KiCad {sorted(exported.get(n, []))}")
    nc_design = {(p.ref, pin) for p in design.PARTS for pin, net in p.pins.items() if net is None}
    nc_kicad = {(r, p) for n, nodes in nets.items() if n.startswith("unconnected-") for r, p, _ in nodes}
    if nc_design != nc_kicad:
        problems.append(f"no-connect mismatch: design-only {sorted(nc_design - nc_kicad)}, KiCad-only {sorted(nc_kicad - nc_design)}")
    return problems


def flagged_nets(hardware: Path) -> set[str]:
    """Nets carrying a PWR_FLAG: the flag symbol must exist in the schematic and in design.py."""
    text = "".join(p.read_text() for p in hardware.glob("*.kicad_sch"))
    placed = set(re.findall(r'\(reference "(#FLG\d+)"\)', text))
    return {p.pins["1"] for p in design.PARTS if p.symbol == "PWR_FLAG" and p.ref in placed}


def electrical_rules(nets, flagged: set[str] = frozenset()) -> list[str]:
    problems = []
    for n, nodes in nets.items():
        if n.startswith("unconnected-"):
            continue
        types = [t for _, _, t in nodes]
        if len(nodes) < 2:
            problems.append(f"{short(n)}: single-pin net")
        if any(t == "power_in" for t in types) and not any(t == "power_out" for t in types) \
                and short(n) not in flagged:
            problems.append(f"{short(n)}: power input pins without a driver (power_out or PWR_FLAG)")
        if sum(t == "output" for t in types) > 1:
            problems.append(f"{short(n)}: more than one output pin")
        if all(t in ("input", "passive") for t in types) and any(t == "input" for t in types) \
                and not any(r.startswith(("R", "C", "RT")) for r, _, _ in nodes):
            problems.append(f"{short(n)}: input pin(s) not driven")
    return problems
