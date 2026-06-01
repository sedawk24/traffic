"""Idempotent ETL command-line interface.

    uv run python -m etl <command> [--db PATH] [--refresh]

Commands: init-db, network, transit, census, zoning, signals, events, all, status.
Each loader records its source + extract date for provenance and is safe to
re-run (re-running reproduces the same DB content).
"""

from __future__ import annotations

import argparse

from etl import calibration, census, config, db, events, network, signals, transit, zoning

# Ordered: network first (the geographic spine everything else attaches to).
STEPS = {
    "network": network.run,
    "zoning": zoning.run,
    "census": census.run,
    "transit": transit.run,
    "signals": signals.run,
    "events": events.run,
    "calibrate": calibration.run,
}


def cmd_init_db(args: argparse.Namespace) -> int:
    conn = db.connect(args.db)
    db.init_db(conn)
    conn.close()
    print(f"initialized schema (v{db.SCHEMA_VERSION}) in {args.db or config.DB_PATH}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    conn = db.connect(args.db)
    db.init_db(conn)
    print(f"db: {args.db or config.DB_PATH}")
    for table, count in db.table_counts(conn).items():
        print(f"  {table:22s} {count:>8d}")
    rows = conn.execute("SELECT name, license, extract_date FROM sources ORDER BY name").fetchall()
    if rows:
        print("sources:")
        for r in rows:
            print(f"  {r['name']:42s} {r['license'] or '':18s} {r['extract_date'] or ''}")
    conn.close()
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    cmd_init_db(args)
    for name, fn in STEPS.items():
        print(f"\n--- {name} ---")
        try:
            fn(args)
        except NotImplementedError as exc:
            print(f"  skipped: {exc}")
    print()
    return cmd_status(args)


def cmd_step(args: argparse.Namespace) -> int:
    conn = db.connect(args.db)
    db.init_db(conn)
    conn.close()
    return STEPS[args.command](args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="etl", description=__doc__)
    parser.add_argument("--db", default=None, help="SQLite path (default: data/traffic.db)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="create the SQLite schema")
    sub.add_parser("status", help="show table row counts + recorded sources")
    all_p = sub.add_parser("all", help="run init-db + every loader (skips unimplemented)")
    all_p.add_argument("--refresh", action="store_true", help="re-download source data")
    for name in STEPS:
        step_p = sub.add_parser(name, help=f"run the {name} loader")
        step_p.add_argument("--refresh", action="store_true", help="re-download source data")
        if name == "network":
            step_p.add_argument(
                "--area",
                choices=["peninsula", "metro"],
                default="peninsula",
                help="study area: peninsula (micro) or metro (meso, major roads)",
            )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "init-db":
        return cmd_init_db(args)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "all":
        return cmd_all(args)
    return cmd_step(args)
