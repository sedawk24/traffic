"""Simulation CLI: ``uv run python -m sim run [options]``.

Generates demand (random or census), runs SUMO via the unified libsumo runner
(geo FCD + per-approach signal states + tripinfo, with optional mid-run closure
injection), post-processes the trajectory, and registers the run in SQLite.

  uv run python -m sim run --demand census --name census            # baseline
  uv run python -m sim run --demand census --name lionsgate \
        --scenario close_lions_gate                                 # closure scenario
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from importlib import metadata
from pathlib import Path

from etl import config, db
from sim import demand, demand_census, trace


def _sumo_version() -> str:
    try:
        return metadata.version("eclipse-sumo")
    except Exception:  # noqa: BLE001
        return "?"


def _scenario_event(name: str) -> dict | None:
    """The closure event (edge + window) for a named scenario, if any."""
    conn = db.connect()
    row = conn.execute(
        "SELECT e.target, e.start_s, e.end_s FROM scenarios s JOIN events e "
        "ON e.scenario_id = s.scenario_id WHERE s.name = ? AND e.kind = 'closure' "
        "ORDER BY e.event_id LIMIT 1",
        (name,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _tripinfo_metrics(path: Path) -> dict:
    """Aggregate before/after metrics from a SUMO tripinfo file."""
    if not path.exists():
        return {"completed": 0, "avg_duration": 0.0, "avg_wait": 0.0, "avg_route": 0.0}
    durs, waits, routes = [], [], []
    for t in ET.parse(path).getroot().iter("tripinfo"):
        durs.append(float(t.get("duration")))
        waits.append(float(t.get("waitingTime")))
        routes.append(float(t.get("routeLength")))
    n = len(durs) or 1
    return {
        "completed": len(durs),
        "avg_duration": sum(durs) / n,
        "avg_wait": sum(waits) / n,
        "avg_route": sum(routes) / n,
    }


def _register(args, traj_path, started_at, stats, scenario_name, closure) -> int:
    conn = db.connect()
    db.init_db(conn)
    conn.execute(
        "INSERT OR IGNORE INTO scenarios(name, description, base_network, created_at) "
        "VALUES('baseline', 'Baseline run, no events', 'peninsula', datetime('now'))"
    )
    row = conn.execute(
        "SELECT scenario_id FROM scenarios WHERE name = ?", (scenario_name,)
    ).fetchone()
    if row is None:
        row = conn.execute("SELECT scenario_id FROM scenarios WHERE name = 'baseline'").fetchone()
    sid = row[0]
    conn.execute("DELETE FROM runs WHERE trace_path = ?", (str(traj_path),))
    params = {
        "name": args.name,
        "demand": args.demand,
        "scale": args.scale,
        "scenario": scenario_name,
        "begin": args.begin,
        "end": args.end,
        "seed": args.seed,
        "with_transit": not args.no_transit,
        "closure": (
            {"edge": closure[0], "start": closure[1], "end": closure[2]}
            if closure[0] != "-"
            else None
        ),
    }
    cur = conn.execute(
        """INSERT INTO runs(scenario_id, status, started_at, finished_at, trace_path,
                            sumo_version, params, notes)
           VALUES(?, 'done', ?, datetime('now'), ?, ?, ?, ?)""",
        (sid, started_at, str(traj_path), _sumo_version(), json.dumps(params), json.dumps(stats)),
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


def cmd_run(args: argparse.Namespace) -> int:
    net = config.SUMO_DIR / "peninsula.net.xml"
    if not net.exists():
        raise SystemExit("peninsula.net.xml not found — run `uv run python -m etl network` first.")

    run_dir = config.DATA_DIR / "runs" / args.name
    run_dir.mkdir(parents=True, exist_ok=True)
    routes = run_dir / "routes.rou.xml"
    fcd, traj = run_dir / "fcd.parquet", run_dir / "trajectory.parquet"
    tls_out, tripinfo = run_dir / "tls_states.json", run_dir / "tripinfo.xml"

    closure, scenario_name = ("-", 0, 0), "baseline"
    if args.scenario:
        ev = _scenario_event(args.scenario)
        if not ev:
            raise SystemExit(f"scenario '{args.scenario}' has no closure event (see `etl events`)")
        closure, scenario_name = (ev["target"], ev["start_s"], ev["end_s"]), args.scenario

    print(f"=== sim run '{args.name}'  [{args.begin}..{args.end}s]  scenario={scenario_name} ===")
    started = datetime.now().isoformat(timespec="seconds")
    if args.demand == "census":
        demand_census.build_demand(
            routes, scale=args.scale, seed=args.seed, refresh=args.refresh_demand
        )
    else:
        demand.generate(
            net,
            routes,
            args.begin,
            args.end,
            args.period,
            args.fringe,
            args.seed,
            args.refresh_demand,
        )

    extra = ", closure" if args.scenario else ""
    print(f"  running SUMO (libsumo: FCD + signals + tripinfo{extra}) ...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "sim.librun",
            str(net),
            str(routes),
            str(args.begin),
            str(args.end),
            "0" if args.no_transit else "1",
            str(fcd),
            str(tls_out),
            str(tripinfo),
            closure[0],
            str(closure[1]),
            str(closure[2]),
        ],
        check=True,
        cwd=config.ROOT,
    )
    print("  post-processing FCD -> trajectory ...")
    tstats = trace.build_trajectory(fcd, traj, args.begin)
    metrics = _tripinfo_metrics(tripinfo)
    print(
        f"  vehicles={tstats['vehicles']:,}  peak_active={tstats['peak_active']}  |  "
        f"trips done={metrics['completed']}  avg travel={metrics['avg_duration']:.0f}s  "
        f"avg wait={metrics['avg_wait']:.0f}s"
    )

    rid = _register(
        args, traj, started, {"trajectory": tstats, "metrics": metrics}, scenario_name, closure
    )
    print(
        f"  registered run #{rid} ({scenario_name})  ->  {traj} ({traj.stat().st_size / 1e6:.1f} MB)"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sim", description="SUMO run -> trajectory trace")
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="generate demand, run SUMO, post-process, register")
    r.add_argument("--name", default="baseline", help="run name (-> data/runs/<name>/)")
    r.add_argument(
        "--demand",
        choices=["random", "census"],
        default="random",
        help="demand model: random (placeholder) or census (Phase-4 census-driven)",
    )
    r.add_argument("--scale", type=float, default=0.12, help="census demand sub-sampling factor")
    r.add_argument(
        "--scenario",
        default=None,
        help="closure scenario to inject mid-run (e.g. close_lions_gate)",
    )
    r.add_argument("--begin", type=int, default=25200, help="sim begin (s of day; default 07:00)")
    r.add_argument("--end", type=int, default=28800, help="sim end (s of day; default 08:00)")
    r.add_argument("--period", type=float, default=1.0, help="randomTrips insertion period (s)")
    r.add_argument("--fringe", type=float, default=5.0, help="randomTrips fringe-factor")
    r.add_argument("--seed", type=int, default=42)
    r.add_argument("--no-transit", action="store_true", help="exclude the Phase-1 bus pt")
    r.add_argument("--refresh-demand", action="store_true", help="regenerate routes")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        return cmd_run(args)
    return 1
