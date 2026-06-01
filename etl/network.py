"""ETL step: OpenStreetMap -> SUMO road network for the downtown peninsula.

Pipeline:
  1. Download the peninsula OSM extract via SUMO's ``osmGet.py`` (Overpass-backed),
     saving the raw OSM XML under ``data/osm/`` for provenance/reproducibility.
  2. ``netconvert`` the OSM into a SUMO ``.net.xml`` with actuated signals and the
     standard urban import options (see docs/development/phases/phase-1.md and the
     signal-timing decision in docs/architecture/decisions.md).
  3. Verify the result with ``sumolib`` and record provenance + network metadata
     in SQLite.

The manual ``netedit`` cleanup of bridges/gateways/lane-counts (Task 1) and the
``netdiff`` capture so edits survive an OSM re-import (Task 2) follow this step.

Idempotent: the cached OSM extract is reused (pass ``--refresh`` to re-download)
and the net is overwritten deterministically from the same inputs + options.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

from etl import config, db

NET_NAME = "peninsula"


def _osm_extract_path() -> Path:
    # osmGet.py writes "<prefix>_bbox.osm.xml" when invoked with --bbox.
    return config.OSM_DIR / f"{NET_NAME}_bbox.osm.xml"


def download_osm(refresh: bool = False) -> Path:
    """Fetch the peninsula OSM extract (cached unless ``refresh``)."""
    out = _osm_extract_path()
    if out.exists() and out.stat().st_size > 0 and not refresh:
        print(f"  OSM extract cached: {out} ({out.stat().st_size:,} bytes)")
        return out

    config.OSM_DIR.mkdir(parents=True, exist_ok=True)
    w, s, e, n = config.PENINSULA_BBOX
    osmget = config.sumo_tool("osmGet.py")
    # `--opt=value` form so the negative-longitude leading '-' isn't parsed as a flag.
    cmd = [sys.executable, str(osmget), f"--bbox={w},{s},{e},{n}", f"--prefix={NET_NAME}"]
    print("  $", " ".join(cmd), f"(cwd={config.OSM_DIR})")
    # osmGet.py writes into the working directory.
    subprocess.run(cmd, check=True, cwd=config.OSM_DIR)
    if not out.exists() or out.stat().st_size == 0:
        raise FileNotFoundError(f"osmGet.py did not produce {out}")
    print(f"  downloaded: {out} ({out.stat().st_size:,} bytes)")
    return out


def _netconvert_args(osm_path: Path, net_path: Path) -> list[str]:
    typemap = config.sumo_home() / "data" / "typemap"
    type_files = ",".join(
        str(typemap / t) for t in ("osmNetconvert.typ.xml", "osmNetconvertUrbanDe.typ.xml")
    )
    args = [
        "--osm-files",
        str(osm_path),
        "--type-files",
        type_files,
        "--output-file",
        str(net_path),
        # Signals: actuated defaults + coordination knobs (decisions.md).
        "--tls.default-type",
        "actuated",
        "--tls.min-dur",
        "5",
        "--tls.max-dur",
        "50",
        "--tls.cycle.time",
        "90",
        "--tls.yellow.time",
        "4",
        "--tls.guess-signals",
        "true",
        "--tls.join",
        "true",
        # Topology / geometry cleanup typical of OSM imports.
        "--geometry.remove",
        "true",
        "--roundabouts.guess",
        "true",
        "--ramps.guess",
        "true",
        "--junctions.join",
        "true",
        "--junctions.corner-detail",
        "5",
        "--no-turnarounds",
        "true",
        "--remove-edges.isolated",
        "true",
        # Keep the drivable + surface-transit network; drop foot/rail-only edges
        # (SkyTrain/SeaBus come in later via gtfs2pt as public-transport routes).
        "--keep-edges.by-vclass",
        "passenger,bus,taxi,delivery,truck,emergency,coach",
        # Keep UTM projection metadata so --fcd-output.geo works at sim time.
        "--proj.utm",
        "true",
        "--output.original-names",
        "true",
    ]
    # Cordon trim: keep only edges inside the peninsula polygon, then the largest
    # connected component — drops the across-water spillover (North Shore, Kits,
    # Mount Pleasant) and the stray long ways the generous bbox pulled in.
    if config.CORDON_POLYGON:
        args += [
            "--keep-edges.in-geo-boundary",
            config.cordon_geo_boundary(),
            "--keep-edges.components",
            "1",
        ]
    return args


def build_net(osm_path: Path) -> tuple[Path, list[str]]:
    """Run netconvert; return the net path and the exact argument list used."""
    config.SUMO_DIR.mkdir(parents=True, exist_ok=True)
    net_path = config.SUMO_DIR / f"{NET_NAME}.net.xml"
    args = _netconvert_args(osm_path, net_path)
    cmd = [str(config.sumo_bin("netconvert")), *args]
    print("  $ netconvert", " ".join(args))
    subprocess.run(cmd, check=True)
    if not net_path.exists():
        raise FileNotFoundError(f"netconvert did not produce {net_path}")
    return net_path, args


def verify_and_record(net_path: Path, osm_path: Path, args: list[str]) -> dict[str, int]:
    """Read the net back with sumolib, then persist provenance + metadata."""
    import sumolib

    net = sumolib.net.readNet(str(net_path))
    stats = {
        "n_edges": sum(1 for e in net.getEdges() if not e.getID().startswith(":")),
        "n_junctions": len(net.getNodes()),
        "n_tls": len(net.getTrafficLights()),
    }
    w, s, e, n = config.PENINSULA_BBOX
    conn = db.connect()
    db.init_db(conn)
    db.record_source(
        conn,
        "osm",
        extract_date=date.today().isoformat(),
        notes=f"Peninsula bbox {config.PENINSULA_BBOX}; downloaded via SUMO osmGet.py (Overpass).",
        row_count=stats["n_edges"],
    )
    conn.execute(
        """INSERT INTO network(name, net_path, osm_path, bbox_w, bbox_s, bbox_e, bbox_n,
                               proj, n_edges, n_junctions, n_tls, netconvert_args, source,
                               created_at)
           VALUES(?, ?, ?, ?, ?, ?, ?, 'utm', ?, ?, ?, ?, 'osm', datetime('now'))
           ON CONFLICT(name) DO UPDATE SET
             net_path=excluded.net_path, osm_path=excluded.osm_path,
             bbox_w=excluded.bbox_w, bbox_s=excluded.bbox_s,
             bbox_e=excluded.bbox_e, bbox_n=excluded.bbox_n,
             n_edges=excluded.n_edges, n_junctions=excluded.n_junctions,
             n_tls=excluded.n_tls, netconvert_args=excluded.netconvert_args,
             created_at=excluded.created_at""",
        (
            NET_NAME,
            str(net_path),
            str(osm_path),
            w,
            s,
            e,
            n,
            stats["n_edges"],
            stats["n_junctions"],
            stats["n_tls"],
            " ".join(args),
        ),
    )
    conn.commit()
    conn.close()
    return stats


def run(args) -> int:
    """CLI entry: OSM -> peninsula.net.xml, verified and recorded."""
    print("=== etl network: OSM -> SUMO peninsula net ===")
    osm_path = download_osm(refresh=getattr(args, "refresh", False))
    net_path, ncv_args = build_net(osm_path)
    stats = verify_and_record(net_path, osm_path, ncv_args)
    print(f"  net: {net_path}")
    print(f"  edges={stats['n_edges']}  junctions={stats['n_junctions']}  tls={stats['n_tls']}")
    print("  next (manual): netedit cleanup of bridges/gateways/lanes, then netdiff (Task 2).")
    return 0
