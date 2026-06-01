# Phase 5 — Scenarios (accident / closure injection)

**Goal:** Inject accidents and road closures mid-run via TraCI and surface the before/after impact in the UI — the marquee interactive feature.

**Status:** Complete — `sim/librun.py` injects a mid-run bridge closure (disallow lanes + rerouting devices); `sim run --scenario close_<bridge>`. The viewer shows before/after deltas (Δ travel/wait/trips) vs a matched baseline + highlights the closed edge. Exit gate met. Accident/speed-drop primitives + click-to-place authoring deferred to backlog.

## Tasks

1. **Injection primitives (TraCI / libsumo).** Close an edge or lane, stop a vehicle to simulate an accident, and reduce link speeds — all mid-simulation at a chosen time and duration. Persist as `scenario_events`.
2. **Rerouting.** Trigger affected vehicles to reroute (`rerouteTraveltime` / `setRoute`), so congestion redistributes realistically.
3. **Real closure library.** Ingest DriveBC Open511 events (highways/bridges) as ready-made, realistic closure scenarios; allow hand-authored ones too.
4. **Before/after in the UI.** Run a baseline and a scenario, then compare: delta travel time, queue length, throughput, and a visual diff. The flagship demo is **closing the Lions Gate Bridge** and watching traffic back up and reroute.

## Deliverables

- Scenario authoring + a two-run comparison view.

## Exit gate — met

Injecting a closure mid-run visibly reroutes traffic and the UI reports before/after deltas. **Met** — closing Granville at 08:00 vacated the bridge (200→2 vehicles) and rerouted traffic; the UI reports Δ +14 s travel, +14 s wait, −96 trips vs the baseline run.

## How to run

```
uv run python -m sim run --demand census --scale 0.18 --name am_base     --begin 25200 --end 32400
uv run python -m sim run --demand census --scale 0.18 --name am_granville --scenario close_granville_bridge --begin 25200 --end 32400
```
Open the viewer and pick the scenario run. Other bridges: `close_lions_gate`, `close_burrard_bridge`, `close_cambie_bridge`, `close_georgia_viaduct`.

## Deferred

Click-to-place scenario authoring, timed event sequences, weather/event scenarios → backlog.
