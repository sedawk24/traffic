"""Phase 6 calibration: simulated bridge crossings vs observed counts (GEH).

Closes the loop on the model's credibility. For a finished baseline run it:

1. counts the **AM-peak-hour two-way volume** the simulation puts across each
   bridge gateway (distinct vehicles on the gateway's edges in 07:30-08:30,
   read from the run's `fcd.parquet`);
2. fits a single **demand-scale** so those volumes best match the seeded
   `calibration_targets` (1-D search minimising total GEH) — the standard
   first-order calibration when only screenline counts are available;
3. computes **GEH** per screenline, writes `calibration_results`, and emits a
   coverage report (`docs/calibration/report.md`).

  uv run python -m sim calibrate --run am_base

GEH < 5 is the accepted "good match" threshold for hourly volumes. Per-gateway
residuals expose *routing* imbalance (a global scale can't fix a gateway the
demand model over- or under-feeds) — exactly what calibration should reveal.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from etl import config, db

# AM peak hour window (seconds of day) for the screenline count: 07:30-08:30,
# the heart of the AM peak within a 07:00-09:00 run.
PEAK_BEGIN, PEAK_END = 27000, 30600


def geh(sim: float, obs: float) -> float:
    """GEH statistic; < 5 is a good hourly-volume match, < 10 acceptable."""
    if sim + obs == 0:
        return 0.0
    return math.sqrt(2 * (sim - obs) ** 2 / (sim + obs))


def _gateway_edges() -> dict[str, set[str]]:
    """gateway_id -> its clean cordon-entry screenline (inbound + outbound edge).

    Uses the demand model's single best inbound/outbound edge at each gateway
    rather than the whole bridge+ramp footprint — a tight cut-line every crossing
    traverses exactly once, without catching nearby surface traffic.
    """
    import sumolib

    from sim import demand_census

    net = sumolib.net.readNet(str(config.SUMO_DIR / "peninsula.net.xml"))
    pairs = demand_census._gateway_edges(net, demand_census._peninsula_centroid(net))
    return {gw: {e for e in io if e} for gw, io in pairs.items()}


def _peak_crossings(fcd: Path, gw_edges: dict[str, set[str]]) -> dict[str, int]:
    """Distinct vehicles on each gateway's edges within the AM peak window."""
    import pyarrow.parquet as pq

    t = pq.read_table(fcd, columns=["timestep_time", "vehicle_lane", "vehicle_id"])
    tt = t["timestep_time"].to_pylist()
    lane = t["vehicle_lane"].to_pylist()
    vid = t["vehicle_id"].to_pylist()
    edge_gw: dict[str, list[str]] = {}
    for gw, es in gw_edges.items():
        for e in es:
            edge_gw.setdefault(e, []).append(gw)
    seen: dict[str, set] = {gw: set() for gw in gw_edges}
    for ti, ln, v in zip(tt, lane, vid):
        if ln is None or ti < PEAK_BEGIN or ti >= PEAK_END or ln.startswith(":"):
            continue
        for gw in edge_gw.get(ln.rsplit("_", 1)[0], ()):
            seen[gw].add(v)
    return {gw: len(s) for gw, s in seen.items()}


def _fit_scale(unit: dict[str, float], obs: dict[str, float]) -> float:
    """Demand scale minimising total GEH across the calibrated gateways."""
    keys = [g for g in obs if unit.get(g, 0) > 0]
    if not keys:
        return 1.0
    best_s, best = 1.0, math.inf
    s = 0.1
    while s <= 6.0:
        tot = sum(geh(s * unit[g], obs[g]) for g in keys)
        if tot < best:
            best, best_s = tot, s
        s += 0.02
    return round(best_s, 3)


def _find_run(conn, name: str) -> dict | None:
    for r in conn.execute(
        "SELECT run_id, trace_path, params FROM runs ORDER BY run_id DESC"
    ).fetchall():
        p = json.loads(r["params"])
        if p.get("name") == name:
            return {"run_id": r["run_id"], "trace_path": r["trace_path"], "params": p}
    return None


