"""Reproducible duaIterate user-equilibrium wrapper (Phase 9B).

Phase 8c ran SUMO's duaIterate.py by hand; this wraps it as a first-class step:

    uv run python -m sim equilibrium --demand central --scale 0.10 \
        --iterations 7 --name central_eq2 [--begin 25200 --end 34200] [--seed 42]

* builds raw census trips (vTypes inline) for the window,
* runs duaIterate (meso, **--meso-junction-control** so priority/signal friction
  prices the routes — the Phase-8c equilibrium ignored junction control, which
  is why its routes jammed when replayed micro),
* percent-samples the converged step into ``step{N}_p{25,33,40,50,67}.rou.xml``
  (replay a pXX file via ``sim run --routes-file ... --reroute-prob 0``, or sweep
  them with ``sim sweep --routes-files``).

Everything lands in ``data/runs/<name>_dua/``. Expect ~1-1.5 h for 7 iterations
at central scale ~0.10.
"""

from __future__ import annotations

import gzip
import random
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from etl import config
from sim import demand_metro

# replicated from the Phase-8c hand run (data/runs/central_dua/iter3/*.cfg).
# NOTE: duaIterate sets weights.expand and ignore-errors itself — passing either
# again is a fatal "value already set" inside the generated duarcfg. Unroutable
# OD draws are removed by the pre-clean duarouter pass below instead (the
# Phase-8c hand run did the same: its input was literally `clean.trips.xml`).
DUAROUTER_OPTS = [
    "duarouter--weights.minor-penalty",
    "8",
    "duarouter--weights.priority-factor",
    "3",
]
# ... plus the Phase-9 fix: junction control priced into the meso travel times.
# (duaIterate owns time-to-teleport/begin/end-style options — don't duplicate.)
SUMO_OPTS = [
    "sumo--mesosim",
    "true",
    "sumo--meso-recheck",
    "0",
    "sumo--meso-junction-control",
    "true",
]
DEFAULT_SAMPLES = "40,60,80,100"  # % of the equilibrated demand to materialize


def _percent_sample(routes_gz: Path, out: Path, pct: int, seed: int) -> int:
    """Write a route file keeping each vehicle with probability pct/100."""
    rng = random.Random(seed + pct)
    kept = 0
    with gzip.open(routes_gz, "rb") as f, open(out, "w") as o:
        o.write("<routes>\n")
        for _ev, el in ET.iterparse(f, events=("end",)):
            if el.tag == "vType":
                o.write("  " + ET.tostring(el, encoding="unicode").strip() + "\n")
            elif el.tag == "vehicle":
                if rng.random() < pct / 100.0:
                    o.write("  " + ET.tostring(el, encoding="unicode").strip() + "\n")
                    kept += 1
                el.clear()
        o.write("</routes>\n")
    return kept


def cmd_equilibrium(args) -> int:
    from sim.cli import _PROFILES

    prof = _PROFILES.get(args.demand, _PROFILES["central"])
    net = config.SUMO_DIR / f"{prof['net']}.net.xml"
    out_dir = config.DATA_DIR / "runs" / f"{args.name}_dua"
    out_dir.mkdir(parents=True, exist_ok=True)
    trips = out_dir / f"{args.name}.trips.xml"

    print(
        f"=== sim equilibrium '{args.name}'  net={prof['net']}  scale={args.scale}  "
        f"iters={args.iterations} ==="
    )
    raw = out_dir / f"{args.name}_raw.trips.xml"
    demand_metro.build_demand(
        raw,
        scale=args.scale,
        seed=args.seed,
        refresh=True,
        net_name=prof["net"],
        home_code=prof["home"],
        window=(args.begin, args.end),
        assign=False,
    )
    # pre-clean: duaIterate aborts on the first unroutable trip (and owns the
    # ignore-errors option), so drop infeasible OD draws with one duarouter pass
    print("  $ duarouter --write-trips (pre-clean unroutable trips) ...")
    subprocess.run(
        [
            str(config.sumo_bin("duarouter")),
            "-n",
            str(net),
            "--route-files",
            str(raw),
            "-o",
            str(trips),
            "--write-trips",
            "true",
            "--ignore-errors",
            "true",
            "--no-step-log",
            "true",
            "--no-warnings",
            "true",
        ],
        check=True,
    )
    n_raw = sum(1 for line in open(raw) if "<trip " in line)
    n_clean = sum(1 for line in open(trips) if "<trip " in line)
    print(f"  routable trips: {n_clean:,} / {n_raw:,}")

    dua = config.sumo_tool("assign/duaIterate.py")
    cmd = [
        sys.executable,
        str(dua),
        "-n",
        str(net),
        "-t",
        str(trips),
        "-l",
        str(args.iterations),
        *DUAROUTER_OPTS,
        *SUMO_OPTS,
        # no begin/end/no-warnings/time-to-teleport: duaIterate owns those
        # options; each iteration runs until the (windowed) demand drains
    ]
    print(f"  $ duaIterate ({args.iterations} meso iterations, junction control ON) ...")
    print(f"    log: {out_dir}/dua.log")
    with open(out_dir / "dua.log", "w") as log:
        subprocess.run(cmd, check=True, cwd=out_dir, stdout=log, stderr=subprocess.STDOUT)

    last = args.iterations - 1
    final = out_dir / f"{last:03d}" / f"{args.name}_{last:03d}.rou.xml.gz"
    if not final.exists():
        raise SystemExit(f"duaIterate finished but {final} is missing — check dua.log")
    print(f"  converged routes: {final.relative_to(config.DATA_DIR)}")
    samples = [int(s) for s in (args.samples or DEFAULT_SAMPLES).split(",")]
    for pct in samples:
        out = out_dir / f"step{last:03d}_p{pct}.rou.xml"
        kept = _percent_sample(final, out, pct, args.seed)
        print(f"    {out.name}: {kept:,} vehicles ({pct}% ≈ scale {args.scale * pct / 100:.3f})")
    print(
        "  next: uv run python -m sim sweep --tag <tag> --reroute-prob 0 --routes-files "
        + ",".join(f"p{p}={out_dir / f'step{last:03d}_p{p}.rou.xml'}" for p in samples[:3])
    )
    return 0
