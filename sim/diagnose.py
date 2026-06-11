"""Congestion diagnostics: rank the junctions where vehicles lose the most time.

Reads an existing run's raw geo FCD (``fcd.parquet``) plus the run's SUMO net,
sums stopped vehicle-time per edge (speed < STOP_SPEED), and attributes each
edge to its **downstream junction** — vehicles queue toward the junction they
are waiting on, and time stopped *inside* a junction's internal lanes is
attributed to that junction directly. Each ranked junction is cross-referenced
against the City of Vancouver's real signal inventory, so "the terrible jam at
X" becomes a named, ground-truthed list:

    uv run python -m sim diagnose --run central_final [--top 10] [--write-geojson]

Outputs a console table plus ``<run_dir>/hotspots.json`` (and optionally
``hotspots.geojson``), which the viewer's hotspot panel reads via
``/api/runs/{id}/hotspots``.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from etl import config, db

STOP_SPEED = 0.5  # m/s — below this a vehicle counts as stopped
COV_MATCH_M = 50.0  # junction <-> CoV signal match radius
END_SEGMENT_M = 60.0  # "queued at the stop line" window at the edge end

# CoV `type` classification: signals that control vehicles vs pedestrian-only
# devices (with no pedestrians simulated, a ped-actuated signal rests green for
# cars). Ambiguous/rare kinds (FH, CS, blank) are treated as vehicle signals.
VEHICLE_KINDS = {"Fixed Time", "Semi Actuated", "Fully Actuated", "Bus Actuated Signal"}
PED_KINDS = {"Pedestrian Actuated Signal", "RRFB", "Special Crosswalk"}

_WAY_RE = re.compile(r"^-?(\d+)")


def _run_info(run_name: str) -> tuple[Path, str]:
    """Run directory + area for a registered run name (newest match wins)."""
    run_dir = config.DATA_DIR / "runs" / run_name
    if not (run_dir / "fcd.parquet").exists():
        raise SystemExit(f"no fcd.parquet under {run_dir} — is '{run_name}' a run name?")
    conn = db.connect()
    row = conn.execute(
        "SELECT params FROM runs WHERE json_extract(params, '$.name') = ? "
        "ORDER BY run_id DESC LIMIT 1",
        (run_name,),
    ).fetchone()
    conn.close()
    area = "peninsula"
    if row:
        area = (json.loads(row["params"] or "{}")).get("area") or "peninsula"
    return run_dir, area


def _osm_way_names(area: str) -> dict[int, str]:
    """OSM way id -> street name, from the cached extract (name-less nets)."""
    import xml.etree.ElementTree as ET

    files = sorted(config.OSM_DIR.glob(f"{area}*_*.osm.xml")) or sorted(
        config.OSM_DIR.glob(f"{area}_*.osm.xml")
    )
    names: dict[int, str] = {}
    for f in files:
        for _ev, el in ET.iterparse(str(f), events=("end",)):
            if el.tag == "way":
                for tag in el.findall("tag"):
                    if tag.get("k") == "name":
                        names[int(el.get("id"))] = tag.get("v")
                        break
                el.clear()
            elif el.tag == "node":
                el.clear()
    return names


def _edge_name(edge, way_names: dict[int, str]) -> str | None:
    """Street name of an edge: the net's name attr, else the OSM way name."""
    n = edge.getName()
    if n:
        return n
    m = _WAY_RE.match(edge.getID())
    return way_names.get(int(m.group(1))) if m else None


def _junction_name(node, way_names: dict[int, str]) -> str:
    """'Street A & Street B' from the two most common incoming street names."""
    names = [_edge_name(e, way_names) for e in node.getIncoming() if not e.getID().startswith(":")]
    ranked = [n for n, _ in Counter(n for n in names if n).most_common()]
    distinct: list[str] = []
    for n in ranked:
        if n not in distinct:
            distinct.append(n)
        if len(distinct) == 2:
            break
    return " & ".join(distinct) if distinct else node.getID()


def _tls_by_node(net) -> dict[str, tuple[str, int]]:
    """node id -> (tls id, #controlled links) — handles joined TLS clusters."""
    out: dict[str, tuple[str, int]] = {}
    for tls in net.getTrafficLights():
        conns = tls.getConnections()
        for c in conns:
            in_lane = c[0]
            try:
                nid = in_lane.getEdge().getToNode().getID()
            except Exception:  # noqa: BLE001 — defensive: malformed connection
                continue
            out[nid] = (tls.getID(), len(conns))
    return out


