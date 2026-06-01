# Phase 4 — Demand modeling (realistic)

**Goal:** Replace placeholder demand with believable, census-driven demand that produces the real daily rhythm: AM inbound, midday, PM outbound, plus commercial/industrial delivery traffic.

**Status:** Complete — `sim/demand_census.py` (`sim run --demand census`) produces census-driven SUMO routes for a representative weekday: OD disaggregated to gateways/zones by land-use weights, census departure timing + mode-split scaling, synthesized non-work/delivery/truck demand, and duarouter assignment. Exit gate met. duaIterate (DUE) + signal-timing tuning deferred to the backlog.

## Tasks

1. **OD disaggregation.** Map CSD→CSD commuting flows (98-10-0459) onto peninsula zones — external trips as **bridge-gateway flows**, internal as zone-to-zone — weighted by land use, population, and employment. Handle census base-5 rounding/suppression by smoothing sparse cells.
2. **Mode split + departure timing.** Split car / carpool (HOV) / transit; draw **stochastic departure times** from per-municipality "time leaving for work" histograms (98-10-0458) — not a single 07:00 spike. Add return-trip and midday distributions.
3. **Non-work + freight.** Synthesize non-work, commercial/delivery-van, and heavy-truck demand from land-use heuristics (industrial/commercial zones as freight generators), anchored to TransLink Trip Diary published aggregates (~8.8M weekday trips, mode share).
4. **Assignment.** Route with `duarouter` (one-shot) → optionally `duaIterate.py` toward dynamic user equilibrium; convert to SUMO `.rou.xml`. Tune `tlsCycleAdaptation.py` / `tlsCoordinator.py` on arterials against the realized demand.

## Deliverables

- A demand generator that turns SQLite OD + profiles into SUMO routes for a representative weekday.

## Exit gate — met

Simulated departure histogram and mode split track the census; AM-in / PM-out asymmetry is visible in the replay; bridge gateway volumes are plausible. **Met** — AM departure shape matches the census curve; the full-day sim is bimodal (AM ~801 active @ 08:00, PM ~946 @ 17:00); gateway volumes east > south > Lions Gate, matching the OD origins.

## How to run

`uv run python -m sim run --demand census --scale 0.25 --name census --begin 25200 --end 30600` → a census-driven AM-peak run (tune `--scale` for density; the demand spans the full day, the window selects what runs).

## Deferred

Weekend/seasonal day-types, multi-day chaining, and transit ridership/crowding → backlog.
