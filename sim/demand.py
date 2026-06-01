"""Placeholder demand for the Phase 2 tracer bullet.

Uses SUMO's ``randomTrips.py`` to generate validated routes on the peninsula
net, biased toward the network fringe (the bridge/cordon gateways) so traffic
flows in and out across the bridges. This is deliberately *not* realistic — real
census-driven demand is Phase 4; here we only need vehicles moving.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from etl import config


def generate(
    net: Path,
    out_routes: Path,
    begin: int,
    end: int,
    period: float,
    fringe: float = 5.0,
    seed: int = 42,
    refresh: bool = False,
) -> Path:
    """Generate (and validate) placeholder routes; cached unless ``refresh``."""
    if out_routes.exists() and out_routes.stat().st_size > 0 and not refresh:
        print(f"  demand cached: {out_routes.name}")
        return out_routes

    out_routes.parent.mkdir(parents=True, exist_ok=True)
    trips = out_routes.with_suffix(".trips.xml")
    env = {**os.environ, "SUMO_HOME": str(config.sumo_home())}
    randomtrips = config.sumo_tool("randomTrips.py")
    cmd = [
        sys.executable,
        str(randomtrips),
        "-n",
        str(net),
        "-o",
        str(trips),
        "-r",
        str(out_routes),
        "-b",
        str(begin),
        "-e",
        str(end),
        "-p",
        str(period),
        "--fringe-factor",
        str(fringe),
        "--seed",
        str(seed),
        "--validate",
    ]
    print("  $ randomTrips.py", " ".join(cmd[2:]))
    subprocess.run(cmd, check=True, env=env)
    if not out_routes.exists():
        raise FileNotFoundError(f"randomTrips produced no routes at {out_routes}")
    return out_routes
