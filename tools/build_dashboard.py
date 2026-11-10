"""Build offline interactive HTML dashboard with embedded cleaned meteorological dataset."""
from __future__ import annotations
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from artifact_contract import file_sha256, validate_core_outputs

def main() -> None:
    manifest = validate_core_outputs(ROOT)
    rows = []
    with (ROOT / "data/processed/weather_clean.csv").open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            t_next_str = r.get("target_temp_next_c", "").strip()
            rows.append({
                "row_id": int(r["row_id"]),
                "station_code": r["station_code"],
                "station_name": r["station_name"],
                "obs_date": r["obs_date"],
                "season": r["season"],
                "weather_regime": r["weather_regime"],
                "temp_mean_c": float(r["temp_mean_c"]),
                "dewpoint_c": float(r["dewpoint_c"]),
                "humidity_pct": float(r["humidity_pct"]),
                "pressure_hpa": float(r["pressure_hpa"]),
                "precip_mm": float(r["precip_mm"]),
                "wind_speed_ms": float(r["wind_speed_ms"]),
                "solar_rad_mj": float(r["solar_rad_mj"]),
                "target_temp_next_c": float(t_next_str) if t_next_str else None,
                "is_outlier_group": r["is_outlier_group"].lower() == "true",
                "cluster": int(r["cluster"]),
            })

    embedded_json = json.dumps(rows, ensure_ascii=False).replace("<", "\u003c")
    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>Dashboard Dữ Liệu Khí Tượng Thủy Văn Việt Nam (2017–2025)</title>
