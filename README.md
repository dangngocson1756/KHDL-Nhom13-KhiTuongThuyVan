# Nhóm 13 — dữ liệu khí tượng thủy văn cho dự báo thời tiết

Thành viên: Đinh Quang Thái (N22DCCN176), Đặng Ngọc Sơn (N22DCCN070), Đặng Văn Chương (N22DCCN012).

Bản hiện hành lấy **ERA5 làm kết quả dự báo chính**, bổ sung **GloFAS v4 consolidated** cho thu thập và mô tả lưu lượng, đưa benchmark mô phỏng vào Phụ lục A. Báo cáo có **32 bảng, 14 hình**; bộ kiểm thử hiện hành **48/48 đạt**.

## Nguồn và giới hạn

- `data/era5`: 9.861 địa điểm–ngày, 2017–2025, UTC+7, 3 ô lưới; JSON và request/SHA-256.
- `data/hydrology`: 5.478 địa điểm–ngày, 2017–2021, UTC; Flood API với `models=consolidated_v4`, `daily=river_discharge`. Đây là lưu lượng mô hình GloFAS, chưa xác minh ô sông bằng trạm/lưu vực. Không dùng nó để xác nhận mưa ERA5 hoặc dự báo lũ.
- `data/raw`: benchmark 10.273 dòng cố định. Thiếu mã sinh/seed gốc và chưa xác minh đầy đủ tác giả. Chỉ kiểm thử logic QC, không diễn giải tương quan mô phỏng như cơ chế khí quyển.
- Chưa có chuỗi quan trắc trạm độc lập NOAA ISD/Meteostat. Mốc QCVN khí hậu khác thời kỳ/định nghĩa nên chỉ là đối chiếu tham chiếu.
- Tái lập từ các JSON đóng băng, không bao gồm sinh lại benchmark. ERA5 gán tập theo target_date và cho phép lịch sử đầu vào từ năm trước; benchmark giữ chính sách bảo thủ yêu cầu cả hai ngày cùng tập. Chỉ so baseline và mô hình trong cùng một nhánh.

## Cài đặt và chạy

Python 3.10+: `python -m pip install -r requirements.txt`.

```bash
python scripts/run_project.py --skip-download
python tools/build_final_report.py
python tools/audit_report_consistency.py
python -m unittest discover -s tests -v
```

`python scripts/hydrology.py --refresh` chỉ dùng khi chủ động tải phiên bản mới; cần mạng. Phát lại mặc định kiểm SHA-256 và không cần mạng. Cần LibreOffice (`soffice` hoặc `libreoffice` trên PATH) để xuất PDF; `--workbook` tính lại Excel benchmark khi có LibreOffice.

## Sản phẩm

- Báo cáo chính: `docs/BAO_CAO_TIEU_LUAN_6_CHUONG.docx` và `.pdf`.
- ERA5: `outputs/real/clean.csv`, `features.csv`, `summary.json`, `rain_skill.csv`, `cluster_trials.csv`, `DASHBOARD.html`.
- Thủy văn: `outputs/hydrology/daily.csv`, `summary.csv`, `monthly.csv`, `monthly.png`, `provenance.json`.
- SQLite: `outputs/kttv_weather.sqlite`, gồm `era5_daily` (9.861), `hydrology_daily` (5.478), `observations` benchmark (9.634) và 2 bảng danh mục benchmark. Hai nguồn thật/tái phân tích không bị gộp vào observations.
- Dashboard và Excel benchmark vẫn kèm để kiểm mã, không đại diện kết quả thời tiết quan trắc tại trạm.

## Đọc kết quả

R3 ERA5: RMSE 0,9302 °C so quán tính 1,0741 °C. Mưa: F1 81,67% nhưng CI chênh lệch với quán tính chứa 0. BSS so xác suất khí hậu Train = **0,3810**; BSS so tỷ lệ Test chỉ là tham chiếu hậu nghiệm. Phân cụm k=2 chỉ mô tả ẩm–mưa, không phải hai loại cấu trúc thời tiết.

QCVN 02:2022/BXD gốc, dòng Hà Nội: **1.670,1 mm/năm** ở A.25 (PDF trang 447), **147,9 ngày mưa/năm** ở A.28 (PDF trang 463). Hồ sơ: `references/qcvn02_hanoi_verified.json`; không tiếp tục dùng cặp 1.611/152 chưa khớp nguồn gốc.
