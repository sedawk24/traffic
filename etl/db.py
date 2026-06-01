"""SQLite connection, idempotent schema init, and the provenance helper.

The schema lives in ``schema.sql`` (all ``CREATE ... IF NOT EXISTS``), so
``init_db`` is safe to call at the start of every step.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from etl import config

SCHEMA_SQL = Path(__file__).resolve().parent / "schema.sql"
SCHEMA_VERSION = 1


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open the project DB with sane pragmas (FK enforcement, WAL, Row rows)."""
    path = Path(db_path) if db_path else config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create the schema if absent and stamp the schema version. Idempotent."""
    conn.executescript(SCHEMA_SQL.read_text())
    conn.execute(
        "INSERT INTO meta(key, value) VALUES('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


def record_source(
    conn: sqlite3.Connection,
    key: str,
    *,
    extract_date: str | None = None,
    notes: str | None = None,
    row_count: int | None = None,
    sha256: str | None = None,
) -> None:
    """Upsert a provenance row from the ``config.SOURCES`` registry by key.

    ``extract_date`` is the stable upstream-extract date; ``fetched_at`` is an
    audit timestamp (intentionally volatile, so it is excluded from any
    "identical DB" content comparison).
    """
    src = config.SOURCES[key]
    conn.execute(
        """INSERT INTO sources(name, url, license, extract_date, fetched_at,
                               notes, row_count, sha256)
           VALUES(?, ?, ?, ?, datetime('now'), ?, ?, ?)
           ON CONFLICT(name) DO UPDATE SET
             url=excluded.url, license=excluded.license,
             extract_date=excluded.extract_date, fetched_at=excluded.fetched_at,
             notes=excluded.notes, row_count=excluded.row_count,
             sha256=excluded.sha256""",
        (src["name"], src["url"], src["license"], extract_date, notes, row_count, sha256),
    )
    conn.commit()


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Row count per user table (for ``etl status``)."""
    names = [
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    return {n: conn.execute(f"SELECT count(*) FROM {n}").fetchone()[0] for n in names}
