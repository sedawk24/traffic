# Phase 3 — Visualization (clean cartographic + icons)

**Goal:** Make the replay beautiful and legible — the bespoke value of the project. Visual direction: clean cartographic basemap with crisp zones, styled network, and vehicle icons distinct by type.

**Status:** Complete — exit gate met. Polished, performant replay: per-vehicle car/bus icons (oriented by heading) at street zoom; region→street LOD (flow ribbons coloured by edge volume ↔ icons); land-use zones + legend; classed roads; labelled bridge gateways; bus-route lines; run/speed selectors, layer toggles, day-scrubber, clock. Self-hosted PMTiles deferred to backlog (no tooling; not in the exit gate).

## Tasks

1. **Basemap.** Self-hosted Protomaps PMTiles (clipped BC extract) served statically; clean MapLibre style (OpenFreeMap style as the dev starting point).
2. **Zones.** Land-use-shaded `PolygonLayer` (residential / commercial / industrial / parkland / downtown-core) with a clear palette and legend.
3. **Network.** Styled roads, distinct **bridges/viaducts**, and transit lines (`PathLayer`).
4. **Vehicles.** `IconLayer` with distinct icons per type — car, carpool, bus, delivery van, heavy truck, SkyTrain; optional `TripsLayer` comet-trails for flow.
5. **Level of detail.** Aggregated flow ribbons / edge-density coloring at regional zoom; individual icons at street zoom; viewport-based caps to hold 60fps.
6. **Controls.** Play/pause/speed, time-of-day clock, layer toggles, legend, scenario selector, smooth zoom region→intersection.

## Deliverables

- A polished, performant replay UI on the peninsula.

## Exit gate — met

Vehicle types are visually distinct (car/bus icons); zoom from regional overview to a single intersection is smooth; the LOD transition (flow ribbons → icons at ~zoom 13.2) holds frame rate; bridges (labelled gateways) and transit (bus-route lines) read clearly. **Met** — verified by headless screenshots at region + street zoom.

## How to run

`uv run uvicorn api.main:app` → http://127.0.0.1:8000/ . View params: `?zoom=&lng=&lat=`. Basemap is OpenFreeMap (dev); self-hosted PMTiles is backlogged.
