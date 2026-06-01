"""Run a scenario in SUMO, emitting sampled geo FCD as Parquet.

Uses the ``sumo`` binary in a subprocess for the batch FCD dump. Rationale:
libsumo and pyarrow each bundle Arrow and clash if imported in one process, and
a non-interactive batch runs at the same speed via the binary. Live event
injection (Phase 5) uses libsumo/traci, with FCD post-processing kept in a
separate process. (See docs/architecture/decisions.md.)

Optionally co-loads the Phase-1 transit pt so buses run alongside the traffic.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from etl import config


def simulate(
    net: Path,
    routes: Path,
    fcd_path: Path,
    begin: int,
    end: int,
    with_transit: bool = True,
) -> dict:
    """Run begin->end and write geo FCD Parquet. Returns the run config."""
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

    fcd_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sumolib.checkBinary("sumo"),
        "-n", str(net),
        "-r", ",".join(route_files),
        "--fcd-output", str(fcd_path),
        "--fcd-output.geo", "true",
        "--begin", str(begin),
        "--end", str(end),
        "--ignore-route-errors", "true",
        "--time-to-teleport", "120",
        "--no-step-log", "true",
        "--no-warnings", "true",
    ]
    if add_files:
        cmd += ["-a", ",".join(add_files)]

    subprocess.run(cmd, check=True)
    if not fcd_path.exists():
        raise FileNotFoundError(f"SUMO produced no FCD at {fcd_path}")
    return {"begin": begin, "end": end, "duration_s": end - begin, "with_transit": with_transit}
