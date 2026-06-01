"""ETL step: TransLink GTFS static -> SUMO public transport (Task 3).

Runs SUMO's gtfs2pt.py to map the bus network onto the built peninsula net,
producing the SUMO pt inputs (stop definitions, vehicle routes, vehicle types).
Limited to `bus` and the cordon bbox: SkyTrain/rail/SeaBus need rail/water edges
the road net doesn't carry (visual rail is a later concern — see backlog), and
the GTFS feed is region-wide so the bbox keeps the mapping to the peninsula.

Outputs (SUMO inputs for Phase 2) under data/sumo/:
  peninsula_pt_stops.add.xml, peninsula_pt_vehicles.rou.xml, peninsula_pt_vtypes.xml
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

from etl import config, db, util

GTFS_URL = "https://gtfs-static.translink.ca/gtfs/google_transit.zip"


def _service_wednesday(gtfs_zip: Path) -> str:
    """A representative weekday (Wednesday) within the feed's calendar range."""
    import pandas as pd

    with zipfile.ZipFile(gtfs_zip) as zf:
        cal = pd.read_csv(zf.open("calendar.txt"))
    wed = cal[cal.wednesday == 1]
    start = dt.datetime.strptime(str(int(wed.start_date.min())), "%Y%m%d").date()
    end = dt.datetime.strptime(str(int(wed.end_date.max())), "%Y%m%d").date()
    day = start + dt.timedelta(days=(2 - start.weekday()) % 7)  # first Wed >= start
    return (day if day <= end else start).strftime("%Y%m%d")


def _count(path: Path, tag: str) -> int:
    return path.read_text().count(f"<{tag}") if path.exists() else 0


def run(args) -> int:
    print("=== etl transit: GTFS -> SUMO pt ===")
    refresh = getattr(args, "refresh", False)
    gtfs = util.download_file(GTFS_URL, config.GTFS_DIR / "google_transit.zip", refresh)
    net = config.SUMO_DIR / "peninsula.net.xml"
    svc_date = _service_wednesday(gtfs)
    print(f"  service date (representative Wed): {svc_date}")

    work = config.GTFS_DIR / "work"
    work.mkdir(parents=True, exist_ok=True)
    route_out = config.SUMO_DIR / "peninsula_pt_vehicles.rou.xml"
    add_out = config.SUMO_DIR / "peninsula_pt_stops.add.xml"
    vtype_out = config.SUMO_DIR / "peninsula_pt_vtypes.xml"
    w, s, e, n = config.PENINSULA_BBOX

    gtfs2pt = config.sumo_tool("import/gtfs/gtfs2pt.py")
    env = {**os.environ, "SUMO_HOME": str(config.sumo_home())}
    cmd = [
        sys.executable,
        str(gtfs2pt),
        "-n",
        str(net),
        "--gtfs",
        str(gtfs),
        "--date",
        svc_date,
        "--modes",
        "bus",
        # `--opt=value` so the negative-longitude leading '-' isn't parsed as a flag.
        f"--bbox={w},{s},{e},{n}",
        "--route-output",
        str(route_out),
        "--additional-output",
        str(add_out),
        "--vtype-output",
        str(vtype_out),
        "--repair",
    ]
    print("  $ gtfs2pt.py", " ".join(cmd[2:]))
    subprocess.run(cmd, check=True, cwd=work, env=env)

    n_stops = _count(add_out, "busStop") + _count(add_out, "trainStop")
    n_veh = _count(route_out, "vehicle")
    n_routes = _count(route_out, "route")
    if not route_out.exists():
        raise FileNotFoundError(f"gtfs2pt produced no route output at {route_out}")

    conn = db.connect()
    db.init_db(conn)
    db.record_source(conn, "gtfs_translink", extract_date=date.today().isoformat(), row_count=n_veh)
    conn.commit()
    conn.close()

    print(f"  pt stops: {n_stops}  routes: {n_routes}  vehicles: {n_veh}")
    print(f"  outputs: {add_out.name}, {route_out.name}, {vtype_out.name}")
    return 0
