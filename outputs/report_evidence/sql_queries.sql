SELECT location, COUNT(*) AS n, ROUND(SUM(rain_mm),1) AS rain_sum_mm FROM era5_daily GROUP BY location ORDER BY location;
