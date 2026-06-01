# Phase 0 Research — Data Sources (verified 2026-05-31)

Verified availability, format, access, licensing, freshness, and gotchas for every data source, including **corrections to the original brief**. All sources are open data; attribution requirements are noted.

## TL;DR — feasibility flags

- **Build-ready now:** OSM→SUMO; TransLink GTFS static + GTFS-RT v3; StatCan 2021 commuting OD; Metro 2050 + Vancouver zoning; CoV signal *locations*; DriveBC Open511 closures.
- **❌ Deprecated — do not use:** TransLink **RTTI** (retired 2024-12-03) and **RTDS** (real-time speeds/travel times — no longer offered). *The brief's travel-time calibration source is gone.*
- **⚠️ Thinner than assumed:** City of Vancouver traffic counts are **locations + links, not a bulk hourly feed**; BC MoTI counts are **per-site, quarterly, no bulk API**; TransLink **Trip Diary 2023** is a **public dashboard only** (no open microdata).
- **Requires free registration:** TransLink API key (for real-time feeds only).

---

## 1. Street network — OpenStreetMap

- **Use:** street + bridge network → SUMO via `netconvert`.
- **Access:** `osmnx` or a Geofabrik **British Columbia** extract, clipped to the peninsula bbox; pre-filter with `osmfilter`.
- **License:** ODbL (attribution + share-alike on derived databases).
- **Gotcha:** auto-generated SUMO networks need **manual cleanup** — ramps (`--guess-ramps`), turn lanes, lane counts, connections, traffic-light placement, and especially **bridges/viaducts**. Capture edits with `netdiff.py` so they survive a re-import.
- Docs: <https://sumo.dlr.de/docs/Networks/Import/OpenStreetMap.html>

## 2. Transit — TransLink

Portal: <https://www.translink.ca/about-us/doing-business-with-translink/app-developer-resources>. Register for a free key: <https://developer.translink.ca/account/register>.

- **GTFS static (schedule):** `https://gtfs-static.translink.ca/gtfs/google_transit.zip` — standard GTFS ZIP, **no key**, updated **weekly** (~Fridays). Import to SUMO via `gtfs2pt.py` (bus + rail). **Use this for v1.**
- **GTFS-Realtime v3 (key required, protobuf):** trip updates `…/v3/gtfsrealtime`, vehicle positions `…/v3/gtfsposition`, alerts `…/v3/gtfsalerts` (all on `gtfsapi.translink.ca`, `?apikey=`). **Deferred** to backlog (v1 is batch).
- **License/attribution:** TransLink retains IP; mandatory attribution string required (*"Route and arrival data … provided by permission of TransLink. TransLink assumes no responsibility for the accuracy or currency of the Data."*). Review Terms of Use before shipping commercially.
- **❌ RTTI Open API:** **retired 2024-12-03** — superseded by GTFS-RT v3.
- **❌ RTDS (Regional Traffic Data System):** the 2014-era near-real-time highway speeds/travel-time product is **no longer listed** on any current TransLink developer page. Treat as **unavailable**. For real-time road speeds we'd need another provider (commercial HERE/TomTom/Google) or model it ourselves. **This removes the brief's TransLink travel-time calibration source.**

## 3. Commute demand — Statistics Canada 2021 Census (product 98P1003)

