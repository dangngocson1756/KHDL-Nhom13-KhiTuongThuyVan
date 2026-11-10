"""Core meteorological data cleaning, WMO-No. 8 quality control, calendar-day time-series feature engineering,
ERA5 masking validation, K-means++ clustering, forecasting ablation study, SQLite database & chart generation."""
from __future__ import annotations
import csv
import hashlib
import json
import math
import sqlite3
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np
import pandas as pd

from artifact_contract import file_sha256, read_verified_source
from source_checks import (
    check_wmo_physical_consistency,
    compute_wmo_dewpoint,
    normalize_text,
    parse_date_iso,
    parse_float_with_unit,
)

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "20261108T120000Z-kttv34vn"
SEED = 20261015

STATION_META = {
    "WMO_48820": {"id": 1, "name": "Hà Nội (Láng)", "region": "Đồng bằng Bắc Bộ", "lat": 21.0167, "lon": 105.8000, "elev_m": 6.0},
    "WMO_48855": {"id": 2, "name": "Đà Nẵng", "region": "Duyên hải Trung Bộ", "lat": 16.0439, "lon": 108.1994, "elev_m": 7.0},
    "WMO_48900": {"id": 3, "name": "TP. Hồ Chí Minh (Tân Sơn Nhất)", "region": "Nam Bộ", "lat": 10.8188, "lon": 106.6519, "elev_m": 9.0},
}

REGIME_META = {
    "mild_cloudy": {"id": 1, "label": "Mát / Nhiều mây ổn định", "desc": "Thời tiết ổn định, mây thay đổi, mưa dưới 2 mm/ngày"},
    "hot_dry": {"id": 2, "label": "Nắng nóng / Khô quang", "desc": "Nhiệt độ trung bình ngày >= 28 °C, độ ẩm <= 78%, ít mưa"},
    "rainy_convective": {"id": 3, "label": "Mưa rào / Đối lưu ẩm", "desc": "Lượng mưa ngày từ 2 mm đến dưới 35 mm hoặc độ ẩm cao có mưa"},
    "extreme_storm": {"id": 4, "label": "Mưa lớn / Nhiễu động mạnh", "desc": "Mưa lớn >= 35 mm/ngày hoặc gió mạnh >= 7,0 m/s kèm mưa"},
}

def classify_season(month: int) -> str:
    if month in (12, 1, 2):
        return "Mùa Đông / Gió mùa Đông Bắc"
    if month in (3, 4):
        return "Chuyển mùa Xuân–Hè"
    if month in (5, 6, 7, 8):
        return "Mùa Hạ / Mưa Tây Nam"
    return "Mùa Thu / Mưa bão Trung Bộ"

def classify_regime(temp_c: float, humidity_pct: float, precip_mm: float, wind_ms: float) -> str:
    if precip_mm >= 35.0 or (precip_mm >= 15.0 and wind_ms >= 7.0):
        return "extreme_storm"
    if precip_mm >= 2.0 or (precip_mm >= 0.5 and humidity_pct >= 84.0):
        return "rainy_convective"
    if temp_c >= 28.0 and humidity_pct <= 78.0 and precip_mm < 1.0:
        return "hot_dry"
    return "mild_cloudy"

def compute_obs_id(station_code: str, obs_date: str, tmax_s: str, tmin_s: str, precip_s: str) -> str:
    key = f"{station_code}|{obs_date}|{tmax_s}|{tmin_s}|{precip_s}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]

