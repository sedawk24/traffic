# Phase 4 — Demand modeling (realistic)

**Goal:** Replace placeholder demand with believable, census-driven demand that produces the real daily rhythm: AM inbound, midday, PM outbound, plus commercial/industrial delivery traffic.

**Status:** Not Started.

## Tasks

1. **OD disaggregation.** Map CSD→CSD commuting flows (98-10-0459) onto peninsula zones — external trips as **bridge-gateway flows**, internal as zone-to-zone — weighted by land use, population, and employment. Handle census base-5 rounding/suppression by smoothing sparse cells.
2. **Mode split + departure timing.** Split car / carpool (HOV) / transit; draw **stochastic departure times** from per-municipality "time leaving for work" histograms (98-10-0458) — not a single 07:00 spike. Add return-trip and midday distributions.
3. **Non-work + freight.** Synthesize non-work, commercial/delivery-van, and heavy-truck demand from land-use heuristics (industrial/commercial zones as freight generators), anchored to TransLink Trip Diary published aggregates (~8.8M weekday trips, mode share).
4. **Assignment.** Route with `duarouter` (one-shot) → optionally `duaIterate.py` toward dynamic user equilibrium; convert to SUMO `.rou.xml`. Tune `tlsCycleAdaptation.py` / `tlsCoordinator.py` on arterials against the realized demand.

## Deliverables

- A demand generator that turns SQLite OD + profiles into SUMO routes for a representative weekday.

## Exit gate

Simulated departure histogram and mode split track the census; AM-in / PM-out asymmetry is visible in the replay; bridge gateway volumes are plausible.

## Deferred

Weekend/seasonal day-types, multi-day chaining, and transit ridership/crowding → backlog.
