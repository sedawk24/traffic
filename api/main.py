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


def _run_row(run_id: int) -> dict:
    conn = db.connect()
    row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(404, f"run {run_id} not found")
    return dict(row)


def _ensure_network_geojson() -> Path:
    """Convert the SUMO net edges to a (cached) GeoJSON of lon/lat LineStrings."""
    net_file = config.SUMO_DIR / "peninsula.net.xml"
    out = config.SUMO_DIR / "peninsula_edges.geojson"
    if not net_file.exists():
        raise HTTPException(404, "peninsula.net.xml missing — run `etl network`")
    if out.exists() and out.stat().st_mtime >= net_file.stat().st_mtime:
        return out

    import sumolib

    net = sumolib.net.readNet(str(net_file))
    features = []
    for e in net.getEdges():
        if e.getID().startswith(":"):
            continue
        coords = [list(net.convertXY2LonLat(x, y)) for x, y in e.getShape()]
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": e.getID(),
                    "lanes": e.getLaneNumber(),
                    "speed": round(e.getSpeed(), 1),
                },
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


@app.get("/api/network")
def network() -> FileResponse:
    return FileResponse(_ensure_network_geojson(), media_type=GEOJSON_MEDIA)


@app.get("/api/zones")
def zones() -> FileResponse:
    z = config.ZONES_DIR / "zones.geojson"
    if not z.exists():
        raise HTTPException(404, "zones.geojson missing — run `etl zoning`")
    return FileResponse(z, media_type=GEOJSON_MEDIA)


# Static viewer at / (mounted last so /api/* takes precedence).
_WEB = config.ROOT / "web"
if _WEB.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(_WEB), html=True), name="web")
