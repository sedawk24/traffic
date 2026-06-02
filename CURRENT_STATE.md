# Current State

**Status: Phase 8c — the `central` Vancouver district runs a realistic congested AM rush hour at the network's *measured capacity ceiling*. Run #40 (scale 0.05): 2,370 on-road at the peak, 16.6 km/h, arterials busy-but-moving and residential genuinely quiet. Getting there fixed real bugs and pinned the honest limit: residential streets had been modeled at 50 km/h (= arterial speed) so through-traffic rat-ran the grid — now ~30 km/h, so it stays on arterials; a `duaIterate` user-equilibrium spreads traffic; signals are green-wave-coordinated + de-cluttered. The hard finding (measured): above ~0.05 the dense signalized grid oversaturates into gridlock (0.10 = 6 km/h, 84% stopped — earlier "0-teleported busy" runs were *crawling*, not flowing), and that ceiling is intersection-throughput-bound — NOT lanes (arterials at ~11% volume) and NOT green-split timing (`tlsCycleAdaptation`/junction-nudging both tested, no gain; only coordination helped, ~15%). "Packed AND flowing" is past this auto-net's limit — a bigger network/demand project. The district also runs REAL SUMO buses (stop + obey signals), live signals, and demand fixed for routability + in-window efficiency; calibrated against real bridge volumes (Granville/Cambie GEH<5). All six original build phases (0–6) complete; Phases 7 (metro meso) + 8 (full city) added.**

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

`sim/librun.py` unifies the run into one libsumo process (geo FCD + per-approach signals + tripinfo) and can inject a **mid-run closure** — disallow the **whole bridge's** lanes at the event time, with rerouting devices so traffic redistributes. `sim run --scenario close_<bridge>`. The viewer's run selector (`?run=` param) picks a run; a **scenario panel** shows Δ avg travel / wait / trips-done vs a matched baseline and **highlights the closed edges** (✕). The closure library (5 bridges) was seeded in Phase 1.

A closure targets the **full structure, not one edge.** `etl events` now derives each bridge's complete drivable edge set (both directions + ramps) by buffering the named OSM bridge ways and intersecting the SUMO net — e.g. Granville = **43 edges** (was 1), Cambie 48, Georgia/Dunsmuir 54, Burrard 8, Lions Gate 2. `librun` closes every lane of every edge; the viewer reds them all **only within the closure window** — before the event the bridge renders normally and the scenario panel reads "closes 08:00" (amber), flipping to "✕ closed" (red) at the event time — so it's never shown closed before it actually is. Verified on Granville closing at 08:00 (07:00–09:00 AM run, scale 0.18): the bridge carried 22,895 vehicle-frames while open, **0 new entries after the closure** (both directions), the 3 vehicles mid-span cleared by 08:04, then the deck stayed empty; network impact −174 trips / +8 s travel / +6 s wait vs the matched baseline (modest — Burrard & Cambie absorb the rerouted demand). This fixed a bug where closing a bridge barred only one edge/direction, leaving the opposite direction and other segments open.

## Phase 6 — Scale & calibrate (complete)

