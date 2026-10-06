"""Regenerate the SIB-1 hardware project and results/ from src/sib/design.py.

Steps: symbol + footprint library -> hierarchical schematic -> KiCad netlist export -> netlist and
ERC-style checks -> PCB placement and Freerouting autorouting -> GND pour -> KiCad DRC ->
fabrication outputs (Gerber, drill), BOM, component-selection table, renders, summary.json.
"""
import csv
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
HW = ROOT / "hardware"
OUT = ROOT / "results"
FREEROUTING = Path(os.environ.get("FREEROUTING_JAR", Path.home() / "tools/freerouting.jar"))

from sib import checks, design, footprints, pcb, schematic, symbols  # noqa: E402


def sh(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(" ".join(cmd) + "\n" + r.stdout + r.stderr)
    return r.stdout


def fit_svg(src: Path, dst: Path, pad=4.0, crop=None):
    """Give a KiCad SVG the portfolio slot size (900 x 460): crop, pad, match the aspect ratio, add a background."""
    t = src.read_text()
    vb = re.search(r'viewBox="([-\d.\s]+)"', t)
    x, y, w, h = crop or tuple(map(float, vb[1].split()))
    x, y, w, h = x - pad, y - pad, w + 2 * pad, h + 2 * pad
    target = 900 / 460
    if w / h < target:
        x, w = x - (h * target - w) / 2, h * target
    else:
        y, h = y - (w / target - h) / 2, w / target
    t = re.sub(r'viewBox="[-\d.\s]+"', f'viewBox="{x:g} {y:g} {w:g} {h:g}"', t, count=1)
    t = re.sub(r'<svg([^>]*?)width="[^"]+"([^>]*?)height="[^"]+"', r'<svg\1width="900"\2height="460"', t, count=1)
    t = re.sub(r"(<svg[^>]*>)", rf'\1<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" fill="#FBFCFD"/>', t, count=1)
    t = re.sub(r"<title>.*?</title>", "<title>SIB-1 render</title>", t, count=1)
    dst.write_text(t)


def sheet_extent(sheet_file: Path):
    """Bounding box (x, y, w, h in mm) of everything placed on a schematic sheet, title text excluded."""
    t = sheet_file.read_text()
    t = t[t.index("(lib_symbols"):]
    t = t[t.index("\n  )\n"):]
    pts = [(float(a), float(b)) for a, b in re.findall(r"\((?:at|xy) (-?[\d.]+) (-?[\d.]+)", t)]
    pts = [p for p in pts if p[1] > 26]          # skip the stage title
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    top = max(min(ys) - 10, 26.5)
    return min(xs) - 6, top, max(xs) - min(xs) + 18, max(ys) - top + 10


def bom_rows():
    groups = {}
    for p in design.PARTS:
        if not p.in_bom:
            continue
        groups.setdefault((p.value, p.footprint, p.mpn), []).append(p)
    rows = []
    for (value, fp, mpn), parts in sorted(groups.items(), key=lambda kv: kv[1][0].ref):
        rows.append({"refs": " ".join(sorted((q.ref for q in parts), key=lambda r: (re.sub(r"\d", "", r), int(re.sub(r"\D", "", r))))),
                     "qty": len(parts), "value": value, "footprint": fp, "mpn": mpn,
                     "stage": parts[0].sheet,
                     "role": "; ".join(dict.fromkeys(re.sub(r" \(.*\)$", "", q.role) for q in parts))})
    return rows


def track_plot(board_path: Path, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pcbnew
    b = pcbnew.LoadBoard(str(board_path))
    length, vias = {}, {}
    for t in b.GetTracks():
        n = t.GetNetname()
        if t.GetClass() == "PCB_TRACK":
            length[n] = length.get(n, 0) + pcbnew.ToMM(t.GetLength())
        elif t.GetClass() == "PCB_VIA":
            vias[n] = vias.get(n, 0) + 1
    stage_of_net = {}
    for p in design.PARTS:
        for net in p.pins.values():
            if net:
                stage_of_net.setdefault(net, p.sheet)
    colours = {"power": "#C8742F", "mcu": "#172D49", "analog": "#2F7F91", "interfaces": "#7D8C96"}
    items = sorted(length.items(), key=lambda kv: -kv[1])
    fig, ax = plt.subplots(figsize=(9, 4.6), dpi=100, facecolor="#FBFCFD")
    ax.set_facecolor("#FBFCFD")
    ax.bar([k for k, _ in items], [v for _, v in items],
           color=[colours.get(stage_of_net.get(k, "mcu"), "#172D49") for k, _ in items])
    for i, (k, v) in enumerate(items):
        if vias.get(k):
            ax.text(i, v + 2, str(vias[k]), ha="center", fontsize=8, color="#3D4B55")
    ax.set_ylabel("Routed track length (mm)", color="#172D49")
    ax.set_title("Autorouted SIB-1: track length per net (number = vias; colour = stage)",
                 color="#172D49", fontsize=12)
    ax.tick_params(axis="x", rotation=60, labelsize=8)
    ax.grid(axis="y", color="#DCE3EA")
    ax.spines[["top", "right"]].set_visible(False)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=c, label=s) for s, c in colours.items()], frameon=False)
    fig.tight_layout()
    plt.rcParams["svg.hashsalt"] = "sib"
    fig.savefig(path, format="svg", facecolor="#FBFCFD", metadata={"Date": None})
    plt.close(fig)
    t = path.read_text()
    path.write_text(re.sub(r'width="[\d.]+pt" height="[\d.]+pt"', 'width="900" height="460"', t, count=1))
    return {k: round(v, 1) for k, v in items}, vias


