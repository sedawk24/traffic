"""FastAPI backend for the Greater Vancouver Traffic Simulator (Phase 2+).

Serves the road network and land-use zones as GeoJSON, and per-run trajectory
traces as Apache Arrow (optionally windowed/strided by time), plus the static
viewer. Run with: ``uv run uvicorn api.main:app --reload``.
"""

__all__: list[str] = []
