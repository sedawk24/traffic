"""ETL step: City of Vancouver traffic-signal locations -> signals (Task 6).

CoV publishes signal *locations* only (timing is sold, not open — see
docs/research/signal-timing.md). This loads the locations within the cordon and
maps each to the nearest SUMO traffic-light junction in the built peninsula net
(within a distance threshold), so a signal can be tied to its TLS where one
exists. Idempotent: the cov_signals rows are replaced wholesale on re-run.
"""

from __future__ import annotations

from datetime import date
from math import atan2, cos, radians, sin, sqrt

import geopandas as gpd
from shapely.geometry import Polygon

from etl import config, db, util

SIGNALS_URL = "https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/traffic-signals/exports/geojson"
MATCH_THRESHOLD_M = 60.0


def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    r = 6_371_000.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * atan2(sqrt(a), sqrt(1 - a))


def _tls_nodes() -> list[tuple[str, float, float]]:
    """Geo-located traffic-light junctions in the built peninsula net."""
    import sumolib

    net = sumolib.net.readNet(str(config.SUMO_DIR / "peninsula.net.xml"))
    out = []
    for n in net.getNodes():
        if n.getType() == "traffic_light":
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


def run(args) -> int:
    print("=== etl signals: CoV signal locations -> signals ===")
    refresh = getattr(args, "refresh", False)
    cordon = Polygon(config.CORDON_POLYGON)
    path = util.download_file(
        SIGNALS_URL, config.DATA_DIR / "signals" / "cov_signals.geojson", refresh
    )

    gdf = gpd.clip(gpd.read_file(path), cordon)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]

    tls = _tls_nodes()
    rows = []
    for i, (_, r) in enumerate(gdf.iterrows()):
        pt = r.geometry.representative_point()
        rows.append(
            {
                "signal_id": f"cov_sig_{i:04d}",
                "name": r.get("geo_local_area"),
                "lon": pt.x,
                "lat": pt.y,
                "sumo_tls_id": _nearest_tls(tls, pt.x, pt.y),
            }
        )

    conn = db.connect()
    db.init_db(conn)
    conn.execute("DELETE FROM signals WHERE source = 'cov_signals'")
    conn.executemany(
        """INSERT INTO signals(signal_id, name, lon, lat, sumo_tls_id, source)
           VALUES(:signal_id, :name, :lon, :lat, :sumo_tls_id, 'cov_signals')""",
        rows,
    )
    db.record_source(
        conn, "cov_signals", extract_date=date.today().isoformat(), row_count=len(rows)
    )
    conn.commit()
    conn.close()

    matched = sum(1 for r in rows if r["sumo_tls_id"])
    print(
        f"  signals in cordon: {len(rows)};  matched to a SUMO TLS (<{MATCH_THRESHOLD_M:.0f} m): {matched}"
    )
    print(f"  net traffic-light junctions: {len(tls)}")
    return 0
