# Calibration report — peninsula bridge screenlines

Best-effort quantitative calibration of simulated AM-peak-hour bridge
volumes against published counts. Calibration is data-limited by design
(Phase 0 §7): City of Vancouver counts are VanMap-gated and BC MoTI's are
per-site with no bulk API, so the targets below are the *obtainable subset*
with confidence noted. GEH < 5 is the accepted good-match threshold.

- **Result:** 5/5 screenlines within GEH < 5;  mean GEH 1.22.
- **Gateway split:** corrected via per-gateway demand weights (below) — the
  Phase-4 model over-fed the east viaduct and starved Lions Gate.
- **Demand magnitude:** the observed counts correspond to a full-demand scale of ~3.24 (≈18.0x the replay sub-sample 0.18 used by `am_base`). Full-real-demand microsimulation exceeds SUMO's single-core ceiling (the project's core constraint), so replay sub-samples; gateway *shares* are scale-invariant, so the split calibration holds at the replay scale.
- **AM peak window:** 07:30-08:30; observed = AADT x K_AM (see `etl/calibration.py`).

| Gateway | Observed (veh/h) | Simulated (veh/h) | GEH | Confidence |
|---------|------------------:|------------------:|----:|------------|
| gw_georgia_viaduct | 3,600.0 | 3,600 | 0.00 | medium |
| gw_granville_bridge | 5,850.0 | 5,886 | 0.47 | medium |
| gw_cambie_bridge | 4,950.0 | 4,914 | 0.51 | low |
| gw_burrard_bridge | 4,500.0 | 4,410 | 1.35 | low |
| gw_lions_gate | 5,004.0 | 5,274 | 3.77 | high |

## Gateway demand weights (the split calibration)

Applied in `sim/demand_census.py` to bias the gateway choice; 1.0 = the plain
geographic default. Scale-invariant, so they hold at any replay sub-sample.

| Gateway | Weight |
|---------|-------:|
| gw_lions_gate | 1.58 |
| gw_burrard_bridge | 1.15 |
| gw_granville_bridge | 1.36 |
| gw_cambie_bridge | 1.25 |
| gw_georgia_viaduct | 0.25 |
| gw_east_arterials | 1.0 |

## Coverage (stated honestly)

- **Calibrated:** the five bridge gateways above (Lions Gate, Granville,
  Cambie, Burrard, Georgia/Dunsmuir viaducts) — the cordon screenlines that
  carry essentially all external demand.
- **Uncalibrated:** the diffuse *East gateways* (no single screenline count);
  all internal peninsula links (no obtainable per-link counts); travel times
  (TransLink RTDS retired — Phase 0 §2). Mode share is calibrated upstream by
  the census loader, not here.
- **Method caveat:** a single global demand scale corrects overall magnitude;
  residual per-gateway GEH reflects route-choice imbalance the scale can't fix.
  Low-confidence targets (Cambie, Burrard) are estimates — replace with
  verified MoTI TRADAS / CoV station counts (backlog) before treating their
  GEH as authoritative.
