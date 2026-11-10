"""Six-chapter expanded report grounded in real source caches and executed diagnostics."""
from pathlib import Path
import re,json
import pandas as pd
import report_v2 as base
ROOT=Path(__file__).resolve().parents[1]
vn=base.vn
csv=base.csv
js=base.js

def tables(a):
 t=base.tables(a)
 def add(k,cap,heads,rows,widths,source,label='ERA5'):
  t[k]=dict(caption=f'[{label}] {cap}',headers=heads,rows=rows,widths=widths,source='Nguồn: '+source)
 inv=csv('outputs/report_evidence/source_inventory.csv')
 add('source_coordinates','Tọa độ và lịch dữ liệu thực sự được API trả về',['Nguồn','Địa điểm','Tâm ô lưới','Số ngày','Múi giờ'],[[x.source,x.location,f'{x.latitude:.5f}; {x.longitude:.5f}',vn(x.rows),x.timezone] for x in inv.itertuples()],[2,2.7,5.2,2.2,4.9],'outputs/report_evidence/source_inventory.csv; phản hồi nguyên gốc của API.','CÁC NGUỒN')
 add('data_dictionary','Ánh xạ biến khí tượng từ API sang dữ liệu phân tích',['Trường API','Tên nội bộ','Đơn vị','Ý nghĩa trong ngày'],[
 ['temperature_2m_mean','temp','°C','Nhiệt độ không khí 2 m trung bình'],['temperature_2m_max / min','tmax / tmin','°C','Cực đại / cực tiểu nhiệt độ 2 m'],['relative_humidity_2m_mean','humidity','%','Độ ẩm tương đối trung bình'],['pressure_msl_mean','pressure','hPa','Áp suất trung bình quy về mực biển'],['precipitation_sum','rain','mm','Tổng giáng thủy, dùng định nghĩa nhãn ≥1 mm'],['wind_speed_10m_mean','wind','m/s','Tốc độ gió 10 m trung bình'],['shortwave_radiation_sum','solar','MJ/m²','Tổng bức xạ sóng ngắn']],[6.5,2.4,2,6.2],'data/era5/*_request.json và daily_units; scripts/real_weather.py. Tên rain trong code không biến precipitation_sum thành số đo mưa tại trạm.')
 add('quality_rules','Phép kiểm chất lượng theo từng nguồn',['Nguồn','Điều kiện','Xử lý / phạm vi'],[
 ['ERA5','RH < 0 hoặc RH > 100','Cách ly dòng; 2 điều kiện'],['ERA5','Giáng thủy < 0; gió < 0','Cách ly dòng; 2 điều kiện'],['ERA5','Tmin > Tmax; T < Tmin; T > Tmax','Cách ly dòng; 3 điều kiện'],['ERA5','Khóa location + date trùng','Giữ bản ghi đầu, đếm bản trùng'],['ERA5','Thiếu dữ liệu','Báo số ô thiếu; cửa sổ thiếu T hoặc nhãn bị loại; trung vị Train cho biến giải thích còn thiếu'],['GloFAS','Đơn vị, UTC, lịch ngày và SHA-256','Dừng nếu sai hợp đồng dữ liệu'],['GloFAS','Giá trị thiếu hoặc âm','Gắn quality_flag; không nội suy, loại khỏi thống kê hợp lệ'],['Benchmark','Định dạng, đơn vị, trùng, ngưỡng và Magnus','Bộ kiểm thử riêng; không chuyển nguyên ngưỡng sang ERA5/GloFAS']],[2.1,6.1,8.9],'scripts/real_weather.py, scripts/hydrology.py, src/source_checks.py.','CÁC NGUỒN')
 add('modules','Trách nhiệm và hợp đồng giữa các mô đun',['Mô đun','Đầu vào','Đầu ra chính'],[
 ['scripts/real_weather.py','JSON ERA5 và hồ sơ request','clean, features, predictions, metrics, dashboard ERA5'],['scripts/hydrology.py','JSON GloFAS và request/SHA-256','daily, summary, monthly, provenance'],['src/pipeline.py','Benchmark JSON cố định','CSV sạch/cách ly, lineage, bảng kiểm thử và SQLite'],['src/source_database.py','CSV ERA5 và GloFAS đã xử lý','era5_daily và hydrology_daily'],['tools/report_evidence.py','CSV, dự báo đã khóa, SQLite','Chẩn đoán bổ sung và biểu đồ trong báo cáo'],['tools/build_final_report.py','Đầu ra + mẫu nội dung có tham chiếu','DOCX/PDF, mục lục có số trang'],['tools/audit_report_consistency.py','Nguồn, kết quả, DOCX/PDF','Đối chiếu các khẳng định định lượng quan trọng']],[6,4.8,6.3],'Mã nguồn đóng gói cùng báo cáo.','HỆ THỐNG')
 add('features','Ba cấu hình đặc trưng của hồi quy nhiệt độ',['Cấu hình','Số cột','Các nhóm biến'],[
 ['R1','4','T(t), RH(t), áp suất mực biển(t), gió(t)'],['R2','9','R1 + T(t−1), Δáp suất, giáng thủy(t), giáng thủy(t−1), bức xạ(t)'],['R3','20','R2 + sin/cos ngày trong năm, 3 chỉ báo địa điểm và 6 tương tác địa điểm × sin/cos']],[2,2,13.1],'configs trong scripts/real_weather.py. Logistic dùng cùng bộ đặc trưng R3; toàn bộ đầu vào có thời điểm không sau t.')
 d=csv('outputs/report_evidence/split_inventory.csv')
 add('split_detail','Chia tập theo ngày mục tiêu và tỷ lệ mưa',['Tập','n','Ngày mục tiêu đầu','Ngày mục tiêu cuối','Ngày ≥1 mm','Tỷ lệ %'],[[x.split,vn(x.n),x.target_min[:10],x.target_max[:10],vn(x.wet_n),vn(x.wet_pct,2)] for x in d.itertuples()],[2.5,2,3.5,3.5,3.1,2.5],'outputs/report_evidence/split_inventory.csv; mỗi ngày có tối đa ba địa điểm.')
 add('hyperparameters','Không gian lựa chọn mô hình trên Validation',['Thành phần','Giá trị thử','Tiêu chí / kết quả'],[
 ['Ridge α','0,1; 1; 10; 100','RMSE Validation thấp nhất; α=0,1 cho R1–R3'],['Cấu hình nhiệt độ','R1; R2; R3','Chọn R3 theo Validation'],['Logistic C','0,01; 0,1; 1; 10','F1 Validation; C=0,1'],['Ngưỡng mưa','0,20 đến 0,80; bước 0,05','F1 Validation; ngưỡng 0,45'],['Trọng số dị thường γ','0,30 đến 0,95; bước 0,05','RMSE Validation; γ=0,85'],['Phân tách mô tả','k = 2, 3, 4, 5','Silhouette mẫu 1.000 dòng; không phải chọn mô hình dự báo']],[4.1,5.5,7.5],'scripts/real_weather.py và outputs/real/summary.json; không chọn tham số bằng Test.')
 d=csv('outputs/report_evidence/location_profile.csv')
 add('location_profile','Phân bố khí tượng theo từng ô lưới',['Địa điểm','n','T TB °C','RH trung vị %','Mưa TB mm/ngày','Ngày ≥1 mm %'],[[x.location,vn(x.n),vn(x.temp_mean,2),vn(x.humidity_median,1),vn(x.rain_mean,3),vn(x.wet_pct,2)] for x in d.itertuples()],[2.8,2,2.6,3.1,3.5,3.1],'outputs/report_evidence/location_profile.csv; 2017–2025.')
 d=csv('outputs/report_evidence.spearman_location.csv'.replace('evidence.','evidence/'))
 add('spearman_location','Spearman trong từng địa điểm',['Địa điểm','Cặp biến','Hệ số ρ'],[[x.location,x.pair,vn(x.rho,4)] for x in d.itertuples()],[4.3,7,5.8],'outputs/report_evidence/spearman_location.csv; hệ số mô tả, không kèm kiểm định nhân quả hoặc p-value iid.')
 d=csv('outputs/real/regional_metrics.csv');d=d[d.model.isin(['R3','Persistence','Climatology_anomaly'])]
 add('regional_models','So sánh nhiệt độ theo địa điểm trên Test 2025',['Địa điểm','Mô hình','MAE °C','RMSE °C','R²'],[[x.location,x.model,vn(x.MAE,4),vn(x.RMSE,4),vn(x.R2,4)] for x in d.itertuples()],[2.7,5.6,2.9,2.9,3],'outputs/real/regional_metrics.csv; 365 ngày mục tiêu ở mỗi địa điểm.')
 d=csv('outputs/report_evidence/rain_confusion.csv')
 add('rain_confusion','Đếm đúng sai của phân lớp mưa trên Test',['Phạm vi','n','TP','FP','FN','TN','F1 %'],[[x.location,vn(x.n),str(x.TP),str(x.FP),str(x.FN),str(x.TN),vn(x.F1*100,2)] for x in d.itertuples()],[3.3,2.3,2,2,2,2,3.5],'outputs/report_evidence/rain_confusion.csv; nhãn là precipitation_sum ≥1 mm, ngưỡng xác suất 0,45.')
 d=csv('outputs/report_evidence/calibration.csv')
 add('calibration','Đối chiếu xác suất dự báo và tần suất mưa',['Khoảng xác suất','n','Xác suất TB','Tần suất thực nghiệm'],[[f'{vn(x.bin_left,1)}–{vn(x.bin_right,1)}',str(x.n),vn(x.prob_mean,4),vn(x.observed_rate,4)] for x in d.itertuples()],[4.6,2.7,4.9,4.9],'outputs/report_evidence/calibration.csv; khoảng trái đóng phải mở, riêng khoảng cuối gồm 1; chẩn đoán hậu nghiệm, chưa hiệu chỉnh xác suất.')
 d=csv('outputs/report_evidence/largest_errors.csv')
 add('largest_errors','Sáu sai số tuyệt đối lớn nhất của R3',['Địa điểm','Ngày mục tiêu','ERA5 °C','R3 °C','Quán tính °C','R3 − ERA5 °C'],[[x.location,x.target_date[:10],vn(x.target_temp,2),vn(x.R3,2),vn(x.Persistence,2),vn(x.error,2)] for x in d.itertuples()],[2.5,3.4,2.4,2.4,3.2,3.2],'outputs/report_evidence/largest_errors.csv; chọn sau đánh giá để mô tả lỗi, không dùng lại để chỉnh mô hình.')
 d=csv('outputs/report_evidence/event_window.csv')
 add('event_window','Cửa sổ dữ liệu Hà Nội đầu tháng 9 năm 2024',['Ngày','T TB °C','Áp suất hPa','Giáng thủy mm','Gió TB m/s'],[[x.date[:10],vn(x.temp,1),vn(x.pressure,1),vn(x.rain,1),vn(x.wind,2)] for x in d.itertuples()],[3.5,3,3.5,3.5,3.6],'outputs/report_evidence/event_window.csv; ô ERA5 21,00°B / 105,75°Đ, UTC+7. Năm 2024 thuộc Validation, không phải ca Test 2025.')
 d=csv('outputs/report_evidence/hydrology_quantiles.csv')
 add('hydrology_quantiles','Phân vị lưu lượng mô hình và số ngày bằng không',['Ô gần','n','Ngày Q=0','Q1','Trung vị','Q3','P95'],[[x.location,vn(x.n),str(x.zero_n),*[vn(v,2) for v in [x.q1,x.median,x.q3,x.p95]]] for x in d.itertuples()],[2.7,1.9,2.1,2.4,2.7,2.7,2.6],'outputs/report_evidence/hydrology_quantiles.csv; đơn vị m³/s, 2017–2021 UTC.','GLOFAS')
 d=csv('outputs/hydrology/monthly.csv').pivot(index='month',columns='location',values='river_discharge_m3s')
 add('hydrology_monthly_table','Trung vị lưu lượng theo tháng trong chuỗi mô hình',['Tháng','Hà Nội','Đà Nẵng','TP.HCM'],[[str(m),*[vn(row[l],2) for l in ['Ha_Noi','Da_Nang','TP_HCM']]] for m,row in d.iterrows()],[2.1,5,5,5],'outputs/hydrology/monthly.csv; trung vị của các ngày cùng tháng trong 5 năm, m³/s.','GLOFAS')
 d=csv('outputs/report_evidence/sql_era5_totals.csv')
 add('sql_totals','Kết quả truy vấn kiểm tra dữ liệu ERA5 trong SQLite',['Địa điểm','Số dòng','Tổng giáng thủy 9 năm mm'],[[x.location,vn(x.n),vn(x.rain_sum_mm,1)] for x in d.itertuples()],[4.8,4.1,8.2],'outputs/report_evidence/sql_queries.sql và sql_era5_totals.csv; không diễn giải tổng 9 năm thành mưa một năm.','HỆ THỐNG')
 add('reproducibility_levels','Các mức bằng chứng và điều đã kiểm chứng',['Mức','Đã kiểm chứng','Giới hạn'],[
 ['Toàn vẹn tệp','JSON khớp SHA-256 trong hồ sơ','Hash không chứng minh giá trị đo chính xác'],['Tái lập số học','Chạy lại pipeline, đối chiếu dữ liệu và chỉ số','Giới hạn môi trường thư viện và đầu vào ghim'],['Kiểm thử phần mềm','Unit test, SQL và audit báo cáo','Không thay thế đánh giá ngoài mẫu'],['Đánh giá hồi cứu','Test 2025, baseline, CI khối tháng','Chưa có nhiều năm Test độc lập'],['Kiểm chứng thực địa','Chưa thực hiện','Không có trạm đo/lưu vực độc lập'],['Vận hành trên máy nhóm','Cần nhóm chạy khi bàn giao','Không tự nhận đã chạy Windows hoặc kiểm tra người dùng']],[3.5,6.1,7.5],'Nhật ký thực thi, tests và phạm vi thực nghiệm trong kho mã.','HỆ THỐNG')
 return t

