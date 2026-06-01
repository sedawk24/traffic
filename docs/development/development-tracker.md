# Development Tracker

Detailed phase-by-phase development progress for the **Greater Vancouver Traffic Simulator**.

---

## Phase Overview

| Phase | Name | Status |
|-------|------|--------|
| 0 | Research writeup + environment spike | Complete |
| 1 | Data pipeline (ETL → SQLite + SUMO inputs) | In Progress |
| 2 | End-to-end vertical slice (tracer bullet) | Not Started |
| 3 | Visualization (clean cartographic + icons) | Not Started |
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

## Phase 1: Data pipeline (In Progress)

### Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | OSM → SUMO `.net.xml` for the peninsula (cordon at bridges) | In Progress | `etl network` + automated cordon trim done (7,307 edges / 266 TLS, UTM-10 geo; trimmed at the bridges to the peninsula); fine netedit cleanup (connectivity/lanes/gateways) pending |
| 2 | Capture network edits as netdiff | Not Started | Survive OSM re-import |
| 3 | TransLink GTFS static → SUMO pt (bus + rail) | Done (bus) | `etl transit`: gtfs2pt.py → 254 pt stops, 140 routes, 4,062 bus departures on the peninsula net. SkyTrain/rail/SeaBus deferred (need rail/water edges) |
| 4 | StatCan 98-10-0459 OD + 98-10-0458 departure profiles → SQLite | Not Started | Open Licence |
| 5 | Metro 2050 + Vancouver zoning (+ OSM landuse fallback) → zones | Done (peninsula) | `etl zoning`: CoV zoning + parks → 366 zones (5 classes) + 6 bridge gateways, clipped to cordon; zones.geojson exported. Metro 2050 deferred to region expansion; pop/emp weights to Phase 4 |
| 6 | CoV signal locations + DriveBC Open511 ingest | Done | `etl signals`: 254 CoV signals in cordon, 247 matched to SUMO TLS (<60 m). `etl events`: 5 canonical bridge-closure scenarios (wired to net edges) + live DriveBC events |
| 7 | SQLite schema + idempotent ETL CLI | Mostly Done | `etl/schema.sql` (12 tables) + `python -m etl` CLI live; idempotent harness in place |

### Verification

| Check | Status | Notes |
|-------|--------|-------|
| ETL re-run produces identical DB (idempotent) | Partial | Harness in place (CREATE IF NOT EXISTS + natural-key upserts); content idempotent, audit `fetched_at` intentionally volatile |
| OD totals reconcile with census source | Pending | Census loader not yet built |
| Network opens cleanly in netedit; bridges/gateways present | Partial | Cordon-trimmed; reads cleanly via sumolib with bridge gateway stubs present; fine netedit pass (connectivity/lanes/gateway tagging) pending |
| Zone polygons render with land-use classes | Partial | Data ready: 366 zones with land_use in DB + zones.geojson; visual render is Phase 3 |

---

## Phase 2: End-to-end vertical slice (Not Started)

### Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Build scenario with placeholder demand (randomTrips/toy gateway OD) | Not Started | Realistic demand is Phase 4 |
| 2 | Run one day via libsumo; emit sampled geo Parquet FCD | Not Started | |
| 3 | Post-process FCD → trajectory Parquet (path + timestamps + type) | Not Started | |
| 4 | FastAPI: stream trace as Arrow; serve network/zones as GeoJSON | Not Started | |
| 5 | Minimal deck.gl + MapLibre viewer with day-scrubber | Not Started | Deliberately unpolished |

### Verification

| Check | Status | Notes |
|-------|--------|-------|
| Browser shows zones + roads + moving vehicles from a real SUMO run | Pending | **Key gate** |
| Day-scrubber moves time forward/back | Pending | |

---

## Phase 3: Visualization (Not Started)

### Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | PMTiles basemap (clipped BC) + clean MapLibre style | Not Started | OpenFreeMap for dev |
| 2 | Land-use-shaded zones; styled roads/bridges/transit | Not Started | |
| 3 | Vehicle IconLayer distinct by type; optional TripsLayer trails | Not Started | car/carpool/bus/delivery/truck/SkyTrain |
| 4 | LOD: flow ribbons @region ↔ icons @street | Not Started | Renders within browser ceiling |
| 5 | Controls: play/pause/speed, time-of-day clock, legend, scenario selector | Not Started | |

### Verification

| Check | Status | Notes |
|-------|--------|-------|
| Vehicle types visually distinct; smooth zoom region→intersection | Pending | |
| LOD transition holds 60fps | Pending | |

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
| 2026-05-31 | 1 | **Transit loader (Task 3).** `etl transit`: TransLink GTFS static → SUMO pt via gtfs2pt.py (bus, cordon bbox, `--repair`) → 254 stops + 140 routes + 4,062 bus departures (data/sumo/peninsula_pt_*.xml). SkyTrain/rail/SeaBus deferred (no rail/water edges in the road net). Added `rtree` dep (gtfs2pt requirement). |
| 2026-05-31 | 1 | **Signals + events loaders (Task 6).** `etl signals`: CoV signal locations clipped to the cordon (254) and matched to the nearest SUMO traffic-light junction within 60 m (247/254). `etl events`: 5 canonical bridge-closure scenarios (Lions Gate/Burrard/Granville/Cambie/viaducts), each wired to the nearest drivable net edge, plus live DriveBC Open511 events near the approaches (6). Added `etl/util.py` (shared streaming download). |
| 2026-05-31 | 1 | **Zoning loader (Task 5).** `etl zoning`: CoV zoning + CoV parks (Explore API v2.1) clipped to the cordon and reclassified to {residential, commercial, industrial, parkland, downtown-core}, plus 6 virtual bridge-gateway zones → 366 rows in `zones` + `data/zones/zones.geojson` (252 downtown-core, 58 parkland incl. Stanley Park, 22 industrial, 21 residential, 7 commercial, 6 gateways). Idempotent (delete-by-source + deterministic positional ids). Metro 2050 deferred to the region expansion; pop/emp weights to Phase 4. |
| 2026-05-31 | 1 | **Automated cordon trim.** Added `config.CORDON_POLYGON` + netconvert `--keep-edges.in-geo-boundary` & `--keep-edges.components 1` to `etl network`; trims the raw OSM net at the bridges to the peninsula (15,598 → 7,307 edges; verified geo extent lon[−123.16,−123.08] lat[49.27,49.32], with downtown/Stanley Park in and Kitsilano/North Van out). Added geo/ETL deps (geopandas, pandas, shapely, pyproj, requests). |
| 2026-05-31 | 1 | **Phase 1 started.** Built the ETL backbone: `etl/` package with SQLite schema (`schema.sql`, 12 tables), idempotent CLI (`python -m etl`: init-db/network/zoning/census/transit/signals/events/all/status), open-data source registry, and loader stubs; added `ruff` dev dep (checks pass). Implemented `etl network`: OSM via SUMO `osmGet.py` → `netconvert` → `data/sumo/peninsula.net.xml` (15,598 edges / 6,593 junctions / 473 TLS; UTM-10 geo-projection stored). Provenance + net metadata recorded in `data/traffic.db`. Manual netedit cordon cleanup + zoning/census/transit/signals/events loaders pending. |
| 2026-05-31 | 0 | **Phase 0 complete.** SUMO 1.27 + libsumo verified on Apple Silicon via `uv`; FCD XML + Parquet and `--fcd-output.geo` confirmed; benchmark ~225k vehicle-updates/sec (~34× real-time at 8k active vehicles). Added pyproject.toml, uv.lock, scripts/phase0_spike.py. |
| 2026-05-31 | 0 | Project planning complete; architecture + phased plan agreed. Phase 0 research verified (with corrections: RTDS retired, CoV counts not bulk, Trip Diary dashboard-only). Tracking files and research deliverables populated. |
| 2026-05-31 | -- | Initial development tracker created |
