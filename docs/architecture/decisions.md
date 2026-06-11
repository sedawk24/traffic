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

---

## 2026-06-01 — Batch SUMO runs via the `sumo` binary (not libsumo), to isolate Arrow

**Decision:** Run the Phase-2 batch FCD dump with the `sumo` binary in a subprocess rather than the in-process `libsumo` API. Live event injection (Phase 5) still uses libsumo/traci, but FCD post-processing (pyarrow) runs in a process separate from any libsumo run.

**Reasoning:** `libsumo` and `pyarrow` each bundle the Arrow C++ runtime; importing both in one process throws `ArrowKeyError: scheme 'file' already registered`. A non-interactive batch runs at the same speed via the binary (no per-step Python control is needed), so the binary cleanly sidesteps the clash. The earlier "libsumo for batch speed" decision was about avoiding per-step TraCI overhead during *interactive* control; a pure dump has none.

**Alternatives considered:**
- libsumo for the run + post-process in a child process: keeps the API literal but adds subprocess plumbing and inter-process stat passing; deferred unless in-process control is needed.
- Import-order juggling of pyarrow vs libsumo: fragile and unreliable.

---

## 2026-06-11 — Signal ground truth: CoV inventory decides which junctions are signalized

**Decision:** Treat the City of Vancouver's signal-location dataset (with its `type` — Fixed Time / Semi Actuated / Fully Actuated vs Pedestrian Actuated / RRFB / Special Crosswalk) as ground truth for the TLS set of every Vancouver-area net. `etl signal-truth --area <a>` reconciles the built net against it: net TLS with no CoV device nearby or a ped-only device become priority junctions (with no pedestrians simulated, a ped-actuated signal rests green for cars); CoV vehicle signals missing a TLS get one. Implementation is a plain-XML round-trip (export plain → rewrite junction `type` attrs → rebuild) because netconvert's `--tls.unset` cannot strip TLS already baked into a net; the round-trip keeps edge ids stable so demand/transit artifacts survive.

**Reasoning:** netconvert (OSM tags + `--tls.guess-signals` + joins) signalized 700 junction nodes in the central net vs ~298 real vehicle signals — every bogus signal periodically stops traffic for nobody, and Phase 8c proved the capacity ceiling is intersection-bound. Ground-truthing is data-grounded (open CoV data, consistent with the project ethos) and measured +6% mean speed at scale 0.075 over the gateway-fixed baseline.

**Alternatives considered:**
- `--tls.unset` on a net-to-net pass: confirmed ineffective (TLS already instantiated).
- Trusting OSM signal tags: they are the over-population source (crossing signals tagged as `highway=traffic_signals`).

---

## 2026-06-11 — External demand enters on severed-arterial gateway stubs, capacity/d² weighted

**Decision:** In single-city demand (`sim/demand_metro.py`), external CSDs draw origins/destinations from the net's severed arterials — edges the bbox cut left with no incoming (entries) or no outgoing (exits) — weighted by lanes / distance²-to-centroid. The home city's trip-end pool excludes motorway/trunk/primary mid-blocks.

**Reasoning:** The previous "K=80 nearest edges" pooling funneled every eastern municipality's demand into Chinatown side streets; `sim diagnose` showed the resulting standing queue along Main/Hastings/Powell/Gore held a third of all stopped time. Stubs are the topologically true gateways (Kingsway/Hastings/Broadway/Terminal east, the bridge approaches south, the Causeway north), and capacity-weighting spreads load like reality does. Measured: at scale 0.075, mean speed 12.5 → 22.4 km/h, completed trips +74 %.

**Alternatives considered:**
- Geometric boundary band: caught bbox-extreme edges (Stanley Park Drive), not the real cuts.
- Larger K with uniform weights: still corner-clustered, still side-street entries.

---

## 2026-06-11 — Viewer: runtime dark-restyle of the hosted positron basemap

**Decision:** The dark-cinematic basemap is produced at runtime: try openfreemap's hosted `dark` style; otherwise fetch the positron style JSON and recolor its layers to the app palette in the browser (water/parks/roads/labels reclassified by layer id; POI/shield layers dropped). No tile re-hosting. 3D buildings come from the same vector source's `building` layer as a fill-extrusion added at z≥14.5.

**Reasoning:** A bespoke hosted style or PMTiles pipeline is real infrastructure (backlogged since Phase 3); restyling the already-hosted vector tiles costs one fetch and keeps the offline-PMTiles option open. The recolor is defensive (per-layer try, stock-positron fallback).

**Alternatives considered:**
- Self-hosted PMTiles + custom style: still the eventual offline answer (backlog).
- maplibre dark styles from other providers: new dependency/keys.

---

## 2026-06-11 — Measurement-gated tuning: `sim sweep` is the arbiter; no infinite HUD animations

**Decision:** Every capacity-affecting change lands only if a fixed-seed `sim sweep` (scale ladder; FCD-weighted mean speed, %stopped, teleports, completions) clears the gate (at 0.075: mean +≥5 % or stopped −≥3 pts, teleports not worse). Two implementation rules from profiling the new viewer: deck.gl layer `data` must be referentially stable across frames (a per-frame `concat` re-uploaded ~600k trail vertices every frame), and the HUD uses no infinite CSS animations (an animated `box-shadow`/opacity on one 9-px dot forced full-page recomposites of both WebGL canvases — seconds per frame under software rendering).

**Reasoning:** Phase 8c showed intuition failing ("0 teleports" runs that were actually gridlocked); the sweep keeps Phase 9 honest. The two viewer rules came from CPU-profiling real hangs to (program)/compositor time, not JS.