def main():
    OUT.mkdir(exist_ok=True)
    (HW / "lib").mkdir(parents=True, exist_ok=True)
    sym_names = symbols.write_library(HW / "lib/SIB.kicad_sym")
    fp_names = footprints.write_library(HW / "lib/SIB.pretty")
    schematic.write(HW)
    if not (HW / "sib.kicad_pro").exists():
        (HW / "sib.kicad_pro").write_text(json.dumps({"meta": {"filename": "sib.kicad_pro", "version": 1}}))

    netlist = HW / "sib.net"
    sh("kicad-cli", "sch", "export", "netlist", str(HW / "sib.kicad_sch"), "-o", str(netlist))
    nets = checks.parse(netlist)
    net_problems = checks.compare_with_design(nets)
    erc_problems = checks.electrical_rules(nets, checks.flagged_nets(HW))
    if net_problems or erc_problems:
        raise SystemExit("netlist/ERC problems:\n" + "\n".join(net_problems + erc_problems))

    board = HW / "sib.kicad_pcb"
    stage_of = {p.ref: p.sheet for p in design.PARTS}
    pcb_info = pcb.build(HW, netlist, stage_of, board, route=True, freerouting_jar=FREEROUTING)
    drc = pcb.drc(board, OUT / "drc_report.txt")
    (OUT / "drc_report.txt").write_text(re.sub(r"^\*\* Created on .*$", "** Created by src/run_all.py",
                                               (OUT / "drc_report.txt").read_text(), flags=re.M))

    # fabrication outputs
    fab = OUT / "fab"
    shutil.rmtree(fab, ignore_errors=True)
    fab.mkdir()
    sh("kicad-cli", "pcb", "export", "gerbers", str(board), "-o", str(fab) + "/",
       "-l", "F.Cu,B.Cu,F.Paste,F.SilkS,F.Mask,B.Mask,Edge.Cuts")
    sh("kicad-cli", "pcb", "export", "drill", str(board), "-o", str(fab) + "/")
    with zipfile.ZipFile(OUT / "sib_fabrication.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(fab.iterdir()):
            z.write(f, f.name)
    fab_files = sorted(f.name for f in fab.iterdir())
    shutil.rmtree(fab)

    # schematic and board renders
    sh("kicad-cli", "sch", "export", "pdf", str(HW / "sib.kicad_sch"), "-o", str(OUT / "schematic.pdf"))
    tmp = OUT / "_svg"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    sh("kicad-cli", "sch", "export", "svg", str(HW / "sib.kicad_sch"), "-o", str(tmp), "--exclude-drawing-sheet")
    analog_svg = next(p for p in tmp.iterdir() if "analog" in p.name.lower() or "NTC" in p.name)
    fit_svg(analog_svg, OUT / "schematic_analog.svg", pad=2.0, crop=sheet_extent(HW / "analog.kicad_sch"))
    sh("kicad-cli", "pcb", "export", "svg", str(board), "-o", str(tmp / "pcb.svg"), "--exclude-drawing-sheet",
       "--page-size-mode", "2", "-l", "F.Cu,B.Cu,F.SilkS,Edge.Cuts")
    fit_svg(tmp / "pcb.svg", OUT / "pcb_layout.svg")
    shutil.rmtree(tmp)
    lengths, vias = track_plot(board, OUT / "track_length.svg")

    # BOM and component-selection table
    rows = bom_rows()
    with open(OUT / "bom.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    sel = [{"ref": p.ref, "stage": p.sheet, **p.selection} for p in design.PARTS if p.selection]
    with open(OUT / "component_selection.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ref", "stage", "requirement", "choice", "key_data", "alternatives"])
        w.writeheader()
        w.writerows(sel)

    summary = {
        "provenance": "Generated from src/sib/design.py with KiCad " + sh("kicad-cli", "version").strip()
                      + " (pcbnew Python API, kicad-cli) and Freerouting; not fabricated or bench-tested.",
        "stages": [t for _, t in design.SHEETS],
        "library": {"symbols": len(sym_names), "footprints": len(fp_names)},
        "schematic": {"sheets": len(design.SHEETS) + 1,
                      "components_on_board": sum(1 for p in design.PARTS if not p.ref.startswith("#")),
                      "nets": sum(1 for n in nets if not n.startswith("unconnected-")),
                      "no_connect_pins": sum(1 for n in nets if n.startswith("unconnected-")),
                      "netlist_vs_design_problems": len(net_problems), "erc_style_problems": len(erc_problems)},
        "pcb": {"size_mm": [pcb.BOARD_W, pcb.BOARD_H], "layers": 2, **pcb_info, "drc": drc,
                "track_length_by_net_mm": lengths, "vias_by_net": vias},
        "bom": {"lines": len(rows), "parts": sum(r["qty"] for r in rows)},
        "component_selection_rows": len(sel),
        "fabrication_files": fab_files,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    (OUT / "REPORT.md").write_text(report(summary, sel))
    manifest = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "python": platform.python_version(), "kicad": sh("kicad-cli", "version").strip(),
                "results": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "manifest.json"}}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    netlist.unlink()
    print(json.dumps({k: summary[k] for k in ("library", "schematic", "bom")}, indent=1))
    print(json.dumps({k: v for k, v in summary["pcb"].items() if k not in ("track_length_by_net_mm", "vias_by_net")}, indent=1))


