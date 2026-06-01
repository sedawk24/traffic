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
| 4 | Demand modeling (realistic) | Not Started |
| 5 | Scenarios (accident / closure injection) | Not Started |
| 6 | Scale & calibrate (best-effort quantitative) | Not Started |

**v1 north star:** a polished, fully-working vertical slice on the **downtown Vancouver peninsula** (cordoned at the bridges). Region-wide coverage is a later expansion, not a v1 gate.

---

## Phase 0: Research writeup + environment spike (In Progress)

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

## Phase 4: Demand modeling (Not Started)

### Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Disaggregate CSD→CSD OD to peninsula zones + bridge gateways | Not Started | Weight by land use/pop/employment |
| 2 | Mode split + stochastic departure times from 98-10-0458 | Not Started | Not everyone at 07:00 |
| 3 | Synthesize non-work + commercial/delivery + heavy-truck demand | Not Started | Land-use heuristics + Trip Diary aggregates |
| 4 | Assignment via duarouter/duaIterate → SUMO routes | Not Started | AM-in / midday / PM-out rhythm |

### Verification

| Check | Status | Notes |
|-------|--------|-------|
| Departure histogram + mode split match census | Pending | |
| AM-in / PM-out visible; bridge gateway volumes plausible | Pending | |

---

## Phase 5: Scenarios (Not Started)

### Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | TraCI mid-run injection: close edge/lane, stop vehicle, drop speed | Not Started | |
| 2 | Reroute affected traffic | Not Started | |
| 3 | DriveBC Open511 closure library | Not Started | Highways/bridges |
| 4 | Before/after UI: baseline vs scenario, delta metrics | Not Started | Travel time, queue, throughput |

### Verification

| Check | Status | Notes |
|-------|--------|-------|
| Inject closure → observe rerouting + before/after deltas | Pending | "Close Lions Gate Bridge" demo |

---

## Phase 6: Scale & calibrate (Not Started)

### Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Calibration-data spike: MoTI bridge/highway counts, scrape CoV stations | Not Started | Honest about gaps |
| 2 | Calibrate demand/signals toward GEH < 5 on obtainable subset | Not Started | + corridor travel-time checks |
| 3 | Document calibration coverage | Not Started | calibration_results |
| 4 | Expand outward (meso region + micro focus) | Not Started | Stretch goal |

### Verification

| Check | Status | Notes |
|-------|--------|-------|
| Simulated vs observed counts (GEH<5 on obtainable subset) | Pending | |
| Calibration coverage documented honestly | Pending | |

---

## Change Log

| Date | Phase | Change |
|------|-------|--------|
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
