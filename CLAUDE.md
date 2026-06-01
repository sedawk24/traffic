# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

A traffic simulator for Metro Vancouver (the Greater Vancouver Regional District) that is two things at once: **data-grounded** — driven by real public data on the street network, transit, commute patterns, and traffic volumes — and **visually excellent** — a 2D browser renderer with smooth zoom from regional overview down to individual intersections (SimCity-like, grounded in real geography). It drives **Eclipse SUMO** as the simulation engine and renders SUMO's per-vehicle floating-car-data traces in the browser (**batch-then-replay**), reproducing realistic daily rhythms (AM/PM peaks, midday, commercial/industrial delivery) and supporting injected accidents and road closures whose impact ripples through the network.

## Tech Stack

- **Simulation engine:** Eclipse SUMO 1.27 (microscopic; mesoscopic `--mesosim` for scale), driven via `libsumo` (in-process, for batch speed) and `traci`/`libtraci` (live event injection, GUI/debug). EPL-2.0.
- **ETL / data:** Python 3.11+, `pandas`, `geopandas`, `osmnx`/`pyrosm`, plus SUMO tools (`netconvert`, `gtfs2pt.py`, `randomTrips.py`, `od2trips`, `duarouter`, `tlsCoordinator.py`, `tlsCycleAdaptation.py`).
- **Storage:** SQLite (network metadata, OD matrices, zones, departure profiles, scenarios + events, run registry, calibration targets/results) + Parquet (heavy per-timestep traces; SUMO emits geo FCD directly as Parquet).
- **Backend:** FastAPI — serves traces as Apache Arrow / GeoArrow (chunked by time window), network/zones/transit as GeoJSON, basemap as static PMTiles.
- **Front end:** MapLibre GL JS 5 + deck.gl 9 (`PolygonLayer` zones, `PathLayer` roads/bridges/transit, `IconLayer` + `TripsLayer` vehicles by type). Basemap: OpenFreeMap (dev) → self-hosted Protomaps PMTiles, BC extract (offline). **Not PixiJS.**
- **Environment:** macOS; Python deps managed with `uv`; `ruff` for lint/format.

## Architecture

Four stages, decoupled by files (**batch-then-replay** — heavy compute offline, lightweight replay in the browser):

1. **ETL pipeline** (`etl/`) ingests OSM → SUMO network, TransLink GTFS → transit, StatCan census → OD matrices, and Metro Vancouver/Vancouver zoning → land-use zones, into **SQLite + SUMO input files**.
2. **Simulation runner** (`sim/`) executes a scenario in SUMO via `libsumo`, injects accidents/closures mid-run via TraCI, and emits **sampled geo FCD as Parquet**, post-processed into per-vehicle trajectories.
3. **FastAPI backend** (`api/`) serves trajectories (Arrow), network/zones/transit (GeoJSON), and basemap (PMTiles); launches and controls runs.
4. **Browser front end** (`web/`) replays the trace with deck.gl over MapLibre, with **level-of-detail** (aggregated flow ribbons at regional zoom, individual vehicle icons at street zoom) and **day-scrubbing**.

The **single hard constraint** is that SUMO's microscopic core is effectively single-core (~200k-vehicle ceiling), so the region runs mesoscopic while the focus area runs microscopic; demand is sub-sampled and FCD output is sampled. See `docs/architecture/decisions.md` for the reasoning behind each choice.

## Key Documentation

| File | Purpose |
|------|---------|
| `CURRENT_STATE.md` | Current build status -- read this at the start of every session |
| `docs/development/development-tracker.md` | Phase-by-phase development tracking with change log |
| `docs/development/backlog.md` | Future features, ideas, and deferred work |
| `docs/development/phases/` | Detailed implementation plans for each phase |
| `docs/architecture/decisions.md` | Architectural decision log with reasoning |

## Development Rules

### Initial Project Setup

When this is a new project and a development plan has been created, the FIRST implementation step -- before writing any code -- is to populate the tracking files:

1. Fill in the `{placeholder}` sections of this file (`CLAUDE.md`) with the project overview, tech stack, architecture, and conventions
2. Populate `CURRENT_STATE.md` with the phase overview and first phase details
3. Populate `docs/development/development-tracker.md` with all phases, tasks, and the phase overview table
4. Create phase plan files in `docs/development/phases/` for at least the first phase
5. Log any initial architectural decisions in `docs/architecture/decisions.md`
6. Update `README.md` with the project name, description, and quick start instructions
7. Commit these tracking files before beginning any development work

### HARD RULE: Update Tracking Before Every Commit

**Before staging and committing, you MUST review and update the following files:**

1. **`CURRENT_STATE.md`** -- must reflect the current state of the project
2. **`docs/development/development-tracker.md`** -- must mark completed work, update task statuses, and add a change log entry
3. **`docs/development/backlog.md`** -- if new ideas or future work surfaced during the session, add them here

**This is not a suggestion. This is a required step. Do not stage or commit without updating tracking files first. If tracking files do not reflect the current state of the work, update them before proceeding with the commit.**

### Session Start

1. Read `CURRENT_STATE.md` to understand where the project stands
2. Read the relevant section of `docs/development/development-tracker.md` for detail on the current phase
3. If starting a new phase, check `docs/development/phases/` for a detailed implementation plan

### Session End

1. Update tracking files (see hard rule above)
2. Commit all changes
3. Push to remote

### General Conventions

- Feature branches for new work; merge to main when stable
- Update spec documents in `docs/` if architectural decisions change
- Log all significant architectural decisions in `docs/architecture/decisions.md`

## Project Conventions

- **Repo layout:** `etl/` (data loaders), `sim/` (SUMO runner + event injection + FCD post-processing), `api/` (FastAPI), `web/` (MapLibre + deck.gl front end), `data/` (SQLite DB, Parquet traces, PMTiles, OSM/GTFS extracts — **git-ignored**), `docs/`.
- **Python:** 3.11+, managed with `uv`; `ruff` for lint + format; type hints throughout; ETL steps are small composable CLI entry points.
- **ETL is idempotent and repeatable:** re-running a loader produces the same DB state; each loader records its source and extract date for provenance.
- **No large binaries in git:** the SQLite DB, Parquet traces, PMTiles, and OSM/GTFS/census extracts live under `data/` and are git-ignored.
- **Open data only:** preserve required attribution (TransLink, Statistics Canada Open Licence, OGL-Vancouver / OGL-Metro-Vancouver / OGL-BC, OpenStreetMap ODbL).
- **SUMO network edits** are captured as `netdiff` patches so manual cleanup survives an OSM re-import.
- **Geography in WGS84 (EPSG:4326)** at rest for the renderer (FCD via `--fcd-output.geo`); project only when an analysis step requires it.
- **Phase discipline:** vertical slice first; keep tracking files current (see hard rule above); commit per phase.
