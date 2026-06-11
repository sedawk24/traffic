# Phase 9 — Intersection Capacity v2 + Dark-Cinematic Viewer

## Why

Three user-visible problems with the Phase-8c showcase (run #40, `central`, scale 0.05):

1. **Too little visible traffic at street zoom.** The run sits at scale 0.05 because the auto-generated net gridlocks above ~0.06 (the Phase-8c measured intersection-throughput ceiling). More traffic = honestly raising that ceiling.
2. **Terrible jams at specific intersections** — signal/connection pathology at chokepoints.
3. **Lackluster look & interface** — one-file viewer, dark panels on a light generic basemap, rectangle-glyph cars.

Direction (user-confirmed): dark-cinematic visuals; `central` area first; *realistic congested peak* (no fake density); extras: 3D buildings + tilt, follow-vehicle, hotspot panel.

## Phase A — Diagnostics first (DONE)

- **`sim diagnose --run <name>`** (`sim/diagnose.py`): ranks junctions by stopped vehicle-hours from the run's raw FCD — per-edge stopped time attributed to the downstream junction, internal-lane stops attributed directly, names recovered from the cached OSM extract (the net itself carries no street names yet), each junction cross-referenced against the **real City of Vancouver signal inventory** (kind = Fixed Time / Semi Actuated / Ped Actuated / RRFB / …). Emits console table + `hotspots.json`/`.geojson` per run.
- **`etl signals --area central|vancouver`**: the CoV city-wide signal dataset (966 locations) loaded per area with the new `kind` column (`signals` table migration); peninsula behaviour unchanged.
- **librun**: every run now also emits `edgedata.xml` (5-min per-edge aggregates), `stats.xml` (teleports etc.), `summary.xml` (60 s network curve) for the sweep harness.
- **API**: `GET /api/runs/{id}/hotspots`.

### What the diagnosis of run #40 found (gate met)

- Net has **700 signalized junction nodes vs ~298 real CoV vehicle signals** in the bbox (164 ped-actuated + RRFB + crosswalks; **250 net TLS have no CoV device at all**) — structural over-signalization.
- **The top-15 jams hold 32% of all stopped time (1,757 veh·h).** Ranks 1–4, 7, 9, 12–15 form one standing queue along Main/Hastings/Powell/Gore (Chinatown): the demand model funnels ALL eastern-region OD (Burnaby/Surrey/Tri-Cities/...) into each CSD's **K=80 nearest edges** — i.e. the NE-corner side streets. A demand-gateway artifact, not signal timing.
- Several **priority junctions** show 440–790 s stopped *per vehicle*: arterials blocked mid-corridor (spillback victims of the funnel) and minor-cross-arterial moves that never find a gap — the equilibrium was computed under **meso** dynamics (no real priority-junction friction), then replayed micro.
- The 250 bogus TLS are *not* in the top-15 — they are distributed drag that binds at higher scale, not the visible mega-jams.

## Phase B — Network capacity v2 (measurement-gated)

Harness: **`sim sweep`** (scale ladder, fixed seed; mean km/h FCD-weighted, %stopped, peak active, completed, teleports, avg wait → `data/runs/sweeps/<tag>.json`). Baseline V0 = current net. Keep a variant iff at scale 0.075: mean speed +≥5 % or %stopped −≥3 pts, teleports not worse.

Variant ladder (re-ranked after Phase A):
1. **V1 gateway realism (demand)** — external CSDs enter on **boundary-crossing arterials** (capacity- and inverse-distance-weighted pools) instead of the 80 nearest side-street edges. Targets the Chinatown funnel directly.
2. **V2 signal ground-truthing (net)** — `etl/signal_truth.py` → `--tls.unset` for net TLS whose nearest CoV device is ped-only or absent; `--tls.set` for CoV vehicle signals missing a net TLS. Raises the structural ceiling.
3. **V3 turn lanes** — `--osm.turn-lanes true` (left-turn pockets where OSM tags them).
4. **V4 insertion attrs** — `departLane="best" departSpeed="max" departPos="random_free"`.
5. **V5 home-end realism** — intra-city trip ends keep off the highest-class arterial mid-blocks.
6. **V6 equilibrium realism** — `sim equilibrium` wrapper (duaIterate) with **`--meso-junction-control`** so priority/signal friction prices routes; percent-sample down (the p33 pattern). `sim retime` wrapper re-runs tlsCoordinator on the new net/routes.
7. **V7 bus A/B** — `--no-transit` sweep; bus-bay (`parking="true"`) stops if in-lane dwells cost >10 % mean speed.
8. Residual topology offenders (W 16th Ave cluster etc.): `--junctions.join-dist`, netdiff hand-fix as last resort.

Final cascade: `etl network --area central` (+ `--output.street-names`) → `etl transit --area central` → `etl signals --area central` → `sim equilibrium` → `sim retime` → ceiling sweep → showcase run `central_v2` at the new S\* → `sim calibrate` (Granville/Cambie GEH < 5) → `sim diagnose` (before/after).

**Ceiling S\***: max scale with mean ≥ 15 km/h, %stopped ≤ 45 %, teleports ≈ 0. Success = 0.075 flowing (peak ≥ ~3,500 on-road, +50 % vs run #40); stretch 0.10.

## Phase C — Viewer overhaul (dark cinematic)

`web/` → ES modules (no build step): `index.html` + `css/app.css` + `js/{config,api,state,basemap,atlas,layers,playback,hud,main}.js`. Dark basemap (runtime recolor of positron; openfreemap `dark` style if it exists), glow volume ribbons (additive 2-pass), sprite atlas v2 (car/bus/truck/van, meter-true sizes, per-vehicle hue jitter), trails on by default, signal halos, LOD 13.2→12.6, road tooltips (street names), top bar + right rail (Layers/Legend/Stats live) + bottom timeline with active-vehicle histogram, keyboard shortcuts, fixed run-selector area tags. API: `name` in network props (cache bump `_edges_v2`), `vid` in `/trips`, new `/timeline`, `/api/signals?area=`.

## Phase D — Extras + verification

3D buildings (fill-extrusion ≥ z15) + pitch toggle; follow-vehicle (click, chase-cam, Esc); hotspot panel (`/hotspots` → ranked list, flyTo + pulse ring); `scripts/screenshot.py` + `scripts/smoke_viewer.py` (playwright dev dep). Before/after screenshots in `docs/images/`.

## Verification

1. **More traffic**: sweep table proves S\* ≥ 0.075 flowing → peak on-road ≥ ~3,500 (vs 2,370); identical-viewport before/after screenshots.
2. **Chokepoints**: old top-10 stop veh·h −≥40 %, no new junction worse than old #1; 0.075 mean speed 11 → ≥15 km/h; GEH holds.
3. **Look/UI**: smoke green + interaction checklist + screenshot set.
