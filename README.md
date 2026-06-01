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

```bash
# Prerequisites: Python 3.11+ with uv (SUMO 1.27 arrives as a wheel via uv sync)
uv sync                                        # install Python + SUMO deps

# 1. Build the data pipeline for the downtown peninsula (OSM net, transit,
#    census OD, zoning, signals, closure scenarios, calibration targets)
uv run python -m etl all                       # or a single step, e.g. `etl network`
uv run python -m etl calibrate                 # seed bridge count targets

# 2. Run a calibrated census-driven AM peak (baseline) and a closure scenario
uv run python -m sim run --demand census --name am_base --scale 0.18 \
      --begin 25200 --end 32400
uv run python -m sim run --demand census --name am_granville --scale 0.18 \
      --begin 25200 --end 32400 --scenario close_granville_bridge

# 3. Check calibration (simulated bridge volumes vs published counts, GEH)
uv run python -m sim calibrate --run am_base   # -> docs/calibration/report.md

# 4. Serve and view in the browser
uv run uvicorn api.main:app                    # http://127.0.0.1:8000
# open http://127.0.0.1:8000/  (add ?run=<id> to load a specific run)
```

All six build phases (0–6) are complete; the calibrated peninsula vertical
slice runs end to end. See `docs/development/` for phase plans and the change log.

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
