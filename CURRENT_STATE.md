# Current State

**Status: Phase 0 complete. Phase 1 (data pipeline) is next.**

The system architecture and phased build plan are agreed, Phase 0 research is written up, and the SUMO toolchain is verified on this machine (SUMO 1.27 + libsumo on Apple Silicon; FCD XML/Parquet/geo confirmed; ~225k vehicle-updates/sec, ~34× real-time at 8k active vehicles). Project scaffolding (`pyproject.toml`, uv venv) is in place. No application code yet beyond the toolchain spike.

---

## What Is Complete

- **Planning & architecture.** Full plan agreed: SUMO engine (confirmed via research), batch-then-replay, SQLite + Parquet storage, FastAPI backend, deck.gl + MapLibre front end. v1 north star = a polished vertical slice on the **downtown Vancouver peninsula** (cordoned at the bridges); region-wide is a later expansion.
- **Phase 0 research (verified).** Data-source availability/formats/licensing confirmed, with key corrections to the original brief:
  - ❌ TransLink **RTDS** (real-time speeds/travel times) is **retired** — the brief's travel-time calibration source no longer exists.
  - ⚠️ City of Vancouver traffic counts are **locations + links, not a bulk feed**; calibration data is thinner than assumed.
  - ⚠️ TransLink **Trip Diary 2023** is a public dashboard only (no open microdata) — use StatCan "time leaving for work" tables for departure curves.
  - ✅ Solid: OSM→SUMO, TransLink GTFS static, StatCan 2021 commuting OD (98-10-0459 / 98-10-0458), Metro 2050 + Vancouver zoning, CoV signal locations, DriveBC Open511 closures.
- **Toolchain verified (Phase 0 spike).** SUMO 1.27 + `libsumo`/`traci`/`sumolib` installed via `uv` on Apple Silicon (no build issues). SUMO writes FCD as XML **and Parquet** directly, and `--fcd-output.geo` is supported — validating the trace data path. Benchmark on this machine: **~225k vehicle-updates/sec, ~34× real-time at ~8,000 active vehicles** (`scripts/phase0_spike.py`).

## What Is In Progress

Nothing actively in progress — Phase 0 is complete and committed. Ready to begin **Phase 1 (data pipeline)**; see `docs/development/phases/phase-1.md`.

## What Is Next

- **Phase 1 — Data pipeline.** Repeatable ETL: OSM→SUMO network for the peninsula, GTFS→transit, census→OD, zoning→zones, into SQLite + SUMO inputs.
- **Phase 2 — End-to-end vertical slice.** One simulated day with placeholder demand → Parquet trace → FastAPI → minimal deck.gl viewer with a day-scrubber. *Proves every link in the chain.*
- **Phase 3 — Visualization.** Make it beautiful: PMTiles basemap, land-use zones, styled roads/bridges/transit, vehicle icons by type, LOD, smooth zoom.
- **Phase 4 — Demand modeling.** Real census-driven OD, stochastic departures by mode, commercial/delivery/truck traffic.
- **Phase 5 — Scenarios.** Accident/closure injection via TraCI; before/after impact in the UI.
- **Phase 6 — Scale & calibrate.** Best-effort quantitative calibration against obtainable counts; expand outward from the peninsula.

## Key References

| File | Purpose |
|------|---------|
| `docs/development/development-tracker.md` | Detailed phase tracking and change log |
| `docs/development/phases/` | Phase implementation plans |
| `docs/architecture/decisions.md` | Architectural decision log |
| `docs/research/` | Phase 0 research deliverables |

---

*Last updated: 2026-05-31*
