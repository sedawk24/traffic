"""ETL step: land use -> zones (Phase 1, Task 5).

The peninsula sits entirely within the City of Vancouver, so CoV's detailed
zoning is the primary land-use source; CoV parks supply parkland (parks are not
zoned); and a handful of virtual *gateway* zones mark the bridge crossings where
external demand enters/leaves the cordon. Metro 2050 regional land use is the
base for the later region-wide expansion and is not needed for the peninsula.

Output: rows in `zones` (clipped to the cordon, reclassified to
{residential, commercial, industrial, parkland, downtown-core} plus gateways)
and data/zones/zones.geojson for the renderer. Idempotent — each managed source
(cov_zoning, cov_parks, gateways) is replaced wholesale on re-run.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point, Polygon, mapping

from etl import config, db

ZONING_URL = "https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/zoning-districts-and-labels/exports/geojson"
PARKS_URL = "https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/parks-polygon-representation/exports/geojson"

# CoV zoning_category -> our five land-use classes. Peninsula-appropriate
# heuristic: CD (Comprehensive Development) is the dominant high-density,
# mixed-use downtown fabric here, so it maps to downtown-core (refine when
# expanding city-wide — see backlog).
_DOWNTOWN = {"DD", "CWD", "DEOD", "BCPED", "CD", "HA", "FM", "FSD"}
_INDUSTRIAL = {"I", "M", "IC"}
_COMMERCIAL = {"C", "MC"}

# Virtual gateway zones at the bridge crossings (id, label, lon, lat). External
# origins/destinations attach here in Phase 4; positions are approximate anchors.
# Coordinates are centroids of the named OSM bridge/viaduct ways (data-grounded).
GATEWAYS = [
    ("gw_lions_gate", "Lions Gate Bridge", -123.1362, 49.3181),
    ("gw_burrard_bridge", "Burrard Bridge", -123.1387, 49.2749),
    ("gw_granville_bridge", "Granville Bridge", -123.1357, 49.2704),
    ("gw_cambie_bridge", "Cambie Bridge", -123.1149, 49.2712),
    ("gw_georgia_viaduct", "Georgia / Dunsmuir Viaducts", -123.1066, 49.2778),
    ("gw_east_arterials", "East gateways (Hastings Viaduct)", -123.0823, 49.2810),
]


def reclassify_zoning(category: str | None) -> str:
    """Map a CoV zoning_category code to one of the five land-use classes."""
    c = (category or "").upper().strip()
    if c in _DOWNTOWN or c.startswith("FC"):
        return "downtown-core"
    if c in _INDUSTRIAL:
        return "industrial"
    if c in _COMMERCIAL:
        return "commercial"
    if c.startswith("R"):
        return "residential"
    return "commercial"  # unknown mixed-use codes default to commercial


def _download(url: str, dst: Path, refresh: bool) -> Path:
    if dst.exists() and dst.stat().st_size > 0 and not refresh:
        print(f"  cached: {dst.name} ({dst.stat().st_size:,} bytes)")
        return dst
    import requests

    dst.parent.mkdir(parents=True, exist_ok=True)
    print(f"  GET {url}")
    resp = requests.get(url, timeout=180)
    resp.raise_for_status()
    dst.write_bytes(resp.content)
    print(f"  saved: {dst} ({len(resp.content):,} bytes)")
    return dst


def _clip(path: Path, cordon: Polygon) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)
    gdf = gdf[gdf.geometry.notna() & gdf.geometry.is_valid]
    gdf = gpd.clip(gdf, cordon)
    return gdf[~gdf.geometry.is_empty & gdf.geometry.notna()]


def _zone(zone_id, name, land_use, geom, source, is_gateway=0, category=None) -> dict:
    rp = geom.representative_point()
    # Missing CoV names arrive as float NaN (and `NaN or "park"` keeps NaN, since
    # NaN is truthy); normalise to None so the exported GeoJSON is valid JSON.
    name = None if (name is None or (isinstance(name, float) and name != name)) else str(name)
    return {
        "zone_id": zone_id,
        "name": name,
        "land_use": land_use,
        "category": category,
        "is_gateway": is_gateway,
        "source": source,
        "centroid_lon": rp.x,
        "centroid_lat": rp.y,
        "geometry": mapping(geom),
    }


def _load_zoning(path: Path, cordon: Polygon) -> list[dict]:
    gdf = _clip(path, cordon)
    out = []
    for i, (_, r) in enumerate(gdf.iterrows()):
        cat = r.get("zoning_category")
        out.append(
            _zone(
                f"cov_zone_{i:04d}",
                r.get("zoning_district") or cat,
                reclassify_zoning(cat),
                r.geometry,
                "cov_zoning",
                category=cat,
            )
        )
    return out


def _load_parks(path: Path, cordon: Polygon) -> list[dict]:
    gdf = _clip(path, cordon)
    return [
        _zone(
            f"cov_park_{i:04d}",
            r.get("park_name") or "park",
            "parkland",
            r.geometry,
            "cov_parks",
        )
        for i, (_, r) in enumerate(gdf.iterrows())
    ]


def _load_gateways() -> list[dict]:
    return [
        _zone(zid, name, "gateway", Point(lon, lat), "gateways", is_gateway=1)
        for zid, name, lon, lat in GATEWAYS
    ]


def _write_db(zones: list[dict]) -> None:
    conn = db.connect()
    db.init_db(conn)
    conn.execute("DELETE FROM zones WHERE source IN ('cov_zoning', 'cov_parks', 'gateways')")
    conn.executemany(
        """INSERT INTO zones(zone_id, name, land_use, geometry, centroid_lon, centroid_lat,
                             population, employment, is_gateway, source)
           VALUES(:zone_id, :name, :land_use, :geometry_text, :centroid_lon, :centroid_lat,
                  NULL, NULL, :is_gateway, :source)""",
        [
            {
                "zone_id": z["zone_id"],
                "name": z["name"],
                "land_use": z["land_use"],
                "geometry_text": json.dumps(z["geometry"]),
                "centroid_lon": z["centroid_lon"],
                "centroid_lat": z["centroid_lat"],
                "is_gateway": z["is_gateway"],
                "source": z["source"],
            }
            for z in zones
        ],
    )
    today = date.today().isoformat()
    for key, source in (("cov_zoning", "cov_zoning"), ("cov_parks", "cov_parks")):
        db.record_source(
            conn, key, extract_date=today, row_count=sum(1 for z in zones if z["source"] == source)
        )
    conn.commit()
    conn.close()


def _export_geojson(zones: list[dict], out: Path) -> Path:
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "zone_id": z["zone_id"],
                    "name": z["name"],
                    "land_use": z["land_use"],
                    "is_gateway": z["is_gateway"],
                    "source": z["source"],
                },
                "geometry": z["geometry"],
            }
            for z in zones
        ],
    }
    out.write_text(json.dumps(fc))
    return out


def _summary(zones: list[dict]) -> None:
    from collections import Counter

    by_use = Counter(z["land_use"] for z in zones)
    print("  by land use:", dict(sorted(by_use.items())))
    # zoning category -> class, to surface any default-mapped (unknown) codes
    cats = Counter((z["category"], z["land_use"]) for z in zones if z["source"] == "cov_zoning")
    print("  zoning category -> class:")
    for (cat, cls), n in sorted(cats.items(), key=lambda kv: -kv[1]):
        print(f"    {str(cat):8s} -> {cls:14s} {n}")


def run(args) -> int:
    area = getattr(args, "area", "peninsula")
    print(f"=== etl zoning: land use -> zones ({area}) ===")
    refresh = getattr(args, "refresh", False)
    config.ZONES_DIR.mkdir(parents=True, exist_ok=True)

    zoning_path = _download(ZONING_URL, config.ZONES_DIR / "cov_zoning.geojson", refresh)
    parks_path = _download(PARKS_URL, config.ZONES_DIR / "cov_parks.geojson", refresh)

    if area == "peninsula":
        clip, gateways, out_file = Polygon(config.CORDON_POLYGON), _load_gateways(), "zones.geojson"
    else:
        from shapely.geometry import box

        w, s, e, n = {"central": config.CENTRAL_BBOX, "vancouver": config.VANCOUVER_BBOX}.get(
            area, config.CENTRAL_BBOX
        )
        clip, gateways, out_file = box(w, s, e, n), [], f"{area}_zones.geojson"

    zones = _load_zoning(zoning_path, clip) + _load_parks(parks_path, clip) + gateways
    if area != "peninsula":
        # CD (Comprehensive Development) blanket-maps to downtown-core, which is
        # right downtown but wrong on the West Side (most CD there is residential).
        # Keep downtown-core only inside the actual downtown peninsula.
        dw, ds, de, dn = -123.145, 49.268, -123.095, 49.295
        for z in zones:
            if z["land_use"] == "downtown-core" and not (
                dw <= z["centroid_lon"] <= de and ds <= z["centroid_lat"] <= dn
            ):
                z["land_use"] = "residential"
    out = _export_geojson(zones, config.ZONES_DIR / out_file)
    if area == "peninsula":  # only the calibrated peninsula populates the zones table
        _write_db(zones)

    n_gw = sum(z["is_gateway"] for z in zones)
    print(f"  zones: {len(zones)} ({n_gw} gateways) -> {out}")
    _summary(zones)
    return 0
