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

# External demand enters/leaves the cut net on the SEVERED ARTERIALS — edges the
# bbox cut left with no incoming (entries) or no outgoing (exits). These are the
# real gateway corridors (E: Hastings/Powell/Broadway/Kingsway/Terminal, S: the
# Granville/Oak/Cambie bridge approaches, N: Stanley Park Causeway = Lions Gate,
# W: 4th/10th/16th/NW Marine to UBC), lane-weighted by capacity — the Phase 9
# fix for the Chinatown funnel, where every eastern municipality's demand piled
# onto ~80 NE-corner side-street edges.
ARTERIAL_TYPES = ("motorway", "trunk", "primary", "secondary", "tertiary")
GATEWAY_D_FLOOR_KM = 1.0  # distance floor so the very nearest stub can't dominate
# intra-city trips don't start/end on the heaviest arterial mid-blocks
HOME_END_EXCLUDE = ("motorway", "trunk", "primary")


def _edge_pools(net, home_code: str | None = None) -> tuple[dict, dict]:
    """Map each CSD to (origin pool, destination pool) of trip-end edges.

    * **metro** (``home_code=None``): a Voronoi split — every edge goes to its
      nearest CSD centroid, so trip-ends spread across each municipality's whole
      footprint instead of clustering at a point.
    * **single city** (``home_code`` set): the home city owns **every** street
      (intra-city trips spread everywhere, side streets included); every other
      CSD enters on the severed-arterial **entry stubs** nearest its centroid
      and exits on the **exit stubs** — suburb demand arrives on the real
      gateway corridors at their real capacities instead of on whichever side
      streets happen to lie nearest the suburb."""
    drivable, gw_in, gw_out = [], [], []
    for e in net.getEdges():
        if e.getID().startswith(":") or not e.allows("passenger"):
            continue
        x, y = e.getShape()[len(e.getShape()) // 2]
        etype = e.getType() or ""
        ok_out, ok_in = bool(e.getOutgoing()), bool(e.getIncoming())
        if ok_out and ok_in and e.getLength() >= 30:
            drivable.append((e.getID(), x, y, etype))
        if home_code and any(k in etype for k in ARTERIAL_TYPES):
            lanes = e.getLaneNumber()
            if ok_out and not ok_in:  # severed upstream: a real entry gateway
                gw_in.append((e.getID(), x, y, lanes))
            elif ok_in and not ok_out:  # severed downstream: an exit gateway
                gw_out.append((e.getID(), x, y, lanes))
    cxy = {code: net.convertLonLat2XY(lon, lat) for code, (lon, lat) in CENTROID.items()}

    if home_code:

        def gateway_pool(cands, cx, cy):
            """(edges, weights): weight = lanes / d_km² — a suburb's traffic
            concentrates on the gateway corridors facing it, in proportion to
            their capacity, without a hard cutoff."""
            if not cands:  # degenerate net: fall back to the nearest drivable edges
                order = sorted(drivable, key=lambda d: (d[1] - cx) ** 2 + (d[2] - cy) ** 2)
                return [d[0] for d in order[:80]], None
            edges, weights = [], []
            for eid, x, y, lanes in cands:
                d_km = max(GATEWAY_D_FLOOR_KM, (((x - cx) ** 2 + (y - cy) ** 2) ** 0.5) / 1000)
                edges.append(eid)
                weights.append(max(1, lanes) / (d_km * d_km))
            return edges, weights

        o_pools, d_pools = {}, {}
        for code, (cx, cy) in cxy.items():
            o_pools[code] = gateway_pool(gw_in, cx, cy)
            d_pools[code] = gateway_pool(gw_out, cx, cy)
        # the home city owns every street EXCEPT major-arterial mid-blocks —
        # nobody's driveway opens onto the middle of Granville; trips start and
        # end on the local/collector grid and use arterials to travel (Phase 9)
        home_edges = [d[0] for d in drivable if not any(k in d[3] for k in HOME_END_EXCLUDE)]
        o_pools[home_code] = d_pools[home_code] = (home_edges, None)
        print(
            f"  gateways: {len(gw_in)} severed-arterial entries / {len(gw_out)} exits "
            f"(capacity / distance² weighted);  home trip-end pool: {len(home_edges):,} edges"
        )
        return o_pools, d_pools

    codes = list(cxy)
    pools = {code: [] for code in codes}
    for eid, x, y, _t in drivable:
        best = min(codes, key=lambda c: (cxy[c][0] - x) ** 2 + (cxy[c][1] - y) ** 2)
        pools[best].append(eid)
    return {c: (p, None) for c, p in pools.items()}, {c: (p, None) for c, p in pools.items()}


def _pick(pool: tuple[list[str], list[float] | None], rng: random.Random) -> str:
    """Draw a trip-end edge from a (edges, weights|None) pool."""
    edges, weights = pool
    return rng.choices(edges, weights=weights, k=1)[0] if weights else rng.choice(edges)


def _sample_window(curve, window, rng):
    """Sample a departure time inside [begin, end) weighted by the census curve's
    density within the window. Returns None if the curve doesn't reach the window.
    Lets an AM-peak run generate *only* trips that actually depart in the window,
    instead of wasting ~3/4 of the demand on PM / off-peak trips that never run."""
    b, e = window
    bins = []
    for a, z, w in curve:
        lo, hi = max(a, b), min(z, e)
        if hi > lo and z > a:
            bins.append((lo, hi, w * (hi - lo) / (z - a)))
    if not bins:
        return None
    r = rng.random() * sum(x[2] for x in bins)
    acc = 0.0
    for lo, hi, w in bins:
        acc += w
        if r <= acc:
            return int(rng.uniform(lo, hi))
    return int(bins[-1][1])


def build_demand(
    out_routes: Path,
    scale: float = 0.10,
    seed: int = 42,
    refresh: bool = False,
    net_name: str = "metro",
    home_code: str | None = None,
    window: tuple[int, int] | None = None,
    assign: bool = True,
) -> Path:
    """Generate distributed census trips and assign routes with duarouter.

    Used for both the metro net (region-wide) and the vancouver net. On a
    single-city net pass ``home_code`` (that city's CSD): its trip-end pool
    becomes **every** street so intra-city trips spread across the whole city
    (incl. side streets), while other CSDs keep their boundary cells for the
    demand that crosses the city edge. With ``assign=False`` the raw trips file
    (vTypes inline) is written to ``out_routes`` instead — duaIterate's input."""
    if out_routes.exists() and out_routes.stat().st_size > 0 and not refresh:
        print(f"  {net_name} demand cached: {out_routes.name}")
        return out_routes

    import sumolib

    net = sumolib.net.readNet(str(config.SUMO_DIR / f"{net_name}.net.xml"))
    o_pools, d_pools = _edge_pools(net, home_code=home_code)
    rng = random.Random(seed)

    conn = db.connect()
    od = conn.execute(
        "SELECT origin, destination, count FROM od_flows WHERE source = 'statcan_od'"
    ).fetchall()
    conn.close()

    trips: list[tuple[int, str, str, str]] = []
    n_od = skipped = 0
    for r in od:
        o_pool = o_pools.get(r["origin"])
        d_code = NAME_TO_CODE.get((r["destination"] or "").replace(", B.C.", "").strip())
        d_pool = d_pools.get(d_code) if d_code else None
        if not (o_pool and o_pool[0]) or not (d_pool and d_pool[0]):
            skipped += 1
            continue
        n_od += 1
        for _ in range(int(round(r["count"] * CAR_SHARE * scale))):
            fr, to = _pick(o_pool, rng), _pick(d_pool, rng)
            if fr == to:
                continue
            if window:  # AM-peak run: one trip per commuter, departing in-window
                t = _sample_window(AM_WORK, window, rng)
                if t is not None:
                    trips.append((t, fr, to, "car"))
            else:  # full representative day: AM out + PM return
                trips.append((_sample_time(AM_WORK, rng), fr, to, "car"))
                trips.append((_sample_time(PM_WORK, rng), to, fr, "car"))
    win = f" (in-window {window[0]}-{window[1]})" if window else ""
    print(
        f"  {net_name} OD pairs used={n_od} (skipped {skipped} unmapped) "
        f"-> {len(trips)} trips (scale={scale}){win}"
    )
    if assign:
        _assign(net, trips, out_routes, net_name=net_name)
    else:
        from sim.demand_census import VTYPES

        trips.sort(key=lambda x: x[0])
        vt = VTYPES.replace("<additional>", "").replace("</additional>", "").strip("\n")
        with open(out_routes, "w") as f:
            f.write("<routes>\n" + vt + "\n")
            for i, (t, o, d, vt_id) in enumerate(trips):
                f.write(
                    f'  <trip id="t{i}" type="{vt_id}" depart="{t}" from="{o}" to="{d}"'
                    ' departLane="best" departSpeed="max" departPos="random_free"/>\n'
                )
            f.write("</routes>\n")
        print(f"  wrote raw trips (vTypes inline): {out_routes.name}")
    return out_routes
