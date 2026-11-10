"""Reproducible ERA5 study on real Open-Meteo ECMWF ERA5 daily data (2017-2025).
Works offline from cached data/era5/*.json using pure NumPy/SciPy/pandas (zero scikit-learn requirement)."""
from __future__ import annotations
from pathlib import Path
import argparse
import base64
import datetime
import hashlib
import json
import sys
import urllib.parse
import urllib.request
import numpy as np
import pandas as pd
try:
    from scipy.optimize import minimize
except ImportError:
    minimize = None
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pipeline import classify_season, fit_ridge_closed_form, kmeans_numpy, predict_linear, sampled_silhouette

RAW = ROOT / "data/era5"
OUT = ROOT / "outputs/real"
CHARTS = ROOT / "outputs/charts"
RAW.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
CHARTS.mkdir(parents=True, exist_ok=True)

LOCATIONS = {
    "Ha_Noi": (21.02, 105.80),
    "Da_Nang": (16.04, 108.20),
    "TP_HCM": (10.82, 106.67),
}
VARS = {
    "temperature_2m_mean": "temp",
    "temperature_2m_max": "tmax",
    "temperature_2m_min": "tmin",
    "relative_humidity_2m_mean": "humidity",
    "pressure_msl_mean": "pressure",
    "precipitation_sum": "rain",
    "wind_speed_10m_mean": "wind",
    "shortwave_radiation_sum": "solar",
}


def validate_source_payload(obj: dict, meta: dict, body: bytes) -> None:
    """Reject a changed cache, wrong model contract, units or calendar before replay."""
    if hashlib.sha256(body).hexdigest() != meta.get("sha256"):
        raise ValueError("ERA5 SHA-256 mismatch; restore pinned cache or explicitly refresh")
    params = meta.get("parameters", {})
    if params.get("models") != "era5" or obj.get("utc_offset_seconds") != 25200:
        raise ValueError("ERA5 model/timezone contract mismatch")
    expected_units = {"temperature_2m_mean": "°C", "temperature_2m_max": "°C", "temperature_2m_min": "°C",
        "relative_humidity_2m_mean": "%", "pressure_msl_mean": "hPa", "precipitation_sum": "mm",
        "wind_speed_10m_mean": "m/s", "shortwave_radiation_sum": "MJ/m²"}
    if any(obj.get("daily_units", {}).get(k) != v for k, v in expected_units.items()):
        raise ValueError("ERA5 variable unit mismatch")
    expected = pd.date_range(params["start_date"], params["end_date"]).strftime("%Y-%m-%d").tolist()
    daily = obj.get("daily", {})
    if daily.get("time") != expected or any(len(daily.get(k, [])) != len(expected) for k in VARS):
        raise ValueError("ERA5 daily calendar/array mismatch")