def _cov_signals(area: str) -> list[dict]:
    """CoV signal points {lon, lat, kind} for the area — DB rows if `etl signals
    --area` has run, else straight from the cached city-wide GeoJSON."""
    conn = db.connect()
    rows = conn.execute(
        "SELECT lon, lat, kind FROM signals WHERE source = ?", (f"cov_signals_{area}",)
    ).fetchall()
    conn.close()
    if rows:
        return [{"lon": r["lon"], "lat": r["lat"], "kind": r["kind"]} for r in rows]
    path = config.DATA_DIR / "signals" / "cov_signals.geojson"
    if not path.exists():
        return []
    feats = json.loads(path.read_text())["features"]
    return [
        {
            "lon": f["geometry"]["coordinates"][0],
            "lat": f["geometry"]["coordinates"][1],
            "kind": f["properties"].get("type"),
        }
        for f in feats
        if f.get("geometry") and f["geometry"]["type"] == "Point"
    ]


def _nearest_cov(cov: list[dict], lon: float, lat: float) -> tuple[str | None, float | None]:
    """Nearest CoV signal kind within COV_MATCH_M of a junction (and distance)."""
    from math import cos, radians

    best_kind, best_d2 = None, None
    klon = cos(radians(lat)) * 111_320.0
    klat = 110_540.0
    for s in cov:
        dx, dy = (s["lon"] - lon) * klon, (s["lat"] - lat) * klat
        d2 = dx * dx + dy * dy
        if d2 <= COV_MATCH_M**2 and (best_d2 is None or d2 < best_d2):
            best_kind, best_d2 = s["kind"] or "unknown", d2
    return best_kind, (best_d2**0.5 if best_d2 is not None else None)


