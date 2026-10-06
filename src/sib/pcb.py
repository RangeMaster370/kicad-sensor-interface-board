"""Build the 2-layer SIB-1 PCB with KiCad 7's pcbnew API: footprints from the custom library,
nets from KiCad's exported netlist, stage-based placement, Freerouting autorouting, GND pour, DRC.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pcbnew

MM = pcbnew.FromMM
BOARD_W, BOARD_H = 54.0, 42.0

# Stage regions (x0, y0, x1, y1 in mm); connectors are pinned to edges separately.
REGIONS = {
    "power": (2.0, 2.0, 24.0, 15.0),
    "analog": (25.0, 2.0, 52.0, 17.0),
    "mcu": (2.0, 16.0, 30.0, 40.0),
    "interfaces": (31.0, 18.0, 46.0, 40.0),
}
FIXED = {  # ref -> (x, y, rotation deg) for connectors and the MCU
    "J1": (3.5, 4.0, 0), "J4": (50.5, 25.0, 0), "J5": (36.0, 39.0, 90), "J3": (20.5, 33.5, 0),
    "U2": (12.0, 26.0, 0),
}


def parse_netlist(path: Path):
    text = path.read_text()
    comps = {}
    for m in re.finditer(r'\(comp \(ref "([^"]+)"\)\s*\(value "([^"]*)"\)\s*\(footprint "([^"]*)"\)', text):
        comps[m[1]] = {"value": m[2], "footprint": m[3]}
    nets = {}
    for chunk in text[text.index("(nets"):].split("(net (code")[1:]:
        name = re.search(r'\(name "([^"]+)"\)', chunk)[1]
        nets[name] = re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', chunk)
    return comps, nets


def short(net: str) -> str:
    return net.rsplit("/", 1)[-1]


def _bbox_mm(fp):
    bb = fp.GetCourtyard(pcbnew.F_CrtYd).BBox() if fp.GetCourtyard(pcbnew.F_CrtYd).OutlineCount() else fp.GetBoundingBox()
    return pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())


def build(hw: Path, netlist: Path, stage_of: dict, out: Path, route=True, freerouting_jar=None) -> dict:
    comps, nets = parse_netlist(netlist)
    board = pcbnew.CreateEmptyBoard()
    board.SetCopperLayerCount(2)
    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = MM(0.2)
    ds.m_MinClearance = MM(0.2)
    ds.m_ViasMinSize = MM(0.6)
    ds.m_MinThroughDrill = MM(0.3)
    ds.m_SolderMaskMinWidth = MM(0)      # allow a shared mask opening on 0.5/0.8 mm pitch ICs
    ds.m_SolderMaskExpansion = MM(0.05)
    nc = ds.m_NetSettings.m_DefaultNetClass
    nc.SetClearance(MM(0.2))
    nc.SetTrackWidth(MM(0.25))
    nc.SetViaDiameter(MM(0.6))
    nc.SetViaDrill(MM(0.3))

    # outline
    corners = [(0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H)]
    for a, b in zip(corners, corners[1:] + corners[:1]):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1])))
        seg.SetEnd(pcbnew.VECTOR2I(MM(b[0]), MM(b[1])))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(MM(0.1))
        board.Add(seg)

    # footprints
    lib = str(hw / "lib/SIB.pretty")
    fps = {}
    for ref, c in comps.items():
        name = c["footprint"].split(":", 1)[1]
        fp = pcbnew.FootprintLoad(lib, name)
        fp.SetFPID(pcbnew.LIB_ID("SIB", name))
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        board.Add(fp)
        fps[ref] = fp

    # nets
    netinfo = {}
    for name, nodes in nets.items():
        if name.startswith("unconnected-"):
            continue
        ni = pcbnew.NETINFO_ITEM(board, short(name))
        board.Add(ni)
        netinfo[name] = ni
        for ref, pin in nodes:
            if ref in fps:
                pad = fps[ref].FindPadByNumber(pin)
                if pad is None:
                    raise ValueError(f"{ref} has no pad {pin}")
                pad.SetNet(ni)

    # placement: fixed parts, then first-fit search inside each stage region (no courtyard overlap)
    placed = []

    def rect(fp, gap=0.35):
        bb = fp.GetBoundingBox(False, False)
        return (pcbnew.ToMM(bb.GetLeft()) - gap, pcbnew.ToMM(bb.GetTop()) - gap,
                pcbnew.ToMM(bb.GetRight()) + gap, pcbnew.ToMM(bb.GetBottom()) + gap)

    def free(r):
        return all(r[2] <= q[0] or r[0] >= q[2] or r[3] <= q[1] or r[1] >= q[3] for q in placed)

    for ref, (x, y, rot) in FIXED.items():
        fps[ref].SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        fps[ref].SetOrientationDegrees(rot)
        placed.append(rect(fps[ref], 0.6))
    for stage, (x0, y0, x1, y1) in REGIONS.items():
        for ref in sorted((r for r in fps if stage_of.get(r) == stage and r not in FIXED),
                          key=lambda r: (re.sub(r"\d", "", r), int(re.sub(r"\D", "", r) or 0))):
            fp = fps[ref]
            fp.SetPosition(pcbnew.VECTOR2I(0, 0))
            r0 = rect(fp)
            w, h = r0[2] - r0[0], r0[3] - r0[1]
            spot = None
            y = y0
            while spot is None and y + h <= y1 + 1e-9:
                x = x0
                while x + w <= x1 + 1e-9:
                    cand = (x, y, x + w, y + h)
                    if free(cand):
                        spot = cand
                        break
                    x += 0.25
                y += 0.25
            if spot is None:
                raise RuntimeError(f"no room for {ref} in region {stage}")
            fp.SetPosition(pcbnew.VECTOR2I(MM(spot[0] - r0[0]), MM(spot[1] - r0[1])))
            placed.append(rect(fp))

    # GND pour on the bottom layer
    zone = pcbnew.ZONE(board)
    zone.SetLayer(pcbnew.B_Cu)
    zone.SetNet(next(v for k, v in netinfo.items() if short(k) == "GND"))
    poly = zone.Outline()
    poly.NewOutline()
    for x, y in [(0.5, 0.5), (BOARD_W - 0.5, 0.5), (BOARD_W - 0.5, BOARD_H - 0.5), (0.5, BOARD_H - 0.5)]:
        poly.Append(MM(x), MM(y))
    zone.SetLocalClearance(MM(0.3))
    zone.SetMinThickness(MM(0.25))
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    board.Add(zone)

    out.parent.mkdir(parents=True, exist_ok=True)
    board.SetFileName(str(out))
    info = {"footprints": len(fps), "nets": len(netinfo)}
    if route:
        dsn, ses = out.with_suffix(".dsn"), out.with_suffix(".ses")
        if not pcbnew.ExportSpecctraDSN(board, str(dsn)):
            raise RuntimeError("DSN export failed")
        cmd = ["java", "-Djava.awt.headless=false", "-jar", str(freerouting_jar), "-de", str(dsn), "-do", str(ses),
               "-mp", "40", "-dct", "0"]
        if shutil.which("xvfb-run") and not os.environ.get("DISPLAY"):
            cmd = ["xvfb-run", "-a"] + cmd
        log = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if not ses.exists():
            raise RuntimeError("Freerouting produced no session file:\n" + log.stdout[-2000:] + log.stderr[-2000:])
        import_ses(board, ses)
        dsn.unlink()
        ses.unlink()
    pcbnew.SaveBoard(str(out), board)
    board = pcbnew.LoadBoard(str(out))      # reload so connectivity is built before filling
    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(out), board)
    info["tracks"] = sum(1 for t in board.GetTracks() if t.GetClass() == "PCB_TRACK")
    info["vias"] = sum(1 for t in board.GetTracks() if t.GetClass() == "PCB_VIA")
    info["track_length_mm"] = round(sum(pcbnew.ToMM(t.GetLength()) for t in board.GetTracks()
                                        if t.GetClass() == "PCB_TRACK"), 1)
    return info


def import_ses(board, ses: Path):
    """Add the routed wires and vias from a Specctra session (KiCad 7's ImportSpecctraSES only works in the GUI)."""
    text = ses.read_text()
    res = re.search(r"\(routes\s*\(resolution um (\d+)\)", text)
    scale = 1.0 / int(res[1]) / 1000.0                  # session units -> mm
    nets = {board.GetNetInfo().GetNetItem(i).GetNetname(): board.GetNetInfo().GetNetItem(i)
            for i in range(board.GetNetCount())}
    body = text[text.index("(network_out"):]
    layers = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}
    n_wires = n_vias = 0
    for chunk in re.split(r"\(net ", body)[1:]:
        name = re.match(r'\s*("([^"]+)"|(\S+))', chunk)
        net = nets[name[2] or name[3]]
        for lay, width, pts in re.findall(r"\(path (\S+) (\d+)\s+([-\d\s]+)\)", chunk):
            xy = list(map(int, pts.split()))
            pts_mm = [(xy[i] * scale, -xy[i + 1] * scale) for i in range(0, len(xy), 2)]
            for a, b in zip(pts_mm, pts_mm[1:]):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1])))
                t.SetEnd(pcbnew.VECTOR2I(MM(b[0]), MM(b[1])))
                t.SetWidth(MM(int(width) * scale))
                t.SetLayer(layers[lay])
                t.SetNet(net)
                board.Add(t)
                n_wires += 1
        for x, y in re.findall(r'\(via "[^"]+" (-?\d+) (-?\d+)', chunk):
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(MM(int(x) * scale), MM(-int(y) * scale)))
            v.SetWidth(MM(0.6))
            v.SetDrill(MM(0.3))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNet(net)
            board.Add(v)
            n_vias += 1
    return n_wires, n_vias


def drc(board_path: Path, report: Path) -> dict:
    board = pcbnew.LoadBoard(str(board_path))
    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.WriteDRCReport(board, str(report), pcbnew.EDA_UNITS_MILLIMETRES, True)
    txt = report.read_text()

    def count(label):
        m = re.search(rf"\*\* Found (\d+) {label}", txt)
        return int(m[1]) if m else None

    main = txt.split("unconnected pads")[0]
    errors = len(re.findall(r"Severity: error", main))
    warnings = len(re.findall(r"Severity: warning", main))
    kinds = sorted(set(re.findall(r"^\[(\w+)\]", main, re.M)))
    return {"violations": count("DRC violations"), "unconnected": count("unconnected pads"),
            "footprint_errors": count("Footprint errors"), "errors": errors, "warnings": warnings,
            "kinds": kinds}
