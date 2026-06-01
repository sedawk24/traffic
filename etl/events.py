"""ETL step: DriveBC Open511 + canonical bridge closures -> scenario library (Task 6).

Two seeds for the Phase 5 injection demos:
  1. Canonical bridge-closure scenarios — one per closable gateway structure
     (Lions Gate, Burrard, Granville, Cambie, Georgia/Dunsmuir viaducts), each
     wired to the nearest drivable net edge so it can be injected via TraCI.
  2. Live DriveBC Open511 events near the peninsula approaches — a reference
     library of real closures (provincial highways only, so mostly feeding the
     cordon rather than inside it; stored without an edge target).

Idempotent: the seed/drivebc scenarios + events are replaced wholesale on re-run.
"""

from __future__ import annotations

import json
from datetime import date

from shapely.geometry import LineString, Point

from etl import config, db
from etl.zoning import GATEWAYS

OPEN511_URL = "https://api.open511.gov.bc.ca/events"
# A little wider than the cordon to catch the bridge approaches (e.g. Hwy 99 /
# Lions Gate on the North Shore side).
APPROACH_BBOX = "-123.20,49.24,-123.02,49.36"
# Gateways that correspond to a single closable structure (excludes the diffuse
# east-arterials gateway).
BRIDGE_GATEWAYS = {
    "gw_lions_gate",
    "gw_burrard_bridge",
    "gw_granville_bridge",
    "gw_cambie_bridge",
    "gw_georgia_viaduct",
}


def _nearest_edge(net, lon: float, lat: float) -> tuple[str | None, float]:
    """Nearest drivable edge id to a geo point, with distance in metres."""
    p = Point(*net.convertLonLat2XY(lon, lat))
    best, best_d = None, 1e18
    for e in net.getEdges():
        if e.getID().startswith(":") or not e.allows("passenger"):
            continue
        shape = e.getShape()
        if len(shape) < 2:
            continue
        d = LineString(shape).distance(p)
        if d < best_d:
            best, best_d = e.getID(), d
    return best, best_d


def _fetch_drivebc() -> list[dict]:
    import requests

    try:
        r = requests.get(OPEN511_URL, params={"bbox": APPROACH_BBOX, "format": "json"}, timeout=60)
        r.raise_for_status()
        return r.json().get("events", [])
    except Exception as exc:  # noqa: BLE001 — the live feed is best-effort
        print("  DriveBC fetch failed (continuing):", exc)
        return []


def run(args) -> int:
    print("=== etl events: DriveBC + canonical closures -> scenario library ===")
    import sumolib

    net = sumolib.net.readNet(str(config.SUMO_DIR / "peninsula.net.xml"))
    conn = db.connect()
    db.init_db(conn)
    conn.execute("DELETE FROM events WHERE source IN ('seed', 'drivebc')")
    conn.execute("DELETE FROM scenarios WHERE name LIKE 'close_%' OR name LIKE 'drivebc_%'")

    # 1. Canonical bridge-closure scenarios, wired to the nearest net edge.
    seeded = 0
    for zid, label, lon, lat in GATEWAYS:
        if zid not in BRIDGE_GATEWAYS:
            continue
        edge, dist = _nearest_edge(net, lon, lat)
        sid = conn.execute(
            "INSERT INTO scenarios(name, description, base_network, created_at) "
            "VALUES(?, ?, 'peninsula', datetime('now'))",
            (f"close_{zid.removeprefix('gw_')}", f"Close {label}"),
        ).lastrowid
        conn.execute(
            """INSERT INTO events(scenario_id, kind, target, lane, start_s, end_s, params, source)
               VALUES(?, 'closure', ?, NULL, 28800, 43200, ?, 'seed')""",
            (sid, edge, json.dumps({"gateway": zid})),
        )
        seeded += 1
        print(f"  seed: close_{zid.removeprefix('gw_'):16s} -> {edge} ({dist:.0f} m)")

    # 2. Live DriveBC events near the approaches (reference library; no edge target).
    drivebc = _fetch_drivebc()
    for ev in drivebc:
        eid = (ev.get("id") or "").split("/")[-1]
        sid = conn.execute(
            "INSERT INTO scenarios(name, description, base_network, created_at) "
            "VALUES(?, ?, 'peninsula', datetime('now'))",
            (f"drivebc_{eid}", (ev.get("headline") or ev.get("description") or "")[:200]),
        ).lastrowid
        conn.execute(
            """INSERT INTO events(scenario_id, kind, target, lane, start_s, end_s, params, source)
               VALUES(?, ?, NULL, NULL, NULL, NULL, ?, 'drivebc')""",
            (
                sid,
                (ev.get("event_type") or "incident").lower(),
                json.dumps(
                    {"id": ev.get("id"), "severity": ev.get("severity"), "roads": ev.get("roads")}
                ),
            ),
        )
    db.record_source(
        conn, "drivebc_open511", extract_date=date.today().isoformat(), row_count=len(drivebc)
    )
    conn.commit()
    conn.close()

    print(f"  canonical closure scenarios: {seeded};  DriveBC live events stored: {len(drivebc)}")
    return 0