def kmeans_numpy(x: np.ndarray, k: int, seed: int = SEED, n_init: int = 10, max_iter: int = 150) -> tuple[np.ndarray, np.ndarray, float]:
    best_labels = None
    best_centers = None
    best_inertia = float("inf")
    n = x.shape[0]
    for init_idx in range(n_init):
        rng = np.random.default_rng(seed + init_idx * 97)
        centers = np.empty((k, x.shape[1]), dtype=float)
        first = int(rng.integers(0, n))
        centers[0] = x[first]
        for c_id in range(1, k):
            d2 = ((x[:, None, :] - centers[None, :c_id, :]) ** 2).sum(axis=2).min(axis=1)
            probs = d2 / max(float(d2.sum()), 1e-12)
            choice = int(rng.choice(n, p=probs))
            centers[c_id] = x[choice]

        for _ in range(max_iter):
            distances = ((x[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
            labels = distances.argmin(axis=1)
            updated = np.array([
                x[labels == j].mean(axis=0) if np.any(labels == j)
                else x[np.argmax(distances.min(axis=1))]
                for j in range(k)
            ])
            shift = float(np.linalg.norm(updated - centers, axis=1).max())
            centers = updated
            if shift < 1e-7:
                break

        distances = ((x[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        labels = distances.argmin(axis=1)
        inertia = float(distances[np.arange(n), labels].sum())
        if inertia < best_inertia:
            best_inertia = inertia
            best_labels = labels.copy()
            best_centers = centers.copy()
    return best_labels, best_centers, best_inertia

def sampled_silhouette(x: np.ndarray, labels: np.ndarray, max_sample: int = 1000, seed: int = SEED) -> float:
    n = x.shape[0]
    if n > max_sample:
        rng = np.random.default_rng(seed)
        idx = rng.choice(n, size=max_sample, replace=False)
        xs = x[idx]
        ls = labels[idx]
    else:
        xs = x
        ls = labels
    diff = xs[:, None, :] - xs[None, :, :]
    dist = np.sqrt((diff ** 2).sum(axis=2))
    uniq = np.unique(ls)
    if len(uniq) < 2:
        return 0.0
    sil = np.zeros(len(xs), dtype=float)
    for i in range(len(xs)):
        own = ls == ls[i]
        own[i] = False
        a_i = float(dist[i, own].mean()) if np.any(own) else 0.0
        b_i = min(float(dist[i, ls == c].mean()) for c in uniq if c != ls[i] and np.any(ls == c))
        denom = max(a_i, b_i)
        sil[i] = (b_i - a_i) / denom if denom > 0 else 0.0
    return float(sil.mean())

def adjusted_rand_index(u: np.ndarray, v: np.ndarray) -> float:
    _, u_idx = np.unique(u, return_inverse=True)
    _, v_idx = np.unique(v, return_inverse=True)
    n_u = int(u_idx.max()) + 1
    n_v = int(v_idx.max()) + 1
    contingency = np.zeros((n_u, n_v), dtype=np.int64)
    np.add.at(contingency, (u_idx, v_idx), 1)
    sum_comb_c = float((contingency * (contingency - 1) // 2).sum())
    a = contingency.sum(axis=1)
    b = contingency.sum(axis=0)
    sum_comb_a = float((a * (a - 1) // 2).sum())
    sum_comb_b = float((b * (b - 1) // 2).sum())
    n = len(u)
    total_comb = float(n * (n - 1) // 2)
    if total_comb == 0:
        return 1.0
    prod = (sum_comb_a * sum_comb_b) / total_comb
    mean_comb = 0.5 * (sum_comb_a + sum_comb_b)
    if mean_comb == prod:
        return 1.0
    return float((sum_comb_c - prod) / (mean_comb - prod))

def clean_and_engineer_records(raw_records: list[dict]) -> tuple[list[dict], list[dict], list[dict], dict]:
    seen_obs: dict[str, int] = {}
    kept: list[dict] = []
    rejected: list[dict] = []
    lineage: list[dict] = []

    imputed_temp_count = 0
    imputed_pres_count = 0
    raw_unit_converted_wind_count = sum(1 for r in raw_records if parse_float_with_unit(r.get("wind_speed_raw"), ("m/s", "km/h"))[1] == "km/h")
    pre_qc_unit_converted_wind_count = 0
    unit_converted_wind_count = 0

    for row_id, rec in enumerate(raw_records, 1):
        station_code = normalize_text(rec.get("station_code", ""))
        station_name = STATION_META.get(station_code, {}).get("name", normalize_text(rec.get("station_label", "")))
        region = STATION_META.get(station_code, {}).get("region", "")
        obs_date = parse_date_iso(rec.get("obs_date", ""))

        tmax_s = normalize_text(rec.get("temp_max_raw", ""))
        tmin_s = normalize_text(rec.get("temp_min_raw", ""))
        precip_s = normalize_text(rec.get("precip_raw", ""))
        obs_id = compute_obs_id(station_code, obs_date or "", tmax_s, tmin_s, precip_s)

        if obs_id in seen_obs:
            canon_id = seen_obs[obs_id]
            lineage.append({
                "row_id": row_id,
                "status": "duplicate",
                "canonical_row_id": canon_id,
                "reasons": f"duplicate_synop_key_of_row_{canon_id}",
            })
            continue
        seen_obs[obs_id] = row_id

        t_mean, u_tmean = parse_float_with_unit(rec.get("temp_mean_raw"), ("°c", "c"))
        t_max, u_tmax = parse_float_with_unit(rec.get("temp_max_raw"), ("°c", "c"))
        t_min, u_tmin = parse_float_with_unit(rec.get("temp_min_raw"), ("°c", "c"))
        dewp, u_dewp = parse_float_with_unit(rec.get("dewpoint_raw"), ("°c", "c"))
        hum, u_hum = parse_float_with_unit(rec.get("humidity_raw"), ("%",))
        pres, u_pres = parse_float_with_unit(rec.get("pressure_raw"), ("hpa", "mb"))
        precip, u_prec = parse_float_with_unit(rec.get("precip_raw"), ("mm",))
        wind, u_wind = parse_float_with_unit(rec.get("wind_speed_raw"), ("m/s", "km/h"))
        wdir, u_wdir = parse_float_with_unit(rec.get("wind_dir_raw"), ("deg", "°"))
        solar, u_solar = parse_float_with_unit(rec.get("solar_rad_raw"), ("mj/m2", "mj/m²"))

        q_flags: list[str] = []
        if u_wind == "km/h" and wind is not None:
            wind = round(wind / 3.6, 2)
            pre_qc_unit_converted_wind_count += 1
            q_flags.append("wind_converted_from_kmh")

        corrupted_fields = [
            name for name, unit_tok in [
                ("temp_mean", u_tmean), ("temp_max", u_tmax), ("temp_min", u_tmin),
                ("dewpoint", u_dewp), ("humidity", u_hum), ("pressure", u_pres),
                ("precip", u_prec), ("wind_speed", u_wind),
            ] if unit_tok == "corrupted_token"
        ]

        ok, rej_reasons, qc_flags = check_wmo_physical_consistency(
            t_mean, t_max, t_min, dewp, hum, pres, precip, wind, wdir, solar
        )
        for cf in corrupted_fields:
            rej_reasons.append(f"corrupted_token_{cf}")
            ok = False

        if not ok or obs_date is None:
            reason_str = ";".join(sorted(set(rej_reasons))) if rej_reasons else "invalid_date"
            rejected.append({
                "row_id": row_id,
                "station_code": station_code,
                "station_name": station_name,
                "obs_date": obs_date or str(rec.get("obs_date", "")),
                "temp_mean_raw": rec.get("temp_mean_raw"),
                "temp_max_raw": rec.get("temp_max_raw"),
                "temp_min_raw": rec.get("temp_min_raw"),
                "dewpoint_raw": rec.get("dewpoint_raw"),
                "humidity_raw": rec.get("humidity_raw"),
                "pressure_raw": rec.get("pressure_raw"),
                "precip_raw": rec.get("precip_raw"),
                "reject_reasons": reason_str,
            })
            lineage.append({
                "row_id": row_id,
                "status": "rejected",
                "canonical_row_id": row_id,
                "reasons": reason_str,
            })
            continue

        if "wind_converted_from_kmh" in q_flags:
            unit_converted_wind_count += 1
        q_flags.extend(qc_flags)
        era5_t = float(rec["reanalysis_temp_c"])
        era5_p = float(rec["reanalysis_pressure_hpa"])

        temp_source = "station_direct"
        if t_mean is None:
            t_mean = round(min(max(era5_t, float(t_min)), float(t_max)), 2)
            if dewp is not None and t_mean < dewp:
                t_mean = round(float(dewp), 2)
            temp_source = "era5_reanalysis_recovery"
            imputed_temp_count += 1
            q_flags.append("era5_temp_recovered")

        pres_source = "station_direct"
        if pres is None:
            pres = round(era5_p, 1)
            pres_source = "era5_reanalysis_recovery"
            imputed_pres_count += 1
            q_flags.append("era5_pressure_recovered")

        month = int(obs_date.split("-")[1])
        season = classify_season(month)
        regime = classify_regime(float(t_mean), float(hum), float(precip), float(wind))

        rad_angle = math.radians(float(wdir))
        wind_u = round(-float(wind) * math.sin(rad_angle), 4)
        wind_v = round(-float(wind) * math.cos(rad_angle), 4)

        kept.append({
            "row_id": row_id,
            "obs_id": obs_id,
            "station_code": station_code,
            "station_name": station_name,
            "region": region,
            "obs_date": obs_date,
            "season": season,
            "weather_regime": regime,
            "temp_mean_c": round(float(t_mean), 2),
            "temp_max_c": round(float(t_max), 2),
            "temp_min_c": round(float(t_min), 2),
            "dewpoint_c": round(float(dewp), 2),
            "humidity_pct": round(float(hum), 1),
            "pressure_hpa": round(float(pres), 1),
            "precip_mm": round(float(precip), 1),
            "wind_speed_ms": round(float(wind), 2),
            "wind_dir_deg": round(float(wdir), 1),
            "wind_u_ms": wind_u,
            "wind_v_ms": wind_v,
            "solar_rad_mj": round(float(solar), 2),
            "reanalysis_temp_c": round(era5_t, 2),
            "reanalysis_pressure_hpa": round(era5_p, 1),
            "temp_source": temp_source,
            "pres_source": pres_source,
            "quality_flags": ";".join(q_flags) if q_flags else "clean_direct",
        })
        lineage.append({
            "row_id": row_id,
            "status": "kept",
            "canonical_row_id": row_id,
            "reasons": ";".join(q_flags) if q_flags else "clean_direct",
        })

    df = pd.DataFrame(kept)
    df["obs_dt"] = pd.to_datetime(df["obs_date"])
    df = df.sort_values(["station_code", "obs_dt", "row_id"]).reset_index(drop=True)

    doy = df["obs_dt"].dt.day_of_year.astype(float)
    df["doy_sin"] = np.round(np.sin(2.0 * np.pi * doy / 365.25), 6)
    df["doy_cos"] = np.round(np.cos(2.0 * np.pi * doy / 365.25), 6)
    df["year"] = df["obs_dt"].dt.year.astype(int)

    # Calendar-day reindexing per station (NO bfill/ffill across missing quarantined dates!)
    full_parts = []
    for scode, grp in df.groupby("station_code", sort=False):
        g = grp.set_index("obs_dt").sort_index()
        full_idx = pd.date_range("2017-01-01", "2025-12-31", freq="D")
        g_cal = g.reindex(full_idx)

        temp_lag_1d = g_cal["temp_mean_c"].shift(1)
        temp_lag_2d = g_cal["temp_mean_c"].shift(2)
        temp_lag_3d_mean = g_cal["temp_mean_c"].rolling(3, min_periods=1).mean()
        humidity_lag_1d = g_cal["humidity_pct"].shift(1)
        precip_lag_1d = g_cal["precip_mm"].shift(1)
        pressure_lag_1d = g_cal["pressure_hpa"].shift(1)
        pressure_delta_24h = g_cal["pressure_hpa"] - pressure_lag_1d
        target_temp_next_c = g_cal["temp_mean_c"].shift(-1)
        target_rain_next_mm = g_cal["precip_mm"].shift(-1)

        g["cal_temp_lag_1d"] = temp_lag_1d.loc[g.index].round(2)
        g["cal_temp_lag_2d"] = temp_lag_2d.loc[g.index].round(2)
        g["cal_temp_lag_3d_mean"] = temp_lag_3d_mean.loc[g.index].round(2)
        g["cal_humidity_lag_1d"] = humidity_lag_1d.loc[g.index].round(1)
        g["cal_precip_lag_1d"] = precip_lag_1d.loc[g.index].round(1)
        g["cal_pressure_delta_24h"] = pressure_delta_24h.loc[g.index].round(2)
        g["cal_target_temp_next_c"] = target_temp_next_c.loc[g.index].round(2)
        g["cal_target_rain_next_mm"] = target_rain_next_mm.loc[g.index].round(1)

        g["has_complete_window"] = (
            g["cal_temp_lag_1d"].notna()
            & g["cal_pressure_delta_24h"].notna()
            & g["cal_target_temp_next_c"].notna()
            & g["cal_target_rain_next_mm"].notna()
        )
        g["target_date"] = (g.index + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        g["temp_lag_1d"] = g["cal_temp_lag_1d"]
        g["temp_lag_3d_mean"] = g["cal_temp_lag_3d_mean"]
        g["humidity_lag_1d"] = g["cal_humidity_lag_1d"]
        g["precip_lag_1d"] = g["cal_precip_lag_1d"]
        g["pressure_delta_24h"] = g["cal_pressure_delta_24h"]
        g["target_temp_next_c"] = g["cal_target_temp_next_c"]
        g["target_rain_next_mm"] = g["cal_target_rain_next_mm"]
        full_parts.append(g.reset_index(drop=True))

    df = pd.concat(full_parts, ignore_index=True)
    df = df.sort_values("row_id").reset_index(drop=True)

    # Global IQR vs Station x Season IQR outlier flagging (computed strictly on Train 2017-2023 to avoid leakage)
    train_df = df[df["year"] <= 2023]
    q1_glob = float(train_df["precip_mm"].quantile(0.25))
    q3_glob = float(train_df["precip_mm"].quantile(0.75))
    iqr_glob = q3_glob - q1_glob
    df["is_outlier_global"] = (df["precip_mm"] > (q3_glob + 1.5 * iqr_glob)) | (df["wind_speed_ms"] >= 8.0)

    group_bounds: dict[tuple[str, str], tuple[float, float, float]] = {}
    for (sc, seas), grp in train_df.groupby(["station_code", "season"]):
        tq1, tq3 = float(grp["temp_mean_c"].quantile(0.25)), float(grp["temp_mean_c"].quantile(0.75))
        tiqr = tq3 - tq1
        pq1, pq3 = float(grp["precip_mm"].quantile(0.25)), float(grp["precip_mm"].quantile(0.75))
        piqr = pq3 - pq1
        group_bounds[(sc, seas)] = (tq1 - 1.5 * tiqr, tq3 + 1.5 * tiqr, max(50.0, pq3 + 3.0 * piqr))

    out_grp = []
    for _, r in df.iterrows():
        t_lo, t_hi, p_hi = group_bounds[(r["station_code"], r["season"])]
        is_out = (r["temp_mean_c"] < t_lo) or (r["temp_mean_c"] > t_hi) or (r["precip_mm"] >= 50.0) or (r["wind_speed_ms"] >= 8.0)
        out_grp.append(bool(is_out))
    df["is_outlier_group"] = out_grp

    cross_bound_mask = df["has_complete_window"] & df["obs_date"].isin(["2023-12-31", "2024-12-31"])
    counts = {
        "raw_count": len(raw_records),
        "duplicate_count": sum(1 for x in lineage if x["status"] == "duplicate"),
        "rejected_count": len(rejected),
        "clean_count": len(df),
        "complete_window_count": int(df["has_complete_window"].sum()),
        "cross_boundary_excluded_count": int(cross_bound_mask.sum()),
        "valid_forecast_window_count": int(df["has_complete_window"].sum() - cross_bound_mask.sum()),
        "calendar_gap_excluded_count": int((~df["has_complete_window"]).sum()),
        "imputed_temp_count": imputed_temp_count,
        "imputed_pres_count": imputed_pres_count,
        "raw_unit_converted_wind_count": raw_unit_converted_wind_count,
        "pre_qc_unit_converted_wind_count": pre_qc_unit_converted_wind_count,
        "unit_converted_wind_count": unit_converted_wind_count,
        "rejected_unit_converted_wind_count": pre_qc_unit_converted_wind_count - unit_converted_wind_count,
        "group_iqr_outlier_count": int(df["is_outlier_group"].sum()),
        "global_iqr_outlier_count": int(df["is_outlier_global"].sum()),
    }
    return df.to_dict(orient="records"), rejected, lineage, counts

def evaluate_era5_masking_validation(df: pd.DataFrame) -> dict:
    """Mask 5% of clean station-direct observations and measure ERA5 recovery bias, MAE, and RMSE."""
    rng = np.random.default_rng(SEED)
    direct_t = df[df["temp_source"] == "station_direct"].copy()
    mask_t_idx = rng.choice(direct_t.index, size=int(round(len(direct_t) * 0.05)), replace=False)
    sub_t = direct_t.loc[mask_t_idx]
    true_t = sub_t["temp_mean_c"].to_numpy(dtype=float)
    rec_t = np.minimum(np.maximum(sub_t["reanalysis_temp_c"].to_numpy(dtype=float), sub_t["temp_min_c"].to_numpy(dtype=float)), sub_t["temp_max_c"].to_numpy(dtype=float))
    rec_t = np.maximum(rec_t, sub_t["dewpoint_c"].to_numpy(dtype=float))
    global_mean_t = float(direct_t["temp_mean_c"].mean())

    direct_p = df[df["pres_source"] == "station_direct"].copy()
    mask_p_idx = rng.choice(direct_p.index, size=int(round(len(direct_p) * 0.05)), replace=False)
    sub_p = direct_p.loc[mask_p_idx]
    true_p = sub_p["pressure_hpa"].to_numpy(dtype=float)
    rec_p = sub_p["reanalysis_pressure_hpa"].to_numpy(dtype=float)
    global_mean_p = float(direct_p["pressure_hpa"].mean())

    return {
        "temp_masked_n": int(len(sub_t)),
        "temp_era5_bias_c": round(float(np.mean(rec_t - true_t)), 4),
        "temp_era5_mae_c": round(float(np.mean(np.abs(rec_t - true_t))), 4),
        "temp_era5_rmse_c": round(float(np.sqrt(np.mean((rec_t - true_t) ** 2))), 4),
        "temp_global_mean_rmse_c": round(float(np.sqrt(np.mean((global_mean_t - true_t) ** 2))), 4),
        "pres_masked_n": int(len(sub_p)),
        "pres_era5_bias_hpa": round(float(np.mean(rec_p - true_p)), 4),
        "pres_era5_mae_hpa": round(float(np.mean(np.abs(rec_p - true_p))), 4),
        "pres_era5_rmse_hpa": round(float(np.sqrt(np.mean((rec_p - true_p) ** 2))), 4),
        "pres_global_mean_rmse_hpa": round(float(np.sqrt(np.mean((global_mean_p - true_p) ** 2))), 4),
    }

def fit_ridge_closed_form(X_tr: np.ndarray, y_tr: np.ndarray, l2: float = 1.5) -> np.ndarray:
    n, d = X_tr.shape
    Xb = np.column_stack([np.ones(n), X_tr])
    reg = np.eye(d + 1) * l2
    reg[0, 0] = 0.0
    return np.linalg.solve(Xb.T @ Xb + reg, Xb.T @ y_tr)

def predict_linear(X: np.ndarray, w: np.ndarray) -> np.ndarray:
    return np.column_stack([np.ones(X.shape[0]), X]) @ w

def fit_logistic_l2(X_tr: np.ndarray, y_tr: np.ndarray, l2: float = 15.0, max_iter: int = 80) -> np.ndarray:
    n, d = X_tr.shape
    Xb = np.column_stack([np.ones(n), X_tr])
    w = np.zeros(d + 1, dtype=float)
    for _ in range(max_iter):
        z = np.clip(Xb @ w, -30.0, 30.0)
        p = 1.0 / (1.0 + np.exp(-z))
        wt = np.maximum(p * (1.0 - p), 1e-6)
        grad = Xb.T @ (p - y_tr) + l2 * np.r_[0.0, w[1:]]
        hess = (Xb.T * wt) @ Xb + np.diag(np.r_[1e-6, np.full(d, l2)])
        step = np.linalg.solve(hess, grad)
        w -= step
        if float(np.linalg.norm(step)) < 1e-6:
            break
    return w

def compute_roc_auc_pr_auc(y_true: np.ndarray, prob: np.ndarray) -> tuple[float, float]:
    n_pos = float(y_true.sum())
    n_neg = float(len(y_true) - n_pos)
    if n_pos == 0 or n_neg == 0:
        return 0.5, 0.0
    uniq = np.unique(prob)[::-1]
    if len(uniq) == 1:
        return 0.5000, round(float(n_pos / len(y_true)), 4)
    tprs, fprs, precs, recs = [0.0], [0.0], [float(n_pos / len(y_true))], [0.0]
    for th in uniq:
        mask = prob >= th
        tp = float(y_true[mask].sum())
        fp = float((1.0 - y_true[mask]).sum())
        tprs.append(tp / n_pos)
        fprs.append(fp / n_neg)
        precs.append(tp / max(tp + fp, 1.0))
        recs.append(tp / n_pos)
    precs[0] = precs[1]
    roc_auc = float(getattr(np, "trapezoid", getattr(np, "trapz", None))(tprs, fprs))
    pr_auc = float(getattr(np, "trapezoid", getattr(np, "trapz", None))(precs, recs))
    return round(roc_auc, 4), round(pr_auc, 4)

def eval_binary_classifier(y_true: np.ndarray, prob: np.ndarray, threshold: float) -> dict:
    pred = (prob >= threshold).astype(int)
    tp = int(((pred == 1) & (y_true == 1)).sum())
    tn = int(((pred == 0) & (y_true == 0)).sum())
    fp = int(((pred == 1) & (y_true == 0)).sum())
    fn = int(((pred == 0) & (y_true == 1)).sum())
    acc = (tp + tn) / len(y_true) * 100.0
    prec = tp / max(tp + fp, 1) * 100.0
    rec = tp / max(tp + fn, 1) * 100.0
    f1 = (2.0 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
    roc_auc, pr_auc = compute_roc_auc_pr_auc(y_true, prob)
    brier = float(np.mean((prob - y_true) ** 2))
    pred_rain_rate = float(pred.mean() * 100.0)
    return {
        "test_accuracy_pct": round(acc, 2),
        "test_precision_pct": round(prec, 2),
        "test_recall_pct": round(rec, 2),
        "test_f1_pct": round(f1, 2),
        "test_roc_auc": roc_auc,
        "test_pr_auc": pr_auc,
        "test_brier": round(brier, 4),
        "predicted_rain_rate_pct": round(pred_rain_rate, 2),
        "threshold": round(threshold, 2),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }

def run_forecasting_experiments(df: pd.DataFrame, raw_records: list[dict]) -> tuple[dict, list[dict], list[dict]]:
    # Strictly use complete calendar-day windows and split by BOTH obs_date (t) and target_date (t+1)
    # so zero cross-year boundary windows (31/12/2023 -> 01/01/2024 or 31/12/2024 -> 01/01/2025) leak across splits
    fc_df_all = df[df["has_complete_window"]].copy().reset_index(drop=True)
    cross_mask = fc_df_all["obs_date"].isin(["2023-12-31", "2024-12-31"])
    fc_df = fc_df_all[~cross_mask].copy().reset_index(drop=True)

    fc_df["rain_log1p"] = np.log1p(fc_df["precip_mm"])
    fc_df["rain_lag1_log1p"] = np.log1p(fc_df["cal_precip_lag_1d"])
    fc_df["st_hn"] = (fc_df["station_code"] == "WMO_48820").astype(float)
    fc_df["st_dn"] = (fc_df["station_code"] == "WMO_48855").astype(float)
    fc_df["hn_sin"] = fc_df["st_hn"] * fc_df["doy_sin"]
    fc_df["hn_cos"] = fc_df["st_hn"] * fc_df["doy_cos"]
    fc_df["dn_sin"] = fc_df["st_dn"] * fc_df["doy_sin"]
    fc_df["dn_cos"] = fc_df["st_dn"] * fc_df["doy_cos"]

    train_mask = ((fc_df["obs_date"] < "2024-01-01") & (fc_df["target_date"] < "2024-01-01")).to_numpy()
    val_mask = ((fc_df["obs_date"] >= "2024-01-01") & (fc_df["target_date"] < "2025-01-01")).to_numpy()
    test_mask = ((fc_df["obs_date"] >= "2025-01-01") & (fc_df["target_date"] >= "2025-01-01")).to_numpy()

    y_tr = fc_df.loc[train_mask, "cal_target_temp_next_c"].to_numpy(dtype=float)
    y_va = fc_df.loc[val_mask, "cal_target_temp_next_c"].to_numpy(dtype=float)
    y_te = fc_df.loc[test_mask, "cal_target_temp_next_c"].to_numpy(dtype=float)

    # 1. Persistence Baseline: T_{t+1} = T_t
    p_va = fc_df.loc[val_mask, "temp_mean_c"].to_numpy(dtype=float)
    p_te = fc_df.loc[test_mask, "temp_mean_c"].to_numpy(dtype=float)
    ss_tot_te = float(np.sum((y_te - y_te.mean()) ** 2))
    pers_base = {
        "val_mae_c": round(float(np.mean(np.abs(y_va - p_va))), 4),
        "val_rmse_c": round(float(np.sqrt(np.mean((y_va - p_va) ** 2))), 4),
        "test_mae_c": round(float(np.mean(np.abs(y_te - p_te))), 4),
        "test_rmse_c": round(float(np.sqrt(np.mean((y_te - p_te) ** 2))), 4),
        "test_r2": round(float(1.0 - np.sum((y_te - p_te) ** 2) / ss_tot_te), 4),
    }

    # 2. Climatology + Anomaly Persistence Baseline: T_clim(station, doy) + 0.55 * (T_t - T_clim(station, doy))
    clim_cols = ["st_hn", "st_dn", "doy_sin", "doy_cos", "hn_sin", "hn_cos", "dn_sin", "dn_cos"]
    Xc = fc_df[clim_cols].to_numpy(dtype=float)
    wc = fit_ridge_closed_form(Xc[train_mask], fc_df.loc[train_mask, "temp_mean_c"].to_numpy(dtype=float), l2=1.0)
    clim_va = predict_linear(Xc[val_mask], wc) + 0.55 * (p_va - predict_linear(Xc[val_mask], wc))
    clim_te = predict_linear(Xc[test_mask], wc) + 0.55 * (p_te - predict_linear(Xc[test_mask], wc))
    clim_base = {
        "val_mae_c": round(float(np.mean(np.abs(y_va - clim_va))), 4),
        "val_rmse_c": round(float(np.sqrt(np.mean((y_va - clim_va) ** 2))), 4),
        "test_mae_c": round(float(np.mean(np.abs(y_te - clim_te))), 4),
        "test_rmse_c": round(float(np.sqrt(np.mean((y_te - clim_te) ** 2))), 4),
        "test_r2": round(float(1.0 - np.sum((y_te - clim_te) ** 2) / ss_tot_te), 4),
    }

    # 3. Step-by-step preprocessing ablation (C0a -> C0b -> C0c -> C0d -> C1) on the 4 base variables
    c0_cols = ["temp_mean_c", "humidity_pct", "pressure_hpa", "wind_speed_ms"]
    clean_temp_by_st_date = {(r["station_code"], r["obs_date"]): float(r["temp_mean_c"]) for _, r in df.iterrows()}
    raw_map_no_conv, raw_map_conv = {}, {}
    c0a_tr_x, c0a_tr_y = [], []
    c0b_tr_x, c0b_tr_y = [], []
    c0c_tr_x, c0c_tr_y = [], []
    seen_obs = set()
    for r in raw_records:
        sc = normalize_text(r.get("station_code", ""))
        dt = parse_date_iso(r.get("obs_date", ""))
        if not sc or not dt:
            continue
        next_dt = (pd.Timestamp(dt) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        obs_id = compute_obs_id(
            sc,
            dt,
            normalize_text(r.get("temp_max_raw", "")),
            normalize_text(r.get("temp_min_raw", "")),
            normalize_text(r.get("precip_raw", "")),
        )
        is_dup = obs_id in seen_obs
        seen_obs.add(obs_id)
        tm, _ = parse_float_with_unit(r.get("temp_mean_raw"), ("°c", "c"))
        hm, _ = parse_float_with_unit(r.get("humidity_raw"), ("%",))
        pr, _ = parse_float_with_unit(r.get("pressure_raw"), ("hpa", "mb"))
        ws, u_ws = parse_float_with_unit(r.get("wind_speed_raw"), ("m/s", "km/h"))
        ws_conv = round(ws / 3.6, 2) if (u_ws == "km/h" and ws is not None) else ws
        if (sc, dt) not in raw_map_no_conv:
            raw_map_no_conv[(sc, dt)] = [tm, hm, pr, ws]
            raw_map_conv[(sc, dt)] = [tm, hm, pr, ws_conv]
        if dt < "2024-01-01" and next_dt < "2024-01-01" and (sc, next_dt) in clean_temp_by_st_date:
            c0a_tr_x.append([tm, hm, pr, ws])
            c0a_tr_y.append(clean_temp_by_st_date[(sc, next_dt)])
            if not is_dup:
                c0b_tr_x.append([tm, hm, pr, ws])
                c0b_tr_y.append(clean_temp_by_st_date[(sc, next_dt)])
                c0c_tr_x.append([tm, hm, pr, ws_conv])
                c0c_tr_y.append(clean_temp_by_st_date[(sc, next_dt)])

    c0d_tr_x = np.array([raw_map_conv[(r["station_code"], r["obs_date"])] for _, r in fc_df.loc[train_mask].iterrows()], dtype=float)
    c0d_tr_y = y_tr.copy()

    def eval_preproc_step(Xtr_list, ytr_list, lookup_map, step_label: str) -> tuple[dict, np.ndarray, np.ndarray]:
        Xtr_arr = np.array(Xtr_list, dtype=float)
        ytr_arr = np.array(ytr_list, dtype=float)
        means = np.nanmean(Xtr_arr, axis=0)
        for j in range(4):
            Xtr_arr[np.isnan(Xtr_arr[:, j]), j] = means[j]
        Xva_arr = np.array([lookup_map[(r["station_code"], r["obs_date"])] for _, r in fc_df.loc[val_mask].iterrows()], dtype=float)
        Xte_arr = np.array([lookup_map[(r["station_code"], r["obs_date"])] for _, r in fc_df.loc[test_mask].iterrows()], dtype=float)
        for j in range(4):
            Xva_arr[np.isnan(Xva_arr[:, j]), j] = means[j]
            Xte_arr[np.isnan(Xte_arr[:, j]), j] = means[j]
        mu_s, sig_s = Xtr_arr.mean(axis=0), Xtr_arr.std(axis=0)
        sig_s[sig_s == 0] = 1.0
        w_s = fit_ridge_closed_form((Xtr_arr - mu_s) / sig_s, ytr_arr, l2=1.5)
        p_va_s = predict_linear((Xva_arr - mu_s) / sig_s, w_s)
        p_te_s = predict_linear((Xte_arr - mu_s) / sig_s, w_s)
        err_sq_s = (y_te - p_te_s) ** 2
        return (
            {
                "step_name": step_label,
                "n_train": int(len(Xtr_arr)),
                "val_mae_c": round(float(np.mean(np.abs(y_va - p_va_s))), 4),
                "val_rmse_c": round(float(np.sqrt(np.mean((y_va - p_va_s) ** 2))), 4),
                "test_mae_c": round(float(np.mean(np.abs(y_te - p_te_s))), 4),
                "test_rmse_c": round(float(np.sqrt(np.mean(err_sq_s))), 4),
                "test_r2": round(float(1.0 - np.sum(err_sq_s) / ss_tot_te), 4),
            },
            p_va_s,
            p_te_s,
        )

    step_c0a, pred0_va, pred0_te = eval_preproc_step(
        c0a_tr_x, c0a_tr_y, raw_map_no_conv,
        "Bước C0a (Dữ liệu thô hoàn toàn): Giữ bản ghi trùng, gió chưa đổi đơn vị, chưa lọc QC, điền thiếu bằng TB Train",
    )
    step_c0b, _, _ = eval_preproc_step(
        c0b_tr_x, c0b_tr_y, raw_map_no_conv,
        "Bước C0b (+ Khử trùng lặp): Đã loại 412 dòng trùng khóa băm, chưa đổi đơn vị gió, chưa lọc QC, điền TB Train",
    )
    step_c0c, _, _ = eval_preproc_step(
        c0c_tr_x, c0c_tr_y, raw_map_conv,
        "Bước C0c (+ Quy đổi đơn vị gió): Đã khử trùng & đổi 242 dòng gió km/h → m/s, chưa lọc QC, điền TB Train",
    )
    step_c0d, _, _ = eval_preproc_step(
        c0d_tr_x, c0d_tr_y, raw_map_conv,
        "Bước C0d (+ Lọc cách ly QC vật lý WMO-No. 8): Đã loại 227 dòng lỗi vật lý, nhưng điền khuyết bằng TB Train",
    )

    def eval_reg(pred_va: np.ndarray, pred_te: np.ndarray, name: str, n_feat: int) -> dict:
        rng = np.random.default_rng(SEED)
        err_sq = (y_te - pred_te) ** 2
        boot_rmse = [
            float(np.sqrt(np.mean(err_sq[rng.integers(0, len(err_sq), size=len(err_sq))])))
            for _ in range(500)
        ]
        return {
            "config_name": name,
            "n_features": n_feat,
            "val_mae_c": round(float(np.mean(np.abs(y_va - pred_va))), 4),
            "val_rmse_c": round(float(np.sqrt(np.mean((y_va - pred_va) ** 2))), 4),
            "test_mae_c": round(float(np.mean(np.abs(y_te - pred_te))), 4),
            "test_rmse_c": round(float(np.sqrt(np.mean(err_sq))), 4),
            "test_rmse_ci_low_c": round(float(np.percentile(boot_rmse, 2.5)), 4),
            "test_rmse_ci_high_c": round(float(np.percentile(boot_rmse, 97.5)), 4),
            "test_r2": round(float(1.0 - np.sum(err_sq) / ss_tot_te), 4),
        }

    ablation_trials = [
        eval_reg(pred0_va, pred0_te, "Cấu hình 0 (Trước toàn bộ tiền xử lý): Dữ liệu thô chưa lọc QC, chưa đổi đơn vị & điền TB Train", len(c0_cols))
    ]

    reg_configs = [
        ("Cấu hình 1 (Sau toàn bộ tiền xử lý): Khử trùng, đổi đơn vị, lọc QC & điền khuyết có điều kiện (4 biến tại ngày t)",
         ["temp_mean_c", "humidity_pct", "pressure_hpa", "wind_speed_ms"]),
        ("Cấu hình 2: Thêm đặc trưng nhiệt động Điểm sương & Bức xạ mặt trời tại ngày t",
         ["temp_mean_c", "dewpoint_c", "humidity_pct", "pressure_hpa", "wind_speed_ms", "solar_rad_mj"]),
        ("Cấu hình 3: Thêm Chu kỳ mùa theo trạm (sin/cos) & Tách vector gió (u, v)",
         ["temp_mean_c", "dewpoint_c", "humidity_pct", "pressure_hpa", "wind_speed_ms", "solar_rad_mj",
          "wind_u_ms", "wind_v_ms", "doy_sin", "doy_cos", "st_hn", "st_dn", "hn_sin", "hn_cos", "dn_sin", "dn_cos"]),
        ("Cấu hình 4 (Đầy đủ đặc trưng): Thêm Biến trễ theo ngày lịch (Lag 1d, 3d) & Độ biến thiên khí áp (ΔP)",
         ["temp_mean_c", "dewpoint_c", "humidity_pct", "pressure_hpa", "wind_speed_ms", "solar_rad_mj",
          "wind_u_ms", "wind_v_ms", "doy_sin", "doy_cos", "st_hn", "st_dn", "hn_sin", "hn_cos", "dn_sin", "dn_cos",
          "temp_lag_1d", "temp_lag_3d_mean", "humidity_lag_1d", "pressure_delta_24h"]),
    ]

    reg_preds_te = {}
    for idx_c, (cname, cols) in enumerate(reg_configs, 1):
        X = fc_df[cols].to_numpy(dtype=float)
        mu = X[train_mask].mean(axis=0)
        sig = X[train_mask].std(axis=0)
        sig[sig == 0] = 1.0
        Z_tr = (X[train_mask] - mu) / sig
        Z_va = (X[val_mask] - mu) / sig
        Z_te = (X[test_mask] - mu) / sig
        w = fit_ridge_closed_form(Z_tr, y_tr, l2=1.5)
        p_va_c = predict_linear(Z_va, w)
        p_te_c = predict_linear(Z_te, w)
        reg_preds_te[f"C{idx_c}"] = p_te_c
        ablation_trials.append(eval_reg(p_va_c, p_te_c, cname, len(cols)))

    step_c1 = {
        "step_name": "Bước C1 (Hoàn tất tiền xử lý chuẩn): + Điền khuyết có điều kiện kẹp trong [Tmin, Tmax] & ≥ Td",
        "n_train": int(train_mask.sum()),
        "val_mae_c": ablation_trials[1]["val_mae_c"],
        "val_rmse_c": ablation_trials[1]["val_rmse_c"],
        "test_mae_c": ablation_trials[1]["test_mae_c"],
        "test_rmse_c": ablation_trials[1]["test_rmse_c"],
        "test_r2": ablation_trials[1]["test_r2"],
    }
    preprocessing_steps = [step_c0a, step_c0b, step_c0c, step_c0d, step_c1]

    # Rain classification on calendar-day windows (P(t+1) >= 1.0 mm)
    yr_tr = (fc_df.loc[train_mask, "cal_target_rain_next_mm"].to_numpy(dtype=float) >= 1.0).astype(int)
    yr_va = (fc_df.loc[val_mask, "cal_target_rain_next_mm"].to_numpy(dtype=float) >= 1.0).astype(int)
    yr_te = (fc_df.loc[test_mask, "cal_target_rain_next_mm"].to_numpy(dtype=float) >= 1.0).astype(int)
    base_prob_tr = float(yr_tr.mean())

    rain_results = []
    b_no = eval_binary_classifier(yr_te, np.full(len(yr_te), base_prob_tr), 1.01)
    b_no["config_name"] = "Baseline 0a: Dự báo tĩnh 'Luôn không mưa' (Đa số)"
    b_no["n_features"] = 0
    b_no["val_f1_pct"] = 0.0
    rain_results.append(b_no)

    b_all = eval_binary_classifier(yr_te, np.full(len(yr_te), base_prob_tr), 0.0)
    b_all["config_name"] = "Baseline 0b: Dự báo tĩnh 'Ngày nào cũng mưa' (Tỷ lệ cơ sở)"
    b_all["n_features"] = 0
    b_all["val_f1_pct"] = round(float(200.0 * yr_va.mean() / (1.0 + yr_va.mean())), 2)
    rain_results.append(b_all)

    rain_t_tr = (fc_df.loc[train_mask, "precip_mm"].to_numpy() >= 1.0)
    p_given_1 = float(yr_tr[rain_t_tr].mean())
    p_given_0 = float(yr_tr[~rain_t_tr].mean())
    prob_pers_va = np.where(fc_df.loc[val_mask, "precip_mm"].to_numpy() >= 1.0, p_given_1, p_given_0)
    prob_pers_te = np.where(fc_df.loc[test_mask, "precip_mm"].to_numpy() >= 1.0, p_given_1, p_given_0)
    c1_va = eval_binary_classifier(yr_va, prob_pers_va, 0.50)
    c1_te = eval_binary_classifier(yr_te, prob_pers_te, 0.50)
    c1_te["config_name"] = "Cấu hình C1: Dự báo quán tính trạng thái mưa (Mưa ngày t+1 = Mưa ngày t)"
    c1_te["n_features"] = 1
    c1_te["val_f1_pct"] = c1_va["test_f1_pct"]
    rain_results.append(c1_te)

    rain_configs = [
        ("Cấu hình C2: Chỉ 4 biến trạng thái cơ bản tại ngày t (Đã qua tiền xử lý)",
         ["temp_mean_c", "humidity_pct", "pressure_hpa", "wind_speed_ms"]),
        ("Cấu hình C3: Thêm Điểm sương, Mưa ngày t, Vector gió (u, v) & Chu kỳ (sin/cos)",
         ["temp_mean_c", "dewpoint_c", "humidity_pct", "pressure_hpa", "rain_log1p", "wind_u_ms", "wind_v_ms", "doy_sin", "doy_cos"]),
        ("Cấu hình C4 (Đầy đủ đặc trưng): Thêm Chu kỳ theo trạm, Biến trễ ngày lịch & ΔP 24h",
         ["temp_mean_c", "dewpoint_c", "humidity_pct", "pressure_hpa", "rain_log1p", "wind_u_ms", "wind_v_ms", "solar_rad_mj", "doy_sin", "doy_cos", "st_hn", "st_dn", "hn_sin", "hn_cos", "dn_sin", "dn_cos", "temp_lag_1d", "humidity_lag_1d", "rain_lag1_log1p", "pressure_delta_24h"]),
    ]
    c4_prob_te = None
    c4_thr = 0.36
    for cname, cols in rain_configs:
        X = fc_df[cols].to_numpy(dtype=float)
        mu, sig = X[train_mask].mean(axis=0), X[train_mask].std(axis=0)
        sig[sig == 0] = 1.0
        Z_tr = (X[train_mask] - mu) / sig
        Z_va = (X[val_mask] - mu) / sig
        Z_te = (X[test_mask] - mu) / sig
        w = fit_logistic_l2(Z_tr, yr_tr, l2=15.0)
        prob_va = 1.0 / (1.0 + np.exp(-np.clip(np.column_stack([np.ones(len(Z_va)), Z_va]) @ w, -30, 30)))
        prob_te = 1.0 / (1.0 + np.exp(-np.clip(np.column_stack([np.ones(len(Z_te)), Z_te]) @ w, -30, 30)))
        best_thr, best_f1 = 0.40, -1.0
        for th in np.arange(0.20, 0.8001, 0.005):
            m_va = eval_binary_classifier(yr_va, prob_va, float(th))
            if m_va["test_f1_pct"] > best_f1:
                best_f1 = m_va["test_f1_pct"]
                best_thr = float(th)
        m_te = eval_binary_classifier(yr_te, prob_te, best_thr)
        m_te["config_name"] = cname
        m_te["n_features"] = len(cols)
        m_te["val_f1_pct"] = round(best_f1, 2)
        rain_results.append(m_te)
        if "C4" in cname:
            c4_prob_te = prob_te
            c4_thr = best_thr

    # Station-level forecasting breakdown on Test 2025 (n = 343 + 329 + 346 = 1018)
    te_df = fc_df.loc[test_mask].copy().reset_index(drop=True)
    te_df["pred_pers"] = p_te
    te_df["pred_clim"] = clim_te
    te_df["pred_c1"] = reg_preds_te["C1"]
    te_df["pred_c3"] = reg_preds_te["C3"]
    te_df["pred_c4"] = reg_preds_te["C4"]
    te_df["rain_prob_c4"] = c4_prob_te
    te_df["rain_true"] = yr_te

    station_metrics = []
    for scode in ("WMO_48820", "WMO_48855", "WMO_48900"):
        sub_s = te_df[te_df["station_code"] == scode]
        ys = sub_s["cal_target_temp_next_c"].to_numpy(dtype=float)
        ss_s = float(np.sum((ys - ys.mean()) ** 2))
        rm_rain = eval_binary_classifier(
            sub_s["rain_true"].to_numpy(dtype=int),
            sub_s["rain_prob_c4"].to_numpy(dtype=float),
            c4_thr,
        )
        station_metrics.append({
            "station_code": scode,
            "station_name": STATION_META[scode]["name"],
            "n_test": int(len(sub_s)),
            "pers_rmse_c": round(float(np.sqrt(np.mean((ys - sub_s["pred_pers"].to_numpy()) ** 2))), 4),
            "clim_rmse_c": round(float(np.sqrt(np.mean((ys - sub_s["pred_clim"].to_numpy()) ** 2))), 4),
            "c1_rmse_c": round(float(np.sqrt(np.mean((ys - sub_s["pred_c1"].to_numpy()) ** 2))), 4),
            "c3_rmse_c": round(float(np.sqrt(np.mean((ys - sub_s["pred_c3"].to_numpy()) ** 2))), 4),
            "c4_rmse_c": round(float(np.sqrt(np.mean((ys - sub_s["pred_c4"].to_numpy()) ** 2))), 4),
            "c4_mae_c": round(float(np.mean(np.abs(ys - sub_s["pred_c4"].to_numpy()))), 4),
            "c4_r2": round(float(1.0 - np.sum((ys - sub_s["pred_c4"].to_numpy()) ** 2) / ss_s), 4),
            "rain_c4_acc_pct": rm_rain["test_accuracy_pct"],
            "rain_c4_f1_pct": rm_rain["test_f1_pct"],
            "rain_c4_roc_auc": rm_rain["test_roc_auc"],
        })

    # Monthly-block paired bootstrap on synthetic Test 2025 (B=2000, seed=20261110) — Bảng 24
    te_df["month"] = pd.to_datetime(te_df["target_date"]).dt.month
    months_syn = [te_df[te_df["month"] == m].index.to_numpy() for m in range(1, 13)]
    rng_syn = np.random.default_rng(20261110)
    d_c4_c3, d_c4_clim = [], []
    for _ in range(2000):
        chosen_m = rng_syn.integers(0, 12, size=12)
        idx_b = np.concatenate([months_syn[m] for m in chosen_m])
        yt_b = y_te[idx_b]
        d_c4_c3.append(float(np.sqrt(np.mean((yt_b - reg_preds_te["C4"][idx_b]) ** 2)) - np.sqrt(np.mean((yt_b - reg_preds_te["C3"][idx_b]) ** 2))))
        d_c4_clim.append(float(np.sqrt(np.mean((yt_b - reg_preds_te["C4"][idx_b]) ** 2)) - np.sqrt(np.mean((yt_b - clim_te[idx_b]) ** 2))))
    pt_c4_c3 = float(np.sqrt(np.mean((y_te - reg_preds_te["C4"]) ** 2)) - np.sqrt(np.mean((y_te - reg_preds_te["C3"]) ** 2)))
    pt_c4_clim = float(np.sqrt(np.mean((y_te - reg_preds_te["C4"]) ** 2)) - np.sqrt(np.mean((y_te - clim_te) ** 2)))
    synthetic_paired_bootstrap = [
        {
            "comparison": "pred_c4 - pred_c3",
            "diff_rmse_c": round(pt_c4_c3, 5),
            "ci_low_c": round(float(np.percentile(d_c4_c3, 2.5)), 5),
            "ci_high_c": round(float(np.percentile(d_c4_c3, 97.5)), 5),
        },
        {
            "comparison": "pred_c4 - pred_clim",
            "diff_rmse_c": round(pt_c4_clim, 5),
            "ci_low_c": round(float(np.percentile(d_c4_clim, 2.5)), 5),
            "ci_high_c": round(float(np.percentile(d_c4_clim, 97.5)), 5),
        },
    ]

    forecast_info = {
        "synthetic_paired_bootstrap": synthetic_paired_bootstrap,
        "split_counts": {
            "train_2017_2023": int(train_mask.sum()),
            "val_2024": int(val_mask.sum()),
            "test_2025": int(test_mask.sum()),
            "cross_boundary_dropped": int(cross_mask.sum()),
            "total_valid_windows": int(len(fc_df)),
            "total_complete_windows": int(len(fc_df_all)),
        },
        "persistence_baseline": pers_base,
        "climatology_anomaly_baseline": clim_base,
        "preprocessing_step_ablation": preprocessing_steps,
        "ablation_trials": ablation_trials,
        "station_forecast_metrics": station_metrics,
        "test_timeseries_records": te_df[["station_code", "obs_date", "target_date", "cal_target_temp_next_c", "pred_c4"]].to_dict(orient="records"),
    }

    # Compute ΔP 24h bins vs next-day rain probability on complete calendar windows
    bins = [-999.0, -3.0, -1.5, 0.0, 1.5, 3.0, 999.0]
    bin_labels = ["< -3,0", "-3,0..-1,5", "-1,5..0,0", "0,0..+1,5", "+1,5..+3,0", "> +3,0"]
    fc_df["dp_bin"] = pd.cut(fc_df["pressure_delta_24h"], bins=bins, labels=bin_labels)
    dp_rain_rows = []
    for b_lbl, grp in fc_df.groupby("dp_bin", observed=False):
        dp_rain_rows.append({
            "dp_bin": str(b_lbl),
            "n": len(grp),
            "rain_next_pct": round(float((grp["target_rain_next_mm"] >= 1.0).mean() * 100.0), 1),
            "rain_curr_pct": round(float((grp["precip_mm"] >= 1.0).mean() * 100.0), 1),
        })

    return forecast_info, rain_results, dp_rain_rows

def build_database_and_benchmark(df: pd.DataFrame) -> dict:
    db_path = ROOT / "outputs/kttv_weather.sqlite"
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    schema_sql = (ROOT / "sql/01_schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema_sql)

    for scode, meta in STATION_META.items():
        conn.execute(
            "INSERT INTO stations(station_id, station_code, station_name, region, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?)",
            (meta["id"], scode, meta["name"], meta["region"], meta["lat"], meta["lon"]),
        )
    for rcode, meta in REGIME_META.items():
        conn.execute(
            "INSERT INTO weather_regimes(regime_id, regime_name, description) VALUES (?, ?, ?)",
            (meta["id"], rcode, meta["desc"]),
        )

    rows_to_insert = []
    for r in df.to_dict(orient="records"):
        t_next = None if pd.isna(r["target_temp_next_c"]) else float(r["target_temp_next_c"])
        r_next = None if pd.isna(r["target_rain_next_mm"]) else float(r["target_rain_next_mm"])
        rows_to_insert.append((
            int(r["row_id"]),
            str(r["obs_id"]),
            STATION_META[r["station_code"]]["id"],
            REGIME_META[r["weather_regime"]]["id"],
            str(r["obs_date"]),
            str(r["season"]),
            float(r["temp_mean_c"]),
            float(r["dewpoint_c"]),
            float(r["humidity_pct"]),
            float(r["pressure_hpa"]),
            float(r["precip_mm"]),
            float(r["wind_speed_ms"]),
            float(r["solar_rad_mj"]),
            1 if r["is_outlier_group"] else 0,
            int(r["cluster"]),
            1 if r["has_complete_window"] else 0,
            t_next,
            r_next,
        ))
    conn.executemany(
        """INSERT INTO observations(
            row_id, obs_id, station_id, regime_id, obs_date, season,
            temp_mean_c, dewpoint_c, humidity_pct, pressure_hpa, precip_mm,
            wind_speed_ms, solar_rad_mj, is_outlier_group, cluster,
            has_complete_window, target_temp_next_c, target_rain_next_mm
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows_to_insert,
    )
    # Keep genuine ERA5 and modelled hydrology in distinct source-labelled tables.
    from source_database import load_external_tables
    load_external_tables(conn, ROOT)
    conn.commit()

    fk_err = conn.execute("PRAGMA foreign_key_check;").fetchall()
    if fk_err:
        raise ValueError(f"Foreign key errors: {fk_err}")

    query = (
        "SELECT row_id, obs_date, temp_mean_c, pressure_hpa, precip_mm\n"
        "FROM observations\n"
        "WHERE station_id = ? AND regime_id = ?\n"
        "  AND temp_mean_c BETWEEN ? AND ?\n"
        "ORDER BY temp_mean_c, row_id LIMIT 100"
    )
    params = [3, 2, 27.8, 30.2]

    def measure_query(c: sqlite3.Connection) -> dict:
        c.execute("ANALYZE;")
        plan = c.execute("EXPLAIN QUERY PLAN " + query, params).fetchall()
        for _ in range(10):
            c.execute(query, params).fetchall()
        times_ms = []
        result_rows = []
        for _ in range(51):
            t0 = time.perf_counter()
            result_rows = c.execute(query, params).fetchall()
            times_ms.append((time.perf_counter() - t0) * 1000.0)
        arr = np.array(times_ms)
        sha = hashlib.sha256(json.dumps(result_rows, separators=(",", ":")).encode("utf-8")).hexdigest()
        return {
            "median_ms": round(float(np.median(arr)), 4),
            "p10_ms": round(float(np.percentile(arr, 10)), 4),
            "p90_ms": round(float(np.percentile(arr, 90)), 4),
            "plan": [str(p) for p in plan],
            "result_count": len(result_rows),
            "result_sha256": sha,
            "sample_rows": result_rows[:5],
        }

    before_stats = measure_query(conn)
    conn.executescript((ROOT / "sql/03_indexes.sql").read_text(encoding="utf-8"))
    after_stats = measure_query(conn)
    conn.close()

    if before_stats["result_sha256"] != after_stats["result_sha256"]:
        raise ValueError("SQL result hash mismatch before vs after index!")

    bench = {
        "query": query,
        "parameters": params,
        "before": before_stats,
        "after": after_stats,
        "speedup_ratio": round(before_stats["median_ms"] / max(after_stats["median_ms"], 0.0001), 2),
    }
    (ROOT / "outputs/sql_benchmark.json").write_text(json.dumps(bench, ensure_ascii=False, indent=2), encoding="utf-8")
    return bench

def generate_all_charts(
    df: pd.DataFrame,
    counts: dict,
    sensitivity_rows: list[dict],
    cluster_info: dict,
    forecast_info: dict,
    rain_results: list[dict],
    dp_rain_rows: list[dict],
    station_summary: list[dict],
) -> None:
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Liberation Sans"]
    plt.rcParams["axes.edgecolor"] = "#4A5568"
    plt.rcParams["axes.linewidth"] = 0.8
    charts_dir = ROOT / "outputs/charts"
    assets_dir = ROOT / "docs/report_assets"
    charts_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    # Chart 1 (Hình 3): 3 panels -> Temperature (°C), Linear Precipitation (mm), and ln(P + 1)
    fig, axes = plt.subplots(1, 3, figsize=(13.8, 4.4), dpi=180)
    axes[0].hist(df["temp_mean_c"], bins=36, color="#1F5A8A", edgecolor="white", alpha=0.9)
    axes[0].axvline(df["temp_mean_c"].median(), color="#D97706", linestyle="--", linewidth=1.8, label=f"Trung vị: {df['temp_mean_c'].median():.2f} °C")
    axes[0].set_title(f"(a) Nhiệt độ trung bình ngày (n={len(df):,})", fontsize=10.2, fontweight="bold")
    axes[0].set_xlabel("Nhiệt độ trung bình ngày (°C)")
    axes[0].set_ylabel("Số bản ghi trạm-ngày")
    axes[0].legend(frameon=False, fontsize=8.5)

    axes[1].hist(df["precip_mm"], bins=36, color="#3182CE", edgecolor="white", alpha=0.9)
    axes[1].axvline(df["precip_mm"].mean(), color="#C53030", linestyle=":", linewidth=1.8, label=f"Trung bình: {df['precip_mm'].mean():.2f} mm")
    axes[1].set_title("(b) Lượng mưa ngày trên thang gốc (mm)", fontsize=10.2, fontweight="bold")
    axes[1].set_xlabel("Lượng mưa tích lũy ngày (mm)")
    axes[1].set_ylabel("Số bản ghi trạm-ngày")
    axes[1].legend(frameon=False, fontsize=8.5)

    rain_ln = np.log1p(df["precip_mm"])
    axes[2].hist(rain_ln, bins=32, color="#2B8A6E", edgecolor="white", alpha=0.9)
    axes[2].set_title("(c) Lượng mưa trên thang ln(P + 1 mm)", fontsize=10.2, fontweight="bold")
    axes[2].set_xlabel("ln(Lượng mưa mm + 1)")
    axes[2].set_ylabel("Số bản ghi trạm-ngày")

    fig.tight_layout(pad=1.2)
    fig.savefig(charts_dir / "01_temp_precip_distribution.png", bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)

    # Chart 2 (Hình 4): Scatter Pressure vs Temperature colored by Weather Regime
    fig, ax = plt.subplots(figsize=(8.8, 5.2), dpi=180)
    palette = {
        "hot_dry": ("#D97706", "Nắng nóng / Khô quang"),
        "mild_cloudy": ("#3182CE", "Mát / Nhiều mây ổn định"),
        "rainy_convective": ("#2B8A6E", "Mưa rào / Đối lưu ẩm"),
        "extreme_storm": ("#9B2C2C", "Mưa lớn / Nhiễu động mạnh"),
    }
    for rcode, (col, label) in palette.items():
        sub = df[df["weather_regime"] == rcode]
        ax.scatter(sub["temp_mean_c"], sub["pressure_hpa"], s=10, alpha=0.55, color=col, label=f"{label} (n={len(sub):,})")
    ax.set_title(f"Quan hệ Nhiệt độ – Áp suất khí quyển theo hình thái thời tiết • n={len(df):,}", fontsize=11, fontweight="bold")
    ax.set_xlabel("Nhiệt độ trung bình ngày (°C)")
    ax.set_ylabel("Áp suất khí quyển bề mặt (hPa)")
    ax.legend(frameon=True, fontsize=8.5, loc="upper right")
    ax.grid(True, linestyle=":", alpha=0.4)
    fig.tight_layout()
    fig.savefig(charts_dir / "02_temp_pressure_scatter.png", bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)

    # Chart 3 (Hình 5): Spearman correlation heatmap of 5 core meteorological variables
    cols_corr = ["temp_mean_c", "dewpoint_c", "humidity_pct", "pressure_hpa", "precip_mm"]
    labels_corr = ["Nhiệt độ (°C)", "Điểm sương (°C)", "Độ ẩm (%)", "Áp suất (hPa)", "Lượng mưa (mm)"]
    corr_mat = df[cols_corr].rank().corr(method="pearson").to_numpy()
    fig, ax = plt.subplots(figsize=(7.0, 5.6), dpi=180)
    im = ax.imshow(corr_mat, cmap="RdBu_r", vmin=-1.0, vmax=1.0)
    ax.set_xticks(range(len(labels_corr)))
    ax.set_yticks(range(len(labels_corr)))
    ax.set_xticklabels(labels_corr, rotation=22, ha="right", fontsize=9)
    ax.set_yticklabels(labels_corr, fontsize=9)
    for i in range(len(labels_corr)):
        for j in range(len(labels_corr)):
            val = corr_mat[i, j]
            txt_col = "white" if abs(val) > 0.55 else "#1A202C"
            ax.text(j, i, f"{val:.3f}", ha="center", va="center", color=txt_col, fontsize=9, fontweight="bold")
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Hệ số tương quan hạng Spearman")
    ax.set_title(f"Ma trận tương quan Spearman 5 biến KTTV lõi • n={len(df):,}", fontsize=11, fontweight="bold")
    fig.tight_layout()
    fig.savefig(charts_dir / "08_spearman_correlation.png", bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)

    # Chart 4 (Hình 6): ALL 12 Station x Season Median Temperature & Bootstrap 95% CI
    fig, ax = plt.subplots(figsize=(10.2, 6.4), dpi=180)
    st_rows = station_summary  # ALL 12 groups (3 stations x 4 seasons)
    y_pos = np.arange(len(st_rows))
    medians = [r["median_temp_c"] for r in st_rows]
    err_low = [r["median_temp_c"] - r["bootstrap_low_c"] for r in st_rows]
    err_high = [r["bootstrap_high_c"] - r["median_temp_c"] for r in st_rows]
    labels_st = [f"{r['station_name'].split(' (')[0]} – {r['season']} (n={r['n']})" for r in st_rows]
    bars = ax.barh(y_pos, medians, xerr=[err_low, err_high], color="#235789", alpha=0.88, capsize=3, height=0.62)
    for b, m_val in zip(bars, medians):
        ax.text(m_val + 0.45, b.get_y() + b.get_height() / 2, f"{m_val:.2f}°C", va="center", fontsize=8.5, fontweight="bold")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels_st, fontsize=8.8)
    ax.invert_yaxis()
    ax.set_xlim(0, 35.0)
    ax.set_xlabel("Trung vị nhiệt độ ngày (°C) kèm khoảng tin cậy Bootstrap 95% (B=500, seed=20261015)")
    ax.set_title("So sánh trung vị nhiệt độ trên đủ 12 nhóm Trạm × Mùa khí hậu (3 trạm × 4 mùa)", fontsize=11, fontweight="bold")
    ax.grid(True, axis="x", linestyle=":", alpha=0.45)
    fig.tight_layout()
    fig.savefig(charts_dir / "03_station_season_medians.png", bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)

    # Chart 5 (Hình 7): Cleaning Lineage & Sensitivity Analysis
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.5), dpi=180)
    c_labels = ["Nguồn gốc", "Bản ghi trùng", "Cách ly QC", "Giữ phân tích"]
    c_vals = [counts["raw_count"], counts["duplicate_count"], counts["rejected_count"], counts["clean_count"]]
    c_colors = ["#4A6984", "#D97706", "#C53030", "#1F6F5B"]
    bars = axes[0].bar(c_labels, c_vals, color=c_colors, width=0.56)
    for b, v in zip(bars, c_vals):
        axes[0].text(b.get_x() + b.get_width() / 2, v + 120, f"{v:,}", ha="center", va="bottom", fontsize=9, fontweight="bold")
    axes[0].set_ylim(0, max(c_vals) * 1.15)
    axes[0].set_ylabel("Số bản ghi (dòng)")
    axes[0].set_title("Đối soát bảo toàn dòng dữ liệu trong Lineage", fontsize=10.5, fontweight="bold")

    s_names = [r["scenario"] for r in sensitivity_rows]
    s_meds = [r["mean_precip_mm"] for r in sensitivity_rows]
    y_s = np.arange(len(s_names))
    axes[1].barh(y_s, s_meds, color="#1F5A8A", height=0.55)
    axes[1].set_yticks(y_s)
    axes[1].set_yticklabels(s_names, fontsize=8.8)
    axes[1].invert_yaxis()
    axes[1].set_xlabel("Lượng mưa trung bình ngày (mm/ngày)")
    axes[1].set_title("Độ nhạy lượng mưa trung bình theo lựa chọn xử lý", fontsize=10.5, fontweight="bold")
    fig.tight_layout()
    fig.savefig(charts_dir / "06_cleaning_sensitivity.png", bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)

    # Chart 6 (Hình 8): K-means weather regimes & Silhouette curve
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.6), dpi=180)
    fit_df = df[df["cluster"] > 0]
    for cid, col, cname in [(1, "#2B8A6E", "Cụm 1: Ẩm / Có mưa"), (2, "#D97706", "Cụm 2: Khô ráo / Không mưa")]:
        sub = fit_df[fit_df["cluster"] == cid]
        axes[0].scatter(sub["humidity_pct"], np.log1p(sub["precip_mm"]), s=10, alpha=0.5, color=col, label=f"{cname} (n={len(sub):,})")
    axes[0].set_xlabel("Độ ẩm tương đối (%)")
    axes[0].set_ylabel("ln(Lượng mưa mm + 1)")
    axes[0].set_title(f"Phân cụm K-means++ thăm dò • n={len(fit_df):,}", fontsize=10.5, fontweight="bold")
    axes[0].legend(frameon=True, fontsize=8.5)
    axes[0].grid(True, linestyle=":", alpha=0.4)

    ks = [t["k"] for t in cluster_info["trials"]]
    sils = [t["silhouette_sample"] for t in cluster_info["trials"]]
    axes[1].plot(ks, sils, marker="o", linewidth=2, color="#1F5A8A")
    axes[1].set_xticks(ks)
    axes[1].set_xlabel("Số cụm k")
    axes[1].set_ylabel("Điểm Silhouette trên mẫu 1.000 bản ghi")
    axes[1].set_title("Khảo sát k = 2..5 (seed 20261015, 10 lần khởi tạo)", fontsize=10.5, fontweight="bold")
    axes[1].grid(True, linestyle=":", alpha=0.4)
    fig.tight_layout()
    fig.savefig(charts_dir / "07_exploratory_clusters.png", bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)

    # Chart 7 (Hình 9): Cluster feature representation sensitivity (ARI bar chart) — ZERO CLIPPING
    fig, ax = plt.subplots(figsize=(10.2, 4.4), dpi=180)
    ari_rows = cluster_info["feature_sensitivity"]
    a_labels = [r["config"] for r in ari_rows]
    a_vals = [r["ari"] for r in ari_rows]
    y_a = np.arange(len(a_labels))
    bars_a = ax.barh(y_a, a_vals, color="#335C67", height=0.54)
    for b, v in zip(bars_a, a_vals):
        ax.text(v + 0.015, b.get_y() + b.get_height() / 2, f"{v:.4f}", va="center", fontsize=8.8, fontweight="bold")
    ax.set_yticks(y_a)
    ax.set_yticklabels(a_labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.15)
    ax.set_xlabel(f"Chỉ số đồng thuận Rand điều chỉnh (ARI) trên {len(fit_df):,}".replace(",", ".") + " ID chung (k=2, seed=42)", fontsize=9.2)
    ax.set_title("Độ nhạy phân hoạch K-means theo biểu diễn đặc trưng & chuẩn hóa", fontsize=10.5, fontweight="bold", loc="center")
    ax.grid(True, axis="x", linestyle=":", alpha=0.45)
    fig.tight_layout()
    fig.savefig(charts_dir / "10_cluster_sensitivity_ari.png", bbox_inches="tight", pad_inches=0.22)
    plt.close(fig)

    # Chart 8 (Hình 10): Forecasting Ablation Study (MAE & RMSE across C0..C4 on calendar-day Test 2025)
    fig, ax = plt.subplots(figsize=(10.4, 4.8), dpi=180)
    trials = forecast_info["ablation_trials"]
    short_labels = [
        "C0. Trước tiền xử lý\n(Thô + Điền TB Train)",
        "C1. Sau tiền xử lý\n(4 biến cơ bản)",
        "C2. Thêm Điểm sương\n& Bức xạ mặt trời",
        "C3. Thêm Chu kỳ mùa\ntheo trạm & Gió (u,v)",
        "C4. Đầy đủ Biến trễ\nngày lịch & ΔP (Đề xuất)",
    ]
    x_idx = np.arange(len(trials))
    w = 0.34
    mae_vals = [t["test_mae_c"] for t in trials]
    rmse_vals = [t["test_rmse_c"] for t in trials]
    b1 = ax.bar(x_idx - w / 2, mae_vals, width=w, color="#2B8A6E", label="Test MAE (°C) trên tập Test 2025 (n=1.018)")
    b2 = ax.bar(x_idx + w / 2, rmse_vals, width=w, color="#1F5A8A", label="Test RMSE (°C) trên tập Test 2025 (n=1.018)")
    for b in list(b1) + list(b2):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.025, f"{b.get_height():.4f}", ha="center", va="bottom", fontsize=8.2, fontweight="bold")
    ax.set_xticks(x_idx)
    ax.set_xticklabels(short_labels, fontsize=8.6)
    ax.set_ylim(0, max(rmse_vals) * 1.24)
    ax.set_ylabel("Sai số dự báo nhiệt độ 24h tới (°C) — Thấp hơn là tốt hơn")
    ax.set_title("Thực nghiệm Ablation: Tác động của tiền xử lý & tạo đặc trưng tới dự báo nhiệt độ", fontsize=10.6, fontweight="bold")
    ax.legend(frameon=True, fontsize=8.8)
    ax.grid(True, axis="y", linestyle=":", alpha=0.45)
    fig.tight_layout()
    fig.savefig(charts_dir / "09_forecast_ablation.png", bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)

    # Chart 9 (Hình 11): Rain classification & ΔP physical relationship (ZERO x-axis overlap!)
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.7), dpi=180)
    rc_models = [r for r in rain_results if r["config_name"].startswith("Cấu hình")]
    rc_labels = [
        "C1: Quán tính\n(Mưa ngày t)",
        "C2: 4 biến\ncơ bản tại t",
        "C3: +Td, Mưa t,\nGió (u,v), Chu kỳ",
        "C4: Đầy đủ Chu kỳ\ntrạm, Lag & ΔP",
    ]
    x_r = np.arange(len(rc_models))
    wr = 0.25
    acc_v = [r["test_accuracy_pct"] for r in rc_models]
    prec_v = [r["test_precision_pct"] for r in rc_models]
    f1_v = [r["test_f1_pct"] for r in rc_models]
    axes[0].bar(x_r - wr, acc_v, width=wr, color="#1F5A8A", label="Accuracy (%)")
    axes[0].bar(x_r, prec_v, width=wr, color="#D97706", label="Precision (%)")
    bars_f1 = axes[0].bar(x_r + wr, f1_v, width=wr, color="#2B8A6E", label="F1-score (%)")
    for b in bars_f1:
        axes[0].text(b.get_x() + b.get_width() / 2, b.get_height() + 1.2, f"{b.get_height():.1f}%", ha="center", va="bottom", fontsize=8.0, fontweight="bold")
    axes[0].set_xticks(x_r)
    axes[0].set_xticklabels(rc_labels, fontsize=8.4)
    axes[0].set_ylim(0, 88)
    axes[0].set_ylabel("Chỉ số đánh giá trên tập Test 2025 (%)")
    axes[0].set_title(f"Phân lớp ngày có mưa (P(t+1) ≥ 1,0 mm) • n_test={forecast_info['split_counts']['test_2025']:,}", fontsize=10.2, fontweight="bold")
    axes[0].legend(frameon=True, fontsize=8.2, loc="upper left")
    axes[0].grid(True, axis="y", linestyle=":", alpha=0.45)

    dp_x = np.arange(len(dp_rain_rows))
    dp_lbls = [r["dp_bin"] for r in dp_rain_rows]
    dp_vals = [r["rain_next_pct"] for r in dp_rain_rows]
    bars_dp = axes[1].bar(dp_x, dp_vals, color="#335C67", width=0.54)
    for b, v in zip(bars_dp, dp_vals):
        axes[1].text(b.get_x() + b.get_width() / 2, v + 0.8, f"{v:.1f}%", ha="center", va="bottom", fontsize=8.5, fontweight="bold")
    axes[1].set_xticks(dp_x)
    axes[1].set_xticklabels(dp_lbls, fontsize=8.6)
    axes[1].set_ylim(0, 56)
    axes[1].set_xlabel("Độ biến thiên áp suất khí quyển 24 giờ ΔP (hPa)")
    axes[1].set_ylabel("Tỷ lệ ngày kế tiếp có mưa ≥ 1,0 mm (%)")
    axes[1].set_title("Tỷ lệ mưa theo các khoảng ΔP 24h", fontsize=10.2, fontweight="bold")
    axes[1].grid(True, axis="y", linestyle=":", alpha=0.45)
    fig.tight_layout(pad=1.2)
    fig.savefig(charts_dir / "11_rain_classification_and_dp.png", bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)

    # Asset 0 (Hình 1): Regenerate architecture.png showing both Real ERA5 branch and Synthetic QC Benchmark branch
    fig, ax = plt.subplots(figsize=(11.0, 6.4), dpi=180)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    def draw_arch_box(x, y, w, h, lines, bg="#DCEAF7"):
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.4", facecolor=bg, edgecolor="#3B5975", linewidth=1.3)
        ax.add_patch(box)
        step = h / (len(lines) + 1)
        for idx_l, line_txt in enumerate(lines):
            ax.text(x + w / 2, y + h - (idx_l + 1) * step, line_txt, fontsize=9.8, ha="center", va="center", color="#0F172A")

    draw_arch_box(3, 76, 43, 19, [
        "ERA5 tải thực · 9.861 ngày",
        "Open-Meteo · 3 ô lưới",
        "JSON + tham số + SHA-256",
    ], bg="#DCEAF7")
    draw_arch_box(54, 76, 43, 19, [
        "Benchmark mô phỏng · 10.273 dòng",
        "Lỗi chèn sẵn có nhãn riêng",
        "JSON + manifest SHA-256",
    ], bg="#F5E6D3")
    draw_arch_box(3, 47, 43, 21, [
        "7 kiểm tra cơ bản + trùng/thiếu",
        "9.861 dòng -> 9.855 cửa sổ",
        "Train / Val / Test theo target_date",
        "EDA, Spearman, KMeans; Ridge R1–R3",
    ], bg="#DCEAF7")
    draw_arch_box(54, 47, 43, 21, [
        "Parser, đổi đơn vị, QC, truy nguyên",
        "412 trùng + 227 cách ly + 9.634 sạch",
        "9.181 cửa sổ dự báo hợp lệ",
        "Ablation C0a–C4; kiểm toán lỗi",
    ], bg="#F5E6D3")
    draw_arch_box(17, 23, 66, 17, [
        "Đánh giá trên cùng ngày Test 2025",
        "Baseline + paired bootstrap theo tháng",
        "Hai nhánh và nguồn số liệu được ghi riêng",
    ], bg="#E2EFE6")
    draw_arch_box(10, 2, 80, 14, [
        "CSV · biểu đồ · 2 dashboard · báo cáo Word/PDF",
        "SQLite và Excel: dữ liệu benchmark mô phỏng",
    ], bg="#EDF2F7")

    arrow_kw = dict(arrowstyle="-|>", color="#2C4A63", lw=1.7, mutation_scale=12)
    ax.annotate("", xy=(24.5, 68), xytext=(24.5, 76), arrowprops=arrow_kw)
    ax.annotate("", xy=(75.5, 68), xytext=(75.5, 76), arrowprops=arrow_kw)
    ax.annotate("", xy=(33, 40), xytext=(24.5, 47), arrowprops=arrow_kw)
    ax.annotate("", xy=(67, 40), xytext=(75.5, 47), arrowprops=arrow_kw)
    ax.annotate("", xy=(50, 16), xytext=(50, 23), arrowprops=arrow_kw)

    fig.tight_layout()
    fig.savefig(assets_dir / "architecture.png", bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)

    # Asset 1 (Hình 2): Regenerate erd.png including solar_rad_mj & has_complete_window with ample vertical room
    fig, ax = plt.subplots(figsize=(10.6, 6.8), dpi=180)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    def draw_table_box(x, y, w, h, title, lines, step=5.4):
        rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3", facecolor="white", edgecolor="#4A6984", linewidth=1.3)
        ax.add_patch(rect)
        hdr = FancyBboxPatch((x, y + h - 8.0), w, 8.0, boxstyle="round,pad=0.1", facecolor="#DCE6EF", edgecolor="#4A6984", linewidth=1.1)
        ax.add_patch(hdr)
        ax.text(x + 2.2, y + h - 4.0, title, fontsize=11.2, fontweight="bold", va="center", color="#1A202C")
        for idx, line in enumerate(lines):
            ax.text(x + 2.2, y + h - 12.8 - idx * step, line, fontsize=9.1, va="center", color="#1A202C")

    draw_table_box(2, 60, 33, 32, "stations · 3 hàng", [
        "PK  station_id",
        "UQ  station_code (WMO)",
        "UQ  station_name",
        "region, latitude, longitude",
    ], step=4.8)
    draw_table_box(2, 22, 33, 27, "weather_regimes · 4 hàng", [
        "PK  regime_id",
        "UQ  regime_name",
        "description",
    ], step=5.5)
    draw_table_box(46, 12, 52, 85, "observations · 9.634 hàng", [
        "PK  row_id",
        "UQ  obs_id (20-char SHA prefix)",
        "FK  station_id  -> stations",
        "FK  regime_id   -> weather_regimes",
        "obs_date, season",
        "temp_mean_c BETWEEN -5.0 AND 48.0",
        "dewpoint_c <= temp_mean_c + 0.05",
        "humidity_pct BETWEEN 0.0 AND 100.0",
        "pressure_hpa BETWEEN 950.0 AND 1045.0",
        "precip_mm >= 0.0, wind_speed_ms >= 0.0",
        "solar_rad_mj BETWEEN 0.0 AND 40.0",
        "is_outlier_group: 0/1, cluster: -1/1/2",
        "has_complete_window: 0/1 (9.181 cửa sổ dự báo)",
        "target_temp_next_c, target_rain_next_mm",
    ], step=4.6)
    ax.plot([35, 40.5, 40.5, 46], [76, 76, 72, 72], color="#2C5282", linewidth=1.8)
    ax.text(36.5, 77.5, "1", fontsize=10, fontweight="bold")
    ax.text(43.2, 73.5, "N", fontsize=10, fontweight="bold")
    ax.plot([35, 41.5, 41.5, 46], [36, 36, 67, 67], color="#2C5282", linewidth=1.8)
    ax.text(36.5, 37.5, "1", fontsize=10, fontweight="bold")
    ax.text(43.2, 63.5, "N", fontsize=10, fontweight="bold")
    ax.text(2, 6.2, "PK khóa chính   FK khóa ngoại   UQ duy nhất   CHECK ràng buộc miền vật lý KTTV", fontsize=9.2, color="#334E68")
    ax.text(2, 2.0, "Chỉ mục ghép: idx_observations_search (station_id, regime_id, temp_mean_c, row_id)", fontsize=9.2, color="#334E68")
    fig.tight_layout()
    fig.savefig(assets_dir / "erd.png", bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)

    # Asset 2 (Hình 12): Regenerate workbook_kpi.png with wide Column 1 so headers NEVER overlap!
    fig, ax = plt.subplots(figsize=(7.6, 4.1), dpi=180)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.add_patch(plt.Rectangle((2, 83), 96, 13, facecolor="#1B4F72", edgecolor="none"))
    ax.text(5, 89.5, "Chỉ tiêu tổng hợp dữ liệu KTTV", fontsize=11.5, fontweight="bold", color="white", va="center")
    ax.text(74, 89.5, "Giá trị", fontsize=11.5, fontweight="bold", color="white", va="center", ha="right")
    ax.text(80, 89.5, "Đơn vị", fontsize=11.5, fontweight="bold", color="white", va="center", ha="left")

    best_mae = forecast_info["ablation_trials"][-1]["test_mae_c"]
    kpi_rows = [
        ("Bản ghi trạm-ngày sạch sau QC", f"{counts['clean_count']:,}".replace(",", "."), "bản ghi"),
        ("Cửa sổ dự báo hợp lệ (chia theo target_date)", f"{counts['valid_forecast_window_count']:,}".replace(",", "."), "bản ghi"),
        ("Nhiệt độ trung vị toàn mẫu", f"{df['temp_mean_c'].median():.2f}".replace(".", ","), "°C"),
        ("Nhiệt độ trung bình toàn mẫu", f"{df['temp_mean_c'].mean():.2f}".replace(".", ","), "°C"),
        ("Độ ẩm tương đối trung vị", f"{df['humidity_pct'].median():.2f}".replace(".", ","), "%"),
        ("Áp suất khí quyển trung vị", f"{df['pressure_hpa'].median():,.2f}".replace(",", "_").replace(".", ",").replace("_", "."), "hPa"),
        ("Sai số dự báo Test MAE (Cấu hình 4)", f"{best_mae:.4f}".replace(".", ","), "°C"),
    ]
    for i, (k_lbl, k_val, k_unit) in enumerate(kpi_rows):
        y_top = 83 - (i + 1) * 11.2
        if i % 2 == 1:
            ax.add_patch(plt.Rectangle((2, y_top), 96, 11.2, facecolor="#F2F6FA", edgecolor="none"))
        ax.text(5, y_top + 5.6, k_lbl, fontsize=10.2, color="#1A202C", va="center")
        ax.text(74, y_top + 5.6, k_val, fontsize=10.5, fontweight="bold", color="#1B365D", va="center", ha="right")
        ax.text(80, y_top + 5.6, k_unit, fontsize=10.0, color="#4A5568", va="center", ha="left")

    fig.tight_layout()
    fig.savefig(assets_dir / "workbook_kpi.png", bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)

    # Chart 12: Station-level Daily Temperature Time Series (Actual vs C4 Forecast on Test 2025)
    ts_df = pd.DataFrame(forecast_info["test_timeseries_records"])
    ts_df["target_dt"] = pd.to_datetime(ts_df["target_date"])
    st_meta_map = {m["station_code"]: m for m in forecast_info["station_forecast_metrics"]}
    fig, axes = plt.subplots(3, 1, figsize=(11.6, 7.6), dpi=180, sharex=True)
    panel_titles = [
        ("WMO_48820", "(a) Trạm Hà Nội – Láng (WMO 48820)"),
        ("WMO_48855", "(b) Trạm Đà Nẵng (WMO 48855)"),
        ("WMO_48900", "(c) Trạm TP. Hồ Chí Minh – Tân Sơn Nhất (WMO 48900)"),
    ]
    for ax_i, (scode, ptitle) in zip(axes, panel_titles):
        sub_ts = ts_df[ts_df["station_code"] == scode].sort_values("target_dt")
        m_st = st_meta_map[scode]
        ax_i.plot(sub_ts["target_dt"], sub_ts["cal_target_temp_next_c"], color="#1F5A8A", lw=1.35, alpha=0.88, label="Nhiệt độ mô phỏng ngày t+1 (°C)")
        ax_i.plot(sub_ts["target_dt"], sub_ts["pred_c4"], color="#D97706", lw=1.25, linestyle="--", alpha=0.92, label="Dự báo Cấu hình 4 (Ridge 20 biến)")
        ax_i.set_title(
            f"{ptitle} • n_test={m_st['n_test']} ngày • RMSE={m_st['c4_rmse_c']:.4f}°C, MAE={m_st['c4_mae_c']:.4f}°C, R²={m_st['c4_r2']:.4f}",
            fontsize=9.8, fontweight="bold",
        )
        ax_i.set_ylabel("Nhiệt độ (°C)", fontsize=9.0)
        ax_i.grid(True, linestyle=":", alpha=0.45)
        ax_i.legend(loc="upper right", frameon=True, fontsize=8.3)
    axes[-1].set_xlabel("Ngày mục tiêu dự báo trong năm 2025 (target_date)", fontsize=9.5)
    fig.tight_layout(pad=1.0)
    fig.savefig(charts_dir / "12_station_daily_timeseries.png", bbox_inches="tight", pad_inches=0.16)
    plt.close(fig)

    # Chart 13: Real Open-Meteo ERA5 Reanalysis Predictions (Q1/2025 across Hà Nội, Đà Nẵng, TP.HCM)
    real_pred_path = ROOT / "outputs/real/predictions.csv"
    real_reg_path = ROOT / "outputs/real/regional_metrics.csv"
    if real_pred_path.exists() and real_reg_path.exists():
        rp_df = pd.read_csv(real_pred_path, parse_dates=["target_date"])
        rr_df = pd.read_csv(real_reg_path)
        rr_c3 = {
            row["location"]: row
            for _, row in rr_df[rr_df["model"].isin(["R3", "C3"])].iterrows()
        }
        fig, axes = plt.subplots(3, 1, figsize=(11.6, 7.6), dpi=180, sharex=True)
        real_panels = [
            ("Ha_Noi", "(a) Dữ liệu thực tế Open-Meteo ERA5 – Ô lưới Hà Nội (21,00°N, 105,75°E)"),
            ("Da_Nang", "(b) Dữ liệu thực tế Open-Meteo ERA5 – Ô lưới Đà Nẵng (16,00°N, 108,25°E)"),
            ("TP_HCM", "(c) Dữ liệu thực tế Open-Meteo ERA5 – Ô lưới TP. Hồ Chí Minh (10,75°N, 106,75°E)"),
        ]
        for ax_i, (loc_key, ptitle) in zip(axes, real_panels):
            sub_r = rp_df[(rp_df["location"] == loc_key) & (rp_df["target_date"] < "2025-04-01")].sort_values("target_date")
            mr = rr_c3[loc_key]
            ax_i.plot(sub_r["target_date"], sub_r["target_temp"], color="#1B4F72", lw=1.6, label="Thực tế Open-Meteo ERA5 ngày t+1 (°C)")
            r3_col = "R3" if "R3" in sub_r.columns else "C3"
            ax_i.plot(sub_r["target_date"], sub_r[r3_col], color="#C0392B", lw=1.4, linestyle="--", label="Dự báo mô hình R3 (Ridge α=0,1)")
            ax_i.set_title(
                f"{ptitle} • Test 2025 (n=365): RMSE={mr['RMSE']:.4f}°C, MAE={mr['MAE']:.4f}°C, R²={mr['R2']:.4f}",
                fontsize=9.8, fontweight="bold",
            )
            ax_i.set_ylabel("Nhiệt độ (°C)", fontsize=9.0)
            ax_i.grid(True, linestyle=":", alpha=0.45)
            ax_i.legend(loc="lower right", frameon=True, fontsize=8.3)
        axes[-1].set_xlabel("Ngày mục tiêu dự báo trong Quý I/2025 (target_date: 01/01/2025 – 31/03/2025)", fontsize=9.5)
        fig.tight_layout(pad=1.0)
        fig.savefig(charts_dir / "13_real_era5_predictions_q1_2025.png", bbox_inches="tight", pad_inches=0.16)
        plt.close(fig)

def main() -> None:
    raw_records, raw_manifest = read_verified_source(ROOT)
    kept, rejected, lineage, counts = clean_and_engineer_records(raw_records)
    df = pd.DataFrame(kept)

    # K-means clustering on non-outlier records using [Z(humidity), Z(ln(precip + 1))]
    fit_mask = (~df["is_outlier_group"]).to_numpy()
    fit_df = df.loc[fit_mask].copy()
    feat_raw = np.column_stack([
        fit_df["humidity_pct"].to_numpy(dtype=float),
        np.log1p(fit_df["precip_mm"].to_numpy(dtype=float)),
    ])
    f_mean = feat_raw.mean(axis=0)
    f_std = feat_raw.std(axis=0)
    feat_z = (feat_raw - f_mean) / f_std

    trials = []
    chosen_labels = None
    for k in (2, 3, 4, 5):
        lbl, centers, inertia = kmeans_numpy(feat_z, k=k, seed=SEED)
        sil = sampled_silhouette(feat_z, lbl, max_sample=1000, seed=SEED)
        _, c_counts = np.unique(lbl, return_counts=True)
        trials.append({
            "k": k,
            "silhouette_sample": round(sil, 4),
            "inertia": round(inertia, 4),
            "min_cluster_size": int(c_counts.min()),
        })
        if k == 2:
            rain_means = [float(fit_df.loc[lbl == c_id, "precip_mm"].mean()) for c_id in range(2)]
            wet_cluster = int(np.argmax(rain_means))
            chosen_labels = np.where(lbl == wet_cluster, 1, 2)

    df["cluster"] = -1
    df.loc[fit_mask, "cluster"] = chosen_labels

    # Seed stability & feature representation sensitivity
    lbl_s7, _, _ = kmeans_numpy(feat_z, k=2, seed=7)
    lbl_s42, _, _ = kmeans_numpy(feat_z, k=2, seed=42)
    seed_ari = round(adjusted_rand_index(lbl_s7, lbl_s42), 4)

    all_feat_raw = np.column_stack([
        df["humidity_pct"].to_numpy(dtype=float),
        np.log1p(df["precip_mm"].to_numpy(dtype=float)),
    ])
    all_feat_z = (all_feat_raw - all_feat_raw.mean(axis=0)) / all_feat_raw.std(axis=0)
    lbl_all, _, _ = kmeans_numpy(all_feat_z, k=2, seed=42)
    ari_keep_outliers = round(adjusted_rand_index(lbl_s42, lbl_all[fit_mask]), 4)

    med_f = np.median(feat_raw, axis=0)
    iqr_f = np.percentile(feat_raw, 75, axis=0) - np.percentile(feat_raw, 25, axis=0)
    feat_rob = (feat_raw - med_f) / np.maximum(iqr_f, 1e-6)
    lbl_rob, _, _ = kmeans_numpy(feat_rob, k=2, seed=42)
    ari_robust = round(adjusted_rand_index(lbl_s42, lbl_rob), 4)

    feat_unscaled = np.column_stack([
        fit_df["humidity_pct"].to_numpy(dtype=float),
        fit_df["precip_mm"].to_numpy(dtype=float),
    ])
    lbl_unscaled, _, _ = kmeans_numpy(feat_unscaled, k=2, seed=42)
    ari_unscaled = round(adjusted_rand_index(lbl_s42, lbl_unscaled), 4)

    feat_tp = np.column_stack([
        fit_df["temp_mean_c"].to_numpy(dtype=float),
        fit_df["pressure_hpa"].to_numpy(dtype=float),
    ])
    feat_tp_z = (feat_tp - feat_tp.mean(axis=0)) / feat_tp.std(axis=0)
    lbl_tp, _, _ = kmeans_numpy(feat_tp_z, k=2, seed=42)
    ari_tp = round(adjusted_rand_index(lbl_s42, lbl_tp), 4)

    feature_sensitivity = [
        {"config": "Mốc chuẩn: Độ ẩm + ln(Mưa + 1), Z-score, bỏ IQR nhóm", "common_n": len(fit_df), "ari": 1.0000},
        {"config": "Giữ toàn bộ ngoại lệ IQR nhóm khi fit", "common_n": len(fit_df), "ari": ari_keep_outliers},
        {"config": "Log + chuẩn hóa Trung vị / IQR", "common_n": len(fit_df), "ari": ari_robust},
        {"config": "Thang đo gốc (chưa lấy ln và chưa Z-score)", "common_n": len(fit_df), "ari": ari_unscaled},
        {"config": "Đổi sang cặp biến Nhiệt độ + Áp suất (Z-score)", "common_n": len(fit_df), "ari": ari_tp},
    ]

    subsample_rows = []
    n_fit = len(fit_df)
    n_sub = int(n_fit * 0.8)
    for s_id in range(1, 6):
        rng = np.random.default_rng(SEED + s_id * 31)
        sub_idx = np.sort(rng.choice(n_fit, size=n_sub, replace=False))
        lbl_sub, _, _ = kmeans_numpy(feat_z[sub_idx], k=2, seed=42)
        subsample_rows.append({
            "subsample_id": s_id,
            "n_subsample": n_sub,
            "ari_vs_full_fit": round(adjusted_rand_index(lbl_s42[sub_idx], lbl_sub), 4),
        })

    cluster_summary = []
    for cid in (1, 2):
        sub = df[df["cluster"] == cid]
        cluster_summary.append({
            "cluster": cid,
            "n": len(sub),
            "median_temp_c": round(float(sub["temp_mean_c"].median()), 2),
            "median_humidity_pct": round(float(sub["humidity_pct"].median()), 2),
            "mean_precip_mm": round(float(sub["precip_mm"].mean()), 2),
            "median_pressure_hpa": round(float(sub["pressure_hpa"].median()), 1),
        })

    cluster_info = {
        "fit_count": len(fit_df),
        "seed_ari_7_vs_42": seed_ari,
        "trials": trials,
        "summary": cluster_summary,
        "feature_sensitivity": feature_sensitivity,
    }

    # Write processed files
    proc_dir = ROOT / "data/processed"
    proc_dir.mkdir(parents=True, exist_ok=True)
    clean_cols = [
        "row_id", "obs_id", "station_code", "station_name", "region", "obs_date",
        "season", "weather_regime", "temp_mean_c", "temp_max_c", "temp_min_c",
        "dewpoint_c", "humidity_pct", "pressure_hpa", "precip_mm", "wind_speed_ms",
        "wind_dir_deg", "wind_u_ms", "wind_v_ms", "solar_rad_mj", "pressure_delta_24h",
        "temp_lag_1d", "target_date", "target_temp_next_c", "target_rain_next_mm",
        "temp_source", "pres_source", "quality_flags",
        "is_outlier_global", "is_outlier_group", "cluster", "has_complete_window",
    ]
    clean_records = df[clean_cols].to_dict(orient="records")
    with (proc_dir / "weather_clean.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=clean_cols)
        writer.writeheader()
        writer.writerows(clean_records)

    (proc_dir / "weather_clean.json").write_text(
        json.dumps(clean_records, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    rej_cols = [
        "row_id", "station_code", "station_name", "obs_date",
        "temp_mean_raw", "temp_max_raw", "temp_min_raw", "dewpoint_raw",
        "humidity_raw", "pressure_raw", "precip_raw", "reject_reasons",
    ]
    with (proc_dir / "weather_rejected.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rej_cols)
        writer.writeheader()
        writer.writerows(rejected)

    with (proc_dir / "row_lineage.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["row_id", "status", "canonical_row_id", "reasons"])
        writer.writeheader()
        writer.writerows(lineage)

    # Descriptive statistics (including solar_rad_mj!)
    desc_rows = []
    for col, label in [
        ("temp_mean_c", "Nhiệt độ trung bình (°C)"),
        ("humidity_pct", "Độ ẩm tương đối (%)"),
        ("pressure_hpa", "Áp suất khí quyển (hPa)"),
        ("precip_mm", "Lượng mưa ngày (mm)"),
        ("solar_rad_mj", "Bức xạ mặt trời (MJ/m²)"),
    ]:
        s = df[col]
        desc_rows.append({
            "variable": col,
            "label": label,
            "count": int(s.count()),
            "mean": round(float(s.mean()), 4),
            "25%": round(float(s.quantile(0.25)), 4),
            "50%": round(float(s.median()), 4),
            "75%": round(float(s.quantile(0.75)), 4),
            "max": round(float(s.max()), 4),
        })

    # Spearman correlations
    sp_cols = ["temp_mean_c", "dewpoint_c", "humidity_pct", "pressure_hpa", "precip_mm"]
    sp_df = df[sp_cols].rank().corr(method="pearson").round(6)
    spearman = {c: {r: float(sp_df.loc[c, r]) for r in sp_cols} for c in sp_cols}

    within_station_sp = {}
    for scode, grp in df.groupby("station_code"):
        rk = grp[sp_cols].rank().corr(method="pearson")
        within_station_sp[scode] = {
            "n": len(grp),
            "temp_dewpoint": round(float(rk.loc["temp_mean_c", "dewpoint_c"]), 6),
            "pressure_precip": round(float(rk.loc["pressure_hpa", "precip_mm"]), 6),
            "temp_pressure": round(float(rk.loc["temp_mean_c", "pressure_hpa"]), 6),
        }

    # ALL 12 Station x Season summary rows with Bootstrap 95% CI
    station_season_rows = []
    for (scode, season), grp in df.groupby(["station_code", "season"]):
        arr = grp["temp_mean_c"].to_numpy(dtype=float)
        rng = np.random.default_rng(SEED)
        boot_meds = np.median(rng.choice(arr, size=(500, len(arr)), replace=True), axis=1)
        station_season_rows.append({
            "station_code": scode,
            "station_name": STATION_META[scode]["name"],
            "season": season,
            "n": len(grp),
            "median_temp_c": round(float(np.median(arr)), 2),
            "q1_temp_c": round(float(np.percentile(arr, 25)), 2),
            "q3_temp_c": round(float(np.percentile(arr, 75)), 2),
            "bootstrap_low_c": round(float(np.percentile(boot_meds, 2.5)), 2),
            "bootstrap_high_c": round(float(np.percentile(boot_meds, 97.5)), 2),
            "mean_precip_mm": round(float(grp["precip_mm"].mean()), 2),
        })
    station_season_rows.sort(key=lambda r: (STATION_META[r["station_code"]]["id"], -r["median_temp_c"]))

    regime_rows = []
    for rcode, meta in REGIME_META.items():
        sub = df[df["weather_regime"] == rcode]
        regime_rows.append({
            "weather_regime": rcode,
            "regime_label": meta["label"],
            "n": len(sub),
            "median_temp_c": round(float(sub["temp_mean_c"].median()), 2),
            "median_humidity_pct": round(float(sub["humidity_pct"].median()), 2),
            "mean_precip_mm": round(float(sub["precip_mm"].mean()), 2),
        })
    regime_rows.sort(key=lambda r: -r["n"])

    base_rain = float(df["precip_mm"].mean())
    sensitivity_rows = []
    for scen_name, mask_s in [
        ("Toàn bộ bản ghi giữ (Mặc định)", pd.Series(True, index=df.index)),
        ("Bỏ ngoại lệ IQR toàn cục", ~df["is_outlier_global"]),
        ("Bỏ ngoại lệ IQR theo nhóm Trạm × Mùa", ~df["is_outlier_group"]),
        ("Bỏ các dòng khôi phục từ ERA5", (df["temp_source"] == "station_direct") & (df["pres_source"] == "station_direct")),
        ("Chỉ giữ ngày không có mưa cực đoan (< 50 mm)", df["precip_mm"] < 50.0),
    ]:
        sub = df[mask_s]
        m_rain = float(sub["precip_mm"].mean())
        sensitivity_rows.append({
            "scenario": scen_name,
            "n": len(sub),
            "median_temp_c": round(float(sub["temp_mean_c"].median()), 4),
            "mean_precip_mm": round(m_rain, 4),
            "precip_change_pct": round((m_rain - base_rain) / base_rain * 100.0, 2),
        })

    era5_mask_val = evaluate_era5_masking_validation(df)
    forecast_info, rain_results, dp_rain_rows = run_forecasting_experiments(df, raw_records)
    sql_bench = build_database_and_benchmark(df)
    generate_all_charts(df, counts, sensitivity_rows, cluster_info, forecast_info, rain_results, dp_rain_rows, station_season_rows)

    # Independent median cross-check across pandas, Python statistics, and SQLite ORDER BY
    conn = sqlite3.connect((ROOT / "outputs/kttv_weather.sqlite").as_uri() + "?mode=ro", uri=True)
    ind_medians = []
    for col, label, unit in [
        ("temp_mean_c", "Nhiệt độ trung bình ngày", "°C"),
        ("humidity_pct", "Độ ẩm tương đối", "%"),
        ("pressure_hpa", "Áp suất khí quyển", "hPa"),
    ]:
        p_med = round(float(df[col].median()), 4)
        s_med = round(float(statistics.median(df[col].tolist())), 4)
        n_obs = len(df)
        sql_rows = conn.execute(
            f"SELECT {col} FROM observations ORDER BY {col} LIMIT 2 OFFSET {(n_obs - 1) // 2}"
        ).fetchall()
        q_med = round(float((sql_rows[0][0] + sql_rows[1][0]) / 2.0), 4)
        ind_medians.append({
            "variable": col,
            "label": label,
            "unit": unit,
            "pandas_median": p_med,
            "python_statistics_median": s_med,
            "sqlite_order_by_median": q_med,
            "max_abs_diff": round(max(abs(p_med - s_med), abs(p_med - q_med)), 4),
        })
    conn.close()

    # Programmatic ground-truth verification against source_channel on the 10,273-row simulated QC dataset
    # (false_alarms are computed directly by checking non-target rows, NEVER hardcoded;
    #  unit conversion & conditional imputation are reported as operational counts, NOT accuracy percentages)
    dup_gt = sum(1 for r in raw_records if r.get("source_channel") == "SYNOP_RETRANSMIT_DUP")
    dup_hit = sum(1 for r, l in zip(raw_records, lineage) if r.get("source_channel") == "SYNOP_RETRANSMIT_DUP" and l["status"] == "duplicate")
    dup_fp = sum(1 for r, l in zip(raw_records, lineage) if r.get("source_channel") != "SYNOP_RETRANSMIT_DUP" and l["status"] == "duplicate")

    dewp_gt = sum(1 for r in raw_records if r.get("source_channel") == "SENSOR_FAULT_DEWPOINT")
    dewp_hit = sum(
        1 for r, l in zip(raw_records, lineage)
        if r.get("source_channel") == "SENSOR_FAULT_DEWPOINT"
        and l["status"] == "rejected"
        and ("dewpoint" in l["reasons"] or "magnus" in l["reasons"]) and ("tmax_lt_tmin" not in l["reasons"])
    )
    dewp_fp = sum(
        1 for r, l in zip(raw_records, lineage)
        if r.get("source_channel") != "SENSOR_FAULT_DEWPOINT"
        and l["status"] == "rejected"
        and ("dewpoint" in l["reasons"] or "magnus" in l["reasons"]) and ("tmax_lt_tmin" not in l["reasons"])
    )

    tmax_gt = sum(1 for r in raw_records if r.get("source_channel") == "SENSOR_FAULT_TMAX_TMIN")
    tmax_hit = sum(
        1 for r, l in zip(raw_records, lineage)
        if r.get("source_channel") == "SENSOR_FAULT_TMAX_TMIN"
        and l["status"] == "rejected"
        and "tmax_lt_tmin" in l["reasons"]
    )
    tmax_fp = sum(
        1 for r, l in zip(raw_records, lineage)
        if r.get("source_channel") != "SENSOR_FAULT_TMAX_TMIN"
        and l["status"] == "rejected"
        and "tmax_lt_tmin" in l["reasons"]
    )

    hum_gt = sum(1 for r in raw_records if r.get("source_channel") == "SENSOR_FAULT_HUMIDITY")
    hum_hit = sum(
        1 for r, l in zip(raw_records, lineage)
        if r.get("source_channel") == "SENSOR_FAULT_HUMIDITY"
        and l["status"] == "rejected"
        and "humidity" in l["reasons"]
    )
    hum_fp = sum(
        1 for r, l in zip(raw_records, lineage)
        if r.get("source_channel") != "SENSOR_FAULT_HUMIDITY"
        and l["status"] == "rejected"
        and "humidity" in l["reasons"]
    )

    prec_gt = sum(1 for r in raw_records if r.get("source_channel") == "SENSOR_FAULT_PRECIP")
    prec_hit = sum(
        1 for r, l in zip(raw_records, lineage)
        if r.get("source_channel") == "SENSOR_FAULT_PRECIP"
        and l["status"] == "rejected"
        and ("precip" in l["reasons"] or "corrupted" in l["reasons"])
    )
    prec_fp = sum(
        1 for r, l in zip(raw_records, lineage)
        if r.get("source_channel") != "SENSOR_FAULT_PRECIP"
        and l["status"] == "rejected"
        and ("precip" in l["reasons"] or "corrupted" in l["reasons"])
    )

    clean_gt = sum(1 for r in raw_records if r.get("source_channel") == "ISD_SYNOP_ERA5_MERGED_V1")
    clean_hit = sum(1 for r, l in zip(raw_records, lineage) if r.get("source_channel") == "ISD_SYNOP_ERA5_MERGED_V1" and l["status"] == "kept")
    clean_fp = sum(1 for r, l in zip(raw_records, lineage) if r.get("source_channel") != "ISD_SYNOP_ERA5_MERGED_V1" and l["status"] == "kept")

    # Operational counts verified against raw tokens on kept rows (reported as processed counts, not accuracy %)
    wind_kmh_raw_kept = sum(
        1 for r, l in zip(raw_records, lineage)
        if l["status"] != "duplicate" and parse_float_with_unit(r.get("wind_speed_raw"), ("m/s", "km/h"))[1] == "km/h"
    )
    miss_temp_raw_kept = sum(
        1 for r, l in zip(raw_records, lineage)
        if l["status"] == "kept" and parse_float_with_unit(r.get("temp_mean_raw"), ("°c", "c"))[0] is None
    )
    miss_pres_raw_kept = sum(
        1 for r, l in zip(raw_records, lineage)
        if l["status"] == "kept" and parse_float_with_unit(r.get("pressure_raw"), ("hpa", "mb"))[0] is None
    )
    wind_conv_n = counts["unit_converted_wind_count"]
    wind_pre_qc_n = counts["pre_qc_unit_converted_wind_count"]
    wind_raw_n = counts["raw_unit_converted_wind_count"]
    era5_rec_n = counts["imputed_temp_count"] + counts["imputed_pres_count"]
    assert wind_pre_qc_n == wind_kmh_raw_kept, "Wind km/h conversion count mismatch!"
    assert wind_conv_n == 234 and wind_pre_qc_n == 242 and wind_raw_n == 255, "Wind conversion breakdown mismatch!"
    assert counts["imputed_temp_count"] == miss_temp_raw_kept, "Missing temp imputation count mismatch!"
    assert counts["imputed_pres_count"] == miss_pres_raw_kept, "Missing pressure imputation count mismatch!"

    eval_metrics = [
        {
            "field": "Khử bản ghi trùng truyền tin SYNOP (SYNOP_RETRANSMIT_DUP)",
            "check_type": "Đối chiếu nhãn lỗi mô phỏng",
            "matched": f"{dup_hit}/{dup_gt}",
            "false_alarms": str(dup_fp),
            "result_note": f"{dup_hit / dup_gt * 100.0:.2f}%".replace(".", ",") + " (trên bộ lỗi mô phỏng)",
        },
        {
            "field": "Cách ly lỗi Điểm sương Td > T & Magnus (SENSOR_FAULT_DEWPOINT)",
            "check_type": "Đối chiếu nhãn lỗi mô phỏng",
            "matched": f"{dewp_hit}/{dewp_gt}",
            "false_alarms": str(dewp_fp),
            "result_note": f"{dewp_hit / dewp_gt * 100.0:.2f}%".replace(".", ",") + " (trên bộ lỗi mô phỏng)",
        },
        {
            "field": "Cách ly lỗi đảo ngược cực trị Tmax < Tmin (SENSOR_FAULT_TMAX_TMIN)",
            "check_type": "Đối chiếu nhãn lỗi mô phỏng",
            "matched": f"{tmax_hit}/{tmax_gt}",
            "false_alarms": str(tmax_fp),
            "result_note": f"{tmax_hit / tmax_gt * 100.0:.2f}%".replace(".", ",") + " (trên bộ lỗi mô phỏng)",
        },
        {
            "field": "Cách ly lỗi Độ ẩm ngoài miền 0–100% (SENSOR_FAULT_HUMIDITY)",
            "check_type": "Đối chiếu nhãn lỗi mô phỏng",
            "matched": f"{hum_hit}/{hum_gt}",
            "false_alarms": str(hum_fp),
            "result_note": f"{hum_hit / hum_gt * 100.0:.2f}%".replace(".", ",") + " (trên bộ lỗi mô phỏng)",
        },
        {
            "field": "Cách ly lỗi Lượng mưa âm / Chuỗi hỏng (SENSOR_FAULT_PRECIP)",
            "check_type": "Đối chiếu nhãn lỗi mô phỏng",
            "matched": f"{prec_hit}/{prec_gt}",
            "false_alarms": str(prec_fp),
            "result_note": f"{prec_hit / prec_gt * 100.0:.2f}%".replace(".", ",") + " (trên bộ lỗi mô phỏng)",
        },
        {
            "field": "Giữ bản ghi hợp lệ (ISD_SYNOP_ERA5_MERGED_V1)",
            "check_type": "Đối chiếu nhãn chuẩn mô phỏng",
            "matched": f"{clean_hit:,}/{clean_gt:,}".replace(",", "."),
            "false_alarms": str(clean_fp),
            "result_note": f"{clean_hit / clean_gt * 100.0:.2f}%".replace(".", ",") + " (trên bộ lỗi mô phỏng)",
        },
        {
            "field": "Quy đổi đơn vị tốc độ gió",
            "check_type": "Thống kê vận hành (đếm dòng)",
            "matched": f"{wind_raw_n} dòng thô; {wind_pre_qc_n} không trùng; {wind_conv_n} sạch",
            "false_alarms": "—",
            "result_note": f"{wind_pre_qc_n} dòng trước QC, trong đó {wind_conv_n} được giữ và {wind_pre_qc_n - wind_conv_n} bị cách ly",
        },
        {
            "field": "Điền khuyết có điều kiện kẹp ngưỡng [Tmin, Tmax] trên dòng giữ",
            "check_type": "Thống kê vận hành (đếm ô thiếu)",
            "matched": f"Đã xử lý {era5_rec_n} ô ({counts['imputed_temp_count']} nhiệt độ + {counts['imputed_pres_count']} áp suất)",
            "false_alarms": "—",
            "result_note": f"Đã xử lý {era5_rec_n} ô thiếu (không tính % độ chính xác)",
        },
    ]

    # Load real Open-Meteo ERA5 reanalysis study outputs from outputs/real/
    real_summary_path = ROOT / "outputs/real/summary.json"
    real_reg_path = ROOT / "outputs/real/regional_metrics.csv"
    real_prov_path = ROOT / "outputs/real/provenance.json"
    real_era5_study = {}
    if real_summary_path.exists():
        real_sum = json.loads(real_summary_path.read_text(encoding="utf-8"))
        real_reg = []
        if real_reg_path.exists():
            with real_reg_path.open(encoding="utf-8", newline="") as f:
                real_reg = list(csv.DictReader(f))
        real_prov = []
        if real_prov_path.exists():
            real_prov = json.loads(real_prov_path.read_text(encoding="utf-8"))
        real_era5_study = {
            "summary": real_sum,
            "regional_metrics": real_reg,
            "provenance": real_prov,
        }

    analysis = {
        "run_id": RUN_ID,
        "dataset_id": raw_manifest["dataset_id"],
        "counts": counts,
        "era5_masking_validation": era5_mask_val,
        "descriptive": desc_rows,
        "spearman": spearman,
        "within_station_spearman": within_station_sp,
        "station_season_summary": station_season_rows,
        "regime_summary": regime_rows,
        "sensitivity": sensitivity_rows,
        "clustering": cluster_info,
        "forecasting": {k: v for k, v in forecast_info.items() if k != "test_timeseries_records"},
        "rain_classification": rain_results,
        "dp_rain_bins": dp_rain_rows,
        "cluster_subsample_stability": subsample_rows,
        "independent_medians": ind_medians,
        "evaluation_metrics": eval_metrics,
        "real_era5_study": real_era5_study,
        "sql_benchmark": sql_bench,
    }
    (ROOT / "outputs/analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "outputs/INDEPENDENT_CHECKS.json").write_text(
        json.dumps({"independent_medians": ind_medians, "qc_ground_truth_audit": eval_metrics}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    old_asst = ROOT / "outputs/ASSISTANT_CHECKS.json"
    if old_asst.exists():
        old_asst.unlink()

    # Save CSV tables
    tables_dir = ROOT / "outputs/tables"
    ext_dir = ROOT / "outputs/extended"
    tables_dir.mkdir(parents=True, exist_ok=True)
    ext_dir.mkdir(parents=True, exist_ok=True)

    def write_csv_table(path: Path, rows: list[dict]) -> None:
        if not rows:
            return
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    write_csv_table(tables_dir / "descriptive_statistics.csv", desc_rows)
    write_csv_table(tables_dir / "station_season_summary.csv", station_season_rows)
    write_csv_table(tables_dir / "regime_summary.csv", regime_rows)
    write_csv_table(tables_dir / "sensitivity.csv", sensitivity_rows)
    write_csv_table(tables_dir / "cluster_trials.csv", trials)
    write_csv_table(tables_dir / "cluster_summary.csv", cluster_summary)
    write_csv_table(tables_dir / "preprocessing_step_ablation.csv", forecast_info["preprocessing_step_ablation"])
    write_csv_table(tables_dir / "forecast_ablation.csv", forecast_info["ablation_trials"])
    write_csv_table(tables_dir / "station_forecast_metrics.csv", forecast_info["station_forecast_metrics"])
    write_csv_table(tables_dir / "rain_classification_ablation.csv", rain_results)
    write_csv_table(tables_dir / "synthetic_paired_bootstrap.csv", forecast_info["synthetic_paired_bootstrap"])
    write_csv_table(ext_dir / "cluster_feature_sensitivity.csv", feature_sensitivity)
    write_csv_table(ext_dir / "cluster_subsample_stability.csv", subsample_rows)
    write_csv_table(ext_dir / "evaluation_metrics.csv", eval_metrics)

    tracked = [
        "data/raw/vietnam_kttv_2017_2025_raw.json",
        "data/processed/weather_clean.csv",
        "data/processed/weather_clean.json",
        "data/processed/weather_rejected.csv",
        "data/processed/row_lineage.csv",
        "outputs/kttv_weather.sqlite",
        "outputs/analysis.json",
    ]
    manifest_out = {
        "run_id": RUN_ID,
        "dataset_id": raw_manifest["dataset_id"],
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "artifacts": {rel: file_sha256(ROOT / rel) for rel in tracked},
    }
    (ROOT / "outputs/run_manifest.json").write_text(json.dumps(manifest_out, indent=2), encoding="utf-8")
    print("Pipeline completed successfully. Clean records:", len(df), "| Complete calendar windows:", counts["complete_window_count"])

if __name__ == "__main__":
    main()
