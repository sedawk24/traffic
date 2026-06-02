# Phase 8 — Full-detail city ("complete simulation")

**Goal:** A **complete, microscopic City of Vancouver** simulation — every street (incl. residential side streets), live traffic signals, buses, and demand distributed across the whole city so side streets carry traffic. This is the "make it real" deliverable: the meso metro net (Phase 7) is great for the regional flow overview but is arterials-only and queue-based, so it can't show side-street cars, per-corner signals, or detailed buses. Those need the full street network run microscopically over a city-sized focus area.

**Status:** In progress.

## Why a third study area

Three nested areas, each at the right level of detail:

| Area | Extent | Roads | Engine | Use |
|------|--------|-------|--------|-----|
| `peninsula` | Downtown core | all streets | micro | the original calibrated slice |
| `vancouver` | **Whole City of Vancouver** | **all streets** | **micro** | **the complete, zoom-in experience** |
| `metro` | Core GVRD | arterials only | meso | regional flow overview |

## Approach

1. **Network (`etl network --area vancouver`).** OSM **all drivable roads** (no road-type filter) over `VANCOUVER_BBOX`, tiled → `vancouver.net.xml` (~76k edges / ~28k junctions / ~1.1k signals).
2. **Demand (`sim run --demand vancouver`).** The distributed census model (`demand_metro.build_demand`) with `home_code = Vancouver`: the city's own CSD claims **every** street, so the large intra-Vancouver flow spreads across the whole city (side streets included); other municipalities enter at the city boundary.
3. **Buses (`etl transit --area vancouver`).** `gtfs2pt` over the city net → `vancouver_pt_*` ; the micro run simulates them alongside cars.
4. **Signals.** The micro run captures live per-approach TLS states (as the peninsula does) — every signalized intersection cycles red/green at street zoom.
5. **Run.** Microscopic (`sim run --demand vancouver`), transit on, FCD sampled every 2 s (the all-streets trace is large).
6. **View.** The area-aware viewer loads the city net + buses; zoom out → flow ribbons, zoom in → individual cars + buses on side streets with live signals.

## Exit gate

Zooming into a Vancouver neighbourhood (e.g. the West Side) shows realistic side-street car traffic, buses running, and signals cycling — not an empty grid.

## Deferred (backlog)

- Sub-municipal (census-tract / DA) demand for true neighbourhood-accurate origins, rather than city-uniform intra-Vancouver spread.
- Metro-net calibration; meso↔micro LOD hand-off (auto-switch `vancouver`↔`metro` by zoom).
- Region-wide all-streets (compute-bound — would need distributed/GPU engines).
