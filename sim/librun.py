"""Unified libsumo simulation run (Phase 5).

One libsumo process emits everything a run needs — geo FCD Parquet, per-approach
traffic-signal states, and tripinfo metrics — and can inject a mid-run **closure**
(disallow an edge's lanes at a chosen time, with rerouting devices so traffic
redistributes). Runs as its own process so libsumo never shares an interpreter
with pyarrow (the Arrow-clash note in docs/architecture/decisions.md).

Usage (invoked by sim.cli):
  python -m sim.librun NET ROUTES BEGIN END WITH_TRANSIT FCD TLS TRIPINFO \
                       CLOSURE_EDGE CLOSURE_START CLOSURE_END
where CLOSURE_EDGE is '-' for a plain (baseline) run.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from etl import config

# vehicle classes to bar when a closure is active (everything road-going)
CLOSE_CLASSES = ["passenger", "bus", "taxi", "coach", "delivery", "truck", "emergency"]


def run(
    net_path: Path,
    routes: Path,
    begin: int,
    end: int,
    with_transit: bool,
    fcd_out: Path,
    tls_out: Path,
    tripinfo_out: Path,
    closure_edge: str | None = None,
    closure_start: int = 0,
    closure_end: int = 0,
    meso: bool = False,
    fcd_period: int = 0,
    reroute_prob: float = 1.0,
) -> None:
    import libsumo
    import sumolib

    net = sumolib.net.readNet(str(net_path))
    net_name = net_path.name.split(".")[0]
    route_files = [str(routes)]
    add_files: list[str] = []
    if with_transit:
        pt_routes = config.SUMO_DIR / f"{net_name}_pt_vehicles.rou.xml"
        if pt_routes.exists():
            route_files.append(str(pt_routes))
            # vtypes + stop defs — only add what exists (central buses carry
            # inline stops, so there's no separate stops.add.xml).
            for fn in (f"{net_name}_pt_vtypes.xml", f"{net_name}_pt_stops.add.xml"):
                p = config.SUMO_DIR / fn
                if p.exists():
                    add_files.append(str(p))
    # demand-adapted signal timings. Prefer coordinated green-wave offsets
    # (tlsCoordinator -> *_tls_coord.add.xml, which retunes the running program's
    # offsets so arterials progress) over per-intersection cycle adaptation
    # (tlsCycleAdaptation -> *_tls_cycle.add.xml, program "a"). The coordinated
    # file patches the default program in place, so it needs no activation switch.
    tls_coord = config.SUMO_DIR / f"{net_name}_tls_coord.add.xml"
    tls_cycle = config.SUMO_DIR / f"{net_name}_tls_cycle.add.xml"
    tls_add = tls_coord if tls_coord.exists() else tls_cycle
    tls_program = None if tls_coord.exists() else "a"
    if tls_add.exists():
        add_files.append(str(tls_add))

    cmd = [
        sumolib.checkBinary("sumo"),
        "-n",
        str(net_path),
        "-r",
        ",".join(route_files),
        "--fcd-output",
        str(fcd_out),
        "--fcd-output.geo",
        "true",
        "--tripinfo-output",
        str(tripinfo_out),
        "--device.rerouting.probability",
        str(reroute_prob),
        "--device.rerouting.period",
        "90",
        "--begin",
        str(begin),
        "--end",
        str(end),
        "--ignore-route-errors",
        "true",
        "--time-to-teleport",
        "120",
        # short Vancouver blocks spill back through the upstream junction and
        # cascade into gridlock; let a vehicle nudge through a junction it has
        # been blocked at for >20 s (drivers do) so deadlocks break instead of lock.
        "--ignore-junction-blocker",
        "20",
        "--no-step-log",
        "true",
        "--no-warnings",
        "true",
    ]
    # routing is the only part SUMO threads usefully; the micro core is sequential
    # (--threads gives no meaningful speedup, per SUMO #4767), so we don't set it.
    if reroute_prob > 0:
        nthr = max(1, (os.cpu_count() or 4) - 2)
        cmd += ["--device.rerouting.threads", str(nthr)]
    if meso:
        cmd += ["--mesosim"]  # mesoscopic (queue-based) for the regional scale
    if fcd_period > 0:
        # sample FCD coarsely (regional view renders flow, not every car; the
        # all-streets city run is large) — keeps the trace small enough to replay
        cmd += ["--device.fcd.period", str(fcd_period)]
    if add_files:
        cmd += ["-a", ",".join(add_files)]
    libsumo.start(cmd)

    # static signal geometry (stop-line per movement) + approach edge. Skipped
    # for meso: thousands of regional TLS aren't shown at regional zoom and the
    # per-step capture would dominate runtime + trace size.
    ids = [] if meso else libsumo.trafficlight.getIDList()
    if tls_add.exists() and tls_program and not meso:  # activate the fixed-cycle program
        for t in ids:
            try:
                libsumo.trafficlight.setProgram(t, tls_program)
            except Exception:  # noqa: BLE001 — TLS without an adapted program keep default
                pass
    pos, edges = {}, {}
    for t in ids:
        stoplines, es = [], []
        for grp in libsumo.trafficlight.getControlledLinks(t):
            if grp:
                lane = grp[0][0]
                lon, lat = libsumo.simulation.convertGeo(*libsumo.lane.getShape(lane)[-1])
                stoplines.append([round(lon, 6), round(lat, 6)])
                es.append(libsumo.lane.getEdgeID(lane))
            else:
                stoplines.append(None)
                es.append(None)
        pos[t] = stoplines
        edges[t] = es

    close_lanes = []
    if closure_edge and closure_edge != "-":
        for eid in closure_edge.split(","):  # the full bridge edge set (both directions)
            try:
                close_lanes += [ln.getID() for ln in net.getEdge(eid).getLanes()]
            except KeyError:
                pass

    changes: dict[str, list] = {t: [] for t in ids}
    last: dict[str, str] = {}
    closed = reopened = False
    while libsumo.simulation.getTime() < end:
        now = int(libsumo.simulation.getTime())
        if close_lanes and not closed and now >= closure_start:
            for ln in close_lanes:
                libsumo.lane.setDisallowed(ln, CLOSE_CLASSES)
            closed = True
        if close_lanes and closed and not reopened and closure_end and now >= closure_end:
            for ln in close_lanes:
                libsumo.lane.setDisallowed(ln, [])
            reopened = True
        libsumo.simulationStep()
        rel = int(libsumo.simulation.getTime()) - begin
        for t in ids:
            s = libsumo.trafficlight.getRedYellowGreenState(t)
            if last.get(t) != s:
                changes[t].append([rel, s])
                last[t] = s
    libsumo.close()

    tls_out.write_text(json.dumps({"begin": begin, "pos": pos, "edges": edges, "changes": changes}))


if __name__ == "__main__":
    a = sys.argv
    run(
        Path(a[1]),
        Path(a[2]),
        int(a[3]),
        int(a[4]),
        a[5] == "1",
        Path(a[6]),
        Path(a[7]),
        Path(a[8]),
        None if a[9] == "-" else a[9],
        int(a[10]),
        int(a[11]),
        meso=len(a) > 12 and a[12] == "1",
        fcd_period=int(a[13]) if len(a) > 13 else 0,
        reroute_prob=float(a[14]) if len(a) > 14 else 1.0,
    )
