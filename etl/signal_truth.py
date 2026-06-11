"""ETL step: ground-truth a net's traffic lights against the CoV signal inventory.

netconvert (OSM tags + ``--tls.guess-signals`` + ``--tls.join``) signalizes far
more junctions than the City of Vancouver actually operates — the central net
has ~700 signalized junction nodes vs ~298 real CoV *vehicle* signals; the rest
are pedestrian-actuated crossings (which rest green for cars when no pedestrians
are simulated) or outright guesses. Every bogus signal stops cross traffic for
nobody, and their sum sets the grid's capacity ceiling (Phase 8c finding).

This step **post-processes the built net in place** (a netconvert net-to-net
pass), so edge IDs stay stable and existing demand/transit/zone artifacts
survive:

* **unset** — net TLS junctions whose nearest CoV device within MATCH_M is
  pedestrian-only, or that have no CoV device within UNMATCHED_M at all
  → become priority junctions.
* **set** — CoV vehicle signals with no net TLS within MATCH_M whose nearest
  plain junction is within SET_M → become (actuated) signals.

Decision lists are written to ``data/sumo/{area}_tls_unset.txt`` / ``_set.txt``
for inspection; stale ``*_tls_coord/cycle.add.xml`` files are renamed ``.stale``
(they reference removed TLS — regenerate with ``sim retime`` after equilibrium).

    uv run python -m etl signal-truth --area central [--dry-run]
"""

from __future__ import annotations

import subprocess
from math import atan2, cos, radians, sin, sqrt

from etl import config, db
from etl.signals import PED_KINDS, VEHICLE_KINDS

MATCH_M = 60.0  # TLS <-> CoV device match radius
SET_M = 40.0  # CoV vehicle signal -> plain junction promotion radius


def _haversine_m(lon1, lat1, lon2, lat2) -> float:
    r = 6_371_000.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * atan2(sqrt(a), sqrt(1 - a))


def _cov_signals(area: str) -> list[dict]:
    conn = db.connect()
    rows = conn.execute(
        "SELECT lon, lat, kind FROM signals WHERE source = ?",
        (f"cov_signals_{area}" if area != "peninsula" else "cov_signals",),
    ).fetchall()
    conn.close()
    if not rows:
        raise SystemExit(f"no CoV signals for '{area}' — run `etl signals --area {area}` first")
    return [dict(r) for r in rows]


def _classify(net, cov: list[dict]) -> tuple[list[str], list[str], dict]:
    """(unset junction ids, set junction ids, stats)."""
    tls_nodes, plain_nodes = [], []
    for n in net.getNodes():
        lon, lat = net.convertXY2LonLat(*n.getCoord())
        if n.getType() in ("traffic_light", "traffic_light_right_on_red"):
            tls_nodes.append((n.getID(), lon, lat))
        elif n.getType() not in ("dead_end",):
            plain_nodes.append((n.getID(), lon, lat))

    def nearest(cands, lon, lat, limit):
        best, best_d = None, limit
        for c in cands:
            d = _haversine_m(lon, lat, c["lon"], c["lat"])
            if d < best_d:
                best, best_d = c, d
        return best

    unset, kept_veh, kept_other = [], 0, 0
    matched_cov_pos = []
    for nid, lon, lat in tls_nodes:
        m = nearest(cov, lon, lat, MATCH_M)
        if m is None:
            unset.append(nid)  # no real device anywhere near: a netconvert guess
        elif m["kind"] in PED_KINDS:
            unset.append(nid)  # ped-only crossing: rests green for cars -> priority
            matched_cov_pos.append((m["lon"], m["lat"]))
        else:
            kept_veh += 1 if m["kind"] in VEHICLE_KINDS else 0
            kept_other += 0 if m["kind"] in VEHICLE_KINDS else 1
            matched_cov_pos.append((m["lon"], m["lat"]))

    # CoV vehicle signals nowhere near a net TLS -> promote the nearest junction
    tset = []
    for s in cov:
        if s["kind"] not in VEHICLE_KINDS:
            continue
        if any(_haversine_m(s["lon"], s["lat"], lon, lat) < MATCH_M for _n, lon, lat in tls_nodes):
            continue
        pj = nearest(
            [{"lon": lon, "lat": lat, "id": nid} for nid, lon, lat in plain_nodes],
            s["lon"],
            s["lat"],
            SET_M,
        )
        if pj:
            tset.append(pj["id"])
    tset = sorted(set(tset))
    stats = {
        "tls_nodes": len(tls_nodes),
        "unset": len(unset),
        "kept_vehicle": kept_veh,
        "kept_other": kept_other,
        "set": len(tset),
    }
    return unset, tset, stats


