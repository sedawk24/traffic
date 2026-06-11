"""Census-driven demand for the peninsula (Phase 4).

Turns the SQLite OD matrix (StatCan 98-10-0459) + departure profiles
(98-10-0458) + land-use zones into SUMO routes for a representative weekday,
with realistic timing and the AM-in / PM-out rhythm. Deliberately heuristic —
municipality-level census is disaggregated to the sub-municipal cordon by:

  * land use → per-edge employment (work attraction) + population (home) weights,
  * external origins → the bridge gateway in their direction,
  * a peninsula job/pop share + car-mode share to scale municipal flows down,
  * stochastic departure times drawn from the census "time leaving for work"
    histogram (AM), mirrored to a synthetic PM peak for return trips.

Plus synthesized non-work and commercial/delivery/heavy-truck demand from
land-use generators. Routes are assigned with duarouter.
"""

from __future__ import annotations

import os
import random
import subprocess
from pathlib import Path

from etl import config, db

# --- land use -> trip-end weights -------------------------------------------
EMP_W = {
    "downtown-core": 1.0,
    "commercial": 0.85,
    "industrial": 0.55,
    "residential": 0.12,
    "parkland": 0.0,
}
POP_W = {
    "residential": 1.0,
    "downtown-core": 0.6,
    "commercial": 0.12,
    "industrial": 0.0,
    "parkland": 0.0,
}
FREIGHT_W = {
    "industrial": 1.0,
    "commercial": 0.5,
    "downtown-core": 0.2,
    "residential": 0.0,
    "parkland": 0.0,
}

# --- external origin CSD -> entry gateway group -----------------------------
NORTH_SHORE = {"5915046", "5915051", "5915055", "5915062", "5915065"}  # N/W Van, Bowen, Lions Bay
SOUTH = {"5915015", "5915011"}  # Richmond, Delta
SOUTH_GW = ["gw_burrard_bridge", "gw_granville_bridge", "gw_cambie_bridge"]
EAST_GW = ["gw_georgia_viaduct", "gw_east_arterials"]
VANCOUVER = "5915022"

# Per-gateway calibration weights (Phase 6): bias the within-group gateway choice
# so the simulated bridge split matches observed AADT (docs/calibration/report.md).
# 1.0 = the plain geographic default. The big correction is down-weighting the
# Georgia/Dunsmuir viaduct: the model's "east" bucket is most of Metro Van, but
# those commuters really fan out across surface arterials (east_arterials), not
# the viaduct — which is in reality the *smallest* crossing (40k AADT).
GATEWAY_WEIGHT = {
    "gw_lions_gate": 1.58,
    "gw_burrard_bridge": 1.15,
    "gw_granville_bridge": 1.36,
    "gw_cambie_bridge": 1.25,
    "gw_georgia_viaduct": 0.25,
    "gw_east_arterials": 1.0,
}


def _wchoice(group, rng):
    """Weighted gateway pick using the calibration weights."""
    return rng.choices(group, weights=[GATEWAY_WEIGHT.get(g, 1.0) for g in group], k=1)[0]

# Peninsula shares of City-of-Vancouver totals (downtown is the job core; the
# West End/Yaletown/downtown hold a large resident population).
JOB_SHARE, POP_SHARE = 0.45, 0.27
# Car-mode share by trip type (suburban commuters drive more than dense-core ones).
CAR_INBOUND, CAR_INTERNAL, CAR_OUTBOUND = 0.62, 0.42, 0.55
# Where Vancouver-internal downtown trips enter from (rest of the city).
INTERNAL_ENTRY = {"onpen": 0.30, "south": 0.40, "east": 0.30}

# Departure curves: (start_s, end_s, weight). AM from the census histogram;
# PM/midday synthesized. Times are seconds-of-day.
H = 3600
AM_WORK = [
    (5 * H, 6 * H, 0.039),
    (6 * H, 7 * H, 0.127),
    (7 * H, 8 * H, 0.220),
    (8 * H, 9 * H, 0.252),
    (9 * H, 12 * H, 0.223),
    (12 * H, 15 * H, 0.139),
]
PM_WORK = [
    (14 * H, 15 * H, 0.06),
    (15 * H, 16 * H, 0.20),
    (16 * H, 17 * H, 0.30),
    (17 * H, 18 * H, 0.26),
    (18 * H, 19 * H, 0.13),
    (19 * H, 21 * H, 0.05),
]
MIDDAY = [
    (9 * H, 11 * H, 0.25),
    (11 * H, 14 * H, 0.4),
    (14 * H, 17 * H, 0.25),
    (17 * H, 19 * H, 0.1),
]


