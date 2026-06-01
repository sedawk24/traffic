# Phase 0 Research — Signal-Timing Approximation

**Problem:** the City of Vancouver does not publish signal timing plans (it sells timing reports to insurers/law firms). We must **approximate** urban signal timing and **calibrate** it against observed behavior rather than match exact plans.

**Recommended v1 approach (layered):** generate **actuated** signals everywhere from the OSM import, apply arterial **coordination**, and treat cycle/split/offset as **calibration knobs** against observed travel times and counts. This needs zero proprietary data.

---

## (a) Fixed-time defaults — Webster's method (fallback)

Optimal cycle length **C₀ = (1.5·L + 5) / (1 − Y)**, where `L` = total lost time per cycle (≈ sum of clearance intervals) and `Y` = sum of **critical-lane flow ratios** (v/s) across phases. Green time is split **proportional to each phase's critical flow ratio** (equi-saturation). Valid for undersaturated isolated intersections; degrades as Y→1. Use as the deterministic fallback where actuated control isn't appropriate.

## (b) SUMO fixed-time generation (`netconvert`)

Auto-builds programs with `--tls.cycle.time` (default 90s), green split equally between main phases, `--tls.yellow.time` (~3–4s, speed-derived), `--tls.layout opposites|incoming`, `--tls.left-green.time`, `--tls.allred.time`. The baseline if we don't go actuated.

## (c) Actuated heuristic — the recommended baseline

Set `type="actuated"` (or `--tls.default-type actuated`); replace fixed `duration` with **`minDur`/`maxDur`** and gap-based extension (`max-gap`, default 3s) on auto-generated detectors. Generate with, e.g.:

```
netconvert … --tls.default-type actuated --tls.min-dur 5 --tls.max-dur 50 \
             --tls.cycle.time 90 --tls.yellow.time 4 --tls.rebuild
```

This yields realistic, volume-responsive behavior with **no real plan required** (the OSM Web Wizard already defaults to actuated).

## (d) Coordinated green waves on arterials

Two SUMO tools, run in sequence on the network + a demand route file:

1. **`tlsCycleAdaptation.py`** — resizes **green splits** to the given demand (Webster-like), per intersection.
2. **`tlsCoordinator.py`** — sets **offsets** to create green waves along corridors (offset ≈ block_spacing / progression_speed).

Apply to the main arterials (e.g., Georgia, Burrard, Granville, Robson) after demand is realistic (Phase 4).

## (e) Calibration instead of exact plans

Since we can't validate against real timings, **calibrate network behavior to observed counts and travel times**:

- Feed census/Trip-Diary-derived OD; adjust signal/cycle parameters and route choice until simulated **link counts** match observed (GEH < 5 on most links) and **corridor travel times** are plausible.
- Use SUMO's **`routeSampler.py`** with edge/turn-count files to fit demand to counts; iterate timing as a calibration knob.
- Calibration data is limited (see `data-sources.md`): lean on BC MoTI bridge/highway counts and any scraped CoV station volumes; be explicit about coverage.

## Concrete v1 recipe

1. Import OSM → `netconvert … --tls.default-type actuated --tls.min-dur 5 --tls.max-dur 50 --tls.cycle.time 90 --tls.yellow.time 4`.
2. Build demand from **StatCan 98-10-0459** (OD) shaped by **98-10-0458** (departure times). *(Phase 4)*
3. Run `tlsCycleAdaptation.py` then `tlsCoordinator.py` on main arterials.
4. Calibrate cycle/offset + demand against obtainable counts and observed travel times. *(Phase 6)*

References: SUMO Traffic Lights (<https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html>), tls tools (<https://sumo.dlr.de/docs/Tools/tls.html>), Webster's formula (<https://www.apsed.in/post/traffic-signal-design-webster-s-formula-for-optimum-cycle-length>).
