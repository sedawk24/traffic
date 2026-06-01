"""ETL step: land use -> zones (Phase 1, Task 5).

Planned: Metro 2050 regional land use as the base, overlaid with City of
Vancouver zoning detail and OSM landuse gap-fill, reclassified to
{residential, commercial, industrial, parkland, downtown-core}; mark gateway
zones; store polygons + centroids + population/employment weights in ``zones``
and export GeoJSON for the renderer. Will add: geopandas, shapely.
Not yet implemented.
"""

from __future__ import annotations


def run(args) -> int:
    raise NotImplementedError(
        "etl zoning: land use -> zones not implemented yet (Phase 1, Task 5). "
        "See docs/development/phases/phase-1.md."
    )
