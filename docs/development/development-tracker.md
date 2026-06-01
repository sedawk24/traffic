# Development Tracker

Detailed phase-by-phase development progress for the **Greater Vancouver Traffic Simulator**.

---

## Phase Overview

| Phase | Name | Status |
|-------|------|--------|
| 0 | Research writeup + environment spike | In Progress |
| 1 | Data pipeline (ETL → SQLite + SUMO inputs) | Not Started |
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
| 1 | Populate tracking files (CLAUDE.md, CURRENT_STATE.md, this tracker, backlog, README) | In Progress | Per CLAUDE.md initial-setup rule |
| 2 | Log architectural decisions (ADRs) | In Progress | docs/architecture/decisions.md |
| 3 | Write phase plan files (phase-0 … phase-6) | In Progress | docs/development/phases/ |
| 4 | Write research deliverables | In Progress | data-sources, engine-selection, traffic-modeling-primer, signal-timing |
| 5 | Commit documentation before code | Not Started | Hard rule |
| 6 | Install SUMO 1.27 + libsumo/traci on macOS | Not Started | brew/pip; confirm GUI tools |
| 7 | osmWebWizard tiny-area sanity run + geo Parquet FCD | Not Started | Prove the toolchain |
| 8 | Throughput benchmark on target hardware | Not Started | Close the capacity-assumption gap |

### Verification

| Check | Status | Notes |
|-------|--------|-------|
| SUMO runs a tiny peninsula scenario and writes geo Parquet FCD | Pending | |
| `python -c "import libsumo, traci"` succeeds | Pending | |
| Benchmark recorded (vehicles/sec, faster-than-real-time factor) | Pending | |
| Research docs cover data sources, engine choice, modeling primer, signal timing | Pending | |

---

## Phase 1: Data pipeline (Not Started)

### Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | OSM → SUMO `.net.xml` for the peninsula (cordon at bridges) | Not Started | netconvert + manual cleanup |
| 2 | Capture network edits as netdiff | Not Started | Survive OSM re-import |
| 3 | TransLink GTFS static → SUMO pt (bus + rail) | Not Started | gtfs2pt.py |
| 4 | StatCan 98-10-0459 OD + 98-10-0458 departure profiles → SQLite | Not Started | Open Licence |
| 5 | Metro 2050 + Vancouver zoning (+ OSM landuse fallback) → zones | Not Started | TAZ polygons, land-use class, gateway flags |
| 6 | CoV signal locations + DriveBC Open511 ingest | Not Started | Reference + scenario library |
| 7 | SQLite schema + idempotent ETL CLI | Not Started | Re-run → identical DB |

### Verification

| Check | Status | Notes |
|-------|--------|-------|
| ETL re-run produces identical DB (idempotent) | Pending | |
| OD totals reconcile with census source | Pending | |
| Network opens cleanly in netedit; bridges/gateways present | Pending | |
| Zone polygons render with land-use classes | Pending | |

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
| 2026-05-31 | 0 | Project planning complete; architecture + phased plan agreed. Phase 0 research verified (with corrections: RTDS retired, CoV counts not bulk, Trip Diary dashboard-only). Tracking files and research deliverables populated. |
| 2026-05-31 | -- | Initial development tracker created |
