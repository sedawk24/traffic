# Development Tracker

Detailed phase-by-phase development progress for the **Greater Vancouver Traffic Simulator**.

---

## Phase Overview

| Phase | Name | Status |
|-------|------|--------|
| 0 | Research writeup + environment spike | Complete |
| 1 | Data pipeline (ETL → SQLite + SUMO inputs) | Complete |
| 2 | End-to-end vertical slice (tracer bullet) | Complete |
| 3 | Visualization (clean cartographic + icons) | Complete |
| 4 | Demand modeling (realistic) | Complete |
| 5 | Scenarios (accident / closure injection) | Complete |
| 6 | Scale & calibrate (best-effort quantitative) | Complete |
| 7 | Metro-wide expansion (mesoscopic region) | In Progress |
| 8 | Full-detail city (complete micro simulation) | In Progress |

**v1 north star:** a polished, fully-working vertical slice on the **downtown Vancouver peninsula** (cordoned at the bridges). Region-wide coverage is a later expansion, not a v1 gate.

---

## Phase 0: Research writeup + environment spike (Complete)

### Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Populate tracking files (CLAUDE.md, CURRENT_STATE.md, this tracker, backlog, README) | Complete | Per CLAUDE.md initial-setup rule |
| 2 | Log architectural decisions (ADRs) | Complete | docs/architecture/decisions.md |
| 3 | Write phase plan files (phase-0 … phase-6) | Complete | docs/development/phases/ |
| 4 | Write research deliverables | Complete | data-sources, engine-selection, traffic-modeling-primer, signal-timing |
| 5 | Commit documentation before code | Complete | Branch phase-0-setup |
| 6 | Install SUMO 1.27 + libsumo/traci on macOS | Complete | `uv add`; arm64 wheels, no build |
| 7 | Toolchain sanity run + FCD (XML & Parquet) | Complete | scripts/phase0_spike.py; geo + parquet supported |
| 8 | Throughput benchmark on target hardware | Complete | 225k veh-updates/s; ~34× real-time @ 8k active |

### Verification

| Check | Status | Notes |
|-------|--------|-------|
| SUMO runs headless and writes FCD (XML + Parquet; `--fcd-output.geo` present) | Done | Parquet FCD written directly by SUMO 1.27 |
| `import libsumo, traci` succeeds | Done | libsumo/traci/sumolib 1.27.0 on arm64 |
| Benchmark recorded (vehicle-updates/sec, faster-than-real-time factor) | Done | 225,334 UPS; ~34× real-time @ 8,023 active veh |
| Research docs cover data sources, engine choice, modeling primer, signal timing | Done | docs/research/ |
| Geo + Parquet FCD on the real (projected) peninsula net | Deferred → Phase 1 | Grid net is unprojected; validated on real net during ETL |

---

## Phase 1: Data pipeline (Complete)

### Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | OSM → SUMO `.net.xml` for the peninsula (cordon at bridges) | Done (automated) | `etl network` + automated cordon trim → 7,307 edges / 266 TLS (UTM-10 geo); plain-XML baseline emitted. Optional manual netedit polish (lanes/turns) is documented future refinement |
| 2 | Capture network edits as netdiff | Ready | `etl network` emits the plain-XML baseline; netdiff workflow documented in phase-1.md (run after a manual netedit pass) |
| 3 | TransLink GTFS static → SUMO pt (bus + rail) | Done (bus) | `etl transit`: gtfs2pt.py → 254 pt stops, 140 routes, 4,062 bus departures on the peninsula net. SkyTrain/rail/SeaBus deferred (need rail/water edges) |
| 4 | StatCan 98-10-0459 OD + 98-10-0458 departure profiles → SQLite | Done | `etl census`: streamed full-Canada tables, filtered to Greater Vancouver → 456 intra-GVRD OD flows + 2,618 departure-profile rows (verified: AM peak, 57/23/19 car/transit/active) |
| 5 | Metro 2050 + Vancouver zoning (+ OSM landuse fallback) → zones | Done (peninsula) | `etl zoning`: CoV zoning + parks → 366 zones (5 classes) + 6 bridge gateways, clipped to cordon; zones.geojson exported. Metro 2050 deferred to region expansion; pop/emp weights to Phase 4 |
| 6 | CoV signal locations + DriveBC Open511 ingest | Done | `etl signals`: 254 CoV signals in cordon, 247 matched to SUMO TLS (<60 m). `etl events`: 5 canonical bridge-closure scenarios (wired to net edges) + live DriveBC events |
| 7 | SQLite schema + idempotent ETL CLI | Mostly Done | `etl/schema.sql` (12 tables) + `python -m etl` CLI live; idempotent harness in place |

