"""Metro-wide census demand (Phase 7) — mesoscopic.

Turns the StatCan CSD->CSD commuting OD matrix (98-10-0459) into
municipality-to-municipality trips loaded onto the core Metro Vancouver arterial
network. Each Metro Van census subdivision (CSD) has a centroid -> a pool of
nearby drivable edges; trips run between origin and destination pools. CSDs
beyond the network bbox (Maple Ridge, Langley, Bowen Island ...) snap to the
nearest in-network edge, so their demand enters at the regional boundary like a
gateway. Departures follow the census AM curve with a mirrored PM peak; routes
are assigned with duarouter and the run executes mesoscopically.

Deliberately heuristic (municipality-resolution OD, centroid edge pools) — a
regional flow model, not a street-level one. Calibrating to screenline counts is
backlog work, as for the peninsula.
"""

from __future__ import annotations

import random
from pathlib import Path

from etl import config, db
from sim.demand_census import AM_WORK, PM_WORK, _assign, _sample_time

# Metro Vancouver (CD 5915) CSDs: code, "Name (TYPE)" label (matches the OD
# destination text minus ", B.C."), and an approximate centroid (lon, lat).
# Origins in the OD are codes; destinations are labels — both resolve here.
CSD = [
    ("5915001", "Langley (DM)", -122.62, 49.10),
    ("5915002", "Langley (CY)", -122.61, 49.10),
    ("5915004", "Surrey (CY)", -122.80, 49.13),
    ("5915007", "White Rock (CY)", -122.80, 49.02),
    ("5915011", "Delta (DM)", -123.04, 49.09),
    ("5915015", "Richmond (CY)", -123.13, 49.16),
    ("5915020", "Greater Vancouver A (RDA)", -123.24, 49.26),  # UBC/UEL
    ("5915022", "Vancouver (CY)", -123.11, 49.25),
    ("5915025", "Burnaby (CY)", -122.97, 49.24),
    ("5915029", "Port Coquitlam (CY)", -122.78, 49.26),
    ("5915034", "Coquitlam (CY)", -122.79, 49.28),
    ("5915036", "Belcarra (VL)", -122.93, 49.31),
    ("5915038", "Anmore (VL)", -122.85, 49.32),
    ("5915039", "Port Moody (CY)", -122.85, 49.28),
    ("5915043", "New Westminster (CY)", -122.91, 49.21),
    ("5915046", "North Vancouver (DM)", -123.04, 49.33),
    ("5915051", "West Vancouver (DM)", -123.16, 49.35),
    ("5915055", "North Vancouver (CY)", -123.07, 49.32),
    ("5915062", "Bowen Island (IM)", -123.38, 49.38),
    ("5915065", "Lions Bay (VL)", -123.24, 49.46),
    ("5915070", "Pitt Meadows (CY)", -122.69, 49.22),
    ("5915075", "Maple Ridge (CY)", -122.60, 49.22),
]
CENTROID = {code: (lon, lat) for code, _label, lon, lat in CSD}
NAME_TO_CODE = {label: code for code, label, _lon, _lat in CSD}

# Census car-driver mode share (StatCan 98-10-0458 for Greater Vancouver).
CAR_SHARE = 0.57
EDGES_PER_CSD = 60  # trip-end pool size per municipality centroid


def _edge_pools(net, k: int = EDGES_PER_CSD) -> dict[str, list[str]]:
    """For each CSD centroid, the k nearest drivable edges (its trip-end pool)."""
    eids, mids = [], []
    for e in net.getEdges():
        if e.getID().startswith(":") or not e.allows("passenger") or e.getLength() < 30:
            continue
        shp = e.getShape()
        eids.append(e.getID())
        mids.append(shp[len(shp) // 2])
    pools = {}
    for code, (lon, lat) in CENTROID.items():
        cx, cy = net.convertLonLat2XY(lon, lat)
        order = sorted(range(len(mids)), key=lambda i: (mids[i][0] - cx) ** 2 + (mids[i][1] - cy) ** 2)
        pools[code] = [eids[i] for i in order[:k]]
    return pools


def build_demand(
    out_routes: Path, scale: float = 0.10, seed: int = 42, refresh: bool = False
) -> Path:
    """Generate metro-wide census trips and assign routes with duarouter."""
    if out_routes.exists() and out_routes.stat().st_size > 0 and not refresh:
        print(f"  metro demand cached: {out_routes.name}")
        return out_routes

    import sumolib

    net = sumolib.net.readNet(str(config.SUMO_DIR / "metro.net.xml"))
    pools = _edge_pools(net)
    rng = random.Random(seed)

    conn = db.connect()
    od = conn.execute(
        "SELECT origin, destination, count FROM od_flows WHERE source = 'statcan_od'"
    ).fetchall()
    conn.close()

    trips: list[tuple[int, str, str, str]] = []
    n_od = skipped = 0
    for r in od:
        o_pool = pools.get(r["origin"])
        d_code = NAME_TO_CODE.get((r["destination"] or "").replace(", B.C.", "").strip())
        d_pool = pools.get(d_code) if d_code else None
        if not o_pool or not d_pool:
            skipped += 1
            continue
        n_od += 1
        for _ in range(int(round(r["count"] * CAR_SHARE * scale))):
            fr, to = rng.choice(o_pool), rng.choice(d_pool)
            if fr != to:
                trips.append((_sample_time(AM_WORK, rng), fr, to, "car"))  # AM outbound
                trips.append((_sample_time(PM_WORK, rng), to, fr, "car"))  # PM return
    print(
        f"  metro OD pairs used={n_od} (skipped {skipped} unmapped) "
        f"-> {len(trips)} trips (scale={scale})"
    )
    _assign(net, trips, out_routes, net_name="metro")
    return out_routes
