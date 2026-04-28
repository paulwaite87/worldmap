-- Enable PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

-- Core ship static data (The Cache)
CREATE TABLE IF NOT EXISTS ships (
    mmsi VARCHAR(20) PRIMARY KEY,
    name VARCHAR(255),
    vessel_type INTEGER,
    imo INTEGER,
    callsign VARCHAR(50),
    draught NUMERIC(5, 2),
    prev_draught NUMERIC(5, 2),
    length INTEGER,
    beam INTEGER,
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Bounding Boxes / Zones
CREATE TABLE IF NOT EXISTS ship_regions (
    id SERIAL PRIMARY KEY,
    label VARCHAR(100) UNIQUE,
    boundary GEOMETRY(Polygon, 4326),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for spatial queries
CREATE INDEX idx_ship_regions_boundary ON ship_regions USING GIST(boundary);