### Verification

| Check | Status | Notes |
|-------|--------|-------|
| ETL re-run produces identical DB (idempotent) | Done | All loaders delete-by-source + deterministic/natural keys; content reproducible (audit `fetched_at` volatile by design) |
| OD totals reconcile with census source | Done | 222k intra-GVRD into Vancouver; top origins Vancouver/Burnaby/Surrey/Richmond; mode split 57/23/19 — matches known figures |
| Network opens cleanly in netedit; bridges/gateways present | Done | Reads cleanly via sumolib; cordon-trimmed with bridge gateway stubs; plain-XML baseline emitted |
| Zone polygons render with land-use classes | Partial | Data ready: 366 zones with land_use in DB + zones.geojson; visual render is Phase 3 |

---

## Phase 2: End-to-end vertical slice (Complete)

### Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Build scenario with placeholder demand (randomTrips/toy gateway OD) | Done | `sim/demand.py`: randomTrips, fringe-biased toward the bridge gateways |
| 2 | Run one day via libsumo; emit sampled geo Parquet FCD | Done | `sim run`: SUMO batch → geo FCD Parquet; run registered in `runs`. Binary (not libsumo) for batch to avoid the libsumo/pyarrow Arrow clash — see decisions.md |
| 3 | Post-process FCD → trajectory Parquet (path + timestamps + type) | Done | `sim/trace.py`: t/id/cls/lon/lat/speed/angle. Baseline 07:00–08:00 = 3,877 veh, peak 566, 1.57M rows (incl. 212k bus) |
| 4 | FastAPI: stream trace as Arrow; serve network/zones as GeoJSON | Done | `api/main.py`: `/api/runs`, `/api/runs/{id}/meta`, `/api/runs/{id}/trace` (Arrow IPC, time-windowed/strided), `/api/network` + `/api/zones` (GeoJSON), static viewer |
| 5 | Minimal deck.gl + MapLibre viewer with day-scrubber | Done | `web/index.html`: MapLibre + deck.gl (zones/roads GeoJsonLayers, vehicles ScatterplotLayer by speed), play/scrub/speed + clock. Verified by headless screenshot |

### Verification

| Check | Status | Notes |
|-------|--------|-------|
| Browser shows zones + roads + moving vehicles from a real SUMO run | Done | **Key gate met** — headless screenshot shows the peninsula (Stanley Park/downtown/port zones), road net, and ~280 moving vehicles at 07:05 |
| Day-scrubber moves time forward/back | Done | range scrubber bound to currentTime; play/pause + speed; time-of-day clock |

---

## Phase 3: Visualization (Complete)

### Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | PMTiles basemap (clipped BC) + clean MapLibre style | Deferred | OpenFreeMap positron (dev) meets the visual goal; self-hosted PMTiles → backlog (no tooling; not in the exit gate) |
| 2 | Land-use-shaded zones; styled roads/bridges/transit | Done | Land-use zones + legend; roads styled by class; bridge gateways labelled; transit route lines (138 bus routes) |
| 3 | Vehicle IconLayer distinct by type; optional TripsLayer trails | Done | `IconLayer` car/bus glyphs (mask-tinted by type, oriented by heading, interpolated each frame) = discrete vehicles. Long trails over-painted the dense grid → replaced; kept as an optional tiny tail (toggle) |
| 4 | LOD: flow ribbons @region ↔ icons @street | Done | Roads as flow ribbons coloured by per-edge volume @region ↔ individual icons @street (transition ~zoom 13.2); land-use fills fade with zoom |
| 5 | Controls: play/pause/speed, time-of-day clock, legend, scenario selector | Done | + layer toggles; backend `/api/runs/{id}/trips` serves TripsLayer data |

### Verification

| Check | Status | Notes |
|-------|--------|-------|
| Vehicle types visually distinct; smooth zoom region→intersection | Done | Car/bus icons oriented by heading; MapLibre smooth zoom region→street |
| LOD transition holds 60fps | Done | Flow ribbons (static GPU paths) @region ↔ ~280 icons @street; transition at zoom 13.2 |

---

## Phase 4: Demand modeling (Complete)

### Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Disaggregate CSD→CSD OD to peninsula zones + bridge gateways | Done | `sim/demand_census.py`: edge↔zone sjoin + land-use emp/pop weights; external origins → directional bridge gateways; peninsula job/pop-share scaling |
| 2 | Mode split + stochastic departure times from 98-10-0458 | Done | Stochastic departures from the census AM histogram (+ synthetic PM peak); car-mode-share scaling (transit = the Phase-1 buses) |
| 3 | Synthesize non-work + commercial/delivery + heavy-truck demand | Done | Midday non-work + delivery-van + heavy-truck demand from land-use generators (vTypes car/hov/delivery/truck) |
| 4 | Assignment via duarouter/duaIterate → SUMO routes | Done (one-shot) | `duarouter` → SUMO routes; `sim run --demand census`. duaIterate (DUE) + tls tuning deferred to backlog |

