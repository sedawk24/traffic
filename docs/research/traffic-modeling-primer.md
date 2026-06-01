# Phase 0 Research — Traffic-Modeling Primer

A summary of established traffic-modeling practice so we don't reinvent a worse version of it, with a clear **v1 vs defer** recommendation for each component given our constraints (open data, single machine, batch-then-replay, one focus area).

## The classic four-step model

The traditional aggregate demand-modeling sequence:

1. **Trip generation** — how many trips each zone produces/attracts (from land use, population, employment).
2. **Trip distribution** — pairing productions with attractions into an **origin–destination (OD) matrix** (often a gravity model).
3. **Mode choice** — splitting each OD flow across modes (car, carpool, transit, walk, bike).
4. **Route assignment** — loading trips onto network paths, typically toward an equilibrium where no driver can improve by switching routes.

We approximate this with **census journey-to-work flows** (distribution already done at CSD level), **census mode share** (mode choice), land-use-weighted **disaggregation** (generation to zones), and **SUMO `duarouter`** (assignment).

## Macroscopic vs mesoscopic vs microscopic

- **Macroscopic** — aggregate flow/speed/density on links (volume-delay functions). Fast, coarse; no individual vehicles.
- **Mesoscopic** — vehicles in queues/platoons on links, simplified dynamics. Scales to regions; SUMO `--mesosim` is ~100× faster than micro.
- **Microscopic** — every vehicle individually with car-following and lane-changing. Highest fidelity and the basis of our visualization; single-core-bound (see `engine-selection.md`).

**Our choice:** microscopic for the focus area (the watchable detail), mesoscopic for regional context as we scale.

## Car-following & lane-changing

- **Car-following** governs longitudinal behavior (accel/decel, gap-keeping). SUMO defaults to **Krauss**; others available (IDM, Wiedemann). Determines realistic stop-and-go and queue formation.
- **Lane-changing** governs lateral behavior (overtaking, lane selection, cooperation). SUMO's **LC2013** is the default; a **sublane** model exists for finer lateral detail (heavier).

**v1:** use SUMO defaults (Krauss + LC2013); tune only if calibration demands it. **Defer** sublane.

## OD matrices vs activity-based demand

- **OD matrix** — trips between zones for a period; what the four-step model produces. Simple, the v1 approach.
- **Activity-based** — synthesizes individual daily *plans* (home→work→shop→home) with consistent schedules; richer and the direction MATSim embodies.

**v1:** OD-matrix-based demand from census, with stochastic departure times and synthesized non-work/freight trips. **Defer** full activity-based modeling (backlog: MATSim).

## Dynamic traffic assignment & equilibrium

- **Static assignment** loads a whole period at once. **Dynamic traffic assignment (DTA)** loads time-varying demand and lets congestion evolve.
- **User equilibrium** = no traveler can reduce their cost by unilaterally changing route. SUMO reaches an approximation via **`duaIterate.py`** (iterated `duarouter`), or a cheaper **one-shot** assignment.

**v1:** one-shot or a few `duaIterate` iterations on the focus area. **Defer** full equilibrium convergence at region scale.

## Signal control

Strategies range from **fixed-time** → **actuated** (gap-based, demand-responsive) → **coordinated** (green waves on arterials) → **adaptive** (live optimization). The City doesn't publish timing plans, so we approximate. See `signal-timing.md`.

**v1:** actuated defaults + arterial coordination, calibrated. **Defer** adaptive/live control.

## Stochasticity

Real demand is spread out — people don't all leave at exactly 07:00. Departure times follow distributions; routes and behaviors vary. Modeling this (e.g., sampling departures from the census "time leaving for work" histogram, random seeds) is what makes peaks build and dissipate realistically rather than as a spike.

**v1:** stochastic departure-time sampling by mode/municipality; per-run seeds. **Essential, not deferred.**

## Calibration & validation

A model is credible only when its outputs match observed reality — typically simulated **link volumes vs counts** (the **GEH** statistic; GEH < 5 on most links is the common target) and **corridor travel times vs observed**. Calibration adjusts demand, route choice, and signal parameters until the match is acceptable; validation checks against held-out data.

**v1:** **best-effort quantitative** — GEH on the obtainable open-data subset (BC MoTI bridge/highway counts, scraped CoV stations) + travel-time sanity checks, with coverage documented honestly. Our calibration data is thinner than the brief assumed (RTDS retired; CoV counts not bulk), so we're explicit about gaps. See `data-sources.md`, `phase-6.md`.

## v1 vs defer — summary

| Component | v1 | Defer |
|---|---|---|
| Trip generation/distribution | Census CSD OD + land-use disaggregation | Gravity model from scratch |
| Mode choice | Census mode share (car/carpool/transit) | Discrete-choice logit models |
| Route assignment | `duarouter` one-shot / few `duaIterate` | Full regional equilibrium |
| Resolution | Micro (focus) + meso (region) | All-micro region-wide |
| Car-following / lane-change | SUMO defaults (Krauss / LC2013) | Sublane, custom models |
| Demand structure | OD matrix + stochastic departures + synth freight | Activity-based plans (MATSim) |
| Signals | Actuated + arterial coordination | Adaptive/live control |
| Calibration | Best-effort GEH on obtainable counts | Commercial probe data, custom tabulations |

Key references: SUMO demand modelling (<https://sumo.dlr.de/docs/Demand/Introduction_to_demand_modelling_in_SUMO.html>), Dynamic User Assignment (<https://sumo.dlr.de/docs/Demand/Dynamic_User_Assignment.html>), TransLink RTM (<https://translinkforecasting.github.io/rtmdoc/>).
