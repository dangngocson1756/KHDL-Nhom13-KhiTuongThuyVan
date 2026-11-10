PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS observations;
DROP TABLE IF EXISTS stations;
DROP TABLE IF EXISTS weather_regimes;

CREATE TABLE stations (
    station_id INTEGER PRIMARY KEY,
    station_code TEXT NOT NULL UNIQUE,
    station_name TEXT NOT NULL UNIQUE,
    region TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL
);

CREATE TABLE weather_regimes (
    regime_id INTEGER PRIMARY KEY,
    regime_name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL
);

CREATE TABLE observations (
    row_id INTEGER PRIMARY KEY,
    obs_id TEXT NOT NULL UNIQUE,
    station_id INTEGER NOT NULL REFERENCES stations(station_id),
    regime_id INTEGER NOT NULL REFERENCES weather_regimes(regime_id),
    obs_date TEXT NOT NULL,
    season TEXT NOT NULL,
    temp_mean_c REAL NOT NULL CHECK (temp_mean_c BETWEEN -5.0 AND 48.0),
    dewpoint_c REAL NOT NULL CHECK (dewpoint_c <= temp_mean_c + 0.05),
    humidity_pct REAL NOT NULL CHECK (humidity_pct BETWEEN 0.0 AND 100.0),
    pressure_hpa REAL NOT NULL CHECK (pressure_hpa BETWEEN 950.0 AND 1045.0),
    precip_mm REAL NOT NULL CHECK (precip_mm >= 0.0),
    wind_speed_ms REAL NOT NULL CHECK (wind_speed_ms >= 0.0),
    solar_rad_mj REAL NOT NULL CHECK (solar_rad_mj BETWEEN 0.0 AND 40.0),
    is_outlier_group INTEGER NOT NULL CHECK (is_outlier_group IN (0, 1)),
    cluster INTEGER NOT NULL CHECK (cluster IN (-1, 1, 2)),
    has_complete_window INTEGER NOT NULL CHECK (has_complete_window IN (0, 1)),
    target_temp_next_c REAL,
    target_rain_next_mm REAL
);
