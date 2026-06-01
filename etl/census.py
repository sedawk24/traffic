"""ETL step: StatCan 2021 census -> OD flows + departure profiles (Task 4).

  * 98-10-0459 (commuting flow, residence CSD -> place of work) -> `od_flows`
  * 98-10-0458 (time leaving for work x main mode) -> `departure_profiles`

Both are full-Canada tables (~300/490 MB zipped), so we stream them in chunks
and keep only Greater Vancouver (census division 5915). OD origins are keyed by
their 7-digit CSD code (DGUID[9:]); destinations keep their full "place of work"
name (the source gives no destination code, and names like "Langley"/"North
Vancouver" are ambiguous without the type qualifier). Suppressed / non-numeric
cells are dropped. Idempotent: each source's rows are replaced on re-run.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from etl import config, db, util

OD_PID, DEP_PID = "98100459", "98100458"
OD_URL = f"https://www150.statcan.gc.ca/n1/tbl/csv/{OD_PID}-eng.zip"
DEP_URL = f"https://www150.statcan.gc.ca/n1/tbl/csv/{DEP_PID}-eng.zip"
GVRD = "5915"  # Greater Vancouver census division (SGC code prefix)


def _gvrd_chunks(zf: zipfile.ZipFile, member: str, usecols: list[str]):
    """Yield the chunks of a StatCan CSV whose rows are in Greater Vancouver.

    The tables are sorted by geography, so once we have passed the 5915 block we
    stop reading the (multi-GB) remainder.
    """
    import pandas as pd

    seen = False
    for chunk in pd.read_csv(zf.open(member), chunksize=300_000, dtype=str, usecols=usecols):
        gv = chunk[chunk["DGUID"].str.slice(9).str.startswith(GVRD)]
        if len(gv):
            seen = True
            yield gv
        elif seen:
            return


def load_od(zip_path: Path, conn) -> int:
    import pandas as pd

    val = "Gender (3):Total - Gender[1]"
    with zipfile.ZipFile(zip_path) as zf:
        parts = list(_gvrd_chunks(zf, f"{OD_PID}.csv", ["GEO", "DGUID", "Place of work", val]))
    od = pd.concat(parts, ignore_index=True)

    gvrd_names = set(od["GEO"].str.strip().unique())  # the 38 GVRD CSD short names
    dest = od["Place of work"].fillna("")
    dest_base = dest.str.split(" (", regex=False).str[0].str.strip()
    keep = dest.str.contains(", B.C.", regex=False) & dest_base.isin(gvrd_names)

    od = od[keep].copy()
    od["origin"] = od["DGUID"].str.slice(9)
    od["destination"] = od["Place of work"]
    od["count"] = pd.to_numeric(od[val], errors="coerce")
    od = od.dropna(subset=["count"])
    od = od[od["count"] > 0]

    conn.execute("DELETE FROM od_flows WHERE source = 'statcan_od'")
    conn.executemany(
        """INSERT OR IGNORE INTO od_flows(origin, destination, mode, count, period, source)
           VALUES(?, ?, 'all', ?, 'commute_2021', 'statcan_od')""",
        list(zip(od["origin"], od["destination"], od["count"].astype(int))),
    )
    conn.commit()
    return len(od)


def load_departures(zip_path: Path, conn) -> int:
    import pandas as pd

    val = "Commuting duration (7):Total - Commuting duration[1]"
    cols = [
        "GEO",
        "DGUID",
        "Time leaving for work (7)",
        "Age (15A)",
        "Gender (3)",
        "Statistics (3)",
        "Main mode of commuting (11A)",
        val,
    ]
    kept = []
    with zipfile.ZipFile(zip_path) as zf:
        for gv in _gvrd_chunks(zf, f"{DEP_PID}.csv", cols):
            m = gv[
                (gv["Statistics (3)"] == "Count")
                & (gv["Age (15A)"] == "Total - Age")
                & (gv["Gender (3)"] == "Total - Gender")
            ]
            if len(m):
                kept.append(m)
    dep = pd.concat(kept, ignore_index=True)
    dep["geography"] = dep["DGUID"].str.slice(9)
    dep["value"] = pd.to_numeric(dep[val], errors="coerce")
    dep = dep.dropna(subset=["value"])

    conn.execute("DELETE FROM departure_profiles WHERE source = 'statcan_departure'")
    conn.executemany(
        """INSERT OR IGNORE INTO departure_profiles(geography, mode, time_bin, metric, value, source)
           VALUES(?, ?, ?, 'count', ?, 'statcan_departure')""",
        list(
            zip(
                dep["geography"],
                dep["Main mode of commuting (11A)"],
                dep["Time leaving for work (7)"],
                dep["value"].astype(int),
            )
        ),
    )
    conn.commit()
    return len(dep)


def run(args) -> int:
    print("=== etl census: StatCan OD + departure profiles (Greater Vancouver) ===")
    refresh = getattr(args, "refresh", False)
    od_zip = util.download_file(OD_URL, config.DATA_DIR / "census" / f"od_{OD_PID}.zip", refresh)
    dep_zip = util.download_file(
        DEP_URL, config.DATA_DIR / "census" / f"departure_{DEP_PID}.zip", refresh
    )

    conn = db.connect()
    db.init_db(conn)
    print("  streaming OD table (filtering to Greater Vancouver)...")
    n_od = load_od(od_zip, conn)
    print(f"  od_flows: {n_od} intra-GVRD CSD->CSD commute flows")
    print("  streaming departure table...")
    n_dep = load_departures(dep_zip, conn)
    print(f"  departure_profiles: {n_dep} rows (CSD x time-leaving x mode)")

    db.record_source(
        conn, "statcan_od", extract_date="2021-11-30", row_count=n_od, notes="98-10-0459 intra-GVRD"
    )
    db.record_source(
        conn,
        "statcan_departure",
        extract_date="2021-11-30",
        row_count=n_dep,
        notes="98-10-0458 GVRD",
    )
    conn.commit()
    conn.close()
    return 0