def acquire(refresh: bool = False) -> pd.DataFrame:
    frames = []
    provenance = []
    for name, (lat, lon) in LOCATIONS.items():
        p = RAW / f"{name}.json"
        params = dict(
            latitude=lat,
            longitude=lon,
            start_date="2017-01-01",
            end_date="2025-12-31",
            daily=",".join(VARS),
            models="era5",
            timezone="Asia/Bangkok",
            wind_speed_unit="ms",
        )
        url = "https://archive-api.open-meteo.com/v1/archive?" + urllib.parse.urlencode(params)
        if refresh or not p.exists():
            print("Downloading", name, flush=True)
            with urllib.request.urlopen(url, timeout=90) as r:
                payload = r.read()
            obj = json.loads(payload)
            if "daily" not in obj:
                raise ValueError(obj)
            p.write_bytes(payload)
            (RAW / f"{name}_request.json").write_text(
                json.dumps(
                    {
                        "url": url,
                        "retrieved_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "parameters": params,
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        body = p.read_bytes()
        obj = json.loads(body)
        meta = json.loads((RAW / f"{name}_request.json").read_text())
        validate_source_payload(obj, meta, body)
        f = pd.DataFrame(obj["daily"]).rename(columns={"time": "date", **VARS})
        f["location"] = name
        frames.append(f)
        provenance.append(
            {
                "file": p.name,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "rows": len(f),
                "grid_latitude": obj["latitude"],
                "grid_longitude": obj["longitude"],
                "units": obj["daily_units"],
            }
        )
    (OUT / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    return pd.concat(frames, ignore_index=True)


def prepare(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    d = raw.copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d.sort_values(["location", "date"])
    duplicate = d.duplicated(["location", "date"])
    d = d[~duplicate].copy()
    bad = (
        d.humidity.lt(0)
        | d.humidity.gt(100)
        | d.rain.lt(0)
        | d.wind.lt(0)
        | d.tmin.gt(d.tmax)
        | d.temp.lt(d.tmin)
        | d.temp.gt(d.tmax)
    )
    d.loc[bad].to_csv(OUT / "rejected.csv", index=False)
    d = d[~bad].copy()
    quality = {
        "raw_rows": len(raw),
        "duplicates": int(duplicate.sum()),
        "rejected": int(bad.sum()),
        "clean_rows": len(d),
        "missing": {k: int(v) for k, v in d.isna().sum().items()},
    }
    d.to_csv(OUT / "clean.csv", index=False)

    # 1. Descriptive statistics on 9,861 ERA5 records (Bảng 5)
    desc_rows = []
    for col in ["temp", "humidity", "pressure", "rain", "wind", "solar"]:
        s = d[col]
        desc_rows.append({
            "variable": col,
            "n": int(s.count()),
            "mean": round(float(s.mean()), 2),
            "q1": round(float(s.quantile(0.25)), 2),
            "median": round(float(s.median()), 2),
            "q3": round(float(s.quantile(0.75)), 2),
        })
    pd.DataFrame(desc_rows).to_csv(OUT / "descriptive.csv", index=False)

    # 2. Spearman correlation matrix on 6 ERA5 variables & Hình 3 (real_era5_eda.png)
    sp_cols = ["temp", "humidity", "pressure", "rain", "wind", "solar"]
    sp_df = d[sp_cols].rank().corr(method="pearson")
    sp_df.round(4).to_csv(OUT / "spearman.csv")

    d["month"] = d["date"].dt.month
    d["season"] = d["month"].map(lambda m: "Tháng 12–2" if m in (12,1,2) else "Tháng 3–4" if m in (3,4) else "Tháng 5–8" if m in (5,6,7,8) else "Tháng 9–11")

    # Monthly and annual climate summaries; per-location denominators, no pooled Hanoi row.
    d.groupby(["location", "month"]).agg(temp_median_c=("temp", "median"), rain_mean_mm=("rain", "mean")).reset_index().to_csv(OUT / "monthly_summary.csv", index=False)
    annual = d.assign(year=d.date.dt.year, wet=d.rain.ge(1).astype(int)).groupby(["location", "year"]).agg(rain_total_mm=("rain", "sum"), wet_days_ge1mm=("wet", "sum")).reset_index()
    annual.to_csv(OUT / "annual_climate.csv", index=False)
    climate=[]
    for loc,g in d.groupby("location"):
        ann=annual[annual.location.eq(loc)]
        climate.append({"location":loc,"humidity_median_pct":float(g.humidity.median()),"annual_rain_mean_mm":float(ann.rain_total_mm.mean()),"annual_wet_days_mean":float(ann.wet_days_ge1mm.mean()),"wet_day_rate_pct":float(g.rain.ge(1).mean()*100)})
    pd.DataFrame(climate).to_csv(OUT / "climate_comparison.csv", index=False)

    # 3. 12 Location x fixed calendar groups

    loc_season_rows = []
    for (loc, seas), grp in d.groupby(["location", "season"]):
        loc_season_rows.append({
            "location": loc,
            "season": seas,
            "n": len(grp),
            "temp_median_c": round(float(grp["temp"].median()), 3),
            "humidity_median_pct": round(float(grp["humidity"].median()), 3),
            "rain_mean_mm": round(float(grp["rain"].mean()), 3),
        })
    pd.DataFrame(loc_season_rows).to_csv(OUT / "location_season.csv", index=False)

    # 4. Exploratory K-means++ on ERA5 [Z(humidity), Z(ln(rain+1))] (Bảng 7)
    X_cl = np.column_stack([d["humidity"].to_numpy(dtype=float), np.log1p(d["rain"].to_numpy(dtype=float))])
    Z_cl = (X_cl - X_cl.mean(axis=0)) / X_cl.std(axis=0)
    best_k, best_sil, best_lbl = 2, -1.0, None
    trials = []
    for k_try in (2, 3, 4, 5):
        lbl_k, _, _ = kmeans_numpy(Z_cl, k=k_try, seed=20261015)
        sil_k = sampled_silhouette(Z_cl, lbl_k, max_sample=1000, seed=20261015)
        trials.append({"k": k_try, "silhouette_sample": sil_k, "sample_n": 1000, "seed": 20261015})
        if sil_k > best_sil:
            best_sil = sil_k
            best_k = k_try
            best_lbl = lbl_k
    pd.DataFrame(trials).to_csv(OUT / "cluster_trials.csv", index=False)
    r_means = [float(d.loc[best_lbl == c, "rain"].mean()) for c in range(best_k)]
    wet_c = int(np.argmax(r_means))
    c_assigned = np.where(best_lbl == wet_c, 1, 2)
    cl_rows = []
    for cid in (1, 2):
        sub_c = d[c_assigned == cid]
        cl_rows.append({
            "cluster": cid,
            "n": int(len(sub_c)),
            "temp_median_c": round(float(sub_c["temp"].median()), 2),
            "humidity_median_pct": round(float(sub_c["humidity"].median()), 2),
            "rain_mean_mm": round(float(sub_c["rain"].mean()), 3),
        })
    pd.DataFrame(cl_rows).to_csv(OUT / "cluster_summary.csv", index=False)

    # 5. Plot Hình 3 (real_era5_eda.png): Monthly median temperature & Spearman correlation on ERA5
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.2), dpi=180)
    for loc_name in ["Da_Nang", "Ha_Noi", "TP_HCM"]:
        m_med = d[d["location"] == loc_name].groupby("month")["temp"].median()
        axes[0].plot(m_med.index, m_med.values, marker="o", linewidth=1.8, label=loc_name)
    axes[0].set_title("ERA5 2017–2025 tại ba ô lưới", fontsize=11)
    axes[0].set_xlabel("Tháng")
    axes[0].set_ylabel("Trung vị nhiệt độ (°C)")
    axes[0].legend(loc="upper right", fontsize=8.8)
    axes[0].grid(True, linestyle=":", alpha=0.45)

    corr_arr = sp_df.to_numpy()
    im = axes[1].imshow(corr_arr, cmap="RdBu_r", vmin=-1.0, vmax=1.0)
    axes[1].set_xticks(range(len(sp_cols)))
    axes[1].set_yticks(range(len(sp_cols)))
    axes[1].set_xticklabels(sp_cols, rotation=35, ha="right", fontsize=9)
    axes[1].set_yticklabels(sp_cols, fontsize=9)
    for i in range(len(sp_cols)):
        for j in range(len(sp_cols)):
            axes[1].text(j, i, f"{corr_arr[i, j]:.2f}", ha="center", va="center", fontsize=8.2, color="black")
    axes[1].set_title("Tương quan Spearman trên ERA5", fontsize=11)
    plt.colorbar(im, ax=axes[1], fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(CHARTS / "real_era5_eda.png", bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)

    frames = []
    for name, g in d.groupby("location"):
        g = g.set_index("date").reindex(pd.date_range("2017-01-01", "2025-12-31"))
        g.index.name = "date"
        g["location"] = name
        g["temp_lag1"] = g.temp.shift(1)
        g["pressure_delta"] = g.pressure - g.pressure.shift(1)
        g["rain_lag1"] = g.rain.shift(1)
        g["target_temp"] = g.temp.shift(-1)
        g["target_rain"] = g.rain.shift(-1)
        g["target_date"] = g.index + pd.Timedelta(days=1)
        g["sin"] = np.sin(2 * np.pi * g.index.day_of_year / 365.25)
        g["cos"] = np.cos(2 * np.pi * g.index.day_of_year / 365.25)
        frames.append(g.reset_index())
    f = pd.concat(frames, ignore_index=True).dropna(subset=["temp", "temp_lag1", "target_temp", "target_rain"])
    for name in LOCATIONS:
        f[name] = (f.location == name).astype(int)
        f[name + "_sin"] = f[name] * f["sin"]
        f[name + "_cos"] = f[name] * f["cos"]
    f["split"] = np.where(
        f.target_date < "2024-01-01",
        "train",
        np.where(f.target_date < "2025-01-01", "validation", "test"),
    )
    assert f.loc[f.split == "train", "target_date"].max() < f.loc[f.split == "validation", "target_date"].min()
    assert f.loc[f.split == "validation", "target_date"].max() < f.loc[f.split == "test", "target_date"].min()
    f.to_csv(OUT / "features.csv", index=False)
    return f, quality


def regression(y: np.ndarray, p: np.ndarray) -> dict:
    yt = np.asarray(y, dtype=float)
    pt = np.asarray(p, dtype=float)
    mae = float(np.mean(np.abs(yt - pt)))
    rmse = float(np.sqrt(np.mean((yt - pt) ** 2)))
    ss_tot = float(np.sum((yt - yt.mean()) ** 2))
    r2 = float(1.0 - np.sum((yt - pt) ** 2) / ss_tot)
    return {"MAE": mae, "RMSE": rmse, "R2": r2}


def fit_predict_ridge(tr_df: pd.DataFrame, eval_df: pd.DataFrame, cols: list[str], alpha: float) -> np.ndarray:
    Xtr = tr_df[cols].to_numpy(dtype=float)
    med = np.nanmedian(Xtr, axis=0)
    Xtr = np.where(np.isnan(Xtr), med, Xtr)
    mu = Xtr.mean(axis=0)
    sig = Xtr.std(axis=0)
    sig[sig == 0] = 1.0
    Ztr = (Xtr - mu) / sig
    ytr = tr_df["target_temp"].to_numpy(dtype=float)
    ymu = float(ytr.mean())
    w = np.linalg.solve(Ztr.T @ Ztr + alpha * np.eye(len(cols)), Ztr.T @ (ytr - ymu))

    Xev = eval_df[cols].to_numpy(dtype=float)
    Xev = np.where(np.isnan(Xev), med, Xev)
    Zev = (Xev - mu) / sig
    return Zev @ w + ymu


def fit_predict_logistic_proba(tr_df: pd.DataFrame, eval_df: pd.DataFrame, cols: list[str], ytr: np.ndarray, C: float) -> np.ndarray:
    Xtr = tr_df[cols].to_numpy(dtype=float)
    med = np.nanmedian(Xtr, axis=0)
    Xtr = np.where(np.isnan(Xtr), med, Xtr)
    mu = Xtr.mean(axis=0)
    sig = Xtr.std(axis=0)
    sig[sig == 0] = 1.0
    Ztr = (Xtr - mu) / sig
    yr = np.asarray(ytr, dtype=float)
    n = len(Ztr)

    def loss_grad(wb: np.ndarray) -> tuple[float, np.ndarray]:
        w = wb[:-1]
        b = wb[-1]
        z = Ztr @ w + b
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -35.0, 35.0)))
        y_signed = 2.0 * yr - 1.0
        loss = float(np.mean(np.logaddexp(0.0, -y_signed * z)) + 0.5 / (C * n) * np.dot(w, w))
        diff = (p - yr) / n
        grad_w = Ztr.T @ diff + w / (C * n)
        grad_b = float(np.sum(diff))
        return loss, np.append(grad_w, grad_b)

    if minimize is not None:
        res = minimize(
            loss_grad,
            np.zeros(Ztr.shape[1] + 1),
            jac=True,
            method="L-BFGS-B",
            options={"gtol": 1e-4, "ftol": 1e-12, "maxiter": 2000},
        )
        w = res.x[:-1]
        b = res.x[-1]
    else:
        Xb = np.column_stack([Ztr, np.ones(n)])
        wb = np.zeros(Ztr.shape[1] + 1)
        reg_diag = np.r_[np.full(Ztr.shape[1], 1.0 / (C * n)), 0.0]
        for _ in range(120):
            _, g = loss_grad(wb)
            p = 1.0 / (1.0 + np.exp(-np.clip(Xb @ wb, -35.0, 35.0)))
            wt = np.maximum(p * (1.0 - p), 1e-9) / n
            H = (Xb.T * wt) @ Xb + np.diag(np.maximum(reg_diag, 1e-12))
            step = np.linalg.solve(H, g)
            wb -= step
            if float(np.linalg.norm(step)) < 1e-10:
                break
        w, b = wb[:-1], wb[-1]
    Xev = eval_df[cols].to_numpy(dtype=float)
    Xev = np.where(np.isnan(Xev), med, Xev)
    Zev = (Xev - mu) / sig
    return 1.0 / (1.0 + np.exp(-np.clip(Zev @ w + b, -35.0, 35.0)))


def binary_f1(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    yt = np.asarray(y_true, dtype=int)
    yp = np.asarray(y_pred, dtype=int)
    tp = int(np.sum((yt == 1) & (yp == 1)))
    fp = int(np.sum((yt == 0) & (yp == 1)))
    fn = int(np.sum((yt == 1) & (yp == 0)))
    return float(2 * tp / (2 * tp + fp + fn)) if (2 * tp + fp + fn) > 0 else 0.0


def roc_auc_exact(y_true: np.ndarray, prob: np.ndarray) -> float:
    yt = np.asarray(y_true, dtype=int)
    pr = np.asarray(prob, dtype=float)
    order = np.argsort(-pr, kind="mergesort")
    yt = yt[order]
    tps = np.cumsum(yt == 1)
    fps = np.cumsum(yt == 0)
    tpr = np.r_[0.0, tps / tps[-1]]
    fpr = np.r_[0.0, fps / fps[-1]]
    return float(getattr(np, "trapezoid", getattr(np, "trapz", None))(tpr, fpr))


def average_precision_exact(y_true: np.ndarray, prob: np.ndarray) -> float:
    yt = np.asarray(y_true, dtype=int)
    pr = np.asarray(prob, dtype=float)
    order = np.argsort(-pr, kind="mergesort")
    yt = yt[order]
    tps = np.cumsum(yt == 1)
    fps = np.cumsum(yt == 0)
    prec = tps / (tps + fps)
    rec = tps / tps[-1]
    rec_prev = np.r_[0.0, rec[:-1]]
    return float(np.sum((rec - rec_prev) * prec))


def run(refresh: bool = False) -> dict:
    f, q = prepare(acquire(refresh))
    tr = f[f.split == "train"]
    va = f[f.split == "validation"]
    te = f[f.split == "test"]
    base = ["temp", "humidity", "pressure", "wind"]
    season = ["sin", "cos"] + list(LOCATIONS) + [n + s for n in LOCATIONS for s in ["_sin", "_cos"]]
    configs = {
        "R1": base,
        "R2": base + ["temp_lag1", "pressure_delta", "rain", "rain_lag1", "solar"],
        "R3": base + ["temp_lag1", "pressure_delta", "rain", "rain_lag1", "solar"] + season,
    }
    rows = []
    predictions = {}
    for name, cols in configs.items():
        candidates = []
        for alpha in [0.1, 1, 10, 100]:
            p_va = fit_predict_ridge(tr, va, cols, float(alpha))
            candidates.append((regression(va.target_temp, p_va)["RMSE"], alpha))
        score, alpha = min(candidates, key=lambda x: x[0])
        predictions[name] = fit_predict_ridge(tr, te, cols, float(alpha))
        rows.append({"model": name, "alpha": alpha, "validation_RMSE": score, **regression(te.target_temp, predictions[name])})

    chosen = min(rows, key=lambda x: x["validation_RMSE"])["model"]
    predictions["Persistence"] = te.temp.to_numpy()
    clim = tr.groupby(["location", tr.target_date.dt.month]).target_temp.mean()
    predictions["Monthly_climatology"] = np.array([clim.loc[(r.location, r.target_date.month)] for r in te.itertuples()])

    # Harmonic climatology + anomaly persistence baseline (gamma selected on validation)
    season_harm_cols = ["sin", "cos", "Da_Nang", "Ha_Noi", "Da_Nang_sin", "Da_Nang_cos", "Ha_Noi_sin", "Ha_Noi_cos"]
    wc = fit_ridge_closed_form(tr[season_harm_cols].to_numpy(dtype=float), tr["temp"].to_numpy(dtype=float), l2=1.0)
    c_va = predict_linear(va[season_harm_cols].to_numpy(dtype=float), wc)
    c_te = predict_linear(te[season_harm_cols].to_numpy(dtype=float), wc)
    best_gamma = min(
        [
            (
                float(np.sqrt(np.mean((va.target_temp.to_numpy() - (c_va + g * (va.temp.to_numpy() - c_va))) ** 2))),
                round(float(g), 2),
            )
            for g in np.arange(0.30, 0.96, 0.05)
        ],
        key=lambda x: x[0],
    )[1]
    predictions["Climatology_anomaly"] = c_te + best_gamma * (te["temp"].to_numpy(dtype=float) - c_te)

    for name in ["Persistence", "Monthly_climatology", "Climatology_anomaly"]:
        row_b = {"model": name, **regression(te.target_temp, predictions[name])}
        if name == "Climatology_anomaly":
            row_b["anomaly_weight"] = best_gamma
        rows.append(row_b)
    pd.DataFrame(rows).to_csv(OUT / "temperature_metrics.csv", index=False)

    pred = te[["location", "date", "target_date", "target_temp", "target_rain"]].copy()
    for name, p in predictions.items():
        pred[name] = p
    regional = []
    for name, g in pred.groupby("location"):
        for model in predictions:
            regional.append({"location": name, "model": model, **regression(g.target_temp, g[model])})
    pd.DataFrame(regional).to_csv(OUT / "regional_metrics.csv", index=False)

    cols = configs["R3"]
    yr = (tr.target_rain >= 1).astype(int).to_numpy()
    yv = (va.target_rain >= 1).astype(int).to_numpy()
    yt = (te.target_rain >= 1).astype(int).to_numpy()
    rain_models = []
    for c in [0.01, 0.1, 1, 10]:
        pv = fit_predict_logistic_proba(tr, va, cols, yr, float(c))
        for threshold in np.arange(0.2, 0.81, 0.05):
            rain_models.append((binary_f1(yv, pv >= threshold), c, float(threshold)))
    _, c, threshold = max(rain_models, key=lambda x: x[0])
    prob = fit_predict_logistic_proba(tr, te, cols, yr, float(c))
    pred["rain_probability"] = prob
    pred["rain_prediction"] = (prob >= threshold).astype(int)
    pred["rain_persistence"] = (te.rain >= 1).astype(int).to_numpy()
    pred.to_csv(OUT / "predictions.csv", index=False)

    # Monthly-block paired bootstrap on Test 2025 (B=2000, seed=20261110) — Bảng 23 & Hình 15
    pred_boot = pred.reset_index(drop=True).copy()
    pred_boot["month"] = pd.to_datetime(pred_boot["target_date"]).dt.month
    months = [pred_boot[pred_boot["month"] == m].index.to_numpy() for m in range(1, 13)]
    rng = np.random.default_rng(20261110)
    diffs_r3_pers, diffs_r3_clim, diffs_f1 = [], [], []
    reg_diffs = {loc: [] for loc in ["Da_Nang", "Ha_Noi", "TP_HCM"]}
    yt_rain_arr = (pred_boot["target_rain"].to_numpy() >= 1.0).astype(int)
    yp_log_arr = pred_boot["rain_prediction"].to_numpy().astype(int)
    yp_pers_arr = (te["rain"].to_numpy() >= 1.0).astype(int)

    for _ in range(2000):
        chosen_m = rng.integers(0, 12, size=12)
        idx = np.concatenate([months[m] for m in chosen_m])
        yt_b = pred_boot["target_temp"].to_numpy()[idx]
        r3_b = pred_boot["R3"].to_numpy()[idx]
        ps_b = pred_boot["Persistence"].to_numpy()[idx]
        cl_b = pred_boot["Climatology_anomaly"].to_numpy()[idx]
        diffs_r3_pers.append(float(np.sqrt(np.mean((yt_b - r3_b) ** 2)) - np.sqrt(np.mean((yt_b - ps_b) ** 2))))
        diffs_r3_clim.append(float(np.sqrt(np.mean((yt_b - r3_b) ** 2)) - np.sqrt(np.mean((yt_b - cl_b) ** 2))))
        diffs_f1.append(float((binary_f1(yt_rain_arr[idx], yp_log_arr[idx]) - binary_f1(yt_rain_arr[idx], yp_pers_arr[idx])) * 100.0))
        sub_b = pred_boot.iloc[idx]
        for loc in ["Da_Nang", "Ha_Noi", "TP_HCM"]:
            sl = sub_b[sub_b["location"] == loc]
            reg_diffs[loc].append(float(np.sqrt(np.mean((sl.target_temp - sl.R3) ** 2)) - np.sqrt(np.mean((sl.target_temp - sl.Persistence) ** 2))))

    pt_r3_pers = float(np.sqrt(np.mean((pred_boot.target_temp - pred_boot.R3) ** 2)) - np.sqrt(np.mean((pred_boot.target_temp - pred_boot.Persistence) ** 2)))
    pt_r3_clim = float(np.sqrt(np.mean((pred_boot.target_temp - pred_boot.R3) ** 2)) - np.sqrt(np.mean((pred_boot.target_temp - pred_boot.Climatology_anomaly) ** 2)))
    pt_f1_pp = float((binary_f1(yt_rain_arr, yp_log_arr) - binary_f1(yt_rain_arr, yp_pers_arr)) * 100.0)

    pb_rows = [
        {
            "scope": "ALL",
            "comparison": "R3 - Persistence",
            "metric": "RMSE_C",
            "diff": round(pt_r3_pers, 4),
            "ci_low": round(float(np.percentile(diffs_r3_pers, 2.5)), 4),
            "ci_high": round(float(np.percentile(diffs_r3_pers, 97.5)), 4),
        },
        {
            "scope": "ALL",
            "comparison": "R3 - Climatology_anomaly",
            "metric": "RMSE_C",
            "diff": round(pt_r3_clim, 4),
            "ci_low": round(float(np.percentile(diffs_r3_clim, 2.5)), 4),
            "ci_high": round(float(np.percentile(diffs_r3_clim, 97.5)), 4),
        },
        {
            "scope": "ALL",
            "comparison": "Logistic - rain persistence",
            "metric": "F1_pp",
            "diff": round(pt_f1_pp, 4),
            "ci_low": round(float(np.percentile(diffs_f1, 2.5)), 4),
            "ci_high": round(float(np.percentile(diffs_f1, 97.5)), 4),
        },
    ]
    for loc in ["Da_Nang", "Ha_Noi", "TP_HCM"]:
        sl = pred_boot[pred_boot["location"] == loc]
        pt_l = float(np.sqrt(np.mean((sl.target_temp - sl.R3) ** 2)) - np.sqrt(np.mean((sl.target_temp - sl.Persistence) ** 2)))
        pb_rows.append({
            "scope": loc,
            "comparison": "R3 - Persistence",
            "metric": "RMSE_C",
            "diff": round(pt_l, 4),
            "ci_low": round(float(np.percentile(reg_diffs[loc], 2.5)), 4),
            "ci_high": round(float(np.percentile(reg_diffs[loc], 97.5)), 4),
        })
    pd.DataFrame(pb_rows).to_csv(OUT / "paired_bootstrap.csv", index=False)

    # Plot Hình 15 (real_paired_bootstrap.png)
    fig, ax = plt.subplots(figsize=(7.8, 3.0), dpi=180)
    y_pos = [0, 1]
    pts = [pb_rows[0]["diff"], pb_rows[1]["diff"]]
    lows = [pb_rows[0]["diff"] - pb_rows[0]["ci_low"], pb_rows[1]["diff"] - pb_rows[1]["ci_low"]]
    highs = [pb_rows[0]["ci_high"] - pb_rows[0]["diff"], pb_rows[1]["ci_high"] - pb_rows[1]["diff"]]
    ax.errorbar(pts, y_pos, xerr=[lows, highs], fmt="o", color="#1F77B4", capsize=5, linewidth=1.8, markersize=7)
    ax.axvline(0.0, color="#666666", linestyle="--", linewidth=1.4)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(["R3 - Persistence", "R3 - Climatology_anomaly"], fontsize=10)
    ax.set_xlabel("Chênh lệch RMSE (°C); âm = R3 sai số thấp hơn", fontsize=10)
    ax.set_title("Paired bootstrap theo khối tháng · Test 2025 · B=2000", fontsize=11)
    ax.grid(True, axis="x", linestyle=":", alpha=0.45)
    fig.tight_layout()
    fig.savefig(CHARTS / "real_paired_bootstrap.png", bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)

    rain = {
        "C": c,
        "threshold_validation": threshold,
        "Accuracy": float(np.mean((prob >= threshold).astype(int) == yt)),
        "F1": binary_f1(yt, prob >= threshold),
        "ROC_AUC": roc_auc_exact(yt, prob),
        "Average_precision": average_precision_exact(yt, prob),
        "Brier": float(np.mean((prob - yt) ** 2)),
        "always_dry_accuracy": float((yt == 0).mean()),
        "always_wet_F1": binary_f1(yt, np.ones(len(yt))),
        "persistence_F1": binary_f1(yt, (te.rain >= 1).astype(int).to_numpy()),
    }
    p_train = float(yr.mean())
    p_test = float(yt.mean())
    bs_train = float(np.mean((yt - p_train) ** 2))
    bs_test = p_test * (1 - p_test)
    rain.update({"train_prevalence": p_train, "test_prevalence": p_test,
                 "Brier_climatology_train": bs_train, "Brier_climatology_test_hindsight": bs_test,
                 "BSS_train_climatology": 1 - rain["Brier"] / bs_train,
                 "BSS_test_climatology_hindsight": 1 - rain["Brier"] / bs_test})
    pd.DataFrame([{"reference": "Train prevalence (operational baseline)", "p": p_train, "reference_Brier": bs_train, "BSS": rain["BSS_train_climatology"]},
                  {"reference": "Test prevalence (hindsight reference only)", "p": p_test, "reference_Brier": bs_test, "BSS": rain["BSS_test_climatology_hindsight"]}]).to_csv(OUT / "rain_skill.csv", index=False)
    summary = {
        "source": "Open-Meteo ERA5 reanalysis; not station observations or operational forecasts",
        "quality": q,
        "split_counts": f.split.value_counts().to_dict(),
        "split_policy": "target_date determines split; earlier observed history may cross the year boundary",
        "chosen_by_validation": chosen,
        "temperature": rows,
        "rain": rain,
        "paired_bootstrap": pb_rows,
        "run_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, g in pred.groupby("location"):
        g = g[g.target_date < "2025-04-01"]
        fig, ax = plt.subplots(figsize=(10, 3))
        ax.plot(g.target_date, g.target_temp, label="ERA5")
        ax.plot(g.target_date, g[chosen], label=chosen)
        ax.set(title=name + " - Test 2025", ylabel="Temperature (C)")
        ax.legend()
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(OUT / f"{name}_prediction.png", dpi=150)
        plt.close(fig)

    plots = {n: base64.b64encode((OUT / f"{n}_prediction.png").read_bytes()).decode() for n in LOCATIONS}
    table = pd.DataFrame(rows).round(4).to_html(index=False)
    html = (
        '<!doctype html><meta charset="utf-8"><title>Nhóm 13 — ERA5</title>'
        "<style>body{font:17px Arial;max-width:1100px;margin:40px auto;background:#f4f7fb;color:#18334a}"
        "table{border-collapse:collapse;background:white}td,th{padding:12px}img{width:100%}select{padding:10px}</style>"
        "<h1>Nhóm 13 · Dữ liệu khí tượng và dự báo</h1>"
        "<p>Thực nghiệm hồi cứu trên dữ liệu tái phân tích ERA5 2017–2025. Không phải dự báo thời tiết trực tiếp.</p>"
        "<p>Train: 2017–2023 · Validation: 2024 · Test: 2025 (theo ngày mục tiêu).</p>"
        + table
        + '<h2>Thực tế ERA5 và dự báo · quý I/2025</h2><select id="city">'
        + "".join("<option>" + n + "</option>" for n in LOCATIONS)
        + '</select><img id="plot"><p>Nguồn: Open-Meteo / ECMWF ERA5 · CC BY 4.0. Dữ liệu và bảng kết quả đầy đủ nằm trong outputs/real.</p>'
        + "<script>const plots="
        + json.dumps(plots)
        + ';const city=document.getElementById("city");function draw(){document.getElementById("plot").src="data:image/png;base64,"+plots[city.value]}city.onchange=draw;draw();</script>'
    )
    (OUT / "DASHBOARD.html").write_text(html, encoding="utf-8")
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--refresh", action="store_true")
    run(p.parse_args().refresh)
