# Phase 2 — End-to-end vertical slice (tracer bullet)

**Goal:** Prove every link in the chain — network → demand → SUMO → trace → backend → browser — with a deliberately minimal renderer. Nothing polished; everything connected.

**Status:** In Progress — the `sim/` runner (Tasks 1–3) produces a registered trajectory trace (baseline: 3,877 vehicles / peak 566 / 1.57M rows incl. buses). FastAPI backend (Task 4) + minimal viewer (Task 5) next.

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

## Exit gate (key)

Load the URL → see Vancouver zones + roads + vehicles moving on the basemap, driven by a real SUMO run, with a scrubber that moves time. This is the project's first true milestone.
