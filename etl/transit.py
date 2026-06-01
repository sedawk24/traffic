"""ETL step: TransLink GTFS static -> SUMO public-transport (Phase 1, Task 3).

Planned: download the GTFS zip, run ``gtfs2pt.py --modes bus,tram,subway,rail``
against ``peninsula.net.xml`` to emit stops (``.add.xml``) + vehicles
(``.rou.xml``), and hand-tune vTypes (capacity). Will add: requests.
Not yet implemented.
"""

from __future__ import annotations


def run(args) -> int:
    raise NotImplementedError(
        "etl transit: GTFS -> SUMO pt not implemented yet (Phase 1, Task 3). "
        "See docs/development/phases/phase-1.md."
    )
