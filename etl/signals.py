"""ETL step: City of Vancouver traffic-signal locations -> signals (Task 6 / Phase 9).

CoV publishes signal *locations and kinds* only (timing is sold, not open — see
docs/research/signal-timing.md). This loads the locations for a study area and
maps each to the nearest SUMO traffic-light junction in that area's built net
(within a distance threshold), so a signal can be tied to its TLS where one
exists. The CoV ``type`` (Fixed Time / Semi Actuated / Pedestrian Actuated /
RRFB / ...) is kept as ``kind`` — it is the ground truth for which junctions
deserve a *vehicle* signal (Phase 9 signal truthing). Idempotent: an area's
rows are replaced wholesale on re-run.

    uv run python -m etl signals [--area peninsula|central|vancouver]
"""

from __future__ import annotations

from datetime import date
from math import atan2, cos, radians, sin, sqrt

import geopandas as gpd
from shapely.geometry import Polygon, box

from etl import config, db, util

SIGNALS_URL = "https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/traffic-signals/exports/geojson"
MATCH_THRESHOLD_M = 60.0

# CoV `type` values that control vehicle movements (vs pedestrian-only devices).
VEHICLE_KINDS = {"Fixed Time", "Semi Actuated", "Fully Actuated", "Bus Actuated Signal"}
PED_KINDS = {"Pedestrian Actuated Signal", "RRFB", "Special Crosswalk"}


def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    r = 6_371_000.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * atan2(sqrt(a), sqrt(1 - a))


def _tls_nodes(area: str) -> list[tuple[str, float, float]]:
    """Geo-located traffic-light junctions in an area's built net."""
    import sumolib

    net_path = config.SUMO_DIR / f"{area}.net.xml"
    if not net_path.exists():
        raise SystemExit(f"{net_path.name} missing — run `etl network --area {area}` first")
    net = sumolib.net.readNet(str(net_path))
    out = []
    for n in net.getNodes():
        if n.getType() in ("traffic_light", "traffic_light_right_on_red"):
            lon, lat = net.convertXY2LonLat(*n.getCoord())
            out.append((n.getID(), lon, lat))
    return out


def _nearest_tls(tls: list[tuple[str, float, float]], lon: float, lat: float) -> str | None:
    best, best_d = None, MATCH_THRESHOLD_M
    for tid, tlon, tlat in tls:
        d = _haversine_m(lon, lat, tlon, tlat)
        if d < best_d:
            best, best_d = tid, d
    return best


def _area_clip(area: str) -> Polygon:
    """The clip geometry per area: peninsula keeps its cordon, others their bbox."""
    if area == "peninsula":
        return Polygon(config.CORDON_POLYGON)
    bboxes = {"central": config.CENTRAL_BBOX, "vancouver": config.VANCOUVER_BBOX}
    if area not in bboxes:
        raise SystemExit(f"signals: unsupported area '{area}' (CoV data covers Vancouver only)")
    return box(*bboxes[area])


def run(args) -> int:
    area = getattr(args, "area", "peninsula") or "peninsula"
    print(f"=== etl signals: CoV signal locations -> signals ({area}) ===")
    refresh = getattr(args, "refresh", False)
    path = util.download_file(
        SIGNALS_URL, config.DATA_DIR / "signals" / "cov_signals.geojson", refresh
    )

    gdf = gpd.clip(gpd.read_file(path), _area_clip(area))
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]

    tls = _tls_nodes(area)
    # peninsula keeps its Phase-1 ids/source so existing references survive
    source = "cov_signals" if area == "peninsula" else f"cov_signals_{area}"
    prefix = "cov_sig" if area == "peninsula" else f"cov_{area}"
    rows = []
    for i, (_, r) in enumerate(gdf.iterrows()):
        pt = r.geometry.representative_point()
        rows.append(
            {
                "signal_id": f"{prefix}_{i:04d}",
                "name": r.get("geo_local_area"),
                "lon": pt.x,
                "lat": pt.y,
                "sumo_tls_id": _nearest_tls(tls, pt.x, pt.y),
                "kind": r.get("type"),
            }
        )

    conn = db.connect()
    db.init_db(conn)
    conn.execute("DELETE FROM signals WHERE source = ?", (source,))
    conn.executemany(
        f"""INSERT INTO signals(signal_id, name, lon, lat, sumo_tls_id, kind, source)
           VALUES(:signal_id, :name, :lon, :lat, :sumo_tls_id, :kind, '{source}')""",
        rows,
    )
    db.record_source(
        conn, "cov_signals", extract_date=date.today().isoformat(), row_count=len(rows)
    )
    conn.commit()
    conn.close()

    matched = sum(1 for r in rows if r["sumo_tls_id"])
    n_veh = sum(1 for r in rows if r["kind"] in VEHICLE_KINDS)
    n_ped = sum(1 for r in rows if r["kind"] in PED_KINDS)
    matched_tls = {r["sumo_tls_id"] for r in rows if r["sumo_tls_id"]}
    print(
        f"  signals in {area}: {len(rows)}  (vehicle {n_veh}, ped-only {n_ped}, "
        f"other {len(rows) - n_veh - n_ped});  matched to a SUMO TLS "
        f"(<{MATCH_THRESHOLD_M:.0f} m): {matched}"
    )
    print(
        f"  net traffic-light junctions: {len(tls)};  "
        f"with NO CoV signal nearby: {len(tls) - len(matched_tls)} (over-guessed candidates)"
    )
    return 0
