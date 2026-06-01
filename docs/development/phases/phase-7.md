# Phase 7 — Metro-wide expansion (mesoscopic region)

**Goal:** Grow from the downtown peninsula to **core urbanized Metro Vancouver**, running **mesoscopically** so the regional scale stays within SUMO's single-core budget. Realises the architecture's "region meso + focus micro, LOD switching" intent (CLAUDE.md, decisions.md).

**Status:** In progress — a metro network + census-driven mesoscopic AM-peak run replays in the browser as regional flow ribbons.

## Approach

The peninsula stack stays microscopic and street-detailed; the metro stack is a second, coarser study area selected per run.

1. **Network (`etl network --area metro`).** OSM via `osmGet.py` over the metro bbox (`config.METRO_BBOX`), **major roads only** (`--road-types` motorway…tertiary) and **tiled** (4 tiles) to stay within Overpass limits → `netconvert` → `data/sumo/metro.net.xml`. Minor residential streets are dropped; regional demand loads onto the arterial grid (standard mesoscopic practice).
2. **Demand (`sim/demand_metro.py`).** The StatCan CSD→CSD commuting OD (98-10-0459) becomes municipality-to-municipality trips: each Metro Van CSD has a centroid → a pool of nearby drivable edges; out-of-bbox CSDs snap to the boundary as regional gateways. AM census departure curve + mirrored PM peak; `duarouter` assignment.
3. **Run (`sim run --demand metro`).** Uses `metro.net.xml` with `--mesosim` (queue-based) and coarser FCD sampling (`--device.fcd.period 10`); transit + per-signal capture are skipped (not shown at regional zoom).
4. **Serve + view.** `/api/network?net=metro` serves the metro edges GeoJSON; the viewer is **area-aware** — it loads the run's network/zones per `params.area`, drops to a regional camera, and renders aggregated **flow ribbons** (the existing < `LOD_Z` level-of-detail).

## Deliverables

- A metro network, a mesoscopic census AM-peak run, and a regional flow view in the browser.

## Exit gate

A region-wide mesoscopic run replays in the browser over the metro network with sensible regional flow.

## Deferred (backlog)

- **Metro calibration** against MoTI screenline/bridge counts (the peninsula GEH method generalises to regional screenlines).
- **Regional transit** (GTFS over the metro net), **finer demand** (sub-municipal TAZ, not municipality centroids), and **LOD hand-off** between the meso region and the micro peninsula focus area.
- **Full GVRD extent** (Langley/Maple Ridge/Pitt Meadows east, White Rock/Tsawwassen south) — the current bbox is the urban core.
