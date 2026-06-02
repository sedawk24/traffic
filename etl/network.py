"""ETL step: OpenStreetMap -> SUMO road network.

Builds one of two study areas (``etl network --area peninsula|metro``):

* **peninsula** (default) — the downtown Vancouver peninsula, all drivable
  streets, trimmed to the bridge cordon. Driven microscopically.
* **metro** — core urbanized Metro Vancouver, **major roads only**
  (motorway…tertiary), tiled OSM download. Driven mesoscopically (Phase 7).

Pipeline:
  1. Download the OSM extract via SUMO's ``osmGet.py`` (Overpass-backed), saving
     the raw OSM XML under ``data/osm/`` for provenance/reproducibility.
  2. ``netconvert`` the OSM into a SUMO ``.net.xml`` with actuated signals and
     the standard urban import options.
  3. Verify with ``sumolib`` and record provenance + metadata in SQLite.

Idempotent: the cached OSM extract is reused (``--refresh`` re-downloads) and the
net is overwritten deterministically from the same inputs + options.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

from etl import config, db


def _area(area: str) -> dict:
    """Per-area build parameters."""
    if area == "metro":
        return {
            "name": "metro",
            "bbox": config.METRO_BBOX,
            "road_types": json.dumps({"highway": config.METRO_ROAD_TYPES}),
            "tiles": 4,
            "use_cordon": False,
        }
    if area == "vancouver":
        # Full City of Vancouver: ALL drivable streets (no road-type filter),
        # tiled to clear Overpass limits, largest-component trim, no cordon.
        return {
            "name": "vancouver",
            "bbox": config.VANCOUVER_BBOX,
            "road_types": None,
            "tiles": 4,
            "use_cordon": False,
        }
    if area == "central":
        # Central Vancouver district — all streets, micro, small enough for real
        # gtfs2pt buses + realistic density.
        return {
            "name": "central",
            "bbox": config.CENTRAL_BBOX,
            "road_types": None,
            "tiles": 2,
            "use_cordon": False,
        }
    return {
        "name": "peninsula",
        "bbox": config.PENINSULA_BBOX,
        "road_types": None,
        "tiles": 1,
        "use_cordon": True,
    }


def _osm_files(net_name: str) -> list[Path]:
    """The OSM extract file(s) for an area (one for a plain bbox, N for tiles)."""
    return sorted(config.OSM_DIR.glob(f"{net_name}_*.osm.xml")) or sorted(
        config.OSM_DIR.glob(f"{net_name}[0-9]*.osm.xml")
    )


def download_osm(spec: dict, refresh: bool = False) -> list[Path]:
    """Fetch an area's OSM extract via osmGet.py (cached unless ``refresh``)."""
    name = spec["name"]
    existing = _osm_files(name)
    if existing and not refresh:
        total = sum(f.stat().st_size for f in existing)
        print(f"  OSM extract cached: {len(existing)} file(s), {total:,} bytes")
        return existing

    config.OSM_DIR.mkdir(parents=True, exist_ok=True)
    for stale in _osm_files(name):
        stale.unlink()
    w, s, e, n = spec["bbox"]
    osmget = config.sumo_tool("osmGet.py")
    cmd = [sys.executable, str(osmget), f"--bbox={w},{s},{e},{n}", f"--prefix={name}"]
    if spec["road_types"]:
        cmd.append(f"--road-types={spec['road_types']}")
    if spec["tiles"] > 1:
        cmd.append(f"--tiles={spec['tiles']}")
    print("  $", " ".join(cmd), f"(cwd={config.OSM_DIR})")
    subprocess.run(cmd, check=True, cwd=config.OSM_DIR)
    files = _osm_files(name)
    if not files:
        raise FileNotFoundError(f"osmGet.py produced no OSM extract for '{name}'")
    print(f"  downloaded: {len(files)} file(s), {sum(f.stat().st_size for f in files):,} bytes")
    return files


def _netconvert_args(osm_files: list[Path], net_path: Path, spec: dict) -> list[str]:
    typemap = config.sumo_home() / "data" / "typemap"
    type_files = ",".join(
        str(typemap / t) for t in ("osmNetconvert.typ.xml", "osmNetconvertUrbanDe.typ.xml")
    )
    args = [
        "--osm-files",
        ",".join(str(f) for f in osm_files),
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
        "--plain-output-prefix",
        str(net_path.with_name(f"{spec['name']}.plain")),
    ]
    if spec["use_cordon"] and config.CORDON_POLYGON:
        # Cordon trim: keep only edges inside the peninsula polygon, then the
        # largest connected component.
        args += [
            "--keep-edges.in-geo-boundary",
            config.cordon_geo_boundary(),
            "--keep-edges.components",
            "1",
        ]
    else:
        # Metro: no cordon, but keep the largest connected component so stray
        # disconnected fragments (islands, dead-end ramps) drop out.
        args += ["--keep-edges.components", "1"]
    return args


def build_net(osm_files: list[Path], spec: dict) -> tuple[Path, list[str]]:
    """Run netconvert; return the net path and the exact argument list used."""
    config.SUMO_DIR.mkdir(parents=True, exist_ok=True)
    net_path = config.SUMO_DIR / f"{spec['name']}.net.xml"
    args = _netconvert_args(osm_files, net_path, spec)
    print(f"  $ netconvert (-> {net_path.name}) ...")
    subprocess.run([str(config.sumo_bin("netconvert")), *args], check=True)
    if not net_path.exists():
        raise FileNotFoundError(f"netconvert did not produce {net_path}")
    return net_path, args


def verify_and_record(net_path: Path, osm_files: list[Path], args: list[str], spec: dict) -> dict:
    """Read the net back with sumolib, then persist provenance + metadata."""
    import sumolib

    net = sumolib.net.readNet(str(net_path))
    stats = {
        "n_edges": sum(1 for e in net.getEdges() if not e.getID().startswith(":")),
        "n_junctions": len(net.getNodes()),
        "n_tls": len(net.getTrafficLights()),
    }
    w, s, e, n = spec["bbox"]
    conn = db.connect()
    db.init_db(conn)
    db.record_source(
        conn,
        "osm",
        extract_date=date.today().isoformat(),
        notes=f"{spec['name']} bbox {spec['bbox']}; via SUMO osmGet.py (Overpass).",
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
            spec["name"],
            str(net_path),
            ",".join(str(f) for f in osm_files),
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
    """CLI entry: OSM -> <area>.net.xml, verified and recorded."""
    spec = _area(getattr(args, "area", "peninsula"))
    print(f"=== etl network: OSM -> SUMO {spec['name']} net ===")
    osm_files = download_osm(spec, refresh=getattr(args, "refresh", False))
    net_path, ncv_args = build_net(osm_files, spec)
    stats = verify_and_record(net_path, osm_files, ncv_args, spec)
    print(f"  net: {net_path}")
    print(f"  edges={stats['n_edges']}  junctions={stats['n_junctions']}  tls={stats['n_tls']}")
    return 0