Released 2022-11-30 from the long-form 25% sample. WDS API "PID" = the table digits without dashes. License: **Statistics Canada Open Licence** (<https://www.statcan.gc.ca/en/reference/licence>) — royalty-free, commercial OK, attribution required (*"Source: Statistics Canada, [product], [date]."*).

**Origin–destination (commuting flow) — core of the OD matrix:**
| Product | Geography | Use |
|---|---|---|
| **98-10-0459-01** | CSD → CSD (municipality) | **Primary OD** for Metro Van. <https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=9810045901> |
| 98-10-0460-01 | CMA/CA + mode + duration | Coarser flow with mode. |
| 98-10-0466-01 | CD (regional district) | Regional-level flow. |

**Departure time / mode / duration (the daily-rhythm shape):**
| Product | Geography | Variables |
|---|---|---|
| **98-10-0458-01** | CD + **CSD** | main mode × duration × **time leaving for work** — per-municipality AM-departure histogram |
| 98-10-0457-01 | CMA/CA | same, CMA level |
| 98-10-0462-01 | CD + CSD | commuting destination (within/out of CSD) × mode |

**Access:** per-table CSV/XML download (swap `pid` in the URL) or the **Web Data Service API** (JSON/SDMX; `getCubeMetadata`, `getDataFromVectorsAndLatestNPeriods`) — <https://www.statcan.gc.ca/en/developers/wds>. Topic hub: <https://www12.statcan.gc.ca/census-recensement/2021/rt-td/commuting-navettage-eng.cfm>.

**Gotchas:** counts are **random-rounded to base 5** and **areas < 40 persons suppressed** — small CSD→CSD pairs are noisy/zero. Smooth or aggregate sparse cells; never treat a rounded small flow as exact. **No public tract-level OD** (tract data is destination-only, 98-10-0503/0504); true tract/DA flows need a paid custom tabulation.

## 4. Trip purpose / time-of-day — TransLink Trip Diary 2023

- **What it is:** regional household travel survey (15,992 households, fielded Sep 2023; 24-hour weekday). Captures trip O/D, start/end times, purpose, mode.
- **⚠️ Published vs internal:** **public Tableau dashboard only** — <https://public.tableau.com/app/profile/translink/viz/Trip_Diary_2023/TripDiary> — with breakdowns by purpose, time of day, mode, geography. The technical PDF is methodology, not results. **No open microdata / PUMF.**
- **Headline figures (cross-check):** ~8.8M trips on an average fall-2023 weekday; >30% sustainable modes; regional VKT −5.2% vs 2017.
- **Practical use:** lean on **StatCan 98-10-0458** for machine-readable departure curves; use the Trip Diary dashboard + headline numbers to scale non-work and total trips. The public **TransLink RTM** (four-step EMME model, <https://translinkforecasting.github.io/rtmdoc/>) documents purpose definitions and approach.

## 5. Land use & zoning

- **Metro Vancouver "Metro 2050" regional land use** — ArcGIS Hub (<https://open-data-portal-metrovancouver.hub.arcgis.com/>): one regional layer, all 21 member municipalities; Shapefile/GeoJSON/CSV + ArcGIS REST/WFS/WMS. **Coarse classes** (Urban / Industrial / Mixed Employment / Agricultural / Conservation+Recreation / Rural). License: OGL-Metro-Vancouver. **Use as the regional base.**
- **City of Vancouver zoning** — `zoning-districts-and-labels` (<https://opendata.vancouver.ca/explore/dataset/zoning-districts-and-labels/>): 1,618 polygons, fields `zoning_classification/category/district`; GeoJSON/Shapefile/CSV + Explore API v2.1; actively maintained; OGL-Vancouver. **Use for downtown detail.**
- **OSM landuse** — `landuse=residential|commercial|industrial|retail`, `leisure=park` via Overpass/Geofabrik; ODbL. **Fallback / gap-fill** and O-D weighting.
- **Pragmatic stack:** Metro 2050 base → Vancouver zoning detail → OSM landuse gap-fill, reclassified to {residential, commercial, industrial, parkland, downtown-core}.

## 6. Signals & incidents

- **City of Vancouver traffic signals** — `traffic-signals`: **locations only, no timing** (timing is sold, not open); CSV/GeoJSON/Shapefile + API; OGL-Vancouver. Used to place/identify SUMO TLS. (See `signal-timing.md` for the timing-approximation approach.)
- **DriveBC Open511** — `https://api.open511.gov.bc.ca/events`: real road events/closures/incidents; JSON/XML; **no key**; filters `bbox`, `status`, `event_type`, pagination (max 500/req); OGL-BC. **Gotcha: provincial highways only** (no municipal streets) — good for highway/**bridge** closure scenarios. Docs: <https://api.open511.gov.bc.ca/help>.

## 7. Calibration volumes (⚠️ the weak spot)

- **City of Vancouver counts** — the portal publishes **locations + links, not a bulk hourly time series**: `intersection-traffic-movement-counts` (TMC *locations*, static since 2020, with `url` links), `directional-traffic-count-locations` (2004–2013 legacy; actual counts only in legacy VanMap). The ~35 permanent stations' hourly-by-lane volumes are **not a bulk dataset** — expect to scrape/parse linked pages or contact the program. OGL-Vancouver.
- **BC MoTI Traffic Data Program** — <https://www.th.gov.bc.ca/trafficdata/> + GIS app `https://twm.th.gov.bc.ca/?c=tdp`: permanent provincial-highway stations; AADT/SADT/AAWDT + monthly/hourly per site; **updated quarterly**; **interactive per-site export (TRADAS), no bulk API**. Best source for **bridge/screenline** volumes feeding regional flow.
- **ICBC crash data** — <https://icbc.com/about-icbc/newsroom/Statistics> (Lower Mainland Crashes dashboard + downloadable, filterable by municipality/severity/street); **annual, aggregated** (2024 data released ~June 2025). Optional, for realistic accident placement → backlog.

**Implication:** rigorous per-link calibration is data-limited. v1 calibration is **best-effort quantitative** on the obtainable subset (MoTI bridge/highway counts, scraped CoV stations, census mode share, Trip Diary aggregates), GEH<5 where data exists, with coverage documented honestly. See `decisions.md` and `phase-6.md`.

## 8. Other / aggregators

- **BC Data Catalogue** (province-wide transportation): <https://catalogue.data.gov.bc.ca/dataset?sector=Transportation> (MoTI Road Features Inventory, etc.), mostly OGL-BC.
- **Transitland / Mobility Database** mirror TransLink GTFS/GTFS-RT if a normalized fetch path is preferred.
- **Municipal portals** (Surrey, Burnaby, Richmond, Coquitlam…) publish their own counts/GIS via ArcGIS Hub — relevant when expanding beyond the City of Vancouver and provincial highways.
