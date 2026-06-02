# Backlog

Future features, ideas, and deferred work that surface during development. Items here are not scheduled for any specific phase. When an item is promoted to a phase, move it to the development tracker and note the date.

---

## Features

- **Live simulation over WebSockets.** Drive SUMO live via TraCI and stream FCD to the browser in real time (v1 is batch-then-replay).
- **Live data feeds.** TransLink GTFS-Realtime v3 (vehicle positions, alerts) and DriveBC Open511 as *live* inputs, not just scenario seeds. Requires the free TransLink API key.
- **Region-wide coverage.** *(Phase 7 — started 2026-06-01: a mesoscopic core-Metro network + census run replays as regional flow ribbons.)* Remaining: full GVRD extent (Langley/Maple Ridge/Pitt Meadows east, White Rock/Tsawwassen south); **LOD hand-off** between the meso region and the micro peninsula focus area (run both, switch by zoom); metro **calibration** against regional screenlines; **regional transit** (GTFS over the metro net) and **finer demand** (sub-municipal TAZ rather than municipality centroids).
- **Multiple day-types.** Weekend and seasonal profiles in addition to a representative weekday.
- **Multi-day / week simulation.** Chain days; carry over patterns.
- **Weather / event scenarios.** Rain slowdowns, special events (stadium egress), construction seasons.
- **Richer scenario authoring.** UI to place accidents/closures by clicking the map; schedule timed events. Add the remaining injection primitives (stop-a-vehicle "accident", link speed-drop) alongside the edge closure; pick a scenario from the viewer (currently a CLI flag).
- ~~**Windowed/streaming trace replay (unlocks real density).**~~ **DONE (2026-06-02):** `/api/trips` takes `start`/`end` (predicate-pushed at the parquet level); the viewer streams a 300 s window (`every=3`) for dense runs (>8k veh) and reloads as the clock advances. A 34k-vehicle run that produced a 685 MB trips payload (browser couldn't load it) now streams ~12 MB windows. *Follow-ups:* sort the trajectory parquet by `t` so window reads are <1 s (currently ~2-4 s on the unsorted file); prefetch the next window during playback to avoid a brief stall at window edges.
- **Per-bridge demand balance (central).** Calibration matched Granville/Cambie to real but Burrard was under (routing under-feeds it + its screenline found only 8 edges). Add per-crossing demand weights (like the metro gateway weights) and verify all three to GEH<5.
- **City buses that interact with traffic.** The full-city (`vancouver`) net uses a GTFS-**schedule** bus layer (buses animate on their timetable but don't physically queue in car traffic) because gtfs2pt's per-trip routing is intractable on 76k edges. To get traffic-interacting buses on the big net: pre-build a bus-only sub-network for gtfs2pt, or map routes once and reuse, or run buses as regular SUMO vehicles from the schedule polylines.
- **City demand realism / density.** The city run spreads intra-Vancouver demand *uniformly* across all streets — replace with census-tract/DA-level origins for neighbourhood accuracy. Micro density is compute-bound (single-core); full real density over all 76k edges needs sub-sampling or a faster engine. LOD hand-off (auto-switch `vancouver` micro ↔ `metro` meso by zoom) is the scaling answer.
- **Transit handling during closures.** Buses whose stops sit *on* a closed structure (e.g. a stop on the Granville Bridge deck) can't reach them after the closure ("could not assign stop after rerouting"). A closure should also detour/short-turn affected transit routes rather than letting those bus trips fail.
- **Transit ridership modeling.** Board/alight loads and crowding, not just vehicles running to schedule.
- **Stylized "SimCity" sprite skin.** Optional game-like art layer (would evaluate PixiJS or custom deck.gl icons) on top of the clean cartographic base.
- **Scenario library & sharing.** Save, name, and compare many scenarios; export before/after reports.

## Improvements

- **MATSim integration** for activity-based, full-day regional demand (complement to SUMO, per engine-selection research).
- **GPU engine escape hatch (MOSS)** if microscopic scale becomes the binding constraint (>2M vehicles).
- **Better basemap styling** — bespoke MapLibre style tuned to the app's palette.
- **Self-hosted PMTiles basemap (offline / no-cloud).** Generate a Protomaps PMTiles BC extract (needs tilemaker/planetiler or the `pmtiles` CLI — none installed) + a Protomaps MapLibre style, served via range requests. OpenFreeMap positron is the dev basemap until then (Phase 3 Task 1, deferred).
- **Viewer refinements.** Color-by-type ⇄ congestion toggle is in. Remaining: truck/SkyTrain icons once demand includes those modes; window-on-demand trace loading as the scrubber moves (vs full upfront); glyph-icon polish.
- **Raising the flowing ceiling (a major project, not a tweak).** Measured ceiling: `central` flows realistically (arterials moving, residential quiet) only up to **~scale 0.05** (peak ~2,400 on-road); above that the dense signalized grid oversaturates (density sweep: 0.04→22 km/h, 0.06→17/11, 0.075→11, 0.10→6 km/h with 84 % stopped). Diagnosed to the **intersection/signal throughput**, and the easy levers are exhausted: it is **not lanes** (busiest arterials are 3-lane at ~11 % volume), **not green-split timing** (`tlsCycleAdaptation` Webster re-timing moved it 0), **not spillback nudging** (`--ignore-junction-blocker` moved it 0); only green-wave **coordination** (`tlsCoordinator`) helped, ~15 %. Going meaningfully busier needs a fundamentally better model — a hand-corrected network (lane/turn/junction geometry + real signal programs) and/or sub-area demand calibration — a substantial effort, not a parameter.
- **Road-hierarchy realism in the net.** The auto-net models residential streets at ~44 km/h (≈ arterials) with no stop signs, so routers treat side streets as arterial-equivalent shortcuts (fixed for now via routing penalties — `--weights.minor-penalty`/`priority-factor`). The structural fix: a custom netconvert typemap that sets realistic residential/service speeds (~30/20 km/h) and adds stop-sign control at minor junctions, so the hierarchy is physical, not just a routing weight.
- **Adaptive/coordinated signals via TraCI** beyond actuated defaults (e.g., live green-wave control).
- **Demand calibration loop** using `routeSampler.py` against edge/turn counts.
- **Verified calibration counts.** Replace the estimated Cambie/Burrard bridge AADT (and confirm Granville/viaduct) with verified **BC MoTI TRADAS** per-site exports and **CoV permanent-station** counts (currently VanMap-gated) — see `docs/calibration/report.md`. Then extend screenlines beyond the bridges and add corridor **travel-time** checks (needs a non-RTDS speed source).
- **Demand refinement (Phase 4 follow-ups).** ~~duaIterate (dynamic user equilibrium) over the one-shot duarouter~~ **DONE (2026-06-02)** for the `central` district (run #27 — busy *and* flowing; `sim run --routes-file <equil> --reroute-prob 0`); whole-city duaIterate + the capacity ceiling below remain. Still: replace the land-use emp/pop heuristics with actual census employment/population per zone; HOV-lane modelling; calibrate the peninsula job/pop shares.
- **Whole-city route equilibrium.** Run `duaIterate` on the full `vancouver` 76k-edge net (the central run proved it on 23.6k edges; whole-city is a multi-hour iterate job — script it as a detached run with the same pre-filter-to-routable + inline-vTypes setup under `data/runs/`).
- **Trace compression / streaming** refinements (GeoArrow chunking, delta encoding) for larger areas.
- **Zoning refinement.** Beyond the peninsula, disambiguate CD (Comprehensive Development) — it blanket-maps to downtown-core now; aggregate per-parcel zoning into traffic-analysis zones (TAZ) for OD; map each gateway zone to its SUMO bridge edge(s) for demand injection; add the Metro 2050 base + OSM `landuse` fallback for region-wide land use.

## Technical Debt

- **Reproducible OSM acquisition.** Phase 1 fetches OSM live via SUMO `osmGet.py` (Overpass). For byte-stable re-imports, optionally pin a dated Geofabrik BC extract and clip with a keep-polygon instead.
- **SpatiaLite option.** Geometry is stored as GeoJSON text and spatial ops run in geopandas; revisit SpatiaLite if zone/edge spatial joins need to move into SQL.
- **OSM network maintenance.** Re-import workflow and netdiff hygiene as OSM data drifts.
- **Test coverage** for ETL idempotency and trajectory post-processing.
- **Packaging.** A one-command installer / Docker option if we ever want it to run beyond the dev repo.

## Research

- **Commercial probe data** (HERE/TomTom) or a **custom StatCan tabulation** (tract/DA-level OD) to strengthen calibration beyond open-data limits.
- **City of Vancouver permanent count station** scraping feasibility (hourly-by-lane volumes are behind links, not a bulk feed).
- **BC MoTI per-site count extraction** at scale (interactive tool, no bulk API).
- **ICBC collision data** for realistic accident placement (annual, aggregated).
- **SkyTrain fidelity** — whether full rail-signal modeling adds value or stays visual context.
- **HOV/carpool occupancy modeling** — how to represent eligibility and lane permissions credibly.
