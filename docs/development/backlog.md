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
- **Adaptive/coordinated signals via TraCI** beyond actuated defaults (e.g., live green-wave control).
- **Demand calibration loop** using `routeSampler.py` against edge/turn counts.
- **Verified calibration counts.** Replace the estimated Cambie/Burrard bridge AADT (and confirm Granville/viaduct) with verified **BC MoTI TRADAS** per-site exports and **CoV permanent-station** counts (currently VanMap-gated) — see `docs/calibration/report.md`. Then extend screenlines beyond the bridges and add corridor **travel-time** checks (needs a non-RTDS speed source).
- **Demand refinement (Phase 4 follow-ups).** duaIterate (dynamic user equilibrium) over the one-shot duarouter; tune signal cycles/offsets (tlsCycleAdaptation/tlsCoordinator) against realized demand; replace the land-use emp/pop heuristics with actual census employment/population per zone; HOV-lane modelling; calibrate the peninsula job/pop shares.
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
