# Current State

**Status: Phase 5 (scenarios) complete — mid-run bridge-closure injection with rerouting + before/after deltas in the UI. Phase 6 (scale & calibrate) is next.**

The system architecture and phased build plan are agreed, Phase 0 research is written up, and the SUMO toolchain is verified on this machine (SUMO 1.27 + libsumo on Apple Silicon; FCD XML/Parquet/geo confirmed; ~225k vehicle-updates/sec, ~34× real-time at 8k active vehicles). Project scaffolding (`pyproject.toml`, uv venv) is in place. Phase 1 is complete: the `etl/` package (SQLite schema + idempotent CLI) ingests OSM, TransLink GTFS, StatCan census, and City/Provincial open data into `data/traffic.db` + SUMO inputs for the cordon-trimmed peninsula — a 7,307-edge net, 366 land-use zones, 456 OD flows, 2,618 departure profiles, 254 signals, 4,062 bus departures, and 11 scenarios, across 8 provenance-tracked sources.

---

## What Is Complete

- **Planning & architecture.** Full plan agreed: SUMO engine (confirmed via research), batch-then-replay, SQLite + Parquet storage, FastAPI backend, deck.gl + MapLibre front end. v1 north star = a polished vertical slice on the **downtown Vancouver peninsula** (cordoned at the bridges); region-wide is a later expansion.
- **Phase 0 research (verified).** Data-source availability/formats/licensing confirmed, with key corrections to the original brief:
  - ❌ TransLink **RTDS** (real-time speeds/travel times) is **retired** — the brief's travel-time calibration source no longer exists.
  - ⚠️ City of Vancouver traffic counts are **locations + links, not a bulk feed**; calibration data is thinner than assumed.
  - ⚠️ TransLink **Trip Diary 2023** is a public dashboard only (no open microdata) — use StatCan "time leaving for work" tables for departure curves.
  - ✅ Solid: OSM→SUMO, TransLink GTFS static, StatCan 2021 commuting OD (98-10-0459 / 98-10-0458), Metro 2050 + Vancouver zoning, CoV signal locations, DriveBC Open511 closures.
- **Toolchain verified (Phase 0 spike).** SUMO 1.27 + `libsumo`/`traci`/`sumolib` installed via `uv` on Apple Silicon (no build issues). SUMO writes FCD as XML **and Parquet** directly, and `--fcd-output.geo` is supported — validating the trace data path. Benchmark on this machine: **~225k vehicle-updates/sec, ~34× real-time at ~8,000 active vehicles** (`scripts/phase0_spike.py`).

## Phase 1 — Data Pipeline (complete)

All loaders are idempotent `etl` steps (`uv run python -m etl <step>`):
- **ETL backbone.** `etl/` package: SQLite schema (`etl/schema.sql`, 12 tables), idempotent CLI (`uv run python -m etl <step>` — `init-db`, `network`, `zoning`, `census`, `transit`, `signals`, `events`, `all`, `status`), open-data source registry for provenance, and per-loader stubs. `ruff` added as the dev linter (checks pass).
- **Network (Task 1, automated).** `etl network`: OSM via SUMO `osmGet.py` (Overpass, raw XML cached) → `netconvert` → `data/sumo/peninsula.net.xml`, with an **automated bridge-cordon trim** (`--keep-edges.in-geo-boundary` over `config.CORDON_POLYGON` + largest-component) cutting the raw net to the peninsula: **7,307 edges / 3,201 junctions / 266 TLS** (down from 15,598 pre-trim); UTM-10 geo-projection stored so `--fcd-output.geo` works. Verified geo extent lon[−123.158, −123.078] lat[49.266, 49.324]; downtown/Gastown/Stanley Park in, Kitsilano/North Van out. Provenance + metadata in `data/traffic.db`.

- **Zoning (Task 5).** `etl zoning`: City of Vancouver zoning + parks (Explore API), clipped to the cordon and reclassified to {residential, commercial, industrial, parkland, downtown-core}, plus 6 virtual bridge-gateway zones → **366 zones** in `data/traffic.db` + `data/zones/zones.geojson` (252 downtown-core, 58 parkland incl. Stanley Park, 22 industrial, 21 residential, 7 commercial). Metro 2050 deferred to the region expansion; population/employment weights to Phase 4 (census).

- **Signals + events (Task 6).** `etl signals`: 254 CoV signal locations in the cordon, 247 matched to a SUMO traffic-light junction (<60 m). `etl events`: 5 canonical bridge-closure scenarios wired to net edges (Lions Gate/Burrard/Granville/Cambie/viaducts) + 6 live DriveBC events near the approaches.

- **Transit (Task 3).** `etl transit`: TransLink GTFS → SUMO pt via `gtfs2pt.py` (bus, cordon bbox) → **254 stops, 140 routes, 4,062 bus departures** (`data/sumo/peninsula_pt_*.xml`). SkyTrain/rail/SeaBus deferred (no rail/water edges in the road net).
- **Census (Task 4).** `etl census`: streamed StatCan 98-10-0459 (OD) + 98-10-0458 (departure) full-Canada tables, filtered to Greater Vancouver → **456 intra-GVRD OD flows** + **2,618 departure-profile rows**. Verified: 222k intra-GVRD into Vancouver (top origins Vancouver/Burnaby/Surrey/Richmond), AM-peak histogram, 57/23/19 car/transit/active.

