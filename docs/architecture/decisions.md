# Architectural Decisions

A running log of significant architectural decisions made during this project. Each entry records what was decided, why, and what alternatives were considered. This file exists so that future sessions understand the reasoning behind the current structure and do not relitigate settled decisions.

---

## 2026-05-31 — Use Eclipse SUMO as the simulation engine

**Decision:** Build on Eclipse SUMO 1.27 (microscopic, with mesoscopic mode), driven from Python via `libsumo` (in-process, batch) and `traci`/`libtraci` (live event injection, GUI/debug). We do not build a traffic engine from scratch.

**Reasoning:** SUMO is the only mature open-source engine that simultaneously offers microscopic fidelity, first-class Python control, native OSM import, real GTFS transit (including rail), and geo-referenced floating-car-data output that feeds a browser replay with no extra projection work. Actively maintained (~quarterly), EPL-2.0. Verified in Phase 0 research.

**Alternatives considered:**
- MATSim: activity-based and good for full-region day-scale demand, but mesoscopic and Java-centric — kept as a future complement, not the v1 micro engine.
- Aimsun / PTV Vissim: high fidelity but commercial, closed, costly, Windows/COM-leaning — wrong fit for a local OSS app.
- CityFlow / CBLab / MOSS: RL/GPU-oriented; weak network import and transit. MOSS (GPU, >2M vehicles) noted as a future escape hatch if micro scale becomes binding.
- Flow (Berkeley): abandoned since 2019.

---

## 2026-05-31 — Batch-then-replay execution model

**Decision:** Run each scenario as an offline batch job that writes a per-timestep trace; the browser replays and renders that trace with day-scrubbing. Live websocket-driven simulation is deferred to the backlog.

**Reasoning:** Decouples heavy compute from rendering, lets us scrub through a simulated day, and sidesteps SUMO's single-core real-time ceiling. It is the lowest-risk path to a smooth, watchable result. The brief proposed this and research confirmed it as the right instinct.

**Alternatives considered:**
- Live SUMO over websockets: more interactive but couples render to a single-core sim and complicates the data path — deferred.

---

## 2026-05-31 — Design around SUMO's single-core microscopic ceiling

