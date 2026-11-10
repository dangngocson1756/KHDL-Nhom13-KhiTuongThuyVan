-- Query 1: Summary by station
SELECT s.station_code, s.station_name, COUNT(*) AS n_days,
       ROUND(AVG(o.temp_mean_c), 2) AS avg_temp_c,
       ROUND(AVG(o.precip_mm), 2) AS avg_precip_mm,
       ROUND(AVG(o.pressure_hpa), 2) AS avg_pressure_hpa
FROM observations o
JOIN stations s USING (station_id)
GROUP BY s.station_id, s.station_code, s.station_name
ORDER BY s.station_id;

-- Query 2: Summary by weather regime in Ho Chi Minh City
SELECT r.regime_name, COUNT(*) AS n_days,
       ROUND(AVG(o.temp_mean_c), 2) AS avg_temp_c,
       ROUND(AVG(o.humidity_pct), 2) AS avg_humidity_pct,
       ROUND(AVG(o.precip_mm), 2) AS avg_precip_mm
FROM observations o
JOIN stations s USING (station_id)
JOIN weather_regimes r USING (regime_id)
WHERE s.station_code = 'WMO_48900'
GROUP BY r.regime_id, r.regime_name
ORDER BY n_days DESC;

-- Query 3: Top heavy precipitation events flagged as group IQR outliers
SELECT o.row_id, s.station_name, o.obs_date, o.temp_mean_c, o.pressure_hpa, o.precip_mm
FROM observations o
JOIN stations s USING (station_id)
WHERE o.is_outlier_group = 1
ORDER BY o.precip_mm DESC, o.row_id ASC
LIMIT 20;

-- Query 4: Parameterized range search for composite index benchmark
SELECT row_id, obs_date, temp_mean_c, pressure_hpa, precip_mm
FROM observations
WHERE station_id = ? AND regime_id = ?
  AND temp_mean_c BETWEEN ? AND ?
ORDER BY temp_mean_c, row_id LIMIT 100;