def report(s, sel):
    p = s["pcb"]
    lines = ["# Results report", "", s["provenance"], "",
             "| Check | Result |", "|---|---|",
             f"| Functional stages (schematic sheets) | {len(s['stages'])} + root |",
             f"| Custom library | {s['library']['symbols']} symbols, {s['library']['footprints']} footprints |",
             f"| Components on board / nets | {s['schematic']['components_on_board']} / {s['schematic']['nets']} |",
             f"| KiCad netlist vs design source | {s['schematic']['netlist_vs_design_problems']} differences |",
             f"| ERC-style netlist rules | {s['schematic']['erc_style_problems']} problems |",
             f"| PCB | {p['size_mm'][0]:g} x {p['size_mm'][1]:g} mm, {p['layers']} layers, {p['tracks']} track segments, {p['vias']} vias, {p['track_length_mm']} mm routed |",
             f"| KiCad DRC | {p['drc']['errors']} errors, {p['drc']['warnings']} warnings, {p['drc']['unconnected']} unconnected pads |",
             f"| BOM | {s['bom']['lines']} lines, {s['bom']['parts']} parts |", "",
             "## Component selection", "", "| Ref | Requirement | Choice | Evidence | Alternatives |", "|---|---|---|---|---|"]
    lines += [f"| {r['ref']} | {r['requirement']} | {r['choice']} | {r['key_data']} | {r['alternatives']} |" for r in sel]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
