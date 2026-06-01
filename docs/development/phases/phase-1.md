# Phase 1 — Data pipeline (ETL → SQLite + SUMO inputs)

**Goal:** A repeatable, idempotent ETL that turns open data into a SUMO-ready network + demand + zones for the downtown peninsula, plus a SQLite database of structured inputs.

**Status:** Complete. The `etl/` package (SQLite schema + idempotent `python -m etl` CLI) ingests every source into `data/traffic.db` + SUMO inputs for the cordon-trimmed peninsula: network (7,307 edges, automated cordon trim), zoning (366 zones), signals (254), events (11 scenarios), transit (254 stops / 4,062 bus departures), and census (456 OD flows / 2,618 departure profiles) — across 8 provenance-tracked sources. An optional manual `netedit` polish pass remains (see *Manual refinement* below).

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

## Manual refinement (netedit + netdiff)

The automated build (cordon trim + actuated signals) produces a clean, simulatable net; a manual `netedit` pass is **optional polish** for fidelity (bridge/viaduct lane counts, turn lanes, gateway-edge tagging). To keep such edits reproducible across an OSM re-import, `etl network` emits a **plain-XML baseline** (`data/sumo/peninsula.plain.{nod,edg,con,tll,typ}.xml`). Workflow:

1. `uv run python -m etl network` — builds the net + writes the plain-XML baseline.
2. Edit `data/sumo/peninsula.net.xml` in `netedit`; save.
3. Re-export the edited plain XML: `netconvert -s peninsula.net.xml --plain-output-prefix peninsula.edited`.
4. `netdiff.py peninsula.plain peninsula.edited peninsula.patch` → a reusable patch.
5. On a future OSM re-import, replay the patch so manual edits survive.

Until a manual pass is done, the automated net is used as-is.

## Exit gate — met

- ✅ ETL re-run yields an identical DB (idempotent: delete-by-source + deterministic/natural keys).
- ✅ OD totals reconcile with the census source (222k intra-GVRD into Vancouver; mode split 57/23/19 car/transit/active).
- ✅ The network reads cleanly (sumolib) with the bridge gateway stubs present (cordon-trimmed); plain-XML baseline emitted.
- ✅ Zone polygons carry land-use classes in the DB + `zones.geojson` (visual render is Phase 3).

Bulk traffic-count acquisition is **deferred** to Phase 6, as planned.
