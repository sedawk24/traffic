"""Simulation runner for the Greater Vancouver Traffic Simulator (Phase 2+).

Generates demand, runs a scenario in SUMO via ``libsumo`` (emitting sampled geo
FCD as Parquet), post-processes the FCD into a per-vehicle trajectory Parquet,
and registers the run in SQLite. See ``sim.cli`` (``uv run python -m sim run``).
"""

__all__: list[str] = []