def _write_report(rows: list[dict], s_star: float, run_name: str, scale: float) -> Path:
    from sim.demand_census import GATEWAY_WEIGHT

    out = config.ROOT / "docs" / "calibration" / "report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    good = sum(1 for r in rows if r["geh"] < 5)
    mean_geh = sum(r["geh"] for r in rows) / (len(rows) or 1)
    factor = round(s_star / scale, 1) if scale else 1.0
    lines = [
        "# Calibration report — peninsula bridge screenlines",
        "",
        "Best-effort quantitative calibration of simulated AM-peak-hour bridge",
        "volumes against published counts. Calibration is data-limited by design",
        "(Phase 0 §7): City of Vancouver counts are VanMap-gated and BC MoTI's are",
        "per-site with no bulk API, so the targets below are the *obtainable subset*",
        "with confidence noted. GEH < 5 is the accepted good-match threshold.",
        "",
        f"- **Result:** {good}/{len(rows)} screenlines within GEH < 5;  mean GEH {mean_geh:.2f}.",
        "- **Gateway split:** corrected via per-gateway demand weights (below) — the",
        "  Phase-4 model over-fed the east viaduct and starved Lions Gate.",
        f"- **Demand magnitude:** the observed counts correspond to a full-demand scale of "
        f"~{s_star} (≈{factor}x the replay sub-sample {scale} used by `{run_name}`). "
        "Full-real-demand microsimulation exceeds SUMO's single-core ceiling (the project's "
        "core constraint), so replay sub-samples; gateway *shares* are scale-invariant, so "
        "the split calibration holds at the replay scale.",
        "- **AM peak window:** 07:30-08:30; observed = AADT x K_AM (see `etl/calibration.py`).",
        "",
        "| Gateway | Observed (veh/h) | Simulated (veh/h) | GEH | Confidence |",
        "|---------|------------------:|------------------:|----:|------------|",
    ]
    for r in sorted(rows, key=lambda x: x["geh"]):
        flag = "" if r["geh"] < 5 else (" ⚠️" if r["geh"] < 10 else " ❌")
        lines.append(
            f"| {r['gw']} | {r['obs']:,} | {r['sim']:,} | {r['geh']:.2f}{flag} | {r['conf']} |"
        )
    lines += [
        "",
        "## Gateway demand weights (the split calibration)",
        "",
        "Applied in `sim/demand_census.py` to bias the gateway choice; 1.0 = the plain",
        "geographic default. Scale-invariant, so they hold at any replay sub-sample.",
        "",
        "| Gateway | Weight |",
        "|---------|-------:|",
        *[f"| {gw} | {w} |" for gw, w in GATEWAY_WEIGHT.items()],
    ]
    lines += [
        "",
        "## Coverage (stated honestly)",
        "",
        "- **Calibrated:** the five bridge gateways above (Lions Gate, Granville,",
        "  Cambie, Burrard, Georgia/Dunsmuir viaducts) — the cordon screenlines that",
        "  carry essentially all external demand.",
        "- **Uncalibrated:** the diffuse *East gateways* (no single screenline count);",
        "  all internal peninsula links (no obtainable per-link counts); travel times",
        "  (TransLink RTDS retired — Phase 0 §2). Mode share is calibrated upstream by",
        "  the census loader, not here.",
        "- **Method caveat:** a single global demand scale corrects overall magnitude;",
        "  residual per-gateway GEH reflects route-choice imbalance the scale can't fix.",
        "  Low-confidence targets (Cambie, Burrard) are estimates — replace with",
        "  verified MoTI TRADAS / CoV station counts (backlog) before treating their",
        "  GEH as authoritative.",
        "",
    ]
    out.write_text("\n".join(lines))
    return out


def cmd_calibrate(args: argparse.Namespace) -> int:
    conn = db.connect()
    db.init_db(conn)
    run = _find_run(conn, args.run)
    if run is None:
        raise SystemExit(f"run '{args.run}' not found — run `sim run --name {args.run}` first.")
    scale = run["params"].get("scale") or 1.0
    fcd = Path(run["trace_path"]).parent / "fcd.parquet"
    if not fcd.exists():
        raise SystemExit(f"{fcd} not found (need the raw FCD for edge-level screenlines).")

    targets = conn.execute(
        "SELECT target_id, location, observed, source FROM calibration_targets "
        "WHERE kind='count' AND source LIKE 'calibration:%'"
    ).fetchall()
    if not targets:
        raise SystemExit("no calibration targets — run `uv run python -m etl calibrate` first.")

    print(f"=== sim calibrate: run '{args.run}' (scale {scale}) vs bridge screenlines ===")
    cross = _peak_crossings(fcd, _gateway_edges())
    obs = {t["location"]: t["observed"] for t in targets}
    tid = {t["location"]: t["target_id"] for t in targets}
    conf = {
        t["location"]: t["source"].split(":", 2)[1] if ":" in t["source"] else "?" for t in targets
    }
    unit = {gw: cross.get(gw, 0) / scale for gw in obs}  # scale=1.0 estimate
    s_star = _fit_scale(unit, obs)

    conn.execute("DELETE FROM calibration_results WHERE run_id = ?", (run["run_id"],))
    rows = []
    for gw in obs:
        sim = round(s_star * unit[gw])
        g = geh(sim, obs[gw])
        conn.execute(
            "INSERT INTO calibration_results(run_id, target_id, simulated, geh, computed_at) "
            "VALUES(?, ?, ?, ?, datetime('now'))",
            (run["run_id"], tid[gw], sim, g),
        )
        rows.append({"gw": gw, "obs": obs[gw], "raw": cross.get(gw, 0), "sim": sim, "geh": g, "conf": conf[gw]})
    conn.commit()
    conn.close()

    print(f"  calibrated demand scale -> --scale {s_star}  (was {scale})")
    print(f"  {'gateway':20s} {'obs':>7s} {'sim':>7s} {'GEH':>6s}")
    for r in sorted(rows, key=lambda x: x["geh"]):
        flag = "" if r["geh"] < 5 else ("  <-- GEH>=5" if r["geh"] < 10 else "  <-- GEH>=10")
        print(f"  {r['gw']:20s} {r['obs']:>7,} {r['sim']:>7,} {r['geh']:>6.2f}{flag}")
    good = sum(1 for r in rows if r["geh"] < 5)
    print(f"  {good}/{len(rows)} screenlines within GEH<5;  mean GEH {sum(r['geh'] for r in rows)/len(rows):.2f}")
    report = _write_report(rows, s_star, args.run, scale)
    print(f"  report -> {report}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sim-calibrate", description=__doc__)
    p.add_argument("--run", required=True, help="baseline run name to calibrate against")
    return p


def main(argv: list[str] | None = None) -> int:
    return cmd_calibrate(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
