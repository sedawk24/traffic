"""Schedule-based bus vehicles for large nets (Phase 8).

gtfs2pt's per-trip routing is intractable on the all-streets city net (hours),
so for large areas we render buses straight from the GTFS **timetable**: each bus
trip becomes a polyline of its stops tagged with scheduled arrival times, and the
viewer animates a bus icon along it. These are a faithful *visual* of the transit
network running on schedule — they don't interact with car traffic (that needs
gtfs2pt's SUMO pt, which we keep for the small peninsula net).

Writes ``data/sumo/<net>_bus_schedule.json`` = {"buses": [{path, times}, ...]}
with ``times`` in seconds-of-day; the viewer offsets by the run's begin.
"""

from __future__ import annotations

import json
import zipfile

from etl import config


def _secs(t) -> int | None:
    try:
        h, m, s = str(t).split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)
    except (ValueError, AttributeError):
        return None


def build(net_name: str, bbox, svc_date: str, window=(24000, 32400)) -> dict:
    """Build the schedule-based bus polylines for a net's bbox + AM window."""
    import pandas as pd

    gtfs = config.GTFS_DIR / "google_transit.zip"
    w, s, e, n = bbox
    # GTFS ids are read as strings — TransLink mixes ints/strings across files,
    # which silently breaks isin() joins otherwise.
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
        trip_ids = set(
            trips[trips.route_id.isin(bus_routes) & trips.service_id.isin(active)].trip_id
        )
        st = pd.read_csv(
            z.open("stop_times.txt"),
            usecols=["trip_id", "arrival_time", "stop_id", "stop_sequence"],
            dtype={"trip_id": str, "stop_id": str},
        )

    st = st[st.trip_id.isin(trip_ids)]
    stop_xy = {
        sid: (round(float(lo), 6), round(float(la), 6))
        for sid, lo, la in zip(stops.stop_id, stops.stop_lon, stops.stop_lat)
    }

    buses = []
    for _tid, g in st.groupby("trip_id", sort=False):
        g = g.sort_values("stop_sequence")
        path, times = [], []
        for sid, at in zip(g.stop_id, g.arrival_time):
            sec = _secs(at)
            xy = stop_xy.get(sid)
            if sec is None or xy is None:
                continue
            path.append(list(xy))
            times.append(sec)
        if len(path) < 2 or times[-1] < window[0] or times[0] > window[1]:
            continue
        if not any(w <= p[0] <= e and s <= p[1] <= n for p in path):
            continue
        buses.append({"path": path, "times": times})

    out = config.SUMO_DIR / f"{net_name}_bus_schedule.json"
    out.write_text(json.dumps({"window": list(window), "buses": buses}))
    return {"buses": len(buses), "path": str(out)}
