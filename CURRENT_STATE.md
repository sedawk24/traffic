# Current State

**Status: Phase 0 — Research & environment setup (in progress).**

The system architecture and phased build plan are agreed. Phase 0 deep research is complete and being written up; the SUMO/Python toolchain spike is next. No application code yet.

---

## What Is Complete

- **Planning & architecture.** Full plan agreed: SUMO engine (confirmed via research), batch-then-replay, SQLite + Parquet storage, FastAPI backend, deck.gl + MapLibre front end. v1 north star = a polished vertical slice on the **downtown Vancouver peninsula** (cordoned at the bridges); region-wide is a later expansion.
- **Phase 0 research (verified).** Data-source availability/formats/licensing confirmed, with key corrections to the original brief:
  - ❌ TransLink **RTDS** (real-time speeds/travel times) is **retired** — the brief's travel-time calibration source no longer exists.
  - ⚠️ City of Vancouver traffic counts are **locations + links, not a bulk feed**; calibration data is thinner than assumed.
  - ⚠️ TransLink **Trip Diary 2023** is a public dashboard only (no open microdata) — use StatCan "time leaving for work" tables for departure curves.
  - ✅ Solid: OSM→SUMO, TransLink GTFS static, StatCan 2021 commuting OD (98-10-0459 / 98-10-0458), Metro 2050 + Vancouver zoning, CoV signal locations, DriveBC Open511 closures.

## What Is In Progress

**Phase 0 — Research writeup + environment spike.**
- Writing the research deliverables into `docs/research/` (data sources, engine selection, traffic-modeling primer, signal timing). — *in progress*
- Populating tracking files (this file, CLAUDE.md, development tracker, backlog, decisions, phase plans) and committing them before code. — *in progress*
- Remaining: install SUMO 1.27 + `libsumo`/`traci` on macOS, run `osmWebWizard` on a tiny peninsula slice, emit geo Parquet FCD, record a throughput benchmark. **Gate:** toolchain proven before ETL.

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
