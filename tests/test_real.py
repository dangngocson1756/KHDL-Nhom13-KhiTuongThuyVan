"""Unit and integration tests for the real Open-Meteo ECMWF ERA5 study (9 test cases, bringing total suite to 39 tests)."""
from __future__ import annotations
import hashlib
import json
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/real"


class Checks(unittest.TestCase):
    def test_01_source_provenance_hashes(self):
        prov = json.loads((OUT / "provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(len(prov), 3)
        for r in prov:
            actual = hashlib.sha256((ROOT / "data/era5" / r["file"]).read_bytes()).hexdigest()
            self.assertEqual(actual, r["sha256"])

    def test_02_target_date_boundaries(self):
        f = pd.read_csv(OUT / "features.csv", parse_dates=["date", "target_date"])
        self.assertTrue(((f.target_date - f.date).dt.days == 1).all())
        self.assertTrue((f.loc[f.split == "train", "target_date"] < "2024-01-01").all())
        self.assertTrue(f.loc[f.split == "validation", "target_date"].dt.year.eq(2024).all())
        self.assertTrue(f.loc[f.split == "test", "target_date"].dt.year.eq(2025).all())

    def test_03_labels_alignment(self):
        f = pd.read_csv(OUT / "features.csv")
        d = pd.read_csv(OUT / "clean.csv")
        j = f.merge(
            d[["location", "date", "temp", "rain"]],
            left_on=["location", "target_date"],
            right_on=["location", "date"],
            suffixes=("", "_truth"),
        )
        self.assertEqual(len(j), len(f))
        np.testing.assert_allclose(j.target_temp, j.temp_truth)
        np.testing.assert_allclose(j.target_rain, j.rain_truth)

    def test_04_temperature_metrics_and_r1_r3_labels(self):
        p = pd.read_csv(OUT / "predictions.csv")
        s = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
        models = [r["model"] for r in s["temperature"]]
        for expected in ("R1", "R2", "R3", "Persistence", "Monthly_climatology", "Climatology_anomaly"):
            self.assertIn(expected, models)
        for r in s["temperature"]:
            rmse = float(np.sqrt(np.mean((p.target_temp - p[r["model"]]) ** 2)))
            self.assertAlmostEqual(rmse, r["RMSE"], places=10)

    def test_05_validation_model_selection(self):
        s = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
        candidates = [r for r in s["temperature"] if "validation_RMSE" in r]
        best = min(candidates, key=lambda r: r["validation_RMSE"])["model"]
        self.assertEqual(s["chosen_by_validation"], best)
        self.assertEqual(best, "R3")

    def test_06_era5_descriptive_and_spearman_tables(self):
        desc = pd.read_csv(OUT / "descriptive.csv")
        self.assertEqual(len(desc), 6)
        self.assertTrue((desc["n"] == 9861).all())
        sp = pd.read_csv(OUT / "spearman.csv", index_col=0)
        self.assertEqual(sp.shape, (6, 6))

    def test_07_era5_location_season_and_clusters(self):
        loc_seas = pd.read_csv(OUT / "location_season.csv")
        self.assertEqual(len(loc_seas), 12)
        self.assertEqual(int(loc_seas["n"].sum()), 9861)
        cl = pd.read_csv(OUT / "cluster_summary.csv")
        self.assertEqual(len(cl), 2)
        self.assertEqual(int(cl["n"].sum()), 9861)

    def test_08_era5_paired_bootstrap_table(self):
        pb = pd.read_csv(OUT / "paired_bootstrap.csv")
        self.assertEqual(len(pb), 6)
        r3_pers = pb[(pb["scope"] == "ALL") & (pb["comparison"] == "R3 - Persistence")].iloc[0]
        self.assertLess(float(r3_pers["ci_high"]), 0.0)
        f1_row = pb[(pb["scope"] == "ALL") & (pb["comparison"] == "Logistic - rain persistence")].iloc[0]
        self.assertLess(float(f1_row["ci_low"]), 0.0)
        self.assertGreater(float(f1_row["ci_high"]), 0.0)

    def test_09_synthetic_paired_bootstrap_and_wind_counts(self):
        spb = pd.read_csv(ROOT / "outputs/tables/synthetic_paired_bootstrap.csv")
        self.assertEqual(len(spb), 2)
        a = json.loads((ROOT / "outputs/analysis.json").read_text(encoding="utf-8"))
        c = a["counts"]
        self.assertEqual(c["raw_unit_converted_wind_count"], 255)
        self.assertEqual(c["pre_qc_unit_converted_wind_count"], 242)
        self.assertEqual(c["unit_converted_wind_count"], 234)
        self.assertEqual(c["rejected_unit_converted_wind_count"], 8)


if __name__ == "__main__":
    unittest.main()
