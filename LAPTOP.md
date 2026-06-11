# Running the laptop bundle

A trimmed copy of the Vancouver traffic simulator: full code + the `central`
study area + the two showcase runs (#40 `central_final` = the old scale-0.05
deliverable, and `central_v2` = the Phase-9 scale-0.10 rush hour). Heavy
intermediates (raw FCD, sweep runs, OSM extracts, other study areas) are
excluded — rebuild them with the usual `etl`/`sim` commands if needed.

## Run it

```bash
# prerequisites: uv (https://docs.astral.sh/uv/) and internet on first start
uv sync                       # installs python deps incl. SUMO (~a few min, once)
uv run uvicorn api.main:app   # http://127.0.0.1:8000
```

Open http://127.0.0.1:8000 — pick a run top-left (`central_v2` is the new
showcase). Internet is needed for the basemap tiles + JS CDNs (the simulation
replay itself is fully local).

Good views:
- `/?run=<v2-id>&t=4500` — mid rush hour, flow view; zoom in anywhere on the grid
- click a **Worst intersections** row to fly to a jam; click a car to follow it;
  press **3D**; space = play/pause, ←/→ scrub, ↑/↓ speed

## What's NOT here

- raw `fcd.parquet` per run (only needed for `sim diagnose` / `sim calibrate` —
  re-running `sim run` regenerates everything)
- `data/runs/sweeps/` measurement runs, duaIterate intermediates, OSM extracts,
  and the `peninsula`/`vancouver`/`metro` nets + their runs (rebuild via
  `uv run python -m etl network --area <a>` etc.)
