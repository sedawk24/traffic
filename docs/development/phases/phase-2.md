# Phase 2 — End-to-end vertical slice (tracer bullet)

**Goal:** Prove every link in the chain — network → demand → SUMO → trace → backend → browser — with a deliberately minimal renderer. Nothing polished; everything connected.

**Status:** Complete — the whole chain runs (sim → trace → FastAPI/Arrow → deck.gl viewer) and the key gate is met: a real SUMO run replays on the peninsula in the browser with moving vehicles, land-use zones, the road network, and a day-scrubber (verified by headless screenshot).

## Why a renderer is in this phase (change from the brief)

The brief put visualization in Phase 3. We pull a **minimal viewer into Phase 2** because the novel, risky seam is the SUMO→trace→browser data path. Seeing vehicles move on a map — from a real SUMO run — is the only honest proof the architecture holds. Polish comes in Phase 3.

## Tasks

1. **Scenario with placeholder demand.** Use `randomTrips.py` / a toy gateway OD on the Phase-1 network. (Realistic demand is Phase 4 — here we only need traffic flowing.)
2. **Run a day.** Execute via `libsumo`; emit sampled geo FCD as Parquet (`--device.fcd.probability`, sensible period). Register the run in SQLite (`runs`).
3. **Post-process.** FCD → per-vehicle trajectory Parquet (id, type, path waypoints, timestamps relative to an epoch baseline).
4. **Backend.** FastAPI: `GET /runs/{id}/trace` streams Arrow (chunked by time window); serve network + zones as GeoJSON.
5. **Minimal viewer.** MapLibre basemap + deck.gl: `PolygonLayer` (zones), `PathLayer` (roads), vehicles (`TripsLayer`/`ScatterplotLayer`), and a working **day-scrubber** (`currentTime`). Ugly is fine.

## Deliverables

- A registered run with a Parquet trajectory trace.
- A FastAPI endpoint streaming Arrow.
- A browser page that replays the day on the peninsula.

## Exit gate (key) — met

Load the URL → see Vancouver zones + roads + vehicles moving on the basemap, driven by a real SUMO run, with a scrubber that moves time. **Met** (headless screenshot: peninsula zones, road network, ~280 moving vehicles at 07:05, live scrubber/clock). The project's first true milestone.

## How to run

```
uv run python -m etl all          # data pipeline (Phase 1) -> data/traffic.db + SUMO inputs
uv run python -m sim run          # baseline SUMO run -> data/runs/baseline/trajectory.parquet
uv run uvicorn api.main:app       # backend + viewer at http://127.0.0.1:8000
```

Notes: the OpenFreeMap basemap renders in a real browser (it did not load under headless capture). The trace is ~32 MB at 1 Hz; `/api/runs/{id}/trace?every=N` strides it for lighter loads.
