"""ETL step: StatCan census -> OD + departure profiles (Phase 1, Task 3/4).

Planned: load 98-10-0459 (CSD->CSD commuting flows) into ``od_flows`` and
98-10-0458 (time-leaving-for-work x mode) into ``departure_profiles``, handling
base-5 random rounding and <40 suppression (smooth/aggregate sparse cells).
Will add: pandas, requests. Not yet implemented.
"""

from __future__ import annotations


def run(args) -> int:
    raise NotImplementedError(
        "etl census: StatCan OD + departure profiles not implemented yet "
        "(Phase 1, Task 3). See docs/development/phases/phase-1.md."
    )