**Decision:** Treat the microscopic core as effectively single-threaded (~200k-vehicle ceiling; SUMO's own threading is often slower). Run the wider region mesoscopic (`--mesosim`, same inputs) while the focus area runs microscopic; sub-sample demand; sample FCD output; tile if needed.

**Reasoning:** A region-wide full-day microscopic run is not a single-machine real-time job. Building the two-tier resolution and output discipline in from the start avoids a later rewrite (it's a runtime flag, not new code).

**Alternatives considered:**
- All-micro region-wide: not tractable on one machine in reasonable wall-clock.
- Multi-threaded SUMO: frequently slower due to synchronization overhead.

---

## 2026-05-31 — Storage: SQLite for structured data + Parquet for traces

**Decision:** SQLite holds structured, queryable data (network metadata, OD matrices, zones, departure profiles, scenarios + events, run registry, calibration targets/results). Heavy per-timestep traces live in Parquet files referenced by path (SUMO emits geo FCD directly as Parquet). All under `data/`, git-ignored.

**Reasoning:** Matches the brief's "SQLite unless a strong case otherwise" with the brief's own Parquet intuition. Raw 1 Hz FCD is far too large and write-heavy for SQLite; Parquet is columnar, compact, and reads fast into the serving layer.

**Alternatives considered:**
- Everything in SQLite: trace volume makes this impractical.
- Postgres/PostGIS: heavier than needed for a local single-user app.

---

## 2026-05-31 — Renderer: deck.gl over MapLibre GL (not PixiJS)

**Decision:** Render with deck.gl 9 layered over a MapLibre GL JS 5 basemap. `PolygonLayer` for zones, `PathLayer` for roads/bridges/transit, `IconLayer` + `TripsLayer` for vehicles by type. Visual direction is **clean cartographic + iconography**.

**Reasoning:** deck.gl handles geographic projection, camera/zoom sync, GPU trajectory interpolation, and time-scrubbing (`currentTime`) out of the box. PixiJS would require reimplementing projection and map-camera sync every frame and is only worth it for a fully bespoke sprite aesthetic, which is not a v1 requirement.

**Alternatives considered:**
- PixiJS: more stylized sprite look but heavy plumbing for geo/zoom — deferred to backlog as an optional skin.

---

## 2026-05-31 — Level-of-detail rendering is mandatory

**Decision:** Render aggregated flow ribbons / edge-density coloring at regional zoom and switch to individual vehicle icons at street zoom; cap rendered vehicles by viewport.

**Reasoning:** The browser comfortably animates ~5–20k vehicles at 60fps via the binary data path; a region-day trace far exceeds that. LOD is the only way to reconcile "regional overview" with "individual intersections" within the GPU budget.

**Alternatives considered:**
- Draw every vehicle always: blows the frame budget at regional scale.

---

## 2026-05-31 — Wire format Arrow/GeoArrow; basemap PMTiles (no mandatory cloud)

**Decision:** Serve traces from FastAPI as Apache Arrow / GeoArrow chunked by time window; Parquet at rest. Basemap via OpenFreeMap during development, self-hosted Protomaps PMTiles (clipped BC extract) for offline / no-cloud-dependency.

**Reasoning:** Arrow/GeoArrow is binary and columnar and copies straight to the GPU (no JS object churn); ~16–20 bytes per vehicle-step. PMTiles is a single range-requested file, fully local-capable, satisfying the "no mandatory cloud" constraint.

**Alternatives considered:**
- JSON trace transport: simple but 10–100× larger; fine only for a prototype.
- Cloud tile provider: violates the no-mandatory-cloud constraint.

---

## 2026-05-31 — v1 scope: polished vertical slice on the downtown peninsula (cordoned)

**Decision:** v1 targets a polished, fully-working slice on the **downtown Vancouver peninsula**, cordoned at its bridges/viaducts (external traffic modeled as gateway flows). Region-wide coverage is a later expansion. Phase 2 is a true end-to-end tracer bullet (including a minimal renderer) before any part is polished.

**Reasoning:** The water boundary is a natural cordon, sidestepping the hardest demand problem (open boundaries) while still exercising dense signals, transit, bridges, and the canonical AM-in/PM-out rhythm. Proving the whole chain first retires integration risk early. Decided with the user.

**Alternatives considered:**
- Broadway corridor: good for signal coordination but open boundaries and linear.
- Suburban slice: simpler grid but less iconic, weaker data.
- Region-wide first: too much integration + scale risk before the chain is proven.

---

## 2026-05-31 — Signal timing: actuated defaults + coordination, then calibrate

**Decision:** Generate actuated signals everywhere via `netconvert` (`--tls.default-type actuated`), apply `tlsCycleAdaptation.py` (splits from demand) and `tlsCoordinator.py` (offsets → arterial green waves) on main corridors, and treat cycle/offset as calibration knobs against observed travel times/counts. Webster's method is the fixed-time fallback.

**Reasoning:** The City does not publish signal timing plans (it sells timing reports). This approach needs zero proprietary data and produces realistic, volume-responsive behavior we can calibrate.

**Alternatives considered:**
- Fixed-time only: less realistic at varying demand.
- Acquiring real timing plans: not openly available.

---

## 2026-05-31 — Demand: census CSD OD disaggregated, stochastic departures, synthesized non-work/commercial

**Decision:** Build the OD from StatCan 2021 commuting flows at census-subdivision level (98-10-0459), disaggregated to zones by land use/population/employment; shape departures by mode from per-municipality "time leaving for work" histograms (98-10-0458) with stochasticity; synthesize non-work, commercial/delivery, and heavy-truck demand from land-use heuristics anchored to TransLink Trip Diary published aggregates.

**Reasoning:** This is the best open, reproducible demand foundation. Census journey-to-work covers commute trips only and is municipality-level and random-rounded, so disaggregation + synthesis + stochastic departures are required to get believable daily rhythms.

**Alternatives considered:**
- Trip Diary microdata: not openly available (dashboard only).
- Tract-level census OD: not published (destination-only at tract); would need a paid custom tabulation.

---

## 2026-05-31 — Calibration: best-effort quantitative, honest about gaps

**Decision:** Calibrate to whatever open data we can assemble (BC MoTI highway/bridge counts, scraped City of Vancouver permanent stations, census mode share, Trip Diary aggregates), targeting GEH < 5 on the obtainable subset plus corridor travel-time sanity checks, and document coverage gaps explicitly. Buying commercial probe data or a custom tabulation is a backlog option.

**Reasoning:** Phase 0 research corrected the brief: TransLink **RTDS** (real-time speeds/travel times) is **retired**, and City of Vancouver counts are **locations + links, not a bulk feed**. The richest calibration sources assumed in the brief don't exist as expected, so rigorous per-link calibration is data-limited. Best-effort quantitative is the credible target; honesty about coverage is part of the deliverable.

**Alternatives considered:**
- Plausibility-only: weaker credibility ("toy vs model").
- Invest in commercial data now: deferred unless open data proves insufficient.
