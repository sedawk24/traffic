"""Simulation CLI: ``uv run python -m sim run [options]``.

Generates placeholder demand, runs SUMO via libsumo (geo FCD Parquet),
post-processes into a trajectory Parquet, and registers the run in SQLite.
Defaults to the 07:00-08:00 AM window so the Phase-1 transit is active.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from importlib import metadata

from etl import config, db
from sim import demand
from sim import run as runner
from sim import trace


def _sumo_version() -> str:
    try:
        return metadata.version("eclipse-sumo")
    except Exception:  # noqa: BLE001
        return "?"


def _register(args, traj_path, started_at: str, stats: dict) -> int:
    conn = db.connect()
    db.init_db(conn)
    conn.execute(
        "INSERT OR IGNORE INTO scenarios(name, description, base_network, created_at) "
        "VALUES('baseline', 'Placeholder-demand baseline (Phase 2), no events', "
        "'peninsula', datetime('now'))"
    )
    sid = conn.execute("SELECT scenario_id FROM scenarios WHERE name = 'baseline'").fetchone()[0]
    conn.execute("DELETE FROM runs WHERE trace_path = ?", (str(traj_path),))
    params = {
        "name": args.name,
        "begin": args.begin,
        "end": args.end,
        "period": args.period,
        "fringe": args.fringe,
        "seed": args.seed,
        "with_transit": not args.no_transit,
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
    routes = run_dir / "routes.rou.xml"
    fcd = run_dir / "fcd.parquet"
    traj = run_dir / "trajectory.parquet"

    print(f"=== sim run '{args.name}'  [{args.begin}..{args.end}s]  period={args.period}s ===")
    started = datetime.now().isoformat(timespec="seconds")
    demand.generate(
        net, routes, args.begin, args.end, args.period, args.fringe, args.seed, args.refresh_demand
    )
    print("  running SUMO (batch, geo FCD Parquet) ...")
    stats = runner.simulate(net, routes, fcd, args.begin, args.end, not args.no_transit)
    print("  post-processing FCD -> trajectory ...")
    tstats = trace.build_trajectory(fcd, traj, args.begin)
    print(
        f"  vehicles={tstats['vehicles']:,}  peak_active={tstats['peak_active']}  "
        f"rows={tstats['rows']:,}  by_class={tstats['by_class']}"
    )

    print("  capturing signal states (libsumo, separate process) ...")
    tls_out = run_dir / "tls_states.json"
    subprocess.run(
        [sys.executable, "-m", "sim.tlscapture", str(net), str(routes),
         str(args.begin), str(args.end), "0" if args.no_transit else "1", str(tls_out)],
        check=True, cwd=config.ROOT,
    )
    print(f"  signal states -> {tls_out.name} ({tls_out.stat().st_size // 1024} KB)")

    rid = _register(args, traj, started, {**stats, "trajectory": tstats})
    size_mb = traj.stat().st_size / 1e6
    print(f"  registered run #{rid}  ->  {traj} ({size_mb:.1f} MB)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sim", description="SUMO run -> trajectory trace")
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="generate demand, run SUMO, post-process, register")
    r.add_argument("--name", default="baseline", help="run name (-> data/runs/<name>/)")
    r.add_argument("--begin", type=int, default=25200, help="sim begin (s of day; default 07:00)")
    r.add_argument("--end", type=int, default=28800, help="sim end (s of day; default 08:00)")
    r.add_argument("--period", type=float, default=1.0, help="veh insertion + FCD period (s)")
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
