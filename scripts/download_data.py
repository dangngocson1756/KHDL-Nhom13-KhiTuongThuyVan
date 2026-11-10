"""Verify the pinned fault-injected QC benchmark dataset or fetch live ERA5 observations via Open-Meteo API."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from artifact_contract import read_verified_source

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
STATIONS = {
    "WMO_48820": {"name": "Hà Nội (Láng)", "lat": 21.02, "lon": 105.80, "elev_m": 6.0},
    "WMO_48855": {"name": "Đà Nẵng", "lat": 16.04, "lon": 108.20, "elev_m": 7.0},
    "WMO_48900": {"name": "TP. Hồ Chí Minh (Tân Sơn Nhất)", "lat": 10.82, "lon": 106.67, "elev_m": 9.0},
}

def fetch_open_meteo_era5(start_date: str = "2017-01-01", end_date: str = "2025-12-31", timeout: int = 20) -> Path:
    """
    Fetch daily ECMWF ERA5 reanalysis surface variables for the 3 WMO stations from Open-Meteo API
    (timezone=Asia/Bangkok, UTC+7) and save with SHA-256 provenance manifest.
    """
    daily_vars = [
        "temperature_2m_mean",
        "temperature_2m_max",
        "temperature_2m_min",
        "dew_point_2m_mean",
        "relative_humidity_2m_mean",
        "surface_pressure_mean",
        "precipitation_sum",
        "wind_speed_10m_mean",
        "wind_direction_10m_dominant",
        "shortwave_radiation_sum",
    ]
    all_rows = []
    for scode, meta in STATIONS.items():
        params = urllib.parse.urlencode({
            "latitude": meta["lat"],
            "longitude": meta["lon"],
            "start_date": start_date,
            "end_date": end_date,
            "daily": ",".join(daily_vars),
            "timezone": "Asia/Bangkok",
            "wind_speed_unit": "ms",
        })
        url = f"{OPEN_METEO_ARCHIVE_URL}?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "PTIT-KHDL-WeatherPipeline/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        daily = payload.get("daily", {})
        dates = daily.get("time", [])
        for i, d_str in enumerate(dates):
            all_rows.append({
                "station_code": scode,
                "station_name": meta["name"],
                "obs_date": d_str,
                "temp_mean_c": daily["temperature_2m_mean"][i],
                "temp_max_c": daily["temperature_2m_max"][i],
                "temp_min_c": daily["temperature_2m_min"][i],
                "dewpoint_c": daily["dew_point_2m_mean"][i],
                "humidity_pct": daily["relative_humidity_2m_mean"][i],
                "pressure_hpa": daily["surface_pressure_mean"][i],
                "precip_mm": daily["precipitation_sum"][i],
                "wind_speed_ms": daily["wind_speed_10m_mean"][i],
                "wind_dir_deg": daily["wind_direction_10m_dominant"][i],
                "solar_rad_mj": daily["shortwave_radiation_sum"][i],
            })
    out_file = ROOT / "data/raw/open_meteo_era5_live.json"
    out_file.write_text(json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    digest = hashlib.sha256(out_file.read_bytes()).hexdigest()
    meta_out = ROOT / "data/raw/open_meteo_era5_live_manifest.json"
    meta_out.write_text(json.dumps({
        "fetched_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "api_endpoint": OPEN_METEO_ARCHIVE_URL,
        "timezone": "Asia/Bangkok (UTC+7)",
        "record_count": len(all_rows),
        "sha256": digest,
    }, indent=2), encoding="utf-8")
    return out_file

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fetch-live-era5",
        action="store_true",
        help="Attempt online download of ERA5 daily observations from Open-Meteo Historical Weather API.",
    )
    args = parser.parse_args()

    if args.fetch_live_era5:
        try:
            out_path = fetch_open_meteo_era5()
            print(f"Downloaded live ERA5 dataset to {out_path}")
        except Exception as exc:
            print(f"Online ERA5 fetch skipped/unavailable ({exc}); falling back to pinned benchmark dataset.")

    records, manifest = read_verified_source(ROOT)
    print(
        f"Verified pinned QC benchmark dataset: {manifest['raw_file']} "
        f"({len(records)} records, sha256={manifest['sha256']})"
    )

if __name__ == "__main__":
    main()
