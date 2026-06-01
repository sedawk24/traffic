# Greater Vancouver Traffic Simulator

A data-grounded, visually rich traffic simulator for Metro Vancouver — real street network, transit, and commute data driving **Eclipse SUMO**, rendered as smooth 2D animation in the browser with zoom from regional overview to individual intersections.

> **Status:** Phase 0 (research + environment setup). Not yet runnable end-to-end — see `CURRENT_STATE.md`.

## What it does (target)

- Imports the real OSM street network (including bridges), TransLink transit, and Statistics Canada commute flows for Metro Vancouver.
- Simulates a full day of traffic in SUMO, with realistic AM/PM peaks, midday traffic, and commercial/industrial deliveries.
- Replays the simulation in a browser: land-use zones, roads and bridges, transit lines, and animated vehicles distinguished by type (car, carpool, bus, delivery van, heavy truck, SkyTrain).
- Lets you inject accidents and road closures and watch the impact ripple through the network (before/after comparison).

## Architecture (batch-then-replay)

```
ETL (Python)  ─►  SUMO run (libsumo + TraCI)  ─►  FastAPI  ─►  Browser (deck.gl + MapLibre)
OSM/GTFS/         one simulated day, sampled        Arrow/        zones · roads · transit ·
census/zoning     geo FCD → Parquet trajectories    GeoJSON       vehicles by type · day-scrubber
   │                                                  PMTiles
   └─► SQLite (network meta, OD, zones, scenarios, calibration)
```

## Quick Start

> Being built during Phase 0–2. The intended flow:

```bash
# Prerequisites: Eclipse SUMO 1.27+ and Python 3.11+ with uv
brew install --cask sumo            # macOS (or build from eclipse-sumo.org)
uv sync                             # install Python dependencies

# Build the test-area scenario (downtown Vancouver peninsula) and run a day
uv run etl all --area downtown-peninsula
uv run sim run --scenario downtown-peninsula-baseline

# Serve and view in the browser
uv run api serve                    # FastAPI on http://localhost:8000
# open the web/ front end (Vite dev server) and load the run
```

Exact commands are finalized as the pipeline lands; see `docs/development/phases/`.

## Documentation

| File | Purpose |
|------|---------|
| `CURRENT_STATE.md` | Current build status and what is next |
| `CLAUDE.md` | Development agent instructions and rules |
| `docs/development/development-tracker.md` | Phase-by-phase development progress |
| `docs/development/backlog.md` | Future features and deferred ideas |
| `docs/development/phases/` | Detailed per-phase implementation plans |
| `docs/architecture/decisions.md` | Architectural decision log |
| `docs/research/` | Phase 0 research: data sources, engine selection, traffic-modeling primer, signal timing |

## Project Structure

```
traffic/
├── etl/        # data loaders: OSM→SUMO net, GTFS→transit, census→OD, zoning→zones
├── sim/        # SUMO runner (libsumo), event injection (TraCI), FCD→trajectory post-processing
├── api/        # FastAPI backend (Arrow/GeoJSON/PMTiles)
├── web/        # MapLibre + deck.gl front end
├── data/       # SQLite DB, Parquet traces, PMTiles, source extracts (git-ignored)
└── docs/       # planning, architecture decisions, research, phase plans
```

## Data sources & licensing

Open data only. OpenStreetMap (ODbL), TransLink GTFS (attribution required), Statistics Canada 2021 Census (Open Licence), Metro Vancouver / City of Vancouver / BC open data (OGL). See `docs/research/data-sources.md` for the verified source-by-source breakdown, formats, and attribution requirements.
