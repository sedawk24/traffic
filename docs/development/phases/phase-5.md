# Phase 5 — Scenarios (accident / closure injection)

**Goal:** Inject accidents and road closures mid-run via TraCI and surface the before/after impact in the UI — the marquee interactive feature.

**Status:** Not Started.

## Tasks

1. **Injection primitives (TraCI / libsumo).** Close an edge or lane, stop a vehicle to simulate an accident, and reduce link speeds — all mid-simulation at a chosen time and duration. Persist as `scenario_events`.
2. **Rerouting.** Trigger affected vehicles to reroute (`rerouteTraveltime` / `setRoute`), so congestion redistributes realistically.
3. **Real closure library.** Ingest DriveBC Open511 events (highways/bridges) as ready-made, realistic closure scenarios; allow hand-authored ones too.
4. **Before/after in the UI.** Run a baseline and a scenario, then compare: delta travel time, queue length, throughput, and a visual diff. The flagship demo is **closing the Lions Gate Bridge** and watching traffic back up and reroute.

## Deliverables

- Scenario authoring + a two-run comparison view.

## Exit gate

Injecting a closure mid-run visibly reroutes traffic and the UI reports before/after deltas.

## Deferred

Click-to-place scenario authoring, timed event sequences, weather/event scenarios → backlog.
