

- `data/era5`: 9.861 địa điểm–ngày, 2017–2025, UTC+7, 3 ô lưới; JSON và request/SHA-256.
- `data/hydrology`: 5.478 địa điểm–ngày, 2017–2021, UTC; Flood API với `models=consolidated_v4`, `daily=river_discharge`. Đây là lưu lượng mô hình GloFAS, chưa xác minh ô sông bằng trạm/lưu vực. Không dùng nó để xác nhận mưa ERA5 hoặc dự báo lũ.
- `data/raw`: benchmark 10.273 dòng cố định. Thiếu mã sinh/seed gốc và chưa xác minh đầy đủ tác giả. Chỉ kiểm thử logic QC, không diễn giải tương quan mô phỏng như cơ chế khí quyển.
- Chưa có chuỗi quan trắc trạm độc lập NOAA ISD/Meteostat. Mốc QCVN khí hậu khác thời kỳ/định nghĩa nên chỉ là đối chiếu tham chiếu.
- Tái lập từ các JSON đóng băng, không bao gồm sinh lại benchmark. ERA5 gán tập theo target_date và cho phép lịch sử đầu vào từ năm trước; benchmark giữ chính sách bảo thủ yêu cầu cả hai ngày cùng tập. Chỉ so baseline và mô hình trong cùng một nhánh.


Nguồn chính thức: Open-Meteo Flood API https://open-meteo.com/en/docs/flood-api ; Copernicus GloFAS https://ewds.climate.copernicus.eu/datasets/cems-glofas-historical ; QCVN 47/Thông tư 22: https://vanban.chinhphu.vn/?docid=207442&pageid=27160 .
