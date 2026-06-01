# Phase 0 Research — Simulation Engine Selection (verified 2026-05-31)

**Verdict: build v1 on Eclipse SUMO.** It is the only mature open-source engine that simultaneously offers microscopic fidelity, first-class Python control, native OSM import, real GTFS transit (including rail), and geo-referenced floating-car-data output that feeds a browser replay with no extra projection work.

## SUMO at a glance

- **Version / maintenance:** 1.27.0 (2026-05-21); ~quarterly releases; actively maintained by DLR under the Eclipse Foundation. **License EPL-2.0** (permissive; weak file-level copyleft only if you modify SUMO's own source — our separate process is unaffected).
- **OSM import:** `netconvert --osm-files`, `osmWebWizard.py`, `netedit` GUI. Expect manual cleanup (ramps, turn lanes, connections, TLS, bridges); preserve edits with `netdiff.py`.
- **Python control:** `TraCI` (socket, GUI + multi-client, slower) · **`libsumo`** (in-process, same API, much faster — **use for batch**) · `libtraci` (socket but libsumo-compatible, for GUI/multi-client). Mid-sim control supports incident injection, lane/edge closure, speed changes, and rerouting.
- **Vehicle classes:** `passenger, hov, taxi, bus, coach, delivery, truck, trailer, tram, rail_urban, rail, motorcycle, bicycle, …`. HOV/carpool via lane `allow`/`disallow` permissions (first-class `hov` class).
- **Transit:** `gtfs2pt.py` imports GTFS (`--modes bus,tram,subway,rail`). Rail/subway run as real vehicles on rail edges to timetable — TransLink GTFS imports directly. For SkyTrain (grade-separated) the main traffic value is at stations/interchanges; full rail-signal fidelity is optional for v1.
- **FCD output (our replay feed):** per-vehicle x/y/z, speed, angle, type, lane, edge per timestep. **`--fcd-output.geo` emits WGS84 lon/lat** directly; output as **XML, CSV, or Parquet**, gz-compressible. **Size gotcha:** raw 1 Hz XML is hundreds of MB per vehicle-hour — use Parquet + `--device.fcd.probability` (sample) + `--device.fcd.period` + filtering.
- **Signals:** `netconvert` builds fixed-time by default, `--tls.default-type actuated` for gap-based actuated, NEMA supported; `tlsCoordinator.py` (green waves) and `tlsCycleAdaptation.py` (splits from demand).
- **Demand tools:** `randomTrips.py`, `od2trips`, `activitygen`, `duarouter` (+ `duaIterate.py` for dynamic user equilibrium), `marouter` (macro assignment). **Mesoscopic mode `--mesosim`** (queue-based, up to ~100× faster).

## The single constraint to design around

SUMO's microscopic core is **effectively single-core**: ~100k vehicle-updates/sec/core, a practical ceiling around **~200k simultaneously-active vehicles** per core, and its own multi-threading is frequently *slower* due to synchronization overhead. Therefore a region-wide, full-day **microscopic** run is **not** a single-machine real-time job (Metro Van ≈ 2.6M people → easily >1M trips).

**How we design around it (built in from day one):**
1. **Batch-then-replay** — decouple heavy sim from lightweight browser playback (Parquet/geo FCD).
2. **Two-tier resolution** — mesoscopic for the region, microscopic for the focus area (a `--mesosim` runtime flag, same inputs — no rewrite).
3. **Demand sub-sampling + area tiling** — scale factor + sub-area extraction for tractable full-day runs.
4. **Output discipline** — sampled Parquet FCD, never raw 1 Hz XML region-wide.
5. **Network-prep budget** — assume real human cleanup; lock it with `netdiff.py`.

*Open gap:* the public throughput numbers come from an old reference machine — **benchmark on the real target hardware** in Phase 0 before sizing capacity.

## Alternatives considered

| Engine | OSS | Resolution | Python | OSM | Transit | Verdict |
|---|---|---|---|---|---|---|
| **SUMO** | Yes (EPL-2.0) | Micro (+meso) | Excellent | Native | GTFS, rail+bus | **v1 choice** |
| MATSim | Yes (GPL, Java) | Meso, activity-based | Weak | Yes | pt2matsim | Best for day-scale regional demand — **future complement**, not v1 micro |
| Aimsun Next | No (commercial) | Micro+meso+hybrid | Yes | Yes | Yes | High fidelity but closed/costly |
| PTV Vissim | No (commercial) | Micro | Yes (COM) | 3rd-party | Yes | Industry micro but expensive/Windows |
| CityFlow / CBLab | Yes | Micro | Yes (RL) | Limited | No | Fast but realism/feature-poor, no transit |
| MOSS (2024) | Yes (MIT) | Micro, GPU | Yes | Yes | Partial | >2M vehicles — **future escape hatch** if scale binds; young tooling |
| Flow (Berkeley) | Yes | wraps SUMO | Yes | via SUMO | via SUMO | Abandoned since 2019 — skip |

## Recommendation

SUMO for v1, using **`libsumo` in-process for batch** and **TraCI for GUI/events**. Keep **MATSim** in reserve for activity-based regional demand; **watch MOSS** only if microscopic scale becomes the binding constraint.

Primary sources: SUMO docs (<https://sumo.dlr.de/docs/>), ChangeLog (<https://sumo.dlr.de/docs/ChangeLog.html>), Libsumo (<https://sumo.dlr.de/docs/Libsumo.html>), FCDOutput (<https://sumo.dlr.de/docs/Simulation/Output/FCDOutput.html>), GTFS import (<https://sumo.dlr.de/docs/Tools/Import/GTFS.html>), Meso (<https://sumo.dlr.de/docs/Simulation/Meso.html>).
