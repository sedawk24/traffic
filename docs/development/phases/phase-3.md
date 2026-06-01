# Phase 3 — Visualization (clean cartographic + icons)

**Goal:** Make the replay beautiful and legible — the bespoke value of the project. Visual direction: clean cartographic basemap with crisp zones, styled network, and vehicle icons distinct by type.

**Status:** In Progress — polished viewer done (TripsLayer comet-trails by type, land-use zones + legend, classed roads, labelled bridge gateways, run/speed selectors, layer toggles, clock). Remaining: glyph vehicle icons, transit route lines, explicit region→street LOD, self-hosted PMTiles.

## Tasks

1. **Basemap.** Self-hosted Protomaps PMTiles (clipped BC extract) served statically; clean MapLibre style (OpenFreeMap style as the dev starting point).
2. **Zones.** Land-use-shaded `PolygonLayer` (residential / commercial / industrial / parkland / downtown-core) with a clear palette and legend.
3. **Network.** Styled roads, distinct **bridges/viaducts**, and transit lines (`PathLayer`).
4. **Vehicles.** `IconLayer` with distinct icons per type — car, carpool, bus, delivery van, heavy truck, SkyTrain; optional `TripsLayer` comet-trails for flow.
5. **Level of detail.** Aggregated flow ribbons / edge-density coloring at regional zoom; individual icons at street zoom; viewport-based caps to hold 60fps.
6. **Controls.** Play/pause/speed, time-of-day clock, layer toggles, legend, scenario selector, smooth zoom region→intersection.

## Deliverables

- A polished, performant replay UI on the peninsula.

## Exit gate

Vehicle types are visually distinct; zoom from regional overview to a single intersection is smooth; the LOD transition holds frame rate; bridges and transit read clearly.
