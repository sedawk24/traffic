# Phase 0 — Research writeup + environment spike

**Goal:** Lock in the verified research as durable docs, then prove the SUMO + Python toolchain works on this machine before any ETL is built.

**Status:** In Progress.

## Why this phase exists (changes from the brief)

The brief listed deep research as Phase 0. We keep that and **add a toolchain spike** to the same phase — the biggest early risk after data availability is that SUMO + `libsumo` + the GUI tools don't install/run cleanly on macOS (Apple Silicon). Proving the chain on a tiny area now is cheap insurance before we invest in the ETL.

## Tasks

1. **Tracking files** — populate `CLAUDE.md`, `CURRENT_STATE.md`, `development-tracker.md`, `backlog.md`, `README.md`; create these phase files; log ADRs. Commit before code (CLAUDE.md hard rule).
2. **Research deliverables** in `docs/research/`:
   - `data-sources.md` — every source: availability, format, access, licensing, freshness, gotchas (with the RTDS-retired / counts-not-bulk / Trip-Diary-dashboard-only corrections).
   - `engine-selection.md` — SUMO pressure-test + alternatives + the single-core constraint and how we design around it.
   - `traffic-modeling-primer.md` — four-step model; macro/meso/micro; car-following & lane-changing; OD vs activity-based; DTA/equilibrium; signal control; stochasticity; calibration/validation — and **what we implement in v1 vs defer**.
   - `signal-timing.md` — the approximation approach (actuated defaults, Webster, coordination, calibration).
3. **Install SUMO 1.27** + Python bindings on macOS:
   - `brew install --cask sumo` (or official build); set `SUMO_HOME`.
   - `uv` project; `uv add eclipse-sumo libsumo traci` (verify wheels on Apple Silicon).
   - Confirm `sumo`, `sumo-gui`, `netedit`, `netconvert` on PATH; note any XQuartz/native-GUI caveats.
4. **Sanity run** — `osmWebWizard.py` (or manual `netconvert`) on a tiny peninsula slice (e.g., a few West End blocks); run a short sim; emit `--fcd-output.geo` as **Parquet**; confirm lon/lat rows look right.
5. **Benchmark** — measure vehicle-updates/sec and faster-than-real-time factor on this hardware with a representative small network + the real FCD/output config. Record numbers; they close the capacity-assumption gap noted in research.

## Deliverables

- Populated tracking files + four research docs, committed.
- A working SUMO install with `python -c "import libsumo, traci"` succeeding.
- A tiny geo Parquet FCD file + a recorded benchmark in `development-tracker.md`.

## Exit gate

SUMO runs a tiny peninsula scenario end-to-end and writes geo Parquet FCD; benchmark recorded; research + tracking committed. **Only then start Phase 1.**