**Optional, deferred:** a manual `netedit` polish pass (lane counts/turns/gateway tagging). `etl network` already emits a plain-XML baseline and the netdiff workflow is documented (`phase-1.md`), so such edits can survive an OSM re-import.

## Phase 2 — End-to-end vertical slice (complete)

The full chain runs end to end and the **key gate is met** (a real SUMO run replays in the browser):
- **Sim (`sim/`, Tasks 1–3).** `uv run python -m sim run`: randomTrips placeholder demand (fringe-biased to the bridges) → SUMO batch geo FCD Parquet → trajectory Parquet (`t/id/cls/lon/lat/speed/angle`), registered in `runs`. Baseline 07:00–08:00 = 3,877 vehicles, peak 566, 1.57M rows (incl. 212k bus).
- **Backend (`api/`, Task 4).** FastAPI: `/api/network` + `/api/zones` (GeoJSON), `/api/runs/{id}/trace` (Arrow IPC, time-windowed), `/api/runs/{id}/meta`, and the static viewer. `uv run uvicorn api.main:app`.
- **Viewer (`web/index.html`, Task 5).** MapLibre + deck.gl: land-use zones, road network, vehicles colored by speed, with play/pause, a day-scrubber, speed control, and a time-of-day clock. Verified by a headless screenshot (peninsula + ~280 moving vehicles at 07:05).

## Phase 3 — Visualization (complete)

The replay is polished and performant; the exit gate is met. The viewer (`web/index.html`, MapLibre positron + deck.gl):
- **Per-vehicle icons** (car/bus glyphs oriented by heading, interpolated each frame) at street zoom, **coloured by congestion** (red = stopped → green = moving; toggle to colour by type). **Live per-approach traffic-signal states** (red/green/amber, cycling over time — captured from the run via libsumo) appear at street zoom. Bridge gateways are placed from OSM bridge-way centroids (data-grounded).
- **Region→street LOD:** roads as **flow ribbons** coloured by per-edge traffic volume when zoomed out → individual icons at street zoom (transition ~zoom 13.2).
- **Land-use zones** + legend (fills fade as you zoom in), roads styled by class, **labelled bridge gateways**, subtle **bus-route lines**.
- **Controls:** run selector, speed, day-scrubber, time-of-day clock, layer toggles, `?zoom/&lng/&lat` view params.
- **Backend:** `/api/transit`, `/api/runs/{id}/volumes`, `/api/runs/{id}/trips`, plus the Phase-2 network/zones/trace endpoints.

Deferred: self-hosted PMTiles basemap (offline/no-cloud) → backlog (no tooling; not in the exit gate); OpenFreeMap is the dev basemap.

## Phase 4 — Demand modeling (complete)

`sim/demand_census.py` (`sim run --demand census`) turns the SQLite OD + departure profiles + land-use zones into census-driven SUMO routes for a representative weekday:
- **OD disaggregation:** edge↔zone spatial join + land-use employment/population weights; external origins routed to the **directional bridge gateway** (North Shore→Lions Gate, south→False Creek bridges, east→viaducts); peninsula job/pop-share scaling.
- **Timing + mode:** stochastic departures from the census AM "time-leaving" histogram (+ a synthetic PM peak); car-mode-share scaling (transit = the Phase-1 buses).
- **Freight + non-work:** synthesized midday non-work + delivery-van + heavy-truck demand (vTypes car/hov/delivery/truck).
- **Assignment:** `duarouter`. Verified: AM departure shape matches census; the full-day sim is **bimodal** (AM ~801 @ 08:00, PM ~946 @ 17:00 active); gateway volumes east > south > Lions Gate, matching the OD.

## Phase 5 — Scenarios (complete)

`sim/librun.py` unifies the run into one libsumo process (geo FCD + per-approach signals + tripinfo) and can inject a **mid-run closure** — disallow a bridge edge's lanes at the event time, with rerouting devices so traffic redistributes. `sim run --scenario close_<bridge>`. The viewer's run selector picks a run; a **scenario panel** shows Δ avg travel / wait / trips-done vs a matched baseline and **highlights the closed edge** (✕). Demo: closing Granville at 08:00 vacated the bridge (200→2 vehicles) and rerouted traffic (+14 s travel/wait, −96 trips). The closure library (5 bridges) was seeded in Phase 1.

## What Is In Progress

Nothing actively in progress — Phase 5 is complete (exit gate met). Ready to begin **Phase 6 (scale & calibrate)**: best-effort quantitative calibration against obtainable counts, and expanding outward from the peninsula.

## What Is Next

- **Phase 6 — Scale & calibrate (next).** Best-effort quantitative calibration against obtainable counts; expand outward from the peninsula.
- **Phase 4 — Demand modeling.** Real census-driven OD, stochastic departures by mode, commercial/delivery/truck traffic.
- **Phase 5 — Scenarios.** Accident/closure injection via TraCI; before/after impact in the UI.
- **Phase 6 — Scale & calibrate.** Best-effort quantitative calibration against obtainable counts; expand outward from the peninsula.

## Key References

| File | Purpose |
|------|---------|
| `docs/development/development-tracker.md` | Detailed phase tracking and change log |
| `docs/development/phases/` | Phase implementation plans |
| `docs/architecture/decisions.md` | Architectural decision log |
| `docs/research/` | Phase 0 research deliverables |

---

*Last updated: 2026-05-31*
