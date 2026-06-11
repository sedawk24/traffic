-- SQLite schema for the Greater Vancouver Traffic Simulator ETL (Phase 1).
-- Every table uses CREATE TABLE IF NOT EXISTS so init is idempotent.
-- Geometry is stored as GeoJSON text (no SpatiaLite dependency); spatial ops
-- happen in geopandas. WGS84 (EPSG:4326) at rest.

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- Provenance registry: every loader records its source + extract date here.
CREATE TABLE IF NOT EXISTS sources (
    name         TEXT PRIMARY KEY,
    url          TEXT,
    license      TEXT,
    extract_date TEXT,            -- ISO date of the upstream extract
    fetched_at   TEXT,            -- when this row was last written (audit; volatile)
    notes        TEXT,
    row_count    INTEGER,
    sha256       TEXT
);

-- One row per built SUMO network (the peninsula now; the region later).
CREATE TABLE IF NOT EXISTS network (
    name            TEXT PRIMARY KEY,
    net_path        TEXT NOT NULL,
    osm_path        TEXT,
    bbox_w          REAL, bbox_s REAL, bbox_e REAL, bbox_n REAL,
    proj            TEXT,
    n_edges         INTEGER,
    n_junctions     INTEGER,
    n_tls           INTEGER,
    netconvert_args TEXT,
    source          TEXT,
    created_at      TEXT
);

-- Traffic-analysis zones (land use + demand weights). Geometry/centroid in WGS84.
CREATE TABLE IF NOT EXISTS zones (
    zone_id      TEXT PRIMARY KEY,
    name         TEXT,
    land_use     TEXT,            -- residential|commercial|industrial|parkland|downtown-core
    geometry     TEXT,            -- GeoJSON geometry
    centroid_lon REAL,
    centroid_lat REAL,
    population   REAL,
    employment   REAL,
    is_gateway   INTEGER DEFAULT 0,
    source       TEXT
);

-- Origin-destination commuting flows (StatCan 98-10-0459 to start; CSD->CSD).
CREATE TABLE IF NOT EXISTS od_flows (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    origin      TEXT NOT NULL,
    destination TEXT NOT NULL,
    mode        TEXT,
    count       INTEGER,
    period      TEXT,             -- e.g. 'commute'
    source      TEXT,
    UNIQUE(origin, destination, mode, period, source)
);

-- Departure-time / mode profiles (StatCan 98-10-0458 'time leaving for work').
CREATE TABLE IF NOT EXISTS departure_profiles (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    geography TEXT NOT NULL,      -- CSD / CD code
    mode      TEXT,
    time_bin  TEXT,               -- e.g. '07:00-07:29'
    metric    TEXT,               -- 'count' | 'share'
    value     REAL,
    source    TEXT,
    UNIQUE(geography, mode, time_bin, metric, source)
);

-- Traffic-signal locations (City of Vancouver); mapped to SUMO TLS where possible.
-- kind = the CoV signal type (Fixed Time / Semi Actuated / Fully Actuated /
-- Pedestrian Actuated Signal / RRFB / ...), used to ground-truth which net
-- junctions deserve a vehicle signal (Phase 9).
CREATE TABLE IF NOT EXISTS signals (
    signal_id   TEXT PRIMARY KEY,
    name        TEXT,
    lon         REAL,
    lat         REAL,
    sumo_tls_id TEXT,
    kind        TEXT,
    source      TEXT
);

-- Scenarios = a network + a set of injected events.
CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT UNIQUE NOT NULL,
    description  TEXT,
    base_network TEXT,
    created_at   TEXT
);

-- Events injected mid-run via TraCI (closures, accidents, speed drops).
CREATE TABLE IF NOT EXISTS events (
    event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id INTEGER REFERENCES scenarios(scenario_id),
    kind        TEXT,             -- closure|accident|speed|stop
    target      TEXT,             -- edge id
    lane        TEXT,
    start_s     INTEGER,
    end_s       INTEGER,
    params      TEXT,             -- JSON
    source      TEXT
);

-- Run registry: one row per executed simulation, referencing its trace.
CREATE TABLE IF NOT EXISTS runs (
    run_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id  INTEGER REFERENCES scenarios(scenario_id),
    status       TEXT,            -- queued|running|done|failed
    started_at   TEXT,
    finished_at  TEXT,
    trace_path   TEXT,
    sumo_version TEXT,
    params       TEXT,            -- JSON
    notes        TEXT
);

-- Calibration targets (observed) + results (simulated vs observed, GEH).
CREATE TABLE IF NOT EXISTS calibration_targets (
    target_id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind      TEXT,               -- count|travel_time
    location  TEXT,
    period    TEXT,
    observed  REAL,
    unit      TEXT,
    source    TEXT
);

CREATE TABLE IF NOT EXISTS calibration_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER REFERENCES runs(run_id),
    target_id   INTEGER REFERENCES calibration_targets(target_id),
    simulated   REAL,
    geh         REAL,
    computed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_od_origin ON od_flows(origin);
CREATE INDEX IF NOT EXISTS idx_od_dest ON od_flows(destination);
CREATE INDEX IF NOT EXISTS idx_dep_geo ON departure_profiles(geography);
CREATE INDEX IF NOT EXISTS idx_events_scenario ON events(scenario_id);