def figures():
 fs=base.figures()
 labels={
 'monthly_rain':('Biến thiên tháng của lượng giáng thủy và tỷ lệ ngày mưa','monthly_weather.csv','Trung bình trên tất cả ngày của tháng, không phải tổng mưa một tháng.'),
 'location_distributions':('Phân bố nhiệt độ, độ ẩm và giáng thủy theo địa điểm','location_profile.csv; outputs/real/clean.csv','Boxplot ẩn điểm ngoài râu để dễ đọc; không loại các giá trị này khỏi phân tích.'),
 'rain_calibration':('Xác suất dự báo mưa và tần suất thực nghiệm','calibration.csv','Test 2025; kích thước các khoảng khác nhau. Đường chéo là tham chiếu, không phải kết quả hiệu chỉnh.'),
 'monthly_errors':('Sai số R3 theo từng tháng của Test 2025','monthly_errors.csv','Sai số có dấu bằng R3 trừ ERA5; mô tả hậu nghiệm, không chọn lại mô hình.'),
 'error_ecdf':('Phân phối tích lũy sai số tuyệt đối của R3','outputs/real/predictions.csv','Đường tính từ 365 ngày mỗi địa điểm; chưa phải khoảng tin cậy.'),
 'event_window':('Cửa sổ giáng thủy và áp suất Hà Nội tháng 9 năm 2024','event_window.csv','Chỉ minh họa kiểm tra dữ liệu, không phải chứng minh dự báo được bão.'),
 'flow_duration':('Đường tần suất vượt lưu lượng của chuỗi GloFAS','outputs/hydrology/daily.csv','Thứ hạng thực nghiệm m/(n+1); không phải chu kỳ lặp của lũ, không dùng làm ngưỡng cảnh báo.')}
 for k,(title,src,note) in labels.items():
  label='GLOFAS' if k=='flow_duration' else 'ERA5'
  fs[k]=dict(caption=f'[{label}] {title}',path=f'outputs/report_evidence/charts/{k}.png',prefix=f'Nguồn: {src if src.startswith("outputs/") else "outputs/report_evidence/"+src}. ',note=note)
 return fs

