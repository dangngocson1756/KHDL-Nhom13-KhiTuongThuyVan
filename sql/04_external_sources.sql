DROP TABLE IF EXISTS era5_daily;
DROP TABLE IF EXISTS hydrology_daily;
CREATE TABLE era5_daily (
 location TEXT NOT NULL, date TEXT NOT NULL, temp_c REAL, tmax_c REAL, tmin_c REAL,
 humidity_pct REAL CHECK(humidity_pct BETWEEN 0 AND 100), pressure_msl_hpa REAL,
 rain_mm REAL CHECK(rain_mm>=0), wind_ms REAL CHECK(wind_ms>=0), solar_mj_m2 REAL,
 grid_latitude REAL, grid_longitude REAL, source TEXT NOT NULL, timezone TEXT NOT NULL,
 PRIMARY KEY(location,date)
);
CREATE TABLE hydrology_daily (
 location TEXT NOT NULL, date TEXT NOT NULL, river_discharge_m3s REAL CHECK(river_discharge_m3s>=0),
 quality_flag TEXT NOT NULL, grid_latitude REAL, grid_longitude REAL, source_model TEXT NOT NULL, timezone TEXT NOT NULL,
 PRIMARY KEY(location,date)
);
