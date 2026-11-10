CREATE INDEX IF NOT EXISTS idx_observations_search
ON observations (station_id, regime_id, temp_mean_c, row_id);
ANALYZE;
