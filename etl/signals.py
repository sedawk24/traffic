"""ETL step: City of Vancouver signal locations -> signals (Phase 1, Task 6).

Planned: load the CoV ``traffic-signals`` locations into ``signals`` and map
each to a SUMO TLS id where one exists (nearest-junction match against the built
net). Timing is not published, so only locations are ingested (see
docs/research/signal-timing.md). Will add: requests. Not yet implemented.
"""

from __future__ import annotations


def run(args) -> int:
    raise NotImplementedError(
        "etl signals: CoV signal locations not implemented yet (Phase 1, Task 6). "
        "See docs/development/phases/phase-1.md."
    )
