# Backlog

Future features, ideas, and deferred work that surface during development. Items here are not scheduled for any specific phase. When an item is promoted to a phase, move it to the development tracker and note the date.

---

## Features

- **Live simulation over WebSockets.** Drive SUMO live via TraCI and stream FCD to the browser in real time (v1 is batch-then-replay).
- **Live data feeds.** TransLink GTFS-Realtime v3 (vehicle positions, alerts) and DriveBC Open511 as *live* inputs, not just scenario seeds. Requires the free TransLink API key.
- **Region-wide coverage.** Expand from the downtown peninsula to full Metro Vancouver — mesoscopic for the region with microscopic focus areas, LOD switching between them.
- **Multiple day-types.** Weekend and seasonal profiles in addition to a representative weekday.
- **Multi-day / week simulation.** Chain days; carry over patterns.
- **Weather / event scenarios.** Rain slowdowns, special events (stadium egress), construction seasons.
- **Richer scenario authoring.** UI to place accidents/closures by clicking the map; schedule timed events.
- **Transit ridership modeling.** Board/alight loads and crowding, not just vehicles running to schedule.
- **Stylized "SimCity" sprite skin.** Optional game-like art layer (would evaluate PixiJS or custom deck.gl icons) on top of the clean cartographic base.
- **Scenario library & sharing.** Save, name, and compare many scenarios; export before/after reports.

## Improvements

- **MATSim integration** for activity-based, full-day regional demand (complement to SUMO, per engine-selection research).
- **GPU engine escape hatch (MOSS)** if microscopic scale becomes the binding constraint (>2M vehicles).
- **Better basemap styling** — bespoke MapLibre style tuned to the app's palette.
- **Adaptive/coordinated signals via TraCI** beyond actuated defaults (e.g., live green-wave control).
- **Demand calibration loop** using `routeSampler.py` against edge/turn counts.
- **Trace compression / streaming** refinements (GeoArrow chunking, delta encoding) for larger areas.

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
