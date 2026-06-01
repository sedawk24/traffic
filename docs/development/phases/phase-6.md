# Phase 6 — Scale & calibrate (best-effort quantitative)

**Goal:** Make the model credible by calibrating against the open data we can actually obtain, and begin expanding beyond the peninsula. Calibration is a first-class goal — it is what separates a toy from a model.

**Status:** Not Started.

## Reality check (from Phase 0 research)

The brief's richest calibration sources are weaker than assumed: TransLink **RTDS** (real-time speeds/travel times) is **retired**; City of Vancouver counts are **locations + links, not a bulk feed**; BC MoTI counts are **per-site, quarterly, no bulk API**. So v1 calibration is **best-effort quantitative** on an obtainable subset, with coverage stated honestly.

## Tasks

1. **Calibration-data spike.** Assemble what exists: BC MoTI highway/**bridge** counts (screenlines that matter most for regional flow), scraped CoV permanent stations where feasible, census mode share, Trip Diary published aggregates. Load into `calibration_targets`.
2. **Calibrate.** Adjust demand and signal knobs (and route choice) toward **GEH < 5** on the obtainable links, plus corridor travel-time sanity checks. Use `routeSampler.py` to fit demand to counts where available. Record `calibration_results` (simulated vs observed, GEH).
3. **Document coverage.** Be explicit about which links/corridors are calibrated vs uncalibrated.
4. **Expand outward.** Grow from the peninsula toward the wider region — **mesoscopic** for regional context, **microscopic** for focus areas, with LOD switching. Full Metro Vancouver coverage is a **stretch goal**, not a v1 gate.

## Deliverables

- A calibration report (coverage + GEH) and a path to expand the network.

## Exit gate

Simulated volumes match observed counts (GEH < 5) on the obtainable subset; calibration coverage is documented honestly.

## Deferred

Commercial probe data (HERE/TomTom) or a custom StatCan tabulation for fuller calibration; full-region microscopic coverage → backlog.