The model is now credible against real counts. The peninsula is cordoned at its bridges, so the bridge crossings are the natural calibration **screenlines**:
- **`etl calibrate`** seeds `calibration_targets` from published bridge AADT (Lions Gate 55,596 / Granville 65,000 / Cambie ~55,000 / Burrard ~50,000 / Georgia+Dunsmuir viaducts ~40,000), converted to AM-peak-hour two-way via a K-factor; confidence is tagged per source (the obtainable subset — CoV counts are VanMap-gated, MoTI's have no bulk API).
- **`sim calibrate --run <name>`** counts the AM-peak two-way volume the sim puts across each gateway (clean cordon-entry screenlines, read from the run's FCD), fits a global demand scale, computes **GEH** per screenline, writes `calibration_results`, and emits `docs/calibration/report.md`.
- **Result: 5/5 screenlines within GEH < 5 (mean GEH 1.22).** Calibration exposed the Phase-4 model over-routing the east viaduct and starving Lions Gate; fixed with **per-gateway demand weights** in `sim/demand_census.py` (scale-invariant split correction). Observed volumes correspond to a full-demand scale ~3.24 (≈18× the replay sub-sample) — full-real-demand microsim exceeds SUMO's single-core ceiling (the core constraint), so replay sub-samples while the split holds at any scale.
- **Coverage (honest):** the five bridge gateways are calibrated; the diffuse East gateways, all internal links, and travel times (RTDS retired) are not. Low-confidence targets (Cambie, Burrard) are estimates pending verified MoTI/CoV counts.

## Phase 7 — Metro-wide expansion (in progress)

The peninsula stack stays microscopic; a second, coarser **metro** study area runs mesoscopically over core urbanized Greater Vancouver, selected per run.
- **Network (`etl network --area metro`).** OSM via `osmGet.py` over `config.METRO_BBOX`, **major roads only** (`--road-types` motorway…tertiary), tiled (4) to clear Overpass limits → `netconvert` → `metro.net.xml`: **29,596 edges / 16,964 junctions / 4,777 signals** (vs the peninsula's 7,307).
- **Demand (`sim/demand_metro.py`).** The StatCan CSD→CSD commuting OD becomes municipality-to-municipality trips — each Metro Van CSD has a centroid → a pool of nearby edges; out-of-bbox CSDs snap to the boundary as regional gateways. AM census curve + mirrored PM peak; `duarouter` assignment.
- **Run (`sim run --demand metro`).** `metro.net.xml` with `--mesosim` (queue-based) and coarse FCD sampling; transit + per-signal capture skipped (not shown at regional zoom). A scale-0.15 AM peak = **27,241 vehicles, peak 3,043 active**, replaying as flow ribbons.
- **Serve + view.** `/api/network?net=metro`; the viewer is now **area-aware** (loads each run's network per `params.area`, drops to a regional camera, renders flow ribbons with an adaptive per-run color scale). Per-edge volumes come from the route file for meso runs (the meso FCD carries no lane). Also fixed a duplicate-`id` bug that had left the run-selector dropdown inert.

## Phase 8 — Full-detail city ("complete simulation", in progress)

A third study area — the **whole City of Vancouver, all streets, microscopic** — for the complete zoom-in experience the meso metro net can't give (it's arterials-only). Selected per run via `sim run --demand vancouver`.
- **Network (`etl network --area vancouver`).** OSM **all drivable streets** (no road-type filter) over `VANCOUVER_BBOX`, tiled → `vancouver.net.xml`: **76,220 edges / 28,021 junctions / 1,089 signals** (residential side streets included).
- **Demand.** `demand_metro.build_demand(home_code=Vancouver)`: the city owns *every* street so the large intra-Vancouver flow spreads across all of them (side-street traffic); other CSDs get the K city edges nearest them, so distant suburbs **enter at the boundary** rather than being dropped (318 OD pairs vs 41 before the fix).
- **Buses (`etl transit --area vancouver`).** gtfs2pt's per-trip routing is intractable on 76k edges (hung for >78 min), so large nets use a **GTFS-schedule layer** (`etl/transit_schedule.py`): each bus trip → its stop polyline + scheduled times, animated in the viewer (**1,895 buses** in the AM window, built in ~4 s). Honest tradeoff: scheduled, not traffic-interacting (gtfs2pt's SUMO pt is kept for the peninsula).
- **Signals.** The micro run captures live per-approach states for all 1,089 signals (as the peninsula does) — they cycle at street zoom.
- **Run + view.** Microscopic, FCD sampled every 2 s (the all-streets trace is large). The area-aware viewer loads the city net + schedule buses (distinct blue), regional camera, and at street zoom shows individual cars on side streets, buses, and cycling signals. Verified: a scale-0.12 AM peak = 13,345 vehicles / 1,477 peak active.

### Route equilibrium, road hierarchy, and the network's real capacity ceiling (8c)

A long push to make the `central` district "busy *and* flowing" landed on an honest, measured finding: **this auto-generated network has a low capacity ceiling set by signal/intersection throughput** — it carries realistic flowing traffic only at moderate density and gridlocks when packed. The work and what it taught:

1. **Equilibrium routing.** SUMO **`duaIterate.py`** (7 meso iterations, `central` net) drives traffic to **user-equilibrium**, replayed micro with online rerouting **off** so the converged routes are *followed* — new `sim run --routes-file <equil> --reroute-prob 0` (librun rerouting prob/threads parameterized).
2. **Road hierarchy (a real bug fixed).** The equilibrium over-spread onto residential side streets because the net modeled residential at **50 km/h — identical to arterials** — with no stop signs. Fixed structurally: a `central_types.typ.xml` override drops residential to ~30 km/h (`etl network` applies it; edge IDs stay stable so buses/signals/routes survive), so through-traffic structurally stays on arterials (one-shot arterial vehicle-km **64 %→80 %**, residential **35 %→18 %**).
3. **Signals.** `tlsCoordinator` green-wave offsets (502 signals; librun prefers `*_tls_coord.add.xml`) + a viewer **de-clutter** that merges the approach-dots piled at complex netconvert-joined junctions (they read as "broken lights" but cycle normally — verified).
4. **The capacity ceiling (the real finding).** Earlier "busy" runs reported **0 teleported** but were actually *crawling* — the FCD showed **84 % of vehicles stopped at ~5 km/h** at scale 0.10–0.15: gridlock, not flow (0 teleports only means no car was stuck >120 s in one spot). A density sweep found the knee: **0.04 → 22 km/h, 0.06 → 17 km/h (realistic congested peak), 0.075 → 11 (tipping), 0.10 → 6 (gridlocked)**. Arterials sit at ~11 % of lane capacity, so it is **not lanes** — it's **intersection/signal throughput**, which the auto-net models worse than real.
5. **Signal-throughput tuning — attempted and exhausted.** Since the ceiling is intersection-bound, tried to raise it: green-wave **coordination** bought ~15 %, but **Webster green-split re-timing** (`tlsCycleAdaptation`) and **anti-spillback junction-nudging** (`--ignore-junction-blocker`) each moved it **0** (10.6–11 km/h at 0.075 with or without). The gridlock above ~0.05 is fundamental oversaturation of the dense signalized grid — not a tweakable timing problem. Going meaningfully busier would need a fundamentally cleaner network + demand model (a major project), not a parameter.

**Deliverable (run #40, `central`, scale 0.05, 07:00–09:30): 2,370 on-road at the peak, mean speed 16.6 km/h** — the busiest density that still flows: a realistic congested AM rush hour, arterials busy-but-moving and residential genuinely quiet. View: `/?run=40&t=4500`. "Packed *and* flowing" is past this network's ceiling (see #5) → a bigger network/demand project, backlogged.

## What Is In Progress

Phase 8c — **whole-city route equilibrium.** The central district (equilibrium + arterial bias + signal coordination) is done and proves the approach; extending it to the full 76k-edge city net is a longer (multi-hour) job. The deeper ceiling — the net's effective capacity is ~half of real — now wants **lane-count corrections** (OSM under-tags arterial lanes; signal coordination is already in) to flow at true demand. See `docs/development/phases/phase-8.md`.

## What Is Next

- **Whole-city equilibrium + network capacity.** Run `duaIterate` on the `vancouver` net; raise the flowing ceiling toward real density via lane/turn/signal-coordination fixes (the auto-net under-models capacity).
- **Density / sub-municipal demand.** Census-tract/DA origins for neighbourhood accuracy (vs the city-uniform intra-Vancouver spread).
- **Metro calibration & refinement.** Generalize the peninsula GEH method to regional screenlines; LOD hand-off (auto-switch vancouver↔metro by zoom).
- **Live data + richer scenarios.** GTFS-Realtime / DriveBC as live feeds; click-to-place accidents/closures.

## Key References

| File | Purpose |
|------|---------|
| `docs/development/development-tracker.md` | Detailed phase tracking and change log |
| `docs/development/phases/` | Phase implementation plans |
| `docs/architecture/decisions.md` | Architectural decision log |
| `docs/research/` | Phase 0 research deliverables |

---

*Last updated: 2026-06-02 (Phase 8c — route equilibrium: busy and flowing)*