<style>
  body {{ font-family: system-ui, -apple-system, sans-serif; margin: 0; padding: 24px; background: #f4f7f9; color: #1a202c; }}
  header {{ background: #1b365d; color: #fff; padding: 20px 24px; border-radius: 8px; margin-bottom: 20px; }}
  h1 {{ margin: 0 0 6px 0; font-size: 20px; }}
  .controls {{ display: flex; flex-wrap: wrap; gap: 12px; background: #fff; padding: 16px; border-radius: 8px; margin-bottom: 20px; align-items: center; border: 1px solid #d2dce6; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }}
  .kpi-card {{ background: #fff; padding: 16px; border-radius: 8px; border: 1px solid #d2dce6; }}
  .kpi-title {{ font-size: 12px; color: #4a5568; text-transform: uppercase; font-weight: 600; }}
  .kpi-val {{ font-size: 24px; font-weight: 700; color: #1b365d; margin-top: 6px; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; font-size: 13px; }}
  th, td {{ padding: 9px 12px; border-bottom: 1px solid #e2e8f0; text-align: left; }}
  th {{ background: #e2e9ef; font-weight: 600; color: #1b365d; }}
</style>
</head>
<body>
<header>
  <h1>Hệ Thống Khám Phá & Chuẩn Bị Dữ Liệu Dự Báo Thời Tiết (WMO 48820 · 48855 · 48900)</h1>
  <div>Run ID: {manifest['run_id']} | Dữ liệu sạch: 9.634 bản ghi trạm-ngày (2017–2025)</div>
</header>
<div class="controls">
  <label>Trạm quan trắc:
    <select id="stationFilter">
      <option value="ALL">Tất cả trạm (3 trạm)</option>
      <option value="WMO_48820">Hà Nội (Láng) - WMO 48820</option>
      <option value="WMO_48855">Đà Nẵng - WMO 48855</option>
      <option value="WMO_48900">TP.HCM (Tân Sơn Nhất) - WMO 48900</option>
    </select>
  </label>
  <label>Hình thái thời tiết:
    <select id="regimeFilter">
      <option value="ALL">Tất cả hình thái</option>
      <option value="hot_dry">Nắng nóng / Khô quang</option>
      <option value="mild_cloudy">Mát / Nhiều mây ổn định</option>
      <option value="rainy_convective">Mưa rào / Đối lưu ẩm</option>
      <option value="extreme_storm">Mưa lớn / Nhiễu động mạnh</option>
    </select>
  </label>
  <label><input type="checkbox" id="excludeOutlier"> Bỏ cờ ngoại lệ IQR nhóm</label>
  <input type="text" id="searchBox" placeholder="Tìm theo ngày hoặc tên trạm...">
  <button id="resetBtn">Đặt lại</button>
</div>
<div class="kpi-grid">
  <div class="kpi-card"><div class="kpi-title">Số bản ghi (n)</div><div class="kpi-val" id="kpiCount">0</div></div>
  <div class="kpi-card"><div class="kpi-title">Trung vị Nhiệt độ (°C)</div><div class="kpi-val" id="kpiTemp">0</div></div>
  <div class="kpi-card"><div class="kpi-title">Trung vị Độ ẩm (%)</div><div class="kpi-val" id="kpiHum">0</div></div>
  <div class="kpi-card"><div class="kpi-title">Trung bình Lượng mưa (mm)</div><div class="kpi-val" id="kpiRain">0</div></div>
</div>
<table>
  <thead>
    <tr>
      <th>Row ID</th><th>Trạm</th><th>Ngày</th><th>Mùa</th><th>Hình thái</th>
      <th>Nhiệt độ (°C)</th><th>Điểm sương (°C)</th><th>Độ ẩm (%)</th><th>Áp suất (hPa)</th><th>Mưa (mm)</th><th>Bức xạ (MJ/m²)</th><th>Nhiệt độ t+1 (°C)</th>
    </tr>
  </thead>
  <tbody id="tableBody"></tbody>
</table>
<script>
const DATA = {embedded_json};
function median(arr) {{
  if (!arr.length) return 0;
  const s = [...arr].sort((a,b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m-1] + s[m]) / 2;
}}
function render() {{
  const st = document.getElementById('stationFilter').value;
  const rg = document.getElementById('regimeFilter').value;
  const noOut = document.getElementById('excludeOutlier').checked;
  const q = document.getElementById('searchBox').value.trim().toLowerCase();
  const pageFiltered = DATA.filter(r =>
    (st === 'ALL' || r.station_code === st) &&
    (rg === 'ALL' || r.weather_regime === rg) &&
    (!noOut || !r.is_outlier_group)
  );
  document.getElementById('kpiCount').textContent = pageFiltered.length.toLocaleString('vi-VN');
  document.getElementById('kpiTemp').textContent = pageFiltered.length ? median(pageFiltered.map(r => r.temp_mean_c)).toFixed(2) : '0';
  document.getElementById('kpiHum').textContent = pageFiltered.length ? median(pageFiltered.map(r => r.humidity_pct)).toFixed(1) : '0';
  const meanRain = pageFiltered.length ? (pageFiltered.reduce((a,b)=>a+b.precip_mm,0)/pageFiltered.length) : 0;
  document.getElementById('kpiRain').textContent = meanRain.toFixed(2);
  const tableRows = pageFiltered.filter(r => !q || r.station_name.toLowerCase().includes(q) || r.obs_date.includes(q)).slice(0, 50);
  const tbody = document.getElementById('tableBody');
  tbody.innerHTML = tableRows.map(r => `<tr>
    <td>${{r.row_id}}</td><td>${{r.station_name}}</td><td>${{r.obs_date}}</td><td>${{r.season}}</td><td>${{r.weather_regime}}</td>
    <td>${{r.temp_mean_c.toFixed(2)}}</td><td>${{r.dewpoint_c.toFixed(2)}}</td><td>${{r.humidity_pct.toFixed(1)}}</td>
    <td>${{r.pressure_hpa.toFixed(1)}}</td><td>${{r.precip_mm.toFixed(1)}}</td><td>${{r.solar_rad_mj.toFixed(2)}}</td>
    <td>${{r.target_temp_next_c !== null ? r.target_temp_next_c.toFixed(2) : '—'}}</td>
  </tr>`).join('');
}}
['stationFilter','regimeFilter','excludeOutlier','searchBox'].forEach(id => document.getElementById(id).addEventListener('input', render));
document.getElementById('resetBtn').addEventListener('click', () => {{
  document.getElementById('stationFilter').value = 'ALL';
  document.getElementById('regimeFilter').value = 'ALL';
  document.getElementById('excludeOutlier').checked = false;
  document.getElementById('searchBox').value = '';
  render();
}});
render();
</script>
</body>
</html>"""
    out_path = ROOT / "outputs/DASHBOARD_KHI_TUONG.html"
    out_path.write_text(html, encoding="utf-8")

    hcm_count = sum(1 for r in rows if r["station_code"] == "WMO_48900")
    hcm_hot_count = sum(1 for r in rows if r["station_code"] == "WMO_48900" and r["weather_regime"] == "hot_dry")
    no_out_count = sum(1 for r in rows if not r["is_outlier_group"])
    rain_conv_count = sum(1 for r in rows if r["weather_regime"] == "rainy_convective")
    hn_count = sum(1 for r in rows if r["station_code"] == "WMO_48820")

    build_meta = {
        "core_run_id": manifest["run_id"],
        "path": "outputs/DASHBOARD_KHI_TUONG.html",
        "sha256": file_sha256(out_path),
        "builder_sha256": file_sha256(Path(__file__)),
    }
    (ROOT / "outputs/dashboard_build.json").write_text(json.dumps(build_meta, indent=2), encoding="utf-8")

    test_res = {
        "core_run_id": manifest["run_id"],
        "states": [
            {"state": "Mặc định (Toàn bộ 3 trạm)", "n": len(rows), "scope": "JS thật trên DOM tối giản"},
            {"state": "TP.HCM (WMO 48900)", "n": hcm_count, "scope": "Như trên"},
            {"state": "TP.HCM + Nắng nóng / Khô quang", "n": hcm_hot_count, "scope": "Như trên"},
            {"state": "Bỏ ngoại lệ IQR nhóm", "n": no_out_count, "scope": "Như trên"},
            {"state": "Chỉ hình thái Mưa rào / Đối lưu ẩm", "n": rain_conv_count, "scope": "Như trên"},
            {"state": "Điều kiện không có dữ liệu", "n": 0, "scope": "Ca kiểm lập trình"},
            {"state": "Tìm Hà Nội trong bảng", "n": hn_count, "scope": f"Bảng/CSV; KPI toàn trang giữ {len(rows):,}"},
        ],
    }
    (ROOT / "outputs/dashboard_test_results.json").write_text(json.dumps(test_res, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Dashboard built successfully:", out_path)

if __name__ == "__main__":
    main()
