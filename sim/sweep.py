"""Density sweep harness (Phase 9B): measure a net/demand variant across scales.

Runs the same fixed-seed AM window at each scale (or replays given route files),
then reports the metrics that define "busy AND flowing":

    mean km/h (FCD-weighted) | % stopped | peak active | completed | avg wait | teleports

    uv run python -m sim sweep --tag v0_baseline --scales 0.05,0.075,0.10 \
        [--demand central] [--begin 25200 --end 30600] [--no-transit] [--no-tls-add]
    uv run python -m sim sweep --tag v2_ceiling --reroute-prob 0 \
        --routes-files p25=...rou.xml,p33=...rou.xml

Sweep runs live under ``data/runs/sweeps/<tag>/<label>/`` and are NOT registered
in the runs table (they are measurements, not replayable showcases); the table
is also written to ``data/runs/sweeps/<tag>.json``. Keep a variant iff at scale
0.075: mean speed +>=5% or %stopped ->=3pts vs baseline, teleports not worse.
"""

from __future__ import annotations

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from etl import config
from sim import demand_metro

STOP_SPEED = 0.5  # m/s, matches sim/diagnose.py


def _stats_metrics(path: Path) -> dict:
    """Teleports + insertion counters from SUMO --statistic-output."""
    out = {"teleports": 0, "jam": 0, "inserted": 0, "loaded": 0, "still_waiting": 0}
    if not path.exists():
        return out
    root = ET.parse(path).getroot()
    tele = root.find("teleports")
    veh = root.find("vehicles")
    if tele is not None:
        out["teleports"] = int(float(tele.get("total", 0)))
        out["jam"] = int(float(tele.get("jam", 0)))
    if veh is not None:
        out["inserted"] = int(float(veh.get("inserted", 0)))
        out["loaded"] = int(float(veh.get("loaded", 0)))
        out["still_waiting"] = int(float(veh.get("waiting", 0)))
    return out


def _fcd_metrics(path: Path) -> dict:
    """Speed/occupancy metrics over every FCD sample (vehicle-second weighted)."""
    import pandas as pd

    df = pd.read_parquet(path, columns=["timestep_time", "vehicle_id", "vehicle_speed"])
    if not len(df):
        return {"mean_kmh": 0.0, "pct_stopped": 100.0, "peak_active": 0, "vehicles": 0}
    return {
        "mean_kmh": round(float(df["vehicle_speed"].mean()) * 3.6, 1),
        "pct_stopped": round(float((df["vehicle_speed"] < STOP_SPEED).mean()) * 100, 1),
        "peak_active": int(df["timestep_time"].value_counts().max()),
        "vehicles": int(df["vehicle_id"].nunique()),
    }


def _run_one(
    label: str,
    run_dir: Path,
    args,
    routes_file: str | None,
) -> dict:
    """Demand (or replay routes) + librun + metrics for one sweep point."""
    from sim.cli import _PROFILES, _tripinfo_metrics, _use_routes_file

    prof = _PROFILES.get(args.demand, _PROFILES["central"])
    net = config.SUMO_DIR / f"{prof['net']}.net.xml"
    run_dir.mkdir(parents=True, exist_ok=True)
    routes = run_dir / "routes.rou.xml"
    scale = None
    if routes_file:
        _use_routes_file(Path(routes_file), routes)
    else:
        scale = float(label)
        demand_metro.build_demand(
            routes,
            scale=scale,
            seed=args.seed,
            refresh=True,
            net_name=prof["net"],
            home_code=prof["home"],
            window=(args.begin, args.end),
        )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "sim.librun",
            str(net),
            str(routes),
            str(args.begin),
            str(args.end),
            "1" if (prof["transit"] and not args.no_transit) else "0",
            str(run_dir / "fcd.parquet"),
            str(run_dir / "tls_states.json"),
            str(run_dir / "tripinfo.xml"),
            "-",
            "0",
            "0",
            "1" if prof["meso"] else "0",
            str(prof["fcd_period"]),
            str(args.reroute_prob),
            "0" if args.no_tls_add else "1",
        ],
        check=True,
        cwd=config.ROOT,
    )
    row = {"label": label, "scale": scale}
    row.update(_fcd_metrics(run_dir / "fcd.parquet"))
    ti = _tripinfo_metrics(run_dir / "tripinfo.xml")
    row.update(
        {
            "completed": ti["completed"],
            "avg_wait_s": round(ti["avg_wait"]),
            "avg_dur_s": round(ti["avg_duration"]),
        }
    )
    row.update(_stats_metrics(run_dir / "stats.xml"))
    return row


def _print_table(rows: list[dict]) -> None:
    hdr = (
        f"  {'label':>7} {'veh':>7} {'peak':>6} {'mean':>6} {'%stop':>6} "
        f"{'done':>7} {'wait':>6} {'telep':>6} {'unfin':>6}"
    )
    print("\n" + hdr)
    print("  " + "-" * (len(hdr) - 2))
    for r in rows:
        print(
            f"  {r['label']:>7} {r['vehicles']:>7,} {r['peak_active']:>6,} "
            f"{r['mean_kmh']:>5.1f}k {r['pct_stopped']:>5.1f}% {r['completed']:>7,} "
            f"{r['avg_wait_s']:>5}s {r['teleports']:>6} {r['inserted'] - r['completed']:>6}"
        )


def cmd_sweep(args) -> int:
    tag_dir = config.DATA_DIR / "runs" / "sweeps" / args.tag
    items: list[tuple[str, str | None]] = []
    if args.routes_files:
        for part in args.routes_files.split(","):
            lbl, _, path = part.partition("=")
            items.append((lbl.strip(), path.strip()))
    else:
        items = [(s.strip(), None) for s in args.scales.split(",")]

    print(
        f"=== sim sweep '{args.tag}'  [{args.begin}..{args.end}s]  demand={args.demand}  "
        f"transit={'off' if args.no_transit else 'on'}  tls-add={'off' if args.no_tls_add else 'on'} ==="
    )
    rows = []
    for label, routes_file in items:
        print(f"\n--- {args.tag}/{label} ---")
        t0 = datetime.now()
        row = _run_one(label, tag_dir / label, args, routes_file)
        row["wall_s"] = round((datetime.now() - t0).total_seconds())
        rows.append(row)
        print(
            f"  mean {row['mean_kmh']} km/h | {row['pct_stopped']}% stopped | "
            f"peak {row['peak_active']:,} | teleports {row['teleports']} | {row['wall_s']}s wall"
        )

    _print_table(rows)
    out = {
        "tag": args.tag,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "args": {
            "demand": args.demand,
            "begin": args.begin,
            "end": args.end,
            "seed": args.seed,
            "no_transit": args.no_transit,
            "no_tls_add": args.no_tls_add,
            "reroute_prob": args.reroute_prob,
            "routes_files": args.routes_files,
        },
        "rows": rows,
    }
    out_path = tag_dir.with_suffix(".json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=1))
    print(f"\n  wrote {out_path}")
    return 0
