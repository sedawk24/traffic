# Current State

**Status: Phase 1 (data pipeline) in progress — ETL backbone + automated OSM→SUMO network build are done.**

The system architecture and phased build plan are agreed, Phase 0 research is written up, and the SUMO toolchain is verified on this machine (SUMO 1.27 + libsumo on Apple Silicon; FCD XML/Parquet/geo confirmed; ~225k vehicle-updates/sec, ~34× real-time at 8k active vehicles). Project scaffolding (`pyproject.toml`, uv venv) is in place. Phase 1 has begun: the `etl/` package (SQLite schema + idempotent CLI) is built and the automated OSM→SUMO step has produced the cordon-trimmed peninsula network (7,307 edges / 3,201 junctions / 266 signals; UTM-10 geo-projection stored).

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

**Phase 1 — Data pipeline.** Done so far:
- **ETL backbone.** `etl/` package: SQLite schema (`etl/schema.sql`, 12 tables), idempotent CLI (`uv run python -m etl <step>` — `init-db`, `network`, `zoning`, `census`, `transit`, `signals`, `events`, `all`, `status`), open-data source registry for provenance, and per-loader stubs. `ruff` added as the dev linter (checks pass).
- **Network (Task 1, automated).** `etl network`: OSM via SUMO `osmGet.py` (Overpass, raw XML cached) → `netconvert` → `data/sumo/peninsula.net.xml`, with an **automated bridge-cordon trim** (`--keep-edges.in-geo-boundary` over `config.CORDON_POLYGON` + largest-component) cutting the raw net to the peninsula: **7,307 edges / 3,201 junctions / 266 TLS** (down from 15,598 pre-trim); UTM-10 geo-projection stored so `--fcd-output.geo` works. Verified geo extent lon[−123.158, −123.078] lat[49.266, 49.324]; downtown/Gastown/Stanley Park in, Kitsilano/North Van out. Provenance + metadata in `data/traffic.db`.

Remaining in Phase 1: fine `netedit` cleanup (bridge connectivity, lane counts, gateway tagging) + `netdiff` capture (Tasks 1–2), then the zoning, census, transit, signals, and DriveBC loaders (Tasks 3–6). See `docs/development/phases/phase-1.md`.

## What Is Next

- **Phase 1 (finish) — Data pipeline.** Manual `netedit` cordon cleanup + `netdiff`; then zoning→zones, census→OD/departures, GTFS→transit, CoV signals, DriveBC closures — each an idempotent `etl` step into SQLite + SUMO inputs.
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
