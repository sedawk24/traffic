"""FastAPI app: network/zones GeoJSON, run traces as Arrow, and the static viewer."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response

from etl import config, db

app = FastAPI(title="Greater Vancouver Traffic Simulator")

ARROW_MEDIA = "application/vnd.apache.arrow.stream"
GEOJSON_MEDIA = "application/geo+json"
_VOL_CACHE: dict[int, dict] = {}


def _run_row(run_id: int) -> dict:
    conn = db.connect()
    row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(404, f"run {run_id} not found")
    return dict(row)


def _ensure_network_geojson(net_name: str = "peninsula") -> Path:
    """Convert the SUMO net edges to a (cached) GeoJSON of lon/lat LineStrings."""
    net_file = config.SUMO_DIR / f"{net_name}.net.xml"
    out = config.SUMO_DIR / f"{net_name}_edges.geojson"
    if not net_file.exists():
        raise HTTPException(404, f"{net_name}.net.xml missing — run `etl network --area {net_name}`")
    if out.exists() and out.stat().st_mtime >= net_file.stat().st_mtime:
        return out

    import sumolib

    net = sumolib.net.readNet(str(net_file))
    features = []
    for e in net.getEdges():
        if e.getID().startswith(":"):
            continue
        coords = [list(net.convertXY2LonLat(x, y)) for x, y in e.getShape()]
        spd = e.getSpeed()
        klass = "arterial" if spd >= 16 else "collector" if spd >= 11 else "local"
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": e.getID(),
                    "lanes": e.getLaneNumber(),
                    "speed": round(spd, 1),
                    "class": klass,
                },
                "geometry": {"type": "LineString", "coordinates": coords},
            }
        )
    out.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    return out


def _ensure_transit_geojson(net_name: str = "peninsula") -> Path:
    """Unique transit (bus) route polylines from the SUMO pt routes, as GeoJSON."""
    import xml.etree.ElementTree as ET

    import sumolib

    net_file = config.SUMO_DIR / f"{net_name}.net.xml"
    rou = config.SUMO_DIR / f"{net_name}_pt_vehicles.rou.xml"
    out = config.SUMO_DIR / f"{net_name}_transit.geojson"
    if not rou.exists():
        raise HTTPException(404, f"transit routes missing — run `etl transit --area {net_name}`")
    if out.exists() and out.stat().st_mtime >= rou.stat().st_mtime:
        return out

    net = sumolib.net.readNet(str(net_file))
    features = []
    for route in ET.parse(rou).getroot().iter("route"):
        coords = []
        for eid in (route.get("edges") or "").split():
            if eid.startswith(":"):
                continue
            try:
                edge = net.getEdge(eid)
            except KeyError:
                continue
            coords += [list(net.convertXY2LonLat(x, y)) for x, y in edge.getShape()]
        if len(coords) >= 2:
            features.append(
                {
                    "type": "Feature",
                    "properties": {"route": route.get("id")},
                    "geometry": {"type": "LineString", "coordinates": coords},
                }
            )
    out.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    return out


@app.get("/api/runs")
def list_runs() -> list[dict]:
    conn = db.connect()
    rows = [
        dict(r)
        for r in conn.execute(
            "SELECT run_id, scenario_id, status, trace_path, params FROM runs ORDER BY run_id DESC"
        )
    ]
    conn.close()
    for r in rows:
        r["params"] = json.loads(r["params"] or "{}")
    return rows


@app.get("/api/runs/{run_id}/meta")
def run_meta(run_id: int) -> dict:
    r = _run_row(run_id)
    return {
        "run_id": run_id,
        "status": r["status"],
        "params": json.loads(r["params"] or "{}"),
        "stats": json.loads(r["notes"] or "{}"),
    }


@app.get("/api/runs/{run_id}/trace")
def run_trace(
    run_id: int,
    start: int = 0,
    end: int | None = None,
    every: int = Query(1, ge=1, description="keep every Nth second"),
) -> Response:
    """Stream the trajectory for a time window as an Arrow IPC stream."""
    r = _run_row(run_id)
    path = r["trace_path"]
    if not path or not Path(path).exists():
        raise HTTPException(404, "trace file missing")

    filters = [("t", ">=", start)]
    if end is not None:
        filters.append(("t", "<", end))
    table = pq.read_table(path, filters=filters)

    if every > 1 and table.num_rows:
        lo = pc.min(table["t"]).as_py()
        hi = pc.max(table["t"]).as_py()
        keep = pa.array(range(lo, hi + 1, every), type=table.schema.field("t").type)
        table = table.filter(pc.is_in(table["t"], value_set=keep))

    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return Response(content=sink.getvalue().to_pybytes(), media_type=ARROW_MEDIA)


@app.get("/api/runs/{run_id}/trips")
def run_trips(
    run_id: int,
    every: int = Query(2, ge=1, description="sample every Nth second"),
    start: int | None = Query(None, description="window start (relative s); omit for whole run"),
    end: int | None = Query(None, description="window end (relative s)"),
) -> Response:
    """Per-vehicle paths + timestamps. With start/end, only the time window is
    returned (predicate-pushed at the parquet level) — the viewer streams windows
    so dense runs (whose full trace is too big to load at once) stay viewable."""
    import pandas as pd

    r = _run_row(run_id)
    path = r["trace_path"]
    if not path or not Path(path).exists():
        raise HTTPException(404, "trace file missing")
    filters = []
    if start is not None:
        filters.append(("t", ">=", start))
    if end is not None:
        filters.append(("t", "<=", end))
    df = pd.read_parquet(path, columns=["t", "id", "cls", "lon", "lat"], filters=filters or None)
    if every > 1:
        df = df[df["t"] % every == 0]
    df = df.sort_values(["id", "t"])
    trips = [
        {
            "cls": str(g["cls"].iloc[0]),
            "path": g[["lon", "lat"]].round(6).values.tolist(),
            "timestamps": g["t"].astype(int).tolist(),
        }
        for _, g in df.groupby("id", sort=False)
        if len(g) > 1
    ]
    return Response(json.dumps(trips), media_type="application/json")


def _volumes_from_routes(rou: Path) -> dict:
    """Per-edge vehicle count from a duarouter route file (the meso path, where the
    FCD carries no lane). Counts each vehicle once per edge it traverses."""
    if not rou.exists():
        return {}
    import xml.etree.ElementTree as ET
    from collections import Counter

    c: Counter = Counter()
    for _ev, el in ET.iterparse(str(rou), events=("end",)):
        if el.tag == "route":
            for e in {x for x in (el.get("edges") or "").split() if not x.startswith(":")}:
                c[e] += 1
            el.clear()
    return dict(c)


@app.get("/api/runs/{run_id}/volumes")
def run_volumes(run_id: int) -> dict:
    """Per-edge traffic volume (distinct vehicles) over the run, for flow ribbons."""
    if run_id in _VOL_CACHE:
        return _VOL_CACHE[run_id]
    import pandas as pd

    r = _run_row(run_id)
    fcd = Path(r["trace_path"]).with_name("fcd.parquet")
    vol: dict = {}
    if fcd.exists():
        df = pd.read_parquet(fcd, columns=["vehicle_id", "vehicle_lane"])
        lane = df["vehicle_lane"]
        df = df[lane.notna() & ~lane.str.startswith(":")]
        if len(df):
            df["edge"] = df["vehicle_lane"].str.rsplit("_", n=1).str[0]
            vol = df.groupby("edge")["vehicle_id"].nunique().astype(int).to_dict()
    if not vol:  # mesoscopic FCD has no lane attribute — count from the route file
        vol = _volumes_from_routes(Path(r["trace_path"]).with_name("routes.rou.xml"))
    if not vol:
        raise HTTPException(404, "no volume data for this run")
    _VOL_CACHE[run_id] = vol
    return vol


@app.get("/api/runs/{run_id}/signals-live")
def signals_live(run_id: int) -> FileResponse:
    """Per-signal stop-line positions + state-change timeline (live red/green view)."""
    r = _run_row(run_id)
    f = Path(r["trace_path"]).with_name("tls_states.json")
    if not f.exists():
        raise HTTPException(404, "no captured signal states for this run — re-run `sim run`")
    return FileResponse(f, media_type="application/json")


_AREAS = ("peninsula", "metro", "vancouver", "central")


@app.get("/api/network")
def network(net: str = "peninsula") -> FileResponse:
    name = net if net in _AREAS else "peninsula"
    return FileResponse(_ensure_network_geojson(name), media_type=GEOJSON_MEDIA)


@app.get("/api/transit")
def transit(net: str = "peninsula") -> FileResponse:
    name = net if net in _AREAS else "peninsula"
    return FileResponse(_ensure_transit_geojson(name), media_type=GEOJSON_MEDIA)


@app.get("/api/transit-vehicles")
def transit_vehicles(net: str = "peninsula") -> FileResponse:
    """Schedule-based bus polylines (large nets) — animated as buses in the viewer."""
    name = net if net in _AREAS else "peninsula"
    f = config.SUMO_DIR / f"{name}_bus_schedule.json"
    if not f.exists():
        raise HTTPException(404, "no schedule-based buses for this net")
    return FileResponse(f, media_type="application/json")


@app.get("/api/signals")
def signals() -> Response:
    """City of Vancouver traffic-signal locations (shown at street zoom)."""
    conn = db.connect()
    rows = conn.execute(
        "SELECT signal_id, lon, lat, sumo_tls_id FROM signals WHERE source = 'cov_signals'"
    ).fetchall()
    conn.close()
    features = [
        {
            "type": "Feature",
            "properties": {"id": r["signal_id"], "tls": r["sumo_tls_id"]},
            "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
        }
        for r in rows
        if r["lon"] is not None
    ]
    return Response(
        json.dumps({"type": "FeatureCollection", "features": features}), media_type=GEOJSON_MEDIA
    )


@app.get("/api/zones")
def zones(net: str = "peninsula") -> FileResponse:
    name = net if net in _AREAS else "peninsula"
    # the peninsula has its own cordon-clipped zones (with gateways); every other
    # area shares the whole-City-of-Vancouver land use so it covers the full city.
    z = config.ZONES_DIR / ("zones.geojson" if name == "peninsula" else "vancouver_zones.geojson")
    if not z.exists():
        raise HTTPException(404, f"zones for {name} missing — run `etl zoning --area {name}`")
    return FileResponse(z, media_type=GEOJSON_MEDIA)


# Static viewer at / (mounted last so /api/* takes precedence).
_WEB = config.ROOT / "web"
if _WEB.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(_WEB), html=True), name="web")
