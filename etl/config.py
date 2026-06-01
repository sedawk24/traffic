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

# Peninsula cordon polygon (clockwise), WGS84 (lon, lat). Traces the shoreline
# out over the water and crosses each bridge at its cut point — Lions Gate /
# Stanley Park Causeway (NW), and Burrard / Granville / Cambie across False Creek
# (S) — with an east land screenline at ~Clark Dr. Fed to netconvert's
# --keep-edges.in-geo-boundary to trim the raw OSM net down to the peninsula.
# Edit these vertices to refine the cordon.
CORDON_POLYGON: list[tuple[float, float]] = [
    (-123.144, 49.321),  # Lions Gate cut (First Narrows, N of Prospect Point)
    (-123.118, 49.307),  # inlet, NE of Brockton Point
    (-123.108, 49.300),  # inlet N of Coal Harbour
    (-123.098, 49.296),  # inlet N of Canada Place / Gastown
    (-123.085, 49.294),  # inlet NE near CRAB Park / port
    (-123.080, 49.288),  # NE corner (~Clark Dr at the waterfront)
    (-123.080, 49.273),  # E screenline (~Clark Dr) down to the False Creek head
    (-123.098, 49.270),  # head of False Creek (Science World)
    (-123.108, 49.269),  # Cambie Bridge cut
    (-123.130, 49.269),  # Granville Bridge cut
    (-123.142, 49.270),  # Burrard Bridge cut (toward Kits Point)
    (-123.150, 49.283),  # English Bay, W of the West End shore
    (-123.156, 49.298),  # Stanley Park W shore (Third Beach)
    (-123.160, 49.307),  # Stanley Park NW (Siwash Rock)
    (-123.150, 49.316),  # approach to Prospect Point
]

WGS84 = "EPSG:4326"

# --- Metro-wide study area (Phase 7) -----------------------------------------
# Core urbanized Metro Vancouver (Greater Vancouver RD). (W, S, E, N) in WGS84,
# spanning the North Shore, Vancouver/UBC, Richmond + airport, Burnaby, New West,
# the Tri-Cities, and north Surrey/Delta — with the major regional crossings
# (Lions Gate, Ironworkers, Knight/Oak/Laing, Queensborough, Pattullo, Alex
# Fraser, Massey, Port Mann). Run mesoscopically; the major road network only.
METRO_BBOX: tuple[float, float, float, float] = (-123.28, 49.00, -122.70, 49.37)
# OSM highway types kept for the regional meso net (arterials + highways). Minor
# residential streets are dropped — regional demand loads onto the arterial grid,
# which is standard for a mesoscopic regional model and keeps the net tractable.
METRO_ROAD_TYPES = [
    "motorway", "motorway_link", "trunk", "trunk_link",
    "primary", "primary_link", "secondary", "secondary_link",
    "tertiary", "tertiary_link",
]

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
    "cov_parks": {
        "name": "City of Vancouver parks (polygon representation)",
        "url": "https://opendata.vancouver.ca/explore/dataset/parks-polygon-representation/",
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
    "bridge_counts_published": {
        "name": "Published bridge AADT (calibration screenlines)",
        "url": "https://www.th.gov.bc.ca/trafficdata/",
        "license": "Published estimates (Wikipedia/CoV/MoTI; verify vs MoTI TRADAS)",
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


def cordon_geo_boundary() -> str:
    """``CORDON_POLYGON`` as the flat ``lon,lat,...`` CSV netconvert expects."""
    return ",".join(f"{lon},{lat}" for lon, lat in CORDON_POLYGON)
