"""Capture traffic-light states over time via libsumo, for the live-signal view.

Runs as its own process (``python -m sim.tlscapture ...``) so libsumo never
shares an interpreter with pyarrow — see the Arrow-clash note in
docs/architecture/decisions.md. Same net/routes (+pt) as the FCD run, so the
deterministic signal behaviour matches the trace.

Writes JSON: ``{begin, pos, changes}`` where
  pos[tls]     = [[lon,lat] | null, ...]  one stop-line per signal index
  changes[tls] = [[t, state], ...]        RYG state string per change, t since begin
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from etl import config


def capture(net: Path, routes: Path, begin: int, end: int, with_transit: bool, out: Path) -> None:
    import libsumo
    import sumolib

    route_files = [str(routes)]
    add_files: list[str] = []
    if with_transit:
        pt_routes = config.SUMO_DIR / "peninsula_pt_vehicles.rou.xml"
        pt_stops = config.SUMO_DIR / "peninsula_pt_stops.add.xml"
        pt_vtypes = config.SUMO_DIR / "peninsula_pt_vtypes.xml"
        if pt_routes.exists():
            route_files.append(str(pt_routes))
            add_files += [str(pt_vtypes), str(pt_stops)]

    cmd = [
        sumolib.checkBinary("sumo"), "-n", str(net), "-r", ",".join(route_files),
        "--begin", str(begin), "--end", str(end), "--ignore-route-errors", "true",
        "--time-to-teleport", "120", "--no-step-log", "true", "--no-warnings", "true",
    ]
    if add_files:
        cmd += ["-a", ",".join(add_files)]
    libsumo.start(cmd)

    ids = libsumo.trafficlight.getIDList()
    pos = {}
    for t in ids:
        stoplines = []
        for grp in libsumo.trafficlight.getControlledLinks(t):
            if grp:
                shape = libsumo.lane.getShape(grp[0][0])
                lon, lat = libsumo.simulation.convertGeo(*shape[-1])
                stoplines.append([round(lon, 6), round(lat, 6)])
            else:
                stoplines.append(None)
        pos[t] = stoplines

    changes: dict[str, list] = {t: [] for t in ids}
    last: dict[str, str] = {}
    while libsumo.simulation.getTime() < end:
        libsumo.simulationStep()
        now = int(libsumo.simulation.getTime()) - begin
        for t in ids:
            s = libsumo.trafficlight.getRedYellowGreenState(t)
            if last.get(t) != s:
                changes[t].append([now, s])
                last[t] = s
    libsumo.close()

    out.write_text(json.dumps({"begin": begin, "pos": pos, "changes": changes}))


if __name__ == "__main__":
    _net, _routes, _begin, _end, _wt, _out = sys.argv[1:7]
    capture(Path(_net), Path(_routes), int(_begin), int(_end), _wt == "1", Path(_out))
