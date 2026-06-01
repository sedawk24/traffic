# Phase 1 — Data pipeline (ETL → SQLite + SUMO inputs)

**Goal:** A repeatable, idempotent ETL that turns open data into a SUMO-ready network + demand + zones for the downtown peninsula, plus a SQLite database of structured inputs.

**Status:** In Progress — the ETL backbone (SQLite schema + idempotent `python -m etl` CLI) and the OSM→SUMO network build with an automated bridge-cordon trim (`etl network`, 7,307 edges) are done, plus the zoning (Task 5: 366 zones), signals/events (Task 6), and transit (Task 3: 254 stops / 4,062 bus departures) loaders; fine `netedit` cleanup + `netdiff` (Tasks 1–2) and the census (4) loader are pending.

## Scope

Downtown Vancouver peninsula only (cordoned at the bridges). Build the pipeline so re-running it reproduces the same DB and SUMO inputs.

## Tasks

1. **Network — OSM → SUMO.**
   - Extract the peninsula bbox from a Geofabrik BC extract (or `osmnx`); filter with `osmfilter`.
   - `netconvert --osm-files … --tls.default-type actuated --tls.min-dur 5 --tls.max-dur 50 --tls.cycle.time 90 --tls.yellow.time 4 --guess-ramps …` → `.net.xml`.
   - Manual cleanup in `netedit`: bridge/viaduct connectivity, lane counts, turn lanes, gateway edges at Lions Gate / Burrard / Granville / Cambie / the viaducts / Stanley Park Causeway.
   - Capture edits with `netdiff.py` so they survive an OSM re-import.
2. **Transit — GTFS → SUMO pt.**
   - Download TransLink GTFS static; `gtfs2pt.py --modes bus,tram,subway,rail` → stops `.add.xml` + vehicles `.rou.xml`; hand-tune vTypes (capacity).
3. **Demand inputs — census → SQLite.**
   - Load StatCan **98-10-0459** (CSD→CSD commuting flows) → `od_flows`; **98-10-0458** (departure time × mode) → `departure_profiles`. Handle base-5 rounding and <40 suppression (smooth/aggregate sparse cells). Record source + date.
4. **Zones — land use → SQLite + GeoJSON.**
   - Metro 2050 regional land-use as the base; overlay City of Vancouver zoning for detail; OSM `landuse=*` fallback. Reclassify to {residential, commercial, industrial, parkland, downtown-core}. Mark gateway zones. Store polygons + centroids + population/employment weights in `zones`; export GeoJSON for the renderer.
5. **Reference + scenarios.**
   - CoV signal locations → `signals` (map to SUMO TLS ids where possible). DriveBC Open511 events → a closure scenario library.
6. **Schema + CLI.**
   - Implement the SQLite schema (see plan / decisions). ETL as small composable CLI steps (`etl osm`, `etl gtfs`, `etl census`, `etl zoning`, `etl all`) plus a data registry. Idempotent.

## Deliverables

- `data/traffic.db` (SQLite) populated; `data/sumo/peninsula.net.xml` + transit pt files; zones GeoJSON; netdiff patch.
- `etl/` package with documented, repeatable CLI.

## Exit gate

ETL re-run yields an identical DB; OD totals reconcile with the census source; the network opens cleanly in `netedit` with bridges/gateways intact; zone polygons render with land-use classes. **Defer** bulk traffic-count acquisition to Phase 6.