def _peninsula_centroid(net):
    xs, ys = [], []
    for n in net.getNodes():
        xs.append(n.getCoord()[0])
        ys.append(n.getCoord()[1])
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _edge_pools(net):
    """Per land-use class, the list of drivable edge ids (trip-end candidates)."""
    import geopandas as gpd
    from shapely.geometry import Point

    zones = gpd.read_file(config.ZONES_DIR / "zones.geojson")
    zones = zones[zones.geometry.type.isin(["Polygon", "MultiPolygon"])][["land_use", "geometry"]]
    rows = []
    for e in net.getEdges():
        if e.getID().startswith(":") or not e.allows("passenger") or e.getLength() < 20:
            continue
        shp = e.getShape()
        x, y = shp[len(shp) // 2]
        lon, lat = net.convertXY2LonLat(x, y)
        rows.append({"id": e.getID(), "geometry": Point(lon, lat)})
    edges = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    j = gpd.sjoin(edges, zones, how="inner", predicate="within").drop_duplicates("id")
    pools: dict[str, list[str]] = {}
    for lu, grp in j.groupby("land_use"):
        pools[lu] = list(grp["id"])
    return pools


def _weighted_pool(pools, weights):
    """A flat (edges, cumulative-weight) sampler from class pools × class weight."""
    ids, cum, total = [], [], 0.0
    for lu, w in weights.items():
        if w <= 0 or lu not in pools:
            continue
        per = w / len(pools[lu])
        for eid in pools[lu]:
            total += per
            ids.append(eid)
            cum.append(total)
    return ids, cum, total


def _gateway_edges(net, centroid):
    """For each gateway zone, the best inbound + outbound drivable edge nearby."""
    import math

    conn = db.connect()
    gws = conn.execute(
        "SELECT zone_id, centroid_lon, centroid_lat FROM zones WHERE is_gateway = 1"
    ).fetchall()
    conn.close()
    out = {}
    cx, cy = centroid
    for g in gws:
        gx, gy = net.convertLonLat2XY(g["centroid_lon"], g["centroid_lat"])
        inbound, outbound, bi, bo = None, None, 1e18, 1e18
        for e in net.getEdges():
            if e.getID().startswith(":") or not e.allows("passenger"):
                continue
            shp = e.getShape()
            sx, sy = shp[0]
            ex, ey = shp[-1]
            dmid = math.hypot((sx + ex) / 2 - gx, (sy + ey) / 2 - gy)
            if dmid > 250:
                continue
            d_end = math.hypot(ex - cx, ey - cy)
            d_start = math.hypot(sx - cx, sy - cy)
            if d_end < d_start and dmid < bi:  # heads toward downtown = inbound
                bi, inbound = dmid, e.getID()
            elif d_start < d_end and dmid < bo:
                bo, outbound = dmid, e.getID()
        out[g["zone_id"]] = (inbound, outbound)
    return out


# --- sampling ---------------------------------------------------------------
def _sample(pool, rng):
    import bisect

    ids, cum, total = pool
    return ids[bisect.bisect_left(cum, rng.random() * total)] if ids else None


def _sample_time(curve, rng):
    r = rng.random() * sum(w for *_, w in curve)
    acc = 0.0
    for a, b, w in curve:
        acc += w
        if r <= acc:
            return int(rng.uniform(a, b))
    return int(curve[-1][1])


VTYPES = """<additional>
  <vType id="car" vClass="passenger" length="4.6" color="40,150,245"/>
  <vType id="hov" vClass="passenger" length="4.6" color="120,90,220"/>
  <vType id="delivery" vClass="delivery" length="6.5" color="150,92,60"/>
  <vType id="truck" vClass="truck" length="10.5" accel="1.3" color="120,70,50"/>
</additional>
"""


def build_demand(
    out_routes: Path, scale: float = 0.12, seed: int = 42, refresh: bool = False
) -> Path:
    """Generate census-driven trips and assign routes with duarouter."""
    if out_routes.exists() and out_routes.stat().st_size > 0 and not refresh:
        print(f"  census demand cached: {out_routes.name}")
        return out_routes

    import sumolib

    net = sumolib.net.readNet(str(config.SUMO_DIR / "peninsula.net.xml"))
    centroid = _peninsula_centroid(net)
    pools = _edge_pools(net)
    job, home, freight = (
        _weighted_pool(pools, EMP_W),
        _weighted_pool(pools, POP_W),
        _weighted_pool(pools, FREIGHT_W),
    )
    gw = _gateway_edges(net, centroid)
    rng = random.Random(seed)

    conn = db.connect()
    into = conn.execute(
        "SELECT origin, count FROM od_flows WHERE destination LIKE 'Vancouver (CY)%' AND origin != ?",
        (VANCOUVER,),
    ).fetchall()
    internal = conn.execute(
        "SELECT count FROM od_flows WHERE origin=? AND destination LIKE 'Vancouver (CY)%'",
        (VANCOUVER,),
    ).fetchone()
    outbound = conn.execute(
        "SELECT sum(count) s FROM od_flows WHERE origin=? AND destination NOT LIKE 'Vancouver (CY)%'",
        (VANCOUVER,),
    ).fetchone()
    conn.close()

    def sj():
        return _sample(job, rng)

    def sh():
        return _sample(home, rng)

    def sf():
        return _sample(freight, rng)

    def gin(gid):
        return gw.get(gid, (None, None))[0]

    def gout(gid):
        return gw.get(gid, (None, None))[1]

    trips: list[tuple[int, str, str, str]] = []

    def commute(o, d, am=True):
        if o and d and o != d:
            trips.append((_sample_time(AM_WORK if am else PM_WORK, rng), o, d, "car"))

    # 1. Inbound external commute: gateway -> downtown job (AM), job -> gateway (PM)
    n_ext = 0
    for r in into:
        grp = (
            ["gw_lions_gate"]
            if r["origin"] in NORTH_SHORE
            else SOUTH_GW
            if r["origin"] in SOUTH
            else EAST_GW
        )
        base = r["count"] * JOB_SHARE * CAR_INBOUND * scale
        for gid in grp:  # split the origin's demand across its gateways, weighted
            for _ in range(int(round(base / len(grp) * GATEWAY_WEIGHT.get(gid, 1.0)))):
                ino, j = gin(gid), sj()
                commute(ino, j, am=True)
                commute(j, gout(gid) or ino, am=False)
                n_ext += 1

    # 2. Internal Vancouver -> downtown job; entry split between on-peninsula / south / east
    n_int = 0
    for _ in range(int(round(internal["count"] * JOB_SHARE * CAR_INTERNAL * scale))):
        j = sj()
        u = rng.random()
        if u < INTERNAL_ENTRY["onpen"]:
            o = sh()
        elif u < INTERNAL_ENTRY["onpen"] + INTERNAL_ENTRY["south"]:
            o = gin(_wchoice(SOUTH_GW, rng))
        else:
            o = gin(_wchoice(EAST_GW, rng))
        commute(o, j, am=True)
        commute(j, o, am=False)
        n_int += 1

    # 3. Outbound: peninsula resident -> external work via a gateway (AM out, PM back)
    n_out = 0
    for _ in range(int(round((outbound["s"] or 0) * POP_SHARE * CAR_OUTBOUND * scale))):
        h = sh()
        gid = _wchoice(["gw_lions_gate", *SOUTH_GW, *EAST_GW], rng)
        commute(h, gout(gid), am=True)
        commute(gin(gid), h, am=False)
        n_out += 1

    # 4. Non-work (shopping/personal) — commercial/downtown, spread midday
    n_nonwork = int(round((n_ext + n_int) * 0.45))
    for _ in range(n_nonwork):
        a, b = sj(), (sh() if rng.random() < 0.5 else sj())
        if a and b and a != b:
            trips.append((_sample_time(MIDDAY, rng), a, b, "car"))

    # 5. Freight: delivery vans + heavy trucks from industrial/commercial generators
    n_freight = int(round((n_ext + n_int) * 0.16))
    for _ in range(n_freight):
        van = rng.random() < 0.7
        a = sf()
        b = sf() if rng.random() < 0.5 else sj()
        if a and b and a != b:
            trips.append((_sample_time(MIDDAY, rng), a, b, "delivery" if van else "truck"))

    print(
        f"  trips: ext-commute={n_ext} internal={n_int} outbound={n_out} "
        f"non-work={n_nonwork} freight={n_freight} -> {len(trips)} total (scale={scale})"
    )
    _assign(net, trips, out_routes)
    return out_routes


def _assign(net, trips, out_routes: Path, net_name: str = "peninsula") -> None:
    """Write a trips file (+ vTypes) and route it with duarouter."""
    out_routes.parent.mkdir(parents=True, exist_ok=True)
    vtypes = out_routes.with_name("census_vtypes.add.xml")
    vtypes.write_text(VTYPES)
    trips_xml = out_routes.with_suffix(".trips.xml")
    trips.sort(key=lambda x: x[0])
    with open(trips_xml, "w") as f:
        f.write("<routes>\n")
        for i, (t, o, d, vt) in enumerate(trips):
            # departLane/Speed/Pos (Phase 9): insert moving on the best lane at a
            # free spot — the defaults dropped every vehicle at speed 0 in lane 0,
            # manufacturing a brake-wave at each busy insertion edge.
            f.write(
                f'  <trip id="t{i}" type="{vt}" depart="{t}" from="{o}" to="{d}"'
                ' departLane="best" departSpeed="max" departPos="random_free"/>\n'
            )
        f.write("</routes>\n")

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
        str(out_routes),
        "--ignore-errors",
        "true",
        "--no-step-log",
        "true",
        "--no-warnings",
        "true",
    ]
    print("  $ duarouter (assigning routes) ...")
    subprocess.run(cmd, check=True, env=env)
    if not out_routes.exists():
        raise FileNotFoundError(f"duarouter produced no routes at {out_routes}")
    # duarouter copies the referenced vTypes from the -a file into its output, so
    # the routes file is already self-contained for the sim + signal capture.