def run(args) -> int:
    import sumolib

    area = getattr(args, "area", None)
    if not area:  # `etl all` reaches here without --area: an explicit-only step
        raise NotImplementedError("run explicitly: `etl signal-truth --area <area>`")
    dry = getattr(args, "dry_run", False)
    net_path = config.SUMO_DIR / f"{area}.net.xml"
    if not net_path.exists():
        raise SystemExit(f"{net_path.name} missing — run `etl network --area {area}` first")
    print(f"=== etl signal-truth: CoV ground truth -> {area}.net.xml TLS set ===")
    net = sumolib.net.readNet(str(net_path))
    cov = _cov_signals(area)
    unset, tset, st = _classify(net, cov)
    print(
        f"  net TLS nodes: {st['tls_nodes']}  ->  keep {st['kept_vehicle']} vehicle-signal "
        f"+ {st['kept_other']} ambiguous;  UNSET {st['unset']} (ped-only or no CoV device);  "
        f"SET {st['set']} missing vehicle signals"
    )
    unset_f = config.SUMO_DIR / f"{area}_tls_unset.txt"
    set_f = config.SUMO_DIR / f"{area}_tls_set.txt"
    unset_f.write_text("\n".join(unset) + "\n")
    set_f.write_text("\n".join(tset) + "\n")
    print(f"  wrote {unset_f.name} / {set_f.name}")
    if dry:
        print("  dry run: net unchanged")
        return 0

    # Plain-XML round-trip: --tls.unset can't strip TLS already baked into a
    # built net, so export plain, rewrite the junction `type` attributes from
    # the ground-truth lists, and rebuild (dropping the old tll programs — the
    # rebuild regenerates actuated programs for exactly the kept set). Edge ids
    # survive a plain round-trip, so demand/transit/zone artifacts stay valid.
    import tempfile
    import xml.etree.ElementTree as ET

    bak = net_path.with_suffix(".xml.pretruth")
    net_path.replace(bak)
    unset_s, set_s = set(unset), set(tset)
    with tempfile.TemporaryDirectory() as td:
        prefix = f"{td}/p"
        print("  $ netconvert -> plain ...")
        subprocess.run(
            [
                str(config.sumo_bin("netconvert")),
                "-s",
                str(bak),
                "--plain-output-prefix",
                prefix,
                "--no-warnings",
                "true",
            ],
            check=True,
        )
        nod = ET.parse(f"{prefix}.nod.xml")
        n_unset = n_set = 0
        for node in nod.getroot().iter("node"):
            nid = node.get("id")
            if nid in unset_s:
                node.set("type", "priority")
                node.attrib.pop("tl", None)
                node.attrib.pop("tlType", None)
                n_unset += 1
            elif nid in set_s:
                node.set("type", "traffic_light")
                node.attrib.pop("tl", None)
                n_set += 1
        nod.write(f"{prefix}.nod.xml")
        print(f"  rebuilt junction types: {n_unset} -> priority, {n_set} -> traffic_light")
        print("  $ netconvert plain -> net (regenerating actuated TLS programs) ...")
        subprocess.run(
            [
                str(config.sumo_bin("netconvert")),
                "-n",
                f"{prefix}.nod.xml",
                "-e",
                f"{prefix}.edg.xml",
                "-x",
                f"{prefix}.con.xml",
                "-t",
                f"{prefix}.typ.xml",
                "-o",
                str(net_path),
                # the project's standard signal defaults (etl/network.py)
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
                "--tls.join",
                "true",
                "--no-turnarounds",
                "true",
                "--no-warnings",
                "true",
            ],
            check=True,
        )

    # stale signal-timing add-files reference removed TLS — quarantine them
    for suffix in ("tls_coord", "tls_cycle"):
        f = config.SUMO_DIR / f"{area}_{suffix}.add.xml"
        if f.exists():
            f.replace(f.with_suffix(".xml.stale"))
            print(f"  quarantined stale {f.name} -> .stale (regenerate via `sim retime`)")

    n2 = sumolib.net.readNet(str(net_path))
    n_tls = sum(
        1 for n in n2.getNodes() if n.getType() in ("traffic_light", "traffic_light_right_on_red")
    )
    print(f"  done: signalized junction nodes {st['tls_nodes']} -> {n_tls}  (backup: {bak.name})")
    return 0
