"""Signal re-timing wrapper (Phase 9B): green waves for a net + route flows.

Runs SUMO's tlsCoordinator.py (arterial green-wave offsets — the one signal
lever that measurably helped in Phase 8c, ~15%) and optionally
tlsCycleAdaptation.py (Webster per-intersection splits, program "a") against a
net and a representative route file, writing the add-files sim/librun.py
auto-loads (`{net}_tls_coord.add.xml` preferred over `{net}_tls_cycle.add.xml`):

    uv run python -m sim retime --net central --routes data/runs/central_eq2_dua/step006_p50.rou.xml [--cycle]

Re-run after any change to the net's TLS set (e.g. `etl signal-truth`) — stale
add-files reference junctions that may no longer be signalized.
"""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from etl import config


def _count_tls(add_file: Path) -> int:
    try:
        return sum(1 for _ev, el in ET.iterparse(str(add_file)) if el.tag == "tlLogic")
    except ET.ParseError:
        return -1


def cmd_retime(args) -> int:
    net = config.SUMO_DIR / f"{args.net}.net.xml"
    routes = Path(args.routes)
    if not net.exists():
        raise SystemExit(f"{net} missing")
    if not routes.exists():
        raise SystemExit(f"{routes} missing")
    print(f"=== sim retime: green-wave offsets for {net.name} from {routes.name} ===")

    coord_out = config.SUMO_DIR / f"{args.net}_tls_coord.add.xml"
    cmd = [
        sys.executable,
        str(config.sumo_tool("tlsCoordinator.py")),
        "-n",
        str(net),
        "-r",
        str(routes),
        "-o",
        str(coord_out),
    ]
    print("  $ tlsCoordinator ...")
    subprocess.run(cmd, check=True)
    print(f"  wrote {coord_out.name} ({_count_tls(coord_out)} coordinated TLS)")

    if getattr(args, "cycle", False):
        cycle_out = config.SUMO_DIR / f"{args.net}_tls_cycle.add.xml"
        cmd = [
            sys.executable,
            str(config.sumo_tool("tlsCycleAdaptation.py")),
            "-n",
            str(net),
            "-r",
            str(routes),
            "-o",
            str(cycle_out),
        ]
        print("  $ tlsCycleAdaptation ...")
        subprocess.run(cmd, check=True)
        print(f"  wrote {cycle_out.name} ({_count_tls(cycle_out)} re-timed TLS)")
        print("  note: librun prefers the coord file when both exist")
    return 0
