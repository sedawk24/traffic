"""ETL pipeline for the Greater Vancouver Traffic Simulator (Phase 1).

Turns open data into SUMO-ready inputs + a SQLite database of structured data
for the downtown Vancouver peninsula. Each loader is a small, idempotent CLI
step (see ``etl.cli``); re-running a loader reproduces the same DB state and
records its source + extract date for provenance.
"""

__all__: list[str] = []
