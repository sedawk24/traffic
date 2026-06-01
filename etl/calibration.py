"""ETL step: published bridge-crossing counts -> calibration_targets (Phase 6).

The peninsula is cordoned at its bridges, so the bridge crossings are the
natural calibration **screenlines**: every external trip enters or leaves over
one of them. We seed the published Average Annual Daily Traffic (AADT) for each
crossing, converted to an AM-peak-hour two-way target via a standard K-factor,
into `calibration_targets`.

These are the **obtainable subset** (Phase 0 research: City of Vancouver counts
sit behind VanMap, not a bulk feed, and BC MoTI's are per-site with no bulk
API), so confidence varies by source and coverage is documented honestly in
`docs/calibration/report.md`. Replace the estimates with verified MoTI TRADAS /
CoV station counts when obtained (see backlog).

Idempotent: the `calibration:*` targets are replaced wholesale on re-run.
"""

from __future__ import annotations

from datetime import date

from etl import db

# AM-peak-hour volume as a fraction of AADT (two-way). A standard urban
# commuter-corridor K-factor; a documented assumption to revisit once real
# hourly counts are in hand.
K_AM = 0.09

# gateway_id -> (AADT veh/day, confidence, source citation). Confidence reflects
# how directly the figure is sourced (see docs/research/data-sources.md §7).
BRIDGE_AADT = {
    "gw_lions_gate": (55596, "high", "Lions Gate Bridge 55,596 veh/day (2024) — Wikipedia, citing BC MoTI"),
    "gw_granville_bridge": (65000, "medium", "Granville St Bridge ~65,000 veh/day (8 lanes) — Wikipedia"),
    "gw_georgia_viaduct": (40000, "medium", "Georgia+Dunsmuir Viaducts ~40,000 veh/day combined — CoV NE False Creek plan / Daily Hive"),
    "gw_cambie_bridge": (55000, "low", "Cambie Bridge ~55,000 veh/day (6 lanes; estimate — CoV counts VanMap-gated)"),
    "gw_burrard_bridge": (50000, "low", "Burrard Bridge ~50,000 veh/day (4 lanes, post bike-lanes; estimate — CoV counts VanMap-gated)"),
}


def run(args) -> int:
    print("=== etl calibrate: published bridge AADT -> AM-peak count targets ===")
    conn = db.connect(getattr(args, "db", None))
    db.init_db(conn)
    conn.execute("DELETE FROM calibration_targets WHERE source LIKE 'calibration:%'")
    n = 0
    for gw, (aadt, conf, cite) in BRIDGE_AADT.items():
        observed = round(aadt * K_AM)
        conn.execute(
            "INSERT INTO calibration_targets(kind, location, period, observed, unit, source) "
            "VALUES('count', ?, 'AM peak hr (2-way)', ?, 'veh/h', ?)",
            (gw, observed, f"calibration:{conf}: {cite}; = {aadt:,} AADT x K_AM={K_AM}"),
        )
        n += 1
        print(f"  {gw:20s} {aadt:>6,} AADT  ->  {observed:>5,} veh/h  [{conf}]")
    db.record_source(
        conn, "bridge_counts_published", extract_date=date.today().isoformat(), row_count=n
    )
    conn.commit()
    conn.close()
    print(f"  seeded {n} bridge screenline targets (East gateways left uncalibrated — diffuse, no screenline)")
    return 0
