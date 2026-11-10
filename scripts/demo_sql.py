"""Execute read-only SQL queries and integrity checks on outputs/kttv_weather.sqlite."""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main() -> None:
    db_path = ROOT / "outputs/kttv_weather.sqlite"
    conn = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
    ic = conn.execute("PRAGMA integrity_check;").fetchall()
    fk = conn.execute("PRAGMA foreign_key_check;").fetchall()
    if ic != [("ok",)] or fk:
        raise ValueError(f"Database integrity check failed: ic={ic}, fk={fk}")

    q1 = conn.execute("""
        SELECT s.station_code, s.station_name, COUNT(*) AS n_days,
               ROUND(AVG(o.temp_mean_c), 2), ROUND(AVG(o.precip_mm), 2)
        FROM observations o JOIN stations s USING (station_id)
        GROUP BY s.station_id ORDER BY s.station_id
    """).fetchall()

    q2 = conn.execute("""
        SELECT r.regime_name, COUNT(*) AS n_days, ROUND(AVG(o.temp_mean_c), 2)
        FROM observations o JOIN stations s USING (station_id) JOIN weather_regimes r USING (regime_id)
        WHERE s.station_code = 'WMO_48900'
        GROUP BY r.regime_id ORDER BY n_days DESC
    """).fetchall()

    q3 = conn.execute("""
        SELECT o.row_id, s.station_name, o.obs_date, o.temp_mean_c, o.precip_mm
        FROM observations o JOIN stations s USING (station_id)
        WHERE o.is_outlier_group = 1
        ORDER BY o.precip_mm DESC, o.row_id ASC LIMIT 20
    """).fetchall()

    bench = json.loads((ROOT / "outputs/sql_benchmark.json").read_text(encoding="utf-8"))
    q4 = conn.execute(bench["query"], bench["parameters"]).fetchall()
    conn.close()
    print(f"SQL demo verified: Q1={len(q1)} rows, Q2={len(q2)} rows, Q3={len(q3)} rows, Q4={len(q4)} rows, integrity=ok")

if __name__ == "__main__":
    main()
