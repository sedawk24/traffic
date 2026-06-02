"""Real SUMO bus vehicles from the GTFS timetable (Phase 8b).

gtfs2pt's per-trip routing is too slow/fragile on all-streets nets (it splits the
net by vclass and chokes on stop-mapping). So we build buses ourselves: snap each
GTFS bus trip's stops to the nearest bus-allowed edge, emit a SUMO trip with a
``<stop>`` at each (so the bus dwells), and let ``duarouter`` find the route
between them. The result is **real microscopic bus vehicles that stop at stops
and obey signals** — what the schedule-glide layer (huge nets) can't do.

Outputs ``data/sumo/<net>_pt_vehicles.rou.xml`` + ``<net>_pt_vtypes.xml``.
"""

from __future__ import annotations

import os
import subprocess
import zipfile

from etl import config

DWELL = 15  # seconds a bus dwells at each stop
SNAP_R = 80  # metres: snap a GTFS stop to the nearest bus edge within this radius
VTYPES = '<additional>\n  <vType id="bus" vClass="bus" length="12.0" color="25,115,255"/>\n</additional>\n'


def _bus_trips(gtfs, svc_date, bbox, window):
    """(first_depart_sec, [(lon,lat), ...]) for each bus trip active in window+bbox."""
    import pandas as pd

    w, s, e, n = bbox
    with zipfile.ZipFile(gtfs) as z:
        routes = pd.read_csv(z.open("routes.txt"), dtype={"route_id": str})
        trips = pd.read_csv(
            z.open("trips.txt"), dtype={"route_id": str, "trip_id": str, "service_id": str}
        )
        stops = pd.read_csv(z.open("stops.txt"), dtype={"stop_id": str})
        cal = pd.read_csv(z.open("calendar.txt"), dtype={"service_id": str})
        d = int(svc_date)
        active = set(
            cal[(cal.wednesday == 1) & (cal.start_date <= d) & (cal.end_date >= d)].service_id
        )
        bus_routes = set(routes[routes.route_type == 3].route_id)
        tid = set(trips[trips.route_id.isin(bus_routes) & trips.service_id.isin(active)].trip_id)
        st = pd.read_csv(
            z.open("stop_times.txt"),
            usecols=["trip_id", "arrival_time", "stop_id", "stop_sequence"],
            dtype={"trip_id": str, "stop_id": str},
        )
    st = st[st.trip_id.isin(tid)]
    sxy = {
        sid: (float(lo), float(la))
        for sid, lo, la in zip(stops.stop_id, stops.stop_lon, stops.stop_lat)
    }

    def secs(t):
        try:
            h, m, s2 = str(t).split(":")
            return int(h) * 3600 + int(m) * 60 + int(s2)
        except (ValueError, AttributeError):
            return None

    out = []
    for _tid, g in st.groupby("trip_id", sort=False):
        g = g.sort_values("stop_sequence")
        pts, t0 = [], None
        for sid, at in zip(g.stop_id, g.arrival_time):
            sec, xy = secs(at), sxy.get(sid)
            if sec is None or xy is None:
                continue
            if t0 is None:
                t0 = sec
            pts.append(xy)
        if len(pts) < 2 or t0 is None or t0 < window[0] or t0 > window[1]:
            continue
        if not any(w <= lon <= e and s <= lat <= n for lon, lat in pts):
            continue
        out.append((t0, pts))
    return out


def build(net_name: str, bbox, svc_date: str, window=(24000, 32400)) -> dict:
    import sumolib

    gtfs = config.GTFS_DIR / "google_transit.zip"
    net = sumolib.net.readNet(str(config.SUMO_DIR / f"{net_name}.net.xml"))
    bts = _bus_trips(gtfs, svc_date, bbox, window)

    def snap(lon, lat):
        x, y = net.convertLonLat2XY(lon, lat)
        best, bd = None, 1e18
        for edge, dist in net.getNeighboringEdges(x, y, SNAP_R):
            if edge.allows("bus") and not edge.getID().startswith(":") and dist < bd:
                best, bd = edge, dist
        return best.getID() if best else None

    trips_xml = config.SUMO_DIR / f"{net_name}_pt.trips.xml"
    n_written = 0
    with open(trips_xml, "w") as f:
        f.write("<routes>\n")
        for i, (t0, pts) in enumerate(bts):
            edges = []
            for lon, lat in pts:
                eid = snap(lon, lat)
                if eid and (not edges or edges[-1] != eid):
                    edges.append(eid)
            if len(edges) < 2:
                continue
            f.write(f'  <trip id="bus.{i}" type="bus" depart="{t0}" from="{edges[0]}" to="{edges[-1]}">\n')
            for eid in edges[1:-1]:  # a dwell stop at every intermediate stop
                f.write(f'    <stop edge="{eid}" duration="{DWELL}"/>\n')
            f.write("  </trip>\n")
            n_written += 1
        f.write("</routes>\n")

    # temp vtypes for duarouter — it copies the vType into its output, so we must
    # NOT also leave a separate <net>_pt_vtypes.xml (librun would double-define it).
    vtypes = config.SUMO_DIR / f"{net_name}_pt.vtypes_in.xml"
    vtypes.write_text(VTYPES)
    routes_out = config.SUMO_DIR / f"{net_name}_pt_vehicles.rou.xml"
    env = {**os.environ, "SUMO_HOME": str(config.sumo_home())}
    cmd = [
        str(config.sumo_bin("duarouter")),
        "-n",
        str(config.SUMO_DIR / f"{net_name}.net.xml"),
        "--route-files",
        str(trips_xml),
        "-a",
        str(vtypes),
        "-o",
        str(routes_out),
        "--ignore-errors",
        "true",
        "--no-step-log",
        "true",
        "--no-warnings",
        "true",
    ]
    print(f"  $ duarouter (routing {n_written} bus trips with stops) ...")
    subprocess.run(cmd, check=True, env=env)
    vtypes.unlink(missing_ok=True)  # vType is now embedded in routes_out
    (config.SUMO_DIR / f"{net_name}_pt_vtypes.xml").unlink(missing_ok=True)  # clear any stale copy
    routed = routes_out.read_text().count("<vehicle ") if routes_out.exists() else 0
    return {"buses": n_written, "routed": routed, "path": str(routes_out)}