def write_source():
 base.draw_architecture()
 s=(ROOT/'docs/report_src/expanded_template.md').read_text()
 n=js('outputs/python_test_results.json')['tests_run']
 s=s.replace('{{TESTS}}',str(n))
 (ROOT/'docs/report_src/noi_dung.md').write_text(s)
 base.write_support_docs(s)
 # Additional reviewer-facing handoff is distinct from unperformed human validation.
 write_handoff()

 return s

def write_handoff():
 text="""# Việc nhóm cần tự xác nhận trước khi nộp

## Cần làm

1. Xác nhận tên giảng viên, tên và MSSV thành viên trên bìa. Các thông tin đang giữ từ bộ nộp; chưa đối chiếu hệ thống đào tạo.
2. Đối chiếu yêu cầu chính thức của thầy về cấu trúc, định dạng và cách đếm trang. Báo cáo triển khai đúng tên đề tài đã cung cấp, nhưng chưa có barem/phiếu giao bài đầy đủ để cam kết khớp từng mục.
3. Trên máy dùng bảo vệ, cài requirements, chạy `python scripts/run_project.py --skip-download`, sau đó mở `outputs/real/DASHBOARD.html`. Nếu muốn minh chứng môi trường, chụp một ảnh terminal hiện kết quả kết thúc và một ảnh dashboard ERA5. Báo cáo hiện không cần các ảnh này để đủ số trang và chưa nói đã chạy trên máy Windows của nhóm.
4. Mỗi người tự đọc và chạy phần mình nhận trình bày. Chưa xác minh lịch sử phân công hay đóng góp; không ghi tỷ lệ phần trăm đóng góp chỉ từ đề xuất chia phần.

## Chỉ cần nếu muốn bổ sung một kết quả mới

- Kiểm tra thủ công: chạy `python tools/manual_audit.py sample`, hai người tự điền nhãn độc lập trong hai bản CSV; cần tra manual_audit_context.csv đã bỏ nhãn nguồn để nhận biết dòng trùng. Không xem `_pipeline_decisions.csv` khi gán nhãn. Chạy `score --labels ...` sau khi điền đầy đủ. Hiện chưa có kết quả người kiểm tra và chưa công bố tỷ lệ đồng thuận.
- Chứng minh dữ liệu trạm: cần chuỗi đo độc lập cùng thời kỳ và giấy phép/nguồn rõ. Mốc QCVN chỉ là bối cảnh, không thay chuỗi trạm.
- Diễn giải thủy văn theo sông cụ thể: cần xác minh ô sông/lưu vực/diện tích thượng lưu. Chưa gán tên sông hoặc kết luận sông khô từ giá trị GloFAS bằng 0.
- Nếu muốn ghi có mã sinh benchmark: phải cung cấp mã gốc cùng seed và tham số; chưa có, nên báo cáo chỉ cam kết tái lập từ JSON ghim.

## Những điều đã làm bằng máy tính

Đã tải lại trực tiếp GloFAS consolidated_v4 và giữ phản hồi API, URL, thời gian tải, SHA-256; kiểm số ngày, đơn vị; phát lại ERA5, benchmark và SQLite; tính chẩn đoán sai số từ predictions.csv; chạy kiểm thử và đối soát báo cáo. Chi tiết số test và chỉ số lấy từ nhật ký/JSON kèm bộ nộp. Hình trong báo cáo là biểu đồ dữ liệu, không phải ảnh chụp màn hình giả.
"""
 (ROOT/'docs/VIEC_NHOM_CAN_XAC_NHAN.md').write_text(text)
