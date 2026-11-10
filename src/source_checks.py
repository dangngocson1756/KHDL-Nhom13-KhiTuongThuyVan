"""Physical consistency and WMO-No. 8 / WMO-No. 1269 / QCVN 46:2022/BTNMT quality control checks."""
from __future__ import annotations
import math
import re
import unicodedata

# WMO-No. 8 (Volume I, Chapter 4, Annex 4.B) Magnus coefficients over liquid water
WMO_MAGNUS_A = 17.62
WMO_MAGNUS_B = 243.12

def normalize_text(val: object) -> str:
    if val is None:
        return ""
    s = unicodedata.normalize("NFKC", str(val)).strip()
    return re.sub(r"\s+", " ", s)

def parse_date_iso(val: object) -> str | None:
    s = normalize_text(val)
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", s)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None

def parse_float_with_unit(val: object, allowed_units: tuple[str, ...] = ()) -> tuple[float | None, str]:
    s = normalize_text(val).casefold()
    if not s or s in {"na", "null", "none", "-", "nan"}:
        return None, "missing"
    if "err" in s or "fault" in s:
        return None, "corrupted_token"
    unit_found = "raw"
    for u in allowed_units:
        if s.endswith(u):
            unit_found = u
            s = s[:-len(u)].strip()
            break
    s = s.replace(",", ".")
    try:
        return float(s), unit_found
    except ValueError:
        return None, "unparseable_number"

def compute_wmo_dewpoint(temp_c: float, humidity_pct: float) -> float:
    """Compute theoretical dewpoint (°C) from air temperature (°C) and relative humidity (%) per WMO-No. 8."""
    rh_clamped = min(max(humidity_pct, 1e-4), 100.0)
    gamma = (WMO_MAGNUS_A * temp_c) / (WMO_MAGNUS_B + temp_c) + math.log(rh_clamped / 100.0)
    return (WMO_MAGNUS_B * gamma) / (WMO_MAGNUS_A - gamma)

def check_wmo_physical_consistency(
    temp_mean: float | None,
    temp_max: float | None,
    temp_min: float | None,
    dewpoint: float | None,
    humidity: float | None,
    pressure: float | None,
    precip: float | None,
    wind_speed: float | None,
    wind_dir: float | None,
    solar_rad: float | None,
) -> tuple[bool, list[str], list[str]]:
    """
    Evaluate WMO-No. 8 / WMO-No. 1269 gross plausible limits and internal physical consistency
    (including Magnus psychrometric cross-check between reported Td and theoretical Td(T, RH)).
    Returns (is_accepted, reject_reasons, quality_flags).
    """
    reject_reasons: list[str] = []
    flags: list[str] = []

    if temp_mean is None:
        flags.append("missing_temp_mean_imputable")
    elif not (-5.0 <= temp_mean <= 48.0):
        reject_reasons.append("wmo_gross_limit_temp_mean")

    if temp_max is None or temp_min is None:
        reject_reasons.append("missing_temp_extremes")
    else:
        if not (-5.0 <= temp_min <= 45.0) or not (0.0 <= temp_max <= 50.0):
            reject_reasons.append("wmo_gross_limit_temp_extremes")
        if temp_max < temp_min:
            reject_reasons.append("physical_violation_tmax_lt_tmin")
        if temp_mean is not None and not (temp_min - 0.5 <= temp_mean <= temp_max + 0.5):
            reject_reasons.append("physical_violation_tmean_outside_extremes")

    if humidity is None or not (0.0 <= humidity <= 100.0):
        reject_reasons.append("wmo_gross_limit_humidity")

    if dewpoint is None:
        reject_reasons.append("missing_dewpoint")
    elif temp_mean is not None and dewpoint > temp_mean + 0.05:
        reject_reasons.append("physical_violation_dewpoint_gt_temp")
    elif temp_max is not None and dewpoint > temp_max:
        reject_reasons.append("physical_violation_dewpoint_gt_tmax")
    elif temp_mean is not None and humidity is not None and (0.0 < humidity <= 100.0):
        td_theo = compute_wmo_dewpoint(temp_mean, humidity)
        if abs(dewpoint - td_theo) > 2.5:
            reject_reasons.append("physical_violation_magnus_mismatch")

    if pressure is None:
        flags.append("missing_pressure_imputable")
    elif not (950.0 <= pressure <= 1045.0):
        reject_reasons.append("wmo_gross_limit_pressure")

    if precip is None or precip < 0.0 or precip > 800.0:
        reject_reasons.append("wmo_gross_limit_precip")
    elif precip >= 50.0:
        flags.append("heavy_rain_event_ge_50mm")

    if wind_speed is None or wind_speed < 0.0 or wind_speed > 75.0:
        reject_reasons.append("wmo_gross_limit_wind_speed")

    if wind_dir is None or not (0.0 <= wind_dir <= 360.0):
        reject_reasons.append("wmo_gross_limit_wind_dir")

    if solar_rad is None or not (0.0 <= solar_rad <= 40.0):
        reject_reasons.append("wmo_gross_limit_solar_rad")

    return (len(reject_reasons) == 0), reject_reasons, flags