### Verification

| Check | Status | Notes |
|-------|--------|-------|
| Departure histogram + mode split match census | Done | AM departure shape matches census (06:00/08:00 ratio 0.50 = census); car/transit/active split honoured via scaling |
| AM-in / PM-out visible; bridge gateway volumes plausible | Done | Full-day sim is bimodal (AM ~801 @ 08:00, PM ~946 @ 17:00 active); gateway volumes east > south > Lions Gate, matching the OD |

---

## Phase 5: Scenarios (Complete)

### Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | TraCI mid-run injection: close edge/lane, stop vehicle, drop speed | Done (closure) | `sim/librun.py`: disallow the **whole bridge's** lanes at the event time (+ reopen). Accident (stop-vehicle) + speed-drop are the same TraCI pattern → backlog |
| 2 | Reroute affected traffic | Done | `--device.rerouting` on all vehicles; closing Granville bars the full structure (both directions) — 0 new entries after 08:00 — and traffic redistributes to Burrard/Cambie |
| 3 | DriveBC Open511 closure library | Done | Seeded in Phase 1 (`etl events`): 5 canonical bridge closures, each the **full OSM-derived edge set** (Granville 43, Cambie 48, viaducts 54, Burrard 8, Lions Gate 2) + live DriveBC events |
| 4 | Before/after UI: baseline vs scenario, delta metrics | Done | Run selector (`?run=`) + scenario panel: Δ avg travel / avg wait / trips-done vs a matched baseline; **all** closed edges highlighted (✕) on the map |

### Verification

| Check | Status | Notes |
|-------|--------|-------|
| Inject closure → observe rerouting + before/after deltas | Done | Granville full-bridge closure (07:00–09:00, scale 0.18): 22,895 vehicle-frames while open → **0 new entries after 08:00** (both directions), 3 mid-span vehicles cleared by 08:04; Δ −174 trips / +8 s travel / +6 s wait vs matched baseline. Verified by FCD edge-occupancy query + headless screenshot (empty red span) |

---

## Phase 6: Scale & calibrate (Complete)

### Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Calibration-data spike: MoTI bridge/highway counts, scrape CoV stations | Done | `etl calibrate` seeds published bridge AADT (Lions Gate 55,596 / Granville 65,000 / Cambie ~55k / Burrard ~50k / viaducts ~40k) → `calibration_targets`, confidence-tagged; web-sourced (Wikipedia/CoV/MoTI). CoV/MoTI bulk feeds unobtainable (Phase 0 §7) → estimates flagged, verification → backlog |
| 2 | Calibrate demand/signals toward GEH < 5 on obtainable subset | Done | `sim calibrate` fits a global demand scale + GEH per screenline; the residual route-split imbalance (east viaduct over-fed, Lions Gate starved) fixed with per-gateway demand weights in `sim/demand_census.py`. **5/5 screenlines GEH < 5, mean 1.22** |
| 3 | Document calibration coverage | Done | `docs/calibration/report.md` (auto-generated): per-screenline GEH, gateway weights, demand-scale relationship, honest calibrated/uncalibrated coverage. `calibration_results` written to DB |
| 4 | Expand outward (meso region + micro focus) | Deferred | Stretch goal (not a v1 gate) → backlog "Region-wide coverage" |

### Verification

| Check | Status | Notes |
|-------|--------|-------|
| Simulated vs observed counts (GEH<5 on obtainable subset) | Done | 5/5 bridge screenlines within GEH<5 (Georgia 0.00, Granville 0.47, Cambie 0.51, Burrard 1.35, Lions Gate 3.77); mean GEH 1.22 |
| Calibration coverage documented honestly | Done | `docs/calibration/report.md` states the obtainable subset, low-confidence estimates, and uncalibrated links/travel-times explicitly |

---

## Phase 7: Metro-wide expansion (In Progress)

### Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Metro network (major roads, tiled OSM) | Done | `etl network --area metro`: `osmGet.py` over `METRO_BBOX`, `--road-types` motorway…tertiary, 4 tiles → `metro.net.xml` (29,596 edges / 16,964 junctions / 4,777 TLS) |
| 2 | Metro demand (municipality OD) | Done | `sim/demand_metro.py`: CSD→CSD OD → centroid edge pools (out-of-bbox CSDs snap to boundary as gateways); AM+PM curves; duarouter |
| 3 | Mesoscopic run | Done | `sim run --demand metro` → `--mesosim` + coarse FCD; transit/signal capture skipped. Scale-0.15 AM = 27,241 veh, peak 3,043 |
| 4 | Area-aware API + viewer | Done | `/api/network?net=metro`; viewer loads net per `params.area`, regional camera, adaptive flow-color scale; meso volumes from the route file; fixed duplicate-`id` run-selector bug |
| 5 | Metro calibration (regional screenlines) | Not Started | Generalize the peninsula GEH method → backlog |
| 6 | Regional transit + finer demand + LOD hand-off | Not Started | GTFS over metro net; sub-municipal TAZ; meso↔micro switch → backlog |

### Verification

| Check | Status | Notes |
|-------|--------|-------|
| Region-wide meso run replays in the browser | Done | Metro AM peak (27k veh) renders as regional flow ribbons over the GVRD net; major corridors (Hwy 1, bridges, Surrey/Richmond arterials) light up red at the AM peak |

---

## Phase 8: Full-detail city — "complete simulation" (In Progress)

### Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Full City of Vancouver net (all streets, micro) | Done | `etl network --area vancouver`: all drivable roads over `VANCOUVER_BBOX`, tiled → 76,220 edges / 28,021 junctions / 1,089 TLS |
| 2 | Distributed city demand (side streets populated) | Done | `demand_metro` `home_code`=Vancouver owns every street; other CSDs get K nearest boundary edges (318 OD pairs vs 41) |
| 3 | Buses on the big net | Done | gtfs2pt intractable (>78 min hang) → `etl/transit_schedule.py` GTFS-schedule layer: 1,895 AM buses, built in ~4 s; fixed a GTFS int/str id-join bug |
| 4 | Live signals (micro) | Done | Micro run captures all 1,089 signals' per-approach states; cycle at street zoom |
| 5 | Area-aware API + viewer for the city | Done | `/api/transit-vehicles`; viewer loads city net + schedule buses (blue), regional camera, cars+buses+signals at street zoom |
| 6 | Density tuning / route equilibrium | Done | one-shot routing gridlocked above ~0.06; **duaIterate equilibrium** (central, scale 0.15) flows at **10,452 peak / 0 stuck** (run #27). New `--routes-file` + `--reroute-prob` plumbing |

### Verification

| Check | Status | Notes |
|-------|--------|-------|
| Zoom into a neighbourhood shows side-street cars + buses + signals | Done | West Side @ 08:10: cars on residential streets (congestion-colored), buses (blue) on 4th/Broadway/Macdonald, 1,089 signals cycling — vs the single car before |
| Equilibrium routing yields busy-and-flowing (no gridlock) at high density | Done | Run #27 (central, equilibrium replay, 08:20 peak): 10,452 on-road, **0 teleported** (vs one-shot 21 % stuck); screenshots show traffic distributed across the whole grid, arterials congested-but-moving |

---

## Change Log

| Date | Phase | Change |
|------|-------|--------|
| 2026-06-02 | 8c | **Route equilibrium + road hierarchy + signal coordination — a realistic busy district.** Getting "busy *and* flowing *and* realistic" took three linked fixes. **(1) Equilibrium routing.** One-shot shortest-path routing gridlocked the auto-net above scale ~0.06 (all cars on the same arterials), yet scaling down left it near-empty. SUMO `duaIterate.py` (7 meso iterations, `central` net, scale 0.15, 50,392 routable trips) drove traffic to **user-equilibrium**; replayed micro with online rerouting **off** so the converged routes are *followed* — new `sim run --routes-file <equil> --reroute-prob 0` (librun rerouting prob/threads parameterized; trips pre-filtered to routable + vTypes inlined so duaIterate runs clean). Gave 10,452 peak on-road, 0 stuck (vs one-shot 21 % gridlocked). **(2) Road hierarchy.** That equilibrium *over-spread onto residential side streets* (W 12th jammed while Broadway sat empty) because duarouter routes on time only and the net models residential at 44 km/h ≈ arterials with no stop signs. Re-ran duaIterate with `--weights.priority-factor 4` + `--weights.minor-penalty 12` → arterial vehicle-km **64 %→76 %**, residential **35 %→23 %**, busiest residential street **539→260 veh**, the W 12th rat-run gone. **(3) Signal coordination.** Concentrating traffic back onto the arterials saturated them (avg wait 1,035→1,258 s); `tlsCoordinator` green-wave offsets (502 signals, computed from the equilibrium flows; librun now prefers `*_tls_coord.add.xml` over the per-intersection cycle program) cut wait **−16 %** and raised throughput **+9 %** (1-hour A/B). **Final (run #31, 07:00–09:30): 11,356 peak on-road, avg wait 1,071 s, 0 teleported** — traffic on the right roads, signals coordinated, busy, nothing broken-gridlocked. Deeper ceiling (arterial lane capacity, whole-city equilibrium) → backlog. |
| 2026-06-02 | 8b | **Land use for central/vancouver areas.** Zones (land-use coloring) were only built for the peninsula (clipped to the downtown cordon), so central runs showed no land use. Generalized `etl zoning --area` to clip the city zoning to any area's bbox; `/api/zones?net=` + the viewer now serve/load per-area zones. Refined the CD-blanket-maps-to-downtown-core heuristic geographically (downtown-core only inside the downtown peninsula; West-Side CD -> residential): central 429->239 downtown-core, 159->349 residential. Flow ribbons only cover the district net (the wider region is the metro area). |
| 2026-06-02 | 8b | **Windowed trip streaming (dense runs now viewable).** The viewer loaded *all* trips upfront, so dense runs (a 34k-veh run = 685 MB trips JSON) failed with 'Unexpected end of JSON input'. Added `start`/`end` to `/api/trips` (parquet predicate pushdown) and a streaming window in the viewer (300 s, `every=3`, reload as the clock moves) — dense runs stream ~12 MB windows and display. This removes the display ceiling on density; the remaining density limit is network capacity (gridlock → `duaIterate`). |
| 2026-06-02 | 8b | **Bus fix + signal-tuning (measured).** Root-caused the broken buses: the `transit_buses` route file wasn't sorted by depart, so SUMO silently dropped out-of-order vehicles (cars sort, buses didn't) -> only 68/728 ran, all late. Sorting by depart -> **638 buses run, 540 complete**, stopping + obeying signals throughout the peak (scale 0.05, flowing: 93% trips done, avg wait 123s). Wired demand-adapted signals (`tlsCycleAdaptation` program 'a', activated in librun) — honest negative result: it did NOT clear the over-saturation gridlock at scale 0.12 (avg wait 370->391s), confirming the jam is spillback/one-shot-routing concentration, not signal timing. Density above ~0.06 needs `duaIterate` equilibrium (top backlog item). |
| 2026-06-02 | 8b | **System review + "make it real" fixes (measured, after a sloppy-work call-out).** A measured audit found: (1) the city schedule-buses ignored signals/stops (a regression), (2) density was sparse (~1 car/211m) because **41% of trips were unroutable + 76% departed outside the run window** + scale ~9% of real, (3) `--threads` gives no micro speedup (SUMO #4767). Fixes, each verified: **demand** now samples in-window departures only and filters trip-ends to connected edges → **unroutable 41%→17%, in-window 24%→100%**; new **`central` district** (downtown+West Side, 23,609 edges) for tractable micro at real density; **real SUMO buses** via `etl/transit_buses.py` (snap GTFS stops→edges + duarouter, inline `<stop>` dwells) — **728 buses that stop + obey signals, built in 9 s** (gtfs2pt couldn't); removed `--threads`, kept `--device.rerouting.threads` (routing parallelizes, ~145% CPU). **Calibrated to real bridge volumes** (Granville GEH 3.42, Cambie 0.52 at scale 0.55) — real density ≈ 1 car/71m; that scale's ~1 GB / 170k-veh trace exceeds the batch-replay viewer, so replay uses a denser-than-before but sub-real scale (windowed trace streaming → backlog). Fixed duplicate-vType crash (duarouter embeds the vType). |
| 2026-06-01 | 8 | **Phase 8 — full-detail microscopic City of Vancouver ("complete simulation").** Third study area: `etl network --area vancouver` builds all 76,220 street-edges (incl. residential side streets), `sim run --demand vancouver` runs it micro with live signals (1,089) + buses. Fixed the demand to populate side streets (`home_code` = the city owns every street; distant suburbs enter at the boundary → 318 OD pairs vs 41). Diagnosed gtfs2pt as intractable on the big net (>78 min hang across 3 attempts) and replaced it with a GTFS-**schedule** bus layer (`etl/transit_schedule.py`, `/api/transit-vehicles`, viewer bus animation) — 1,895 AM buses in ~4 s; fixed a GTFS int/str id-join bug that silently yielded 0 buses. Viewer made area-aware (loads each run's net/buses per `params.area`, distinct blue buses). Verified a populated West Side (cars on side streets + buses + cycling signals) at scale 0.12 (13,345 veh); density tuning to 0.30 in progress. |
| 2026-06-01 | 7 | **Phase 7 — metro-wide mesoscopic expansion (region replays in the browser).** Generalized the network builder for a second study area: `etl network --area metro` fetches major roads (`--road-types`, 4 tiles) over `METRO_BBOX` → `metro.net.xml` (29,596 edges). New `sim/demand_metro.py` turns the CSD→CSD OD into municipality-to-municipality trips via centroid edge pools (out-of-bbox CSDs snap to the boundary). `sim run --demand metro` runs `--mesosim` (parameterized `librun`: meso flag, coarse FCD, skip transit/signal capture); a scale-0.15 AM peak = 27,241 veh. Made the API + viewer area-aware (`/api/network?net=`, per-run network load, regional camera, adaptive flow-color scale, route-file volumes for meso); fixed a duplicate-`id` bug that left the run-selector inert. Metro calibration/transit/finer-demand → backlog. |
| 2026-06-01 | 6 | **Phase 6 complete — calibration; exit gate met (final phase).** Bridge crossings are the cordon screenlines. `etl/calibration.py` (`etl calibrate`) seeds published bridge AADT → AM-peak count targets (web-sourced: Wikipedia/CoV/MoTI; CoV+MoTI bulk feeds unobtainable, estimates flagged). `sim/calibrate.py` (`sim calibrate --run`) counts simulated AM-peak two-way gateway volumes from the FCD, fits a global demand scale, computes GEH, writes `calibration_results` + `docs/calibration/report.md`. Calibration exposed the Phase-4 east-viaduct over-routing / Lions-Gate starvation; fixed with per-gateway demand weights (`GATEWAY_WEIGHT`) in `sim/demand_census.py` (scale-invariant split correction). **Result: 5/5 screenlines GEH<5, mean 1.22.** Full-demand scale ~3.24 (≈18× the replay sub-sample) — full microsim exceeds SUMO's single-core ceiling, so replay sub-samples while the split holds. Re-ran am_base + am_granville on the calibrated demand. All 6 build phases (0–6) now complete. |
| 2026-06-01 | 5 | **Fix: closure highlight is time-gated to the closure window.** The red "✕ closed" edges + scenario header showed from 07:00 even though Granville doesn't close until 08:00 — confusing (bridge marked closed while traffic crossed it). `web/index.html` now only reds the closed edges when `begin+T` is within `[closure.start, closure.end)`, and a live panel header reads "closes 08:00" (amber) → "✕ closed" (red) → "reopened" (green). Verified via DOM dump at 07:30 (amber, unmarked) vs 08:10 (red, ✕). |
| 2026-06-01 | 5 | **Fix: closures now bar the whole bridge, not one edge.** A closed bridge had traffic running the opposite way because only the single nearest edge/direction was disallowed. `etl events` now derives each bridge's full drivable edge set (both directions + ramps) by buffering the named OSM bridge ways and intersecting the SUMO net (`_bridge_edges` + `BRIDGE_OSM_NAMES`); stores them in `events.params.edges` (Granville 43, Cambie 48, viaducts 54, Burrard 8, Lions Gate 2). `sim/cli.py` passes the full edge list through; `sim/librun.py` closes every lane of every edge; `web/index.html` reds them all + a `?run=` selector. Re-verified Granville: 0 new entries after the 08:00 closure (both ways), bridge empties by 08:04. FK-detach (`runs.scenario_id → NULL`) before re-seeding scenarios. |
| 2026-06-01 | 5 | **Phase 5 complete — closure injection + before/after; exit gate met.** Unified the run path into `sim/librun.py` (one libsumo process → geo FCD + per-approach signals + tripinfo, with optional mid-run **closure**: disallow an edge's lanes at the event time, with `--device.rerouting` so traffic redistributes). `sim run --scenario close_<bridge>`; runs register their scenario + metrics. Viewer: scenario panel with Δ avg travel / wait / trips-done vs a matched baseline + the closed edge highlighted (✕). Demo: closing Granville vacated the bridge (200→2 after 08:00), rerouted traffic, +14 s travel/wait, −96 trips. Replaced run.py + tlscapture.py with librun. Accident/speed-drop primitives + click-to-place authoring → backlog. |
| 2026-06-01 | 4 | **Phase 4 complete — census demand; exit gate met.** `sim/demand_census.py` turns the SQLite OD (98-10-0459) + departure profiles (98-10-0458) + land-use zones into SUMO routes for a representative weekday: edge↔zone sjoin + emp/pop weights, external origins → directional bridge gateways, census AM departure curve (+ synthetic PM), car-mode-share scaling, and synthesized non-work/delivery/truck demand; duarouter assignment. `sim run --demand census`. Verified: AM departure shape matches census; full-day sim is bimodal (AM ~801 / PM ~946 active); gateway volumes east > south > Lions Gate (matches the OD). Fixed `trace._classify` for non-string vTypes. duaIterate + tls tuning → backlog. |
| 2026-06-01 | 3 | **Signals: one indicator per approach (review).** Per-movement dots (3 per approach) read as confusing clutter. `tlscapture` now records each movement's incoming approach edge; the viewer groups movements by edge and shows a single green/yellow/red dot per approach (green if any movement is green, else yellow, else red), positioned at the approach's stop line — a normal traffic-light read. |
| 2026-06-01 | 3 | **Signal-dot styling fix (review).** Signal markers used deck's default 1-*metre* stroke, so the ring ballooned to a solid black dot when zoomed in. Switched to a thin pixel-based white halo + radius that scales with zoom (clamped) — colour now reads clearly at street zoom. |
| 2026-06-01 | 3 | **Live traffic signals + data-grounded bridges (review).** Built the live-signal feature: a libsumo pass (`sim/tlscapture.py`, separate process to avoid the Arrow clash) captures each light's per-approach state + stop-line positions over the run → `/api/runs/{id}/signals-live`; the viewer renders per-approach **red/green/amber dots at street zoom that cycle over time** (verified t=320 vs t=345 differ). Fixed bridge-gateway coordinates properly by extracting the named OSM bridge/viaduct way centroids (Cambie was ~600 m off); closure edges now 3–30 m from the bridges. |
| 2026-06-01 | 3 | **Phase 3 review polish.** Street-zoom vehicles now coloured by **congestion** (red = stopped → green = moving; speed derived from the path) with a `congestion` toggle — the jam indicator is back; icons enlarged for legibility. **Corrected bridge-gateway coordinates** to the real bridge midspans (Granville/Cambie/Burrard were off) and re-ran zoning + events (closure edges now 11–136 m from the bridges). Added `/api/signals` + traffic-signal location markers at street zoom (≥ z15.3). Live signal red/green state queued (needs TLS-phase capture) — backlog. |
| 2026-06-01 | 3 | **Phase 3 complete — transit + LOD; exit gate met.** Backend: `/api/transit` (138 bus-route polylines) + `/api/runs/{id}/volumes` (per-edge traffic). Viewer: region→street **LOD** — roads as flow ribbons coloured by edge volume when zoomed out, individual icons at street zoom (transition ~zoom 13.2); subtle bus-route lines; legend with a flow ramp. Exit gate met (vehicle types distinct, smooth zoom, LOD holds frame rate, bridges + transit clear). Self-hosted PMTiles deferred to backlog (no tooling; not in the exit gate). |
| 2026-06-01 | 3 | **Vehicles: trails → icons (review feedback).** Long comet-trails over-painted the dense downtown grid (every segment stayed coloured). Replaced with per-vehicle `IconLayer` glyphs (car/bus, mask-tinted by type, oriented by heading), interpolated client-side each frame from `/trips?every=2` for smooth motion. Trails demoted to an optional tiny tail (off by default). Land-use fills now fade as you zoom to street level. Added `?zoom=&lng=&lat=` view params. Verified by zoomed headless screenshots. |
| 2026-06-01 | 3 | **Phase 3 started — visual overhaul.** Backend: `/api/runs/{id}/trips` (per-vehicle paths for TripsLayer) + road `class` on `/api/network`. Viewer rebuilt: animated `TripsLayer` comet-trails coloured by vehicle type (car=blue, bus=orange), refined land-use zone palette + legend, roads styled by class, labelled bridge gateways, run/speed selectors, layer toggles, time-of-day clock. Verified by headless screenshot (positron basemap + downtown trails at 07:05). Remaining: glyph icons, transit route lines, region→street LOD, self-hosted PMTiles. |
| 2026-06-01 | 2 | **Phase 2 complete — backend + viewer (Tasks 4–5); key gate met.** `api/` FastAPI: net/zones GeoJSON + run trace as Arrow IPC (time-windowed). `web/index.html`: MapLibre + deck.gl viewer (zones/roads + vehicles colored by speed) with play/scrub/speed + time-of-day clock. Headless screenshot confirms the peninsula with moving vehicles at 07:05. Added fastapi + uvicorn. Fixed a Phase-1 bug: zones GeoJSON emitted `NaN` names (invalid JSON) — normalised in `etl/zoning.py` + regenerated. |
| 2026-06-01 | 2 | **Phase 2 started — sim runner (Tasks 1–3).** `sim/` package: randomTrips placeholder demand (fringe-biased to gateways) → SUMO batch geo FCD Parquet → trajectory Parquet (t/id/cls/lon/lat/speed/angle), run registered in `runs`. Baseline (07:00–08:00, with transit): 3,877 vehicles, peak 566 concurrent, 1.57M rows incl. 212k bus, 32 MB. Validates the SUMO→trace path on the real projected net (clears the deferred Phase 0 geo+Parquet check). Added pyarrow; chose the sumo binary over libsumo for batch to avoid the libsumo/pyarrow Arrow clash (ADR in decisions.md). |
| 2026-05-31 | 1 | **Phase 1 complete.** All ETL loaders done + verified; DB populated — network 1, zones 366, od_flows 456, departure_profiles 2,618, signals 254, scenarios/events 11, across 8 provenance-tracked sources. `etl network` emits a plain-XML baseline; the netedit/netdiff manual-refinement workflow is documented in phase-1.md. Optional manual net polish moved to backlog. |
| 2026-05-31 | 1 | **Census loader (Task 4).** `etl census`: streamed StatCan 98-10-0459 (OD) + 98-10-0458 (departure) full-Canada tables, filtered to Greater Vancouver (CD 5915) → 456 intra-GVRD CSD→CSD flows + 2,618 departure rows. Verified: 222k intra-GVRD commuters into Vancouver (top origins Vancouver/Burnaby/Surrey/Richmond), AM-peak departure histogram, 57/23/19 car/transit/active mode split. Added plain-XML netdiff baseline to `etl network`. |
| 2026-05-31 | 1 | **Transit loader (Task 3).** `etl transit`: TransLink GTFS static → SUMO pt via gtfs2pt.py (bus, cordon bbox, `--repair`) → 254 stops + 140 routes + 4,062 bus departures (data/sumo/peninsula_pt_*.xml). SkyTrain/rail/SeaBus deferred (no rail/water edges in the road net). Added `rtree` dep (gtfs2pt requirement). |
| 2026-05-31 | 1 | **Signals + events loaders (Task 6).** `etl signals`: CoV signal locations clipped to the cordon (254) and matched to the nearest SUMO traffic-light junction within 60 m (247/254). `etl events`: 5 canonical bridge-closure scenarios (Lions Gate/Burrard/Granville/Cambie/viaducts), each wired to the nearest drivable net edge, plus live DriveBC Open511 events near the approaches (6). Added `etl/util.py` (shared streaming download). |
| 2026-05-31 | 1 | **Zoning loader (Task 5).** `etl zoning`: CoV zoning + CoV parks (Explore API v2.1) clipped to the cordon and reclassified to {residential, commercial, industrial, parkland, downtown-core}, plus 6 virtual bridge-gateway zones → 366 rows in `zones` + `data/zones/zones.geojson` (252 downtown-core, 58 parkland incl. Stanley Park, 22 industrial, 21 residential, 7 commercial, 6 gateways). Idempotent (delete-by-source + deterministic positional ids). Metro 2050 deferred to the region expansion; pop/emp weights to Phase 4. |
| 2026-05-31 | 1 | **Automated cordon trim.** Added `config.CORDON_POLYGON` + netconvert `--keep-edges.in-geo-boundary` & `--keep-edges.components 1` to `etl network`; trims the raw OSM net at the bridges to the peninsula (15,598 → 7,307 edges; verified geo extent lon[−123.16,−123.08] lat[49.27,49.32], with downtown/Stanley Park in and Kitsilano/North Van out). Added geo/ETL deps (geopandas, pandas, shapely, pyproj, requests). |
| 2026-05-31 | 1 | **Phase 1 started.** Built the ETL backbone: `etl/` package with SQLite schema (`schema.sql`, 12 tables), idempotent CLI (`python -m etl`: init-db/network/zoning/census/transit/signals/events/all/status), open-data source registry, and loader stubs; added `ruff` dev dep (checks pass). Implemented `etl network`: OSM via SUMO `osmGet.py` → `netconvert` → `data/sumo/peninsula.net.xml` (15,598 edges / 6,593 junctions / 473 TLS; UTM-10 geo-projection stored). Provenance + net metadata recorded in `data/traffic.db`. Manual netedit cordon cleanup + zoning/census/transit/signals/events loaders pending. |
| 2026-05-31 | 0 | **Phase 0 complete.** SUMO 1.27 + libsumo verified on Apple Silicon via `uv`; FCD XML + Parquet and `--fcd-output.geo` confirmed; benchmark ~225k vehicle-updates/sec (~34× real-time at 8k active vehicles). Added pyproject.toml, uv.lock, scripts/phase0_spike.py. |
| 2026-05-31 | 0 | Project planning complete; architecture + phased plan agreed. Phase 0 research verified (with corrections: RTDS retired, CoV counts not bulk, Trip Diary dashboard-only). Tracking files and research deliverables populated. |
| 2026-05-31 | -- | Initial development tracker created |