def diagnose(run_name: str, top: int = 10, write_geojson: bool = False) -> dict:
    import pandas as pd
    import sumolib

    run_dir, area = _run_info(run_name)
    net_path = config.SUMO_DIR / f"{area}.net.xml"
    print(f"=== sim diagnose '{run_name}' (net: {area}) ===")
    net = sumolib.net.readNet(str(net_path))

    df = pd.read_parquet(
        run_dir / "fcd.parquet",
        columns=["timestep_time", "vehicle_id", "vehicle_lane", "vehicle_speed", "vehicle_pos"],
    )
    df = df[df["vehicle_lane"].notna()]
    times = df["timestep_time"].drop_duplicates().sort_values().diff().dropna()
    period = float(times.mode().iloc[0]) if len(times) else 1.0
    print(f"  fcd rows: {len(df):,}  (sample period {period:g}s)")

    internal = df["vehicle_lane"].str.startswith(":")
    df["edge"] = df["vehicle_lane"].str.rsplit("_", n=1).str[0]
    df.loc[internal, "edge"] = None
    df["junction"] = None
    df.loc[internal, "junction"] = (
        df.loc[internal, "vehicle_lane"].str[1:].str.rsplit("_", n=2).str[0]
    )
    stopped = df["vehicle_speed"] < STOP_SPEED

    # --- per-edge aggregation (regular lanes), attributed to the downstream node
    reg = df[~internal]
    reg_stopped = reg["vehicle_speed"] < STOP_SPEED
    edge_stats = reg.groupby("edge").agg(
        rows=("vehicle_id", "size"),
        vehicles=("vehicle_id", "nunique"),
        mean_ms=("vehicle_speed", "mean"),
    )
    edge_stats["stop_s"] = (
        reg[reg_stopped].groupby("edge").size().reindex(edge_stats.index, fill_value=0) * period
    )

    lengths, to_node = {}, {}
    for eid in edge_stats.index:
        try:
            e = net.getEdge(eid)
        except KeyError:
            continue
        lengths[eid] = e.getLength()
        to_node[eid] = e.getToNode().getID()
    edge_stats = edge_stats[edge_stats.index.isin(to_node)]
    edge_stats["junction"] = edge_stats.index.map(to_node)

    # stopped within the last END_SEGMENT_M of the edge = queued at the stop line
    reg_stop = reg[reg_stopped].copy()
    reg_stop["len"] = reg_stop["edge"].map(lengths)
    at_end = reg_stop[reg_stop["vehicle_pos"] >= reg_stop["len"] - END_SEGMENT_M]
    edge_stats["stop_end_s"] = (
        at_end.groupby("edge").size().reindex(edge_stats.index, fill_value=0) * period
    )

    # --- junction totals: incoming-edge stop time + time stopped inside it
    jcol = df.loc[internal & stopped, "junction"]
    internal_stop = (jcol.value_counts() * period).rename("internal_stop_s")
    jn = edge_stats.groupby("junction").agg(
        stop_s=("stop_s", "sum"),
        stop_end_s=("stop_end_s", "sum"),
        vehicles=("vehicles", "sum"),
    )
    jn = jn.join(internal_stop, how="outer").fillna(0)
    jn["total_stop_s"] = jn["stop_s"] + jn["internal_stop_s"]
    jn = jn.sort_values("total_stop_s", ascending=False)

    way_names = _osm_way_names(area)
    cov = _cov_signals(area)
    tls_map = _tls_by_node(net)
    print(
        f"  junctions with stopped traffic: {(jn['total_stop_s'] > 0).sum():,}  "
        f"|  CoV signals loaded: {len(cov)}  |  street names: {len(way_names):,}"
    )

    keep = min(max(top * 3, 30), len(jn))
    hotspots = []
    for rank, (jid, row) in enumerate(jn.head(keep).iterrows(), start=1):
        try:
            node = net.getNode(jid)
        except Exception:  # noqa: BLE001 — junction id not in net (stale fcd)
            continue
        lon, lat = net.convertXY2LonLat(*node.getCoord())
        kind, dist = _nearest_cov(cov, lon, lat)
        tls_id, n_links = tls_map.get(jid, (None, 0))
        approaches = []
        for eid, er in (
            edge_stats[edge_stats["junction"] == jid]
            .sort_values("stop_s", ascending=False)
            .iterrows()
        ):
            if er["stop_s"] <= 0 or len(approaches) >= 4:
                continue
            approaches.append(
                {
                    "edge": eid,
                    "name": _edge_name(net.getEdge(eid), way_names),
                    "stop_veh_h": round(er["stop_s"] / 3600, 2),
                    "vehicles": int(er["vehicles"]),
                    "mean_kmh": round(er["mean_ms"] * 3.6, 1),
                }
            )
        veh = int(row["vehicles"]) or 1
        hotspots.append(
            {
                "rank": rank,
                "junction": jid,
                "name": _junction_name(node, way_names),
                "lon": round(lon, 6),
                "lat": round(lat, 6),
                "jtype": node.getType(),
                "tls_id": tls_id,
                "tls_links": n_links,
                "cov_kind": kind,
                "cov_dist_m": round(dist, 1) if dist is not None else None,
                "stop_veh_h": round(row["total_stop_s"] / 3600, 2),
                "stop_end_veh_h": round((row["stop_end_s"] + row["internal_stop_s"]) / 3600, 2),
                "vehicles": int(row["vehicles"]),
                "stop_s_per_veh": round(row["total_stop_s"] / veh, 1),
                "approaches": approaches,
            }
        )

    out = {
        "run": run_name,
        "area": area,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "fcd_period": period,
        "stop_speed_ms": STOP_SPEED,
        "total_stop_veh_h": round((jn["total_stop_s"].sum()) / 3600, 1),
        "top_share": round(
            jn["total_stop_s"].head(top).sum() / max(jn["total_stop_s"].sum(), 1), 3
        ),
        "hotspots": hotspots,
    }
    (run_dir / "hotspots.json").write_text(json.dumps(out, indent=1))
    if write_geojson:
        feats = [
            {
                "type": "Feature",
                "properties": {k: v for k, v in h.items() if k != "approaches"},
                "geometry": {"type": "Point", "coordinates": [h["lon"], h["lat"]]},
            }
            for h in hotspots
        ]
        (run_dir / "hotspots.geojson").write_text(
            json.dumps({"type": "FeatureCollection", "features": feats})
        )

    # --- console report ------------------------------------------------------
    sig = "TLS" if any(h["tls_id"] for h in hotspots) else ""
    print(
        f"\n  network stopped time: {out['total_stop_veh_h']:,} veh·h  "
        f"(top {top} junctions hold {out['top_share']:.0%})\n"
    )
    hdr = f"  {'#':>2} {'junction (streets)':<38} {'ctrl':<14} {'CoV ground truth':<22} {'stop':>7} {'s/veh':>6}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for h in hotspots[:top]:
        ctrl = f"{sig} {h['tls_links']}lk" if h["tls_id"] else h["jtype"]
        cov_lbl = h["cov_kind"] or "— no CoV signal"
        print(
            f"  {h['rank']:>2} {h['name'][:38]:<38} {ctrl:<14} {cov_lbl[:22]:<22} "
            f"{h['stop_veh_h']:>6.1f}h {h['stop_s_per_veh']:>6.0f}"
        )
    n_tls_top = sum(1 for h in hotspots[:top] if h["tls_id"])
    n_bogus = sum(
        1
        for h in hotspots[:top]
        if h["tls_id"] and (h["cov_kind"] is None or h["cov_kind"] in PED_KINDS)
    )
    print(
        f"\n  of the top {top}: {n_tls_top} are signalized in the net; "
        f"{n_bogus} of those have NO real vehicle signal (ped-only or unmatched in CoV data)"
    )
    print(f"  wrote {run_dir / 'hotspots.json'}")
    return out


def cmd_diagnose(args) -> int:
    diagnose(args.run, top=args.top, write_geojson=args.write_geojson)
    return 0
