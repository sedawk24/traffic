"""Paths, the peninsula cordon bbox, and the open-data source registry.

Centralises everything a loader needs to know about *where* things live and
*what* upstream data they come from (URL + licence, for the provenance record).
Geography is WGS84 (EPSG:4326) at rest, per the project conventions.
"""

from __future__ import annotations

from pathlib import Path

import sumolib

# --- Paths (everything under data/ is git-ignored) ---------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "traffic.db"
OSM_DIR = DATA_DIR / "osm"
SUMO_DIR = DATA_DIR / "sumo"
GTFS_DIR = DATA_DIR / "gtfs"
ZONES_DIR = DATA_DIR / "zones"

# --- Study area --------------------------------------------------------------
# Downtown Vancouver peninsula, cordoned at its bridges. (W, S, E, N) in WGS84.
# Deliberately a touch generous so the bridge landings come in as gateway edges:
# Lions Gate / Stanley Park Causeway (NW), Burrard / Granville / Cambie across
# False Creek (S), and the Georgia/Dunsmuir viaducts + Main St (E, out to ~Clark
# Dr). The exact cordon is trimmed during the manual netedit cleanup (Task 1).
PENINSULA_BBOX: tuple[float, float, float, float] = (-123.170, 49.262, -123.080, 49.320)

WGS84 = "EPSG:4326"

# --- Open-data source registry (cited by loaders in the `sources` table) ------
# Verified in docs/research/data-sources.md (2026-05-31). Attribution required.
SOURCES: dict[str, dict[str, str]] = {
    "osm": {
        "name": "OpenStreetMap",
        "url": "https://www.openstreetmap.org",
        "license": "ODbL",
    },
    "gtfs_translink": {
        "name": "TransLink GTFS static",
        "url": "https://gtfs-static.translink.ca/gtfs/google_transit.zip",
        "license": "TransLink Terms of Use (attribution required)",
    },
    "statcan_od": {
        "name": "StatCan 98-10-0459 (CSD-CSD commuting flows)",
        "url": "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=9810045901",
        "license": "Statistics Canada Open Licence",
    },
    "statcan_departure": {
        "name": "StatCan 98-10-0458 (time leaving for work x mode)",
        "url": "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=9810045801",
        "license": "Statistics Canada Open Licence",
    },
    "metro2050": {
        "name": "Metro 2050 regional land use",
        "url": "https://open-data-portal-metrovancouver.hub.arcgis.com/",
        "license": "OGL-Metro-Vancouver",
    },
    "cov_zoning": {
        "name": "City of Vancouver zoning districts and labels",
        "url": "https://opendata.vancouver.ca/explore/dataset/zoning-districts-and-labels/",
        "license": "OGL-Vancouver",
    },
    "cov_signals": {
        "name": "City of Vancouver traffic signals (locations)",
        "url": "https://opendata.vancouver.ca/explore/dataset/traffic-signals/",
        "license": "OGL-Vancouver",
    },
    "drivebc_open511": {
        "name": "DriveBC Open511 events",
        "url": "https://api.open511.gov.bc.ca/events",
        "license": "OGL-BC",
    },
}


# --- SUMO tool discovery (derived from the installed wheel, not $SUMO_HOME) ----
def sumo_home() -> Path:
    """SUMO installation root (``.../site-packages/sumo``)."""
    return Path(sumolib.checkBinary("netconvert")).resolve().parent.parent


def sumo_bin(name: str) -> Path:
    """Absolute path to a compiled SUMO binary (e.g. ``netconvert``)."""
    return Path(sumolib.checkBinary(name))


def sumo_tool(rel: str) -> Path:
    """Absolute path to a SUMO python tool (e.g. ``osmGet.py``)."""
    return sumo_home() / "tools" / rel
