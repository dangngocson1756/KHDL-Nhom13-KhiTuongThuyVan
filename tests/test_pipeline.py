"""Automated unit and integration tests for KHDL-KhiTuongThuyVan pipeline (30 test cases)."""
from __future__ import annotations
import csv
import json
import sqlite3
import sys
import unittest
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from artifact_contract import file_sha256, read_verified_source, validate_core_outputs
from source_checks import (
    check_wmo_physical_consistency,
    normalize_text,
    parse_date_iso,
    parse_float_with_unit,
)
from pipeline import adjusted_rand_index, classify_regime, classify_season, kmeans_numpy

class TestMeteorologicalPipeline(unittest.TestCase):
    def test_01_normalize_text(self):
        self.assertEqual(normalize_text("  Hà   Nội \n "), "Hà Nội")

    def test_02_parse_date_iso_standard(self):
        self.assertEqual(parse_date_iso("2024-07-15"), "2024-07-15")

    def test_03_parse_date_iso_slash_vn(self):
        self.assertEqual(parse_date_iso("15/07/2024"), "2024-07-15")

    def test_04_parse_date_invalid(self):
        self.assertIsNone(parse_date_iso("2024/15/07"))

    def test_05_parse_float_celsius(self):
        val, u = parse_float_with_unit("27,5°C", ("°c", "c"))
        self.assertAlmostEqual(val, 27.5)
        self.assertEqual(u, "°c")

    def test_06_parse_float_hpa(self):
        val, u = parse_float_with_unit("1012.4 hPa", ("hpa",))
        self.assertAlmostEqual(val, 1012.4)
        self.assertEqual(u, "hpa")

    def test_07_parse_float_wind_kmh(self):
        val, u = parse_float_with_unit("18.0 km/h", ("km/h", "m/s"))
        self.assertAlmostEqual(val, 18.0)
        self.assertEqual(u, "km/h")

    def test_08_parse_float_missing_tokens(self):
        for tok in ("NA", "", "null", None):
            val, u = parse_float_with_unit(tok, ("mm",))
            self.assertIsNone(val)
            self.assertEqual(u, "missing")

    def test_09_parse_float_corrupted_token(self):
        val, u = parse_float_with_unit("ERR_SYNOP_NULL", ("mm",))
        self.assertIsNone(val)
        self.assertEqual(u, "corrupted_token")

    def test_10_wmo_qc_valid_observation(self):
        ok, rej, flags = check_wmo_physical_consistency(26.0, 30.0, 22.5, 21.0, 75.0, 1011.0, 5.0, 3.2, 120.0, 16.5)
        self.assertTrue(ok)
        self.assertEqual(rej, [])

    def test_11_wmo_qc_dewpoint_exceeds_temp(self):
        ok, rej, _ = check_wmo_physical_consistency(25.0, 28.0, 22.0, 26.5, 80.0, 1010.0, 0.0, 2.0, 90.0, 15.0)
        self.assertFalse(ok)
        self.assertIn("physical_violation_dewpoint_gt_temp", rej)

    def test_12_wmo_qc_tmax_less_than_tmin(self):
        ok, rej, _ = check_wmo_physical_consistency(22.0, 18.0, 25.0, 16.0, 70.0, 1010.0, 0.0, 2.0, 90.0, 15.0)
        self.assertFalse(ok)
        self.assertIn("physical_violation_tmax_lt_tmin", rej)

    def test_13_wmo_qc_humidity_over_100(self):
        ok, rej, _ = check_wmo_physical_consistency(26.0, 30.0, 22.0, 20.0, 112.0, 1010.0, 0.0, 2.0, 90.0, 15.0)
        self.assertFalse(ok)
        self.assertIn("wmo_gross_limit_humidity", rej)

    def test_14_wmo_qc_negative_precipitation(self):
        ok, rej, _ = check_wmo_physical_consistency(26.0, 30.0, 22.0, 20.0, 75.0, 1010.0, -3.5, 2.0, 90.0, 15.0)
        self.assertFalse(ok)
        self.assertIn("wmo_gross_limit_precip", rej)

    def test_15_wmo_qc_imputable_missing_temp_mean(self):
        ok, rej, flags = check_wmo_physical_consistency(None, 30.0, 22.0, 20.0, 75.0, 1010.0, 0.0, 2.0, 90.0, 15.0)
        self.assertTrue(ok)
        self.assertIn("missing_temp_mean_imputable", flags)

    def test_16_wmo_qc_heavy_rain_flag(self):
        ok, rej, flags = check_wmo_physical_consistency(25.0, 28.0, 23.0, 23.5, 92.0, 1004.0, 68.0, 6.2, 180.0, 6.0)
        self.assertTrue(ok)
        self.assertIn("heavy_rain_event_ge_50mm", flags)

    def test_17_classify_season(self):
        self.assertEqual(classify_season(1), "Mùa Đông / Gió mùa Đông Bắc")
        self.assertEqual(classify_season(4), "Chuyển mùa Xuân–Hè")
        self.assertEqual(classify_season(7), "Mùa Hạ / Mưa Tây Nam")
        self.assertEqual(classify_season(10), "Mùa Thu / Mưa bão Trung Bộ")

    def test_18_classify_regime(self):
        self.assertEqual(classify_regime(25.0, 94.0, 48.0, 8.0), "extreme_storm")
        self.assertEqual(classify_regime(26.0, 89.0, 12.0, 3.0), "rainy_convective")
        self.assertEqual(classify_regime(29.5, 62.0, 0.0, 2.5), "hot_dry")
        self.assertEqual(classify_regime(21.0, 72.0, 0.0, 2.5), "mild_cloudy")

    def test_19_kmeans_convergence_and_ari(self):
        rng = np.random.default_rng(42)
        x = np.vstack([rng.normal(-2, 0.4, (60, 2)), rng.normal(2, 0.4, (60, 2))])
        l1, _, _ = kmeans_numpy(x, k=2, seed=1)
        l2, _, _ = kmeans_numpy(x, k=2, seed=2)
        self.assertAlmostEqual(adjusted_rand_index(l1, l2), 1.0, places=5)

    def test_20_verified_raw_source_checksum(self):
        records, manifest = read_verified_source(ROOT)
        self.assertEqual(len(records), 10273)
        self.assertEqual(manifest["dataset_id"], "VN-KTTV-SYNOP-ERA5-2017-2025-V1")
        meta = json.loads((ROOT / "data/raw/kttv_metadata.json").read_text(encoding="utf-8"))
        for dossier in (manifest, meta):
            self.assertEqual(dossier["dataset_nature"], "synthetic_fault_injected_benchmark")
            self.assertFalse(dossier["reproducibility"]["original_generator_included"])
            self.assertEqual(dossier["sha256"], manifest["sha256"])


    def test_21_lineage_conservation(self):
        with (ROOT / "data/processed/row_lineage.csv").open(encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 10273)
        statuses = [r["status"] for r in rows]
        self.assertEqual(statuses.count("kept") + statuses.count("duplicate") + statuses.count("rejected"), 10273)

    def test_22_clean_csv_physical_bounds(self):
        with (ROOT / "data/processed/weather_clean.csv").open(encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                t = float(r["temp_mean_c"])
                td = float(r["dewpoint_c"])
                rh = float(r["humidity_pct"])
                pr = float(r["precip_mm"])
                self.assertLessEqual(td, t + 0.05)
                self.assertTrue(0.0 <= rh <= 100.0)
                self.assertGreaterEqual(pr, 0.0)

    def test_23_sqlite_schema_and_foreign_keys(self):
        conn = sqlite3.connect((ROOT / "outputs/kttv_weather.sqlite").as_uri() + "?mode=ro", uri=True)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM stations").fetchone()[0], 3)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM weather_regimes").fetchone()[0], 4)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0], 9634)
        self.assertEqual(conn.execute("PRAGMA foreign_key_check;").fetchall(), [])
        conn.close()

    def test_24_sql_benchmark_hash_equivalence(self):
        bench = json.loads((ROOT / "outputs/sql_benchmark.json").read_text(encoding="utf-8"))
        self.assertEqual(bench["before"]["result_sha256"], bench["after"]["result_sha256"])
        self.assertEqual(bench["before"]["result_count"], 100)

    def test_25_forecast_ablation_improvement(self):
        a = json.loads((ROOT / "outputs/analysis.json").read_text(encoding="utf-8"))
        trials = a["forecasting"]["ablation_trials"]
        self.assertLess(trials[-1]["test_rmse_c"], trials[0]["test_rmse_c"])
        self.assertLess(trials[-1]["val_mae_c"], trials[0]["val_mae_c"])

    def test_26_manifest_artifact_hashes(self):
        manifest = validate_core_outputs(ROOT)
        self.assertEqual(manifest["run_id"], "20261108T120000Z-kttv34vn")

    def test_27_dashboard_and_workbook_metadata_sync(self):
        d_meta = json.loads((ROOT / "outputs/dashboard_build.json").read_text(encoding="utf-8"))
        w_meta = json.loads((ROOT / "outputs/workbook_build.json").read_text(encoding="utf-8"))
        self.assertEqual(d_meta["core_run_id"], w_meta["core_run_id"])
        self.assertEqual(file_sha256(ROOT / d_meta["path"]), d_meta["sha256"])
        self.assertEqual(file_sha256(ROOT / w_meta["path"]), w_meta["sha256"])


    def test_28_target_date_two_sided_split_no_boundary_leakage(self):
        a = json.loads((ROOT / "outputs/analysis.json").read_text(encoding="utf-8"))
        sc = a["forecasting"]["split_counts"]
        self.assertEqual(sc["train_2017_2023"], 7140)
        self.assertEqual(sc["val_2024"], 1023)
        self.assertEqual(sc["test_2025"], 1018)
        self.assertEqual(sc["cross_boundary_dropped"], 6)
        self.assertEqual(sc["total_valid_windows"], 9181)

    def test_29_preprocessing_step_ablation_and_station_metrics(self):
        a = json.loads((ROOT / "outputs/analysis.json").read_text(encoding="utf-8"))
        steps = a["forecasting"]["preprocessing_step_ablation"]
        self.assertEqual(len(steps), 5)
        self.assertLess(steps[-1]["test_rmse_c"], steps[0]["test_rmse_c"])
        st_m = a["forecasting"]["station_forecast_metrics"]
        self.assertEqual(sum(r["n_test"] for r in st_m), 1018)

    def test_30_programmatic_qc_audit_and_operational_counts(self):
        a = json.loads((ROOT / "outputs/analysis.json").read_text(encoding="utf-8"))
        labeled = [r for r in a["evaluation_metrics"] if "nhãn" in r["check_type"]]
        operational = [r for r in a["evaluation_metrics"] if "vận hành" in r["check_type"]]
        self.assertEqual(len(labeled), 6)
        self.assertEqual(len(operational), 2)
        for row in labeled:
            self.assertEqual(row["false_alarms"], "0")
            self.assertIn("100,00%", row["result_note"])
        for row in operational:
            self.assertEqual(row["false_alarms"], "—")
            self.assertTrue("Đã xử lý" in row["result_note"] or "234 được giữ" in row["result_note"])

if __name__ == "__main__":
    unittest.main()
