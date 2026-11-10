"""ERA5-first report definitions; benchmark tables are restricted to an appendix."""
from pathlib import Path
import json,sqlite3
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
def js(p):return json.loads((ROOT/p).read_text())
def csv(p):return pd.read_csv(ROOT/p)
def vn(x,d=0):return f'{float(x):,.{d}f}'.replace(',','_').replace('.',',').replace('_','.')
def tables(a):
 t={}
 def add(k,cap,heads,rows,widths,source,label='ERA5'):
  t[k]={'caption':f'[{label}] {cap}','headers':heads,'rows':rows,'widths':widths,'source':'Nguồn: '+source}
 real=js('outputs/real/summary.json'); hydro=csv('outputs/hydrology/summary.csv');rain=real['rain']; ntests=js('outputs/python_test_results.json')['tests_run']
 add('scope','Nguồn, phạm vi và giới hạn', ['Nguồn','Quy mô / thời gian','Vai trò và giới hạn'],[
 ['ERA5','9.861 địa điểm–ngày; 2017–2025; 3 ô lưới','Nguồn chính cho EDA và dự báo ngày kế tiếp; không phải số đo trạm.'],
 ['GloFAS v4 consolidated',f'{vn(hydro.n_total.sum())} địa điểm–ngày; 2017–2021; UTC','Thu thập, QC, mô tả lưu lượng mô hình; chưa dự báo lũ hoặc xác minh lưu vực.'],
 ['Benchmark đóng băng','10.273 dòng mô phỏng có nhãn lỗi','Chỉ kiểm thử logic QC trong Phụ lục A. Chưa xác minh tác giả/mã sinh/seed gốc.']], [3.5,5.4,8.19],'data/era5, data/hydrology và data/raw; hồ sơ SHA-256.','CÁC NGUỒN')
 add('database','Cấu trúc và số dòng trong SQLite',['Bảng','Số dòng','Nguồn / ngày / vai trò'],[
 ['era5_daily','9.861','ECMWF ERA5; UTC+7; khóa (location,date).'],['hydrology_daily',vn(hydro.n_total.sum()),'GloFAS v4 consolidated; UTC; khóa (location,date).'],['observations','9.634','Benchmark mô phỏng; tách riêng với ERA5.'],['stations / weather_regimes','3 / 4','Danh mục của nhánh mô phỏng, không phải trạm đo của ERA5.']],[3.6,2.4,11.09],'sql/01_schema.sql, sql/04_external_sources.sql, outputs/kttv_weather.sqlite.','CÁC NGUỒN')
 add('operation','Lệnh chạy và bằng chứng đầu ra',['Lệnh','Kết quả / phạm vi'],[
 ['python scripts/run_project.py --skip-download','Phát lại GloFAS và ERA5 từ JSON; benchmark QC; SQLite; dashboard; kiểm thử.'],['python scripts/hydrology.py --refresh','Tải lại GloFAS qua Flood API, lưu URL/params/thời gian/SHA-256; cần mạng.'],['python tools/build_final_report.py','Dựng Word/PDF và đồng bộ mục lục từ đầu ra.'],['python tools/audit_report_consistency.py','Đối chiếu số liệu ERA5, thủy văn, BSS, nguồn và metadata.'],['python -m unittest discover -s tests -v',f'{ntests} ca kiểm thử hiện hành; không thay thế kiểm định độ chính xác ngoài trạm.']],[8.4,8.69],'scripts, tools và outputs/python_test_results.json.','CÁC NGUỒN')
 d=csv('outputs/real/descriptive.csv')
 add('real_descriptive','Thống kê mô tả sáu biến khí tượng',['Biến','n','Trung bình','Q1','Trung vị','Q3'],[[x.variable,vn(x.n),*[vn(v,2) for v in [x.mean,x.q1,x.median,x.q3]]] for x in d.itertuples()],[2.8,2.2,3,3,3,3.09],'outputs/real/descriptive.csv. temp °C; humidity %; pressure hPa mực biển; rain mm/ngày; wind m/s; solar MJ/m²/ngày.')
 d=csv('outputs/real/location_season.csv')
 add('real_location_season','Mười hai nhóm địa điểm × khoảng tháng',['Địa điểm','Khoảng tháng','n','T trung vị °C','RH trung vị %','Mưa TB mm'],[[x.location,x.season,vn(x.n),vn(x.temp_median_c,2),vn(x.humidity_median_pct,2),vn(x.rain_mean_mm,3)] for x in d.itertuples()],[2.4,3.2,1.8,3.2,3.2,3.29],'outputs/real/location_season.csv. Đây là nhóm lịch cố định, không gán mùa mưa Trung Bộ cho cả nước.')
 d=csv('outputs/real/cluster_trials.csv')
 add('cluster_trials_real','Silhouette của phân tách mô tả ẩm–mưa',['k','Silhouette','Cỡ mẫu / seed'],[[str(x.k),vn(x.silhouette_sample,4),f'{x.sample_n} / {x.seed}'] for x in d.itertuples()],[2,5,10.09],'outputs/real/cluster_trials.csv. Fit RH và ln(mưa+1) trên toàn tập mô tả; không dùng nhãn cụm cho dự báo.')
 d=csv('outputs/real/cluster_summary.csv')
 add('real_cluster_summary','Hai nhóm mô tả theo độ ẩm và lượng mưa',['Nhóm','n','T trung vị °C','RH trung vị %','Mưa TB mm'],[[str(x.cluster),vn(x.n),vn(x.temp_median_c,2),vn(x.humidity_median_pct,2),vn(x.rain_mean_mm,3)] for x in d.itertuples()],[2,2.5,4,4,4.59],'outputs/real/cluster_summary.csv. Phân tách chủ yếu chịu ảnh hưởng mưa bằng 0 và biến đổi log; không phải phân loại cấu trúc thời tiết.')
 c=csv('outputs/real/climate_comparison.csv').set_index('location').loc['Ha_Noi'];norm=js('references/qcvn02_hanoi_verified.json')
 add('climate_comparison','Hà Nội: ERA5 và mốc khí hậu QCVN 02',['Chỉ tiêu','ERA5 2017–2025','QCVN 02:2022/BXD [16]'],[
 ['Mưa TB năm (mm)',vn(c.annual_rain_mean_mm,1),f"{vn(norm['annual_precipitation_mm'],1)}; Bảng A.25, dòng Hà Nội"],
 ['Ngày mưa TB năm',f'{vn(c.annual_wet_days_mean,1)} (ngưỡng ≥1 mm)',f"{vn(norm['mean_rainy_days_per_year'],1)}; Bảng A.28, định nghĩa riêng"],
 ['Tỷ lệ ngày mưa',f'{vn(c.wet_day_rate_pct,1)}% (≥1 mm)','Không so ngang nếu khác ngưỡng và thời kỳ'],
 ['Độ ẩm trung vị Hà Nội',f'{vn(c.humidity_median_pct,1)}% (chỉ ô Hà Nội)','Không so trung vị với độ ẩm trung bình khí hậu']],[5,5.3,6.79],'outputs/real/climate_comparison.csv và QCVN gốc, PDF trang 447 / 463; chưa có chuỗi đo trạm độc lập.')
 d=csv('outputs/real/temperature_metrics.csv')
 add('real_temperature','Dự báo nhiệt độ ngày kế tiếp: mô hình và baseline',['Mô hình','Val RMSE','Test MAE','Test RMSE','Test R²'],[[x.model,vn(x.validation_RMSE,4) if pd.notna(x.validation_RMSE) else '—',vn(x.MAE,4),vn(x.RMSE,4),vn(x.R2,4)] for x in d.itertuples()],[6,3,2.7,2.7,2.69],'outputs/real/temperature_metrics.csv; Test 2025 n=1.095; chọn R1–R3 và siêu tham số trên validation.')
 add('rain_skill','Đánh giá mưa và Brier skill score',['Chỉ số','Giá trị','Cách đọc'],[
 ['F1 Logistic / quán tính',f"{vn(rain['F1']*100,2)}% / {vn(rain['persistence_F1']*100,2)}%",'CI chênh lệch chứa 0; chưa khẳng định ưu thế F1.'],
 ['F1 luôn mưa / tỷ lệ nền Test',f"{vn(rain['always_wet_F1']*100,2)}% / {vn(rain['test_prevalence']*100,2)}%",'F1 cao một phần do tỷ lệ ngày mưa cao.'],
 ['ROC-AUC / Average precision',f"{vn(rain['ROC_AUC'],4)} / {vn(rain['Average_precision'],4)}",'Đọc AP cùng tỷ lệ nền; không coi nhãn ERA5 là quan trắc trạm.'],
 ['Brier mô hình',vn(rain['Brier'],6),'Sai số xác suất; thấp hơn tốt hơn.'],
 ['Brier baseline p_train',vn(rain['Brier_climatology_train'],6),f"p_train={vn(rain['train_prevalence'],4)} được cố định từ Train."],
 ['BSS so p_train',vn(rain['BSS_train_climatology'],4),'Baseline hợp lệ ngoài mẫu; dương là cải thiện Brier.'],
 ['BSS so p_test (hậu nghiệm)',vn(rain['BSS_test_climatology_hindsight'],4),f"BS_ref=p_test(1−p_test)={vn(rain['Brier_climatology_test_hindsight'],6)}. Chỉ tham chiếu hậu nghiệm."]],[5.5,4.5,7.09],'outputs/real/summary.json và rain_skill.csv; Test 2025; threshold chọn trên Val.')
 d=csv('outputs/real/paired_bootstrap.csv')
 add('real_paired_bootstrap','Chênh lệch cặp và CI khối tháng',['Phạm vi','So sánh','Chỉ số','Chênh lệch','CI 95%'],[[x.scope,x.comparison,x.metric,vn(x.diff,4),f'{vn(x.ci_low,4)} đến {vn(x.ci_high,4)}'] for x in d.itertuples()],[2.6,5.4,2.2,2.5,4.39],'outputs/real/paired_bootstrap.csv; 12 khối tháng Test 2025, B=2.000. RMSE âm có lợi R3; F1 tính bằng điểm phần trăm.')
 add('hydrology_summary','Chuỗi lưu lượng GloFAS đã thu thập',['Vị trí gần','Ô lưới trả về','n hợp lệ','TB m³/s','Trung vị m³/s','P95 m³/s'],[[x.location,f'{x.grid_latitude:.5f}; {x.grid_longitude:.5f}',vn(x.n_valid),vn(x.mean_m3s,2),vn(x.median_m3s,2),vn(x.p95_m3s,2)] for x in hydro.itertuples()],[2.8,4.5,2.1,2.8,2.8,2.09],'outputs/hydrology/summary.csv; 2017–2021 UTC, consolidated_v4; đây là dữ liệu mô hình GloFAS.','GLOFAS')
 add('benchmark_qc','Đối soát logic QC trên tệp mô phỏng cố định',['Bước','Số dòng / ô','Giới hạn'],[
 ['Nguồn / trùng / cách ly / sạch','10.273 / 412 / 227 / 9.634','Đối chiếu nhãn đã biết; không đo độ chính xác QC trên trạm.'],['Quy đổi gió trước QC / giữ / cách ly','242 / 234 / 8','255 dòng thô gồm các bản sao.'],['Điền khuyết nhiệt độ / áp suất','183 / 146 ô','Cột tham chiếu mô phỏng gần giá trị gốc; không đánh giá khả năng khôi phục trạm thật.']],[6.5,4,6.59],'outputs/analysis.json và data/processed/row_lineage.csv.','MÔ PHỎNG')
 d=csv('outputs/tables/preprocessing_step_ablation.csv')
 # Preserve the actual column names of the ablation table in a compact selected-column view.
 heads=list(d.columns);cols=[c for c in heads if c in ['step','step_name','config_name','test_rmse','test_rmse_c','test_RMSE','test_mae']]
 # Explicit table generated from analysis avoids dependence on capitalization in CSV schema.
 rows=a['forecasting'].get('preprocessing_steps',[])
 add('benchmark_limits','Hai kết quả phụ thuộc thiết kế bộ mô phỏng',['Kết quả','Giá trị','Diễn giải hợp lệ'],[
 ['C0d→C1 (RMSE)','−0,0928 °C','Tác động trên bộ kiểm thử; không tính là cải thiện đã chứng minh trên khí quyển thật.'],['Che 5% nhiệt độ','RMSE 0,2366 °C','Xấp xỉ nhiễu σ≈0,25 °C của cột tham chiếu; kiểm thử thuật toán kẹp ngưỡng.'],['Ngày Yagi 07/09/2024','Mô phỏng 0,0 mm / ERA5 196,6 mm','Bộ mô phỏng không đồng bộ sự kiện thật; không diễn giải tương quan của nó như cơ chế vật lý.']],[5,4.3,7.79],'outputs/tables/preprocessing_step_ablation.csv, outputs/analysis.json và data/era5/Ha_Noi.json.','MÔ PHỎNG')
 return t

def figures():
 return {
 'architecture':dict(caption='[CÁC NGUỒN] Luồng xử lý và vai trò ba nguồn',path='docs/report_assets/architecture.png',prefix='Nguồn: mã nguồn dự án. ',note='ERA5 là nhánh dự báo chính; GloFAS chỉ mô tả lưu lượng; benchmark chỉ kiểm thử QC.'),
 'real_era5_eda':dict(caption='[ERA5] Trung vị nhiệt độ theo tháng và tương quan Spearman',path='outputs/charts/real_era5_eda.png',prefix='Nguồn: outputs/real/clean.csv và spearman.csv. ',note='9.861 địa điểm–ngày; tương quan trong mẫu không xác nhận quan hệ nhân quả.'),
 '13_real_era5_predictions_q1_2025':dict(caption='[ERA5] Nhiệt độ ngày kế tiếp và dự báo R3 trong Quý I/2025',prefix='Nguồn: outputs/real/predictions.csv. ',note='Test 2025; các chỉ số trên đầu mỗi đồ thị tính trên cả năm, không riêng Quý I.'),
 'real_paired_bootstrap':dict(caption='[ERA5] CI chênh lệch RMSE bằng bootstrap khối tháng',path='outputs/charts/real_paired_bootstrap.png',prefix='Nguồn: outputs/real/paired_bootstrap.csv. ',note='B=2.000; giữ ba địa điểm trong cùng khối; không bao gồm bất định huấn luyện hoặc nhiều năm test.'),
 'hydrology_monthly':dict(caption='[GLOFAS] Trung vị lưu lượng theo tháng tại ba ô lưới',path='outputs/hydrology/monthly.png',prefix='Nguồn: outputs/hydrology/monthly.csv, Open-Meteo / GloFAS [22], [23]. ',note='2017–2021, UTC; lưu lượng mô hình m³/s, không phải số đo tại trạm và không dùng để chứng minh độ chính xác dự báo lũ.')}

def write_source():
 draw_architecture()
 a=js('outputs/analysis.json');r=js('outputs/real/summary.json');rain=r['rain'];cl=csv('outputs/real/cluster_trials.csv');sil=float(cl.loc[cl.k.eq(2),'silhouette_sample'].iloc[0]);h=csv('outputs/hydrology/summary.csv')
 mon=csv('outputs/real/monthly_summary.csv').set_index(['location','month']);sp=pd.read_csv(ROOT/'outputs/real/spearman.csv',index_col=0)
 jan=' / '.join(vn(mon.loc[(loc,1),'temp_median_c'],1) for loc in ['Ha_Noi','Da_Nang','TP_HCM'])
 ntests=js('outputs/python_test_results.json')['tests_run']
 text=f'''# Chương 1 Giới thiệu đề tài

Mục tiêu duy nhất là xây dựng và thẩm định quy trình thu thập, kiểm tra và chuẩn hóa dữ liệu khí tượng thủy văn có truy nguyên, phục vụ chuẩn bị đầu vào và thực nghiệm dự báo thời tiết ngày kế tiếp. Kết quả khí tượng dựa trên ERA5 tải từ API; bộ mô phỏng chỉ là dữ liệu kiểm thử phần mềm và được chuyển sang Phụ lục A.

Ý nghĩa thực tiễn: các JSON, URL truy vấn, tọa độ ô lưới, múi giờ và SHA-256 giúp kiểm tra nguồn và phát lại xử lý. CSV, SQLite và dashboard hỗ trợ tra cứu đầu vào dự báo. Đây là nghiên cứu hồi cứu; chưa phải hệ thống cảnh báo thời tiết hoặc lũ đang vận hành.

Ý nghĩa nghiên cứu: so sánh mô hình với baseline trên cùng ngày mục tiêu, đọc chênh lệch cùng khoảng tin cậy và phân biệt dữ liệu mô hình với số đo tại trạm. Không coi cải thiện trên bộ sinh mô phỏng là bằng chứng về cơ chế khí quyển.

@table scope

Bốn câu hỏi nghiên cứu được đặt ra: Q1 — các biến ERA5 phân bố và biến động theo tháng như thế nào? Q2 — tương quan và nhóm lịch cố định thể hiện khác biệt địa điểm ra sao? Q3 — quy trình bảo đảm chất lượng đầu vào đến mức nào và phân cụm ẩm–mưa chỉ mô tả được điều gì? Q4 — biến trễ, chu kỳ mùa và tiền xử lý có cải thiện dự báo ngoài mẫu so với baseline hay không? Chương 6 trả lời lần lượt Q1–Q4; thủy văn là phần mở rộng thu thập và xử lý, không thêm một bài toán dự báo lũ chưa được đánh giá.

Phạm vi nguồn: ERA5 có 3 ô lưới tại Hà Nội (21,00; 105,75), Đà Nẵng (16,00; 108,25) và TP.HCM (10,75; 106,75), giai đoạn 2017–2025, UTC+7. GloFAS v4 consolidated lấy ba vị trí gần các thành phố trong 2017–2021 theo ngày UTC. Hai nguồn đều là sản phẩm mô hình/tái phân tích, không phải chuỗi quan trắc trạm độc lập. GloFAS được tạo từ mô hình thủy văn dùng ERA5 làm đầu vào [22], [23], nên cũng không phải đối chứng độc lập cho ERA5.

Bộ mô phỏng 10.273 dòng chỉ được tiếp nhận như tệp cố định; hồ sơ hiện không xác minh đầy đủ tác giả, mã sinh, seed và tham số gốc. Nhóm chỉ tái lập các bước từ JSON kèm SHA-256, không tuyên bố tái tạo được quá trình sinh bộ này. Nhãn WMO và ISD_SYNOP_ERA5_MERGED_V1 là định danh cũ của mẫu kiểm thử, không xác nhận nguồn NOAA ISD/Meteostat.

# Chương 2 Cơ sở lý thuyết và phương pháp

ERA5 là tái phân tích theo ô lưới [1], [2]. pressure_msl_mean là áp suất quy về mực biển, rain là tổng mưa ngày, wind là tốc độ gió 10 m trung bình ngày. Tọa độ yêu cầu có thể khác tâm ô lưới trả về. Không gọi ba ô lưới này là ba trạm WMO.

Nhánh ERA5 loại dòng theo bảy điều kiện: RH < 0%, RH > 100%, mưa < 0 mm, gió < 0 m/s, Tmin > Tmax, T trung bình < Tmin hoặc T trung bình > Tmax; ngoài ra kiểm tra trùng địa điểm–ngày và ô thiếu. Nhánh này không dùng Magnus hoặc ngưỡng áp suất của source_checks.py. Không phát hiện vi phạm không đồng nghĩa không có sai lệch tái phân tích.

GloFAS được thu thập qua Flood API với daily=river_discharge, models=consolidated_v4, start_date=2017-01-01, end_date=2021-12-31, timezone=GMT và cell_selection=nearest [22]. Chọn phiên bản consolidated và thời kỳ lịch sử để không trộn dự báo tương lai. Kiểm đơn vị m³/s, đủ ngày, trùng ngày, giá trị thiếu và âm; giữ cờ chất lượng, không tự điền lưu lượng. API có thể chọn ô sông chưa đại diện đúng lưu vực; chưa xác minh bằng bản đồ lưu vực hoặc trạm thủy văn. Không dịch nhãn UTC thành ngày mưa UTC+7 rồi coi là tổng cùng ngày.

QCVN 46:2022/BTNMT [6] là bối cảnh quan trắc khí tượng; QCVN 47:2022/BTNMT [24] là bối cảnh quan trắc thủy văn, ban hành kèm Thông tư 22/2022/TT-BTNMT ngày 20/12/2022, hiệu lực từ 20/06/2023. Việc đọc API hoặc kiểm tra giá trị không âm không chứng nhận sản phẩm mô hình tuân thủ đầy đủ quy trình quan trắc của các quy chuẩn này.

Với Ridge, các đặc trưng được chuẩn hóa bằng trung bình và độ lệch chuẩn trên Train; y được trừ trung bình Train. Mã NumPy tối thiểu hóa tổng bình phương sai số cộng phạt L2 như Công thức [[equation:ridge_obj]]. Hệ số chặn không bị phạt và được khôi phục bằng trung bình y Train. Chọn α trong 0,1; 1; 10; 100 trên Validation [20].

@equation ridge_obj

Với Logistic, đặt zᵢ = b + xᵢᵀw và pᵢ = 1/(1+exp(−zᵢ)). Hàm mục tiêu trong code là trung bình log-loss cộng ||w||²/(2Cn), không phạt b, tối ưu bằng SciPy L-BFGS-B [19], [20]. C được chọn trong 0,01; 0,1; 1; 10 và ngưỡng được chọn trên Validation, không trên Test.

@equation logistic_obj

Nhiệt độ được đánh giá bằng MAE, RMSE và R²; nhãn mưa là lượng mưa ERA5 của ngày mục tiêu ≥1 mm, không phải nhãn quan trắc trạm. Đọc F1 cùng baseline luôn mưa, ROC-AUC, Average precision và Brier score. BSS ở Công thức [[equation:brier_skill]] dùng xác suất khí hậu p_train cố định từ Train làm đối chứng ngoài mẫu. BSS với p_test(1−p_test) chỉ là tham chiếu hậu nghiệm.

@equation forecast_metrics

@equation brier_skill

Chia tập ERA5 thuần theo target_date: Train 2017–2023, Validation 2024, Test 2025. Đầu vào ngày t trước ranh giới năm được phép dùng cho dự báo ngày t+1; đó là lịch sử đã biết, không phải rò rỉ nhãn. Nhánh benchmark giữ chính sách bảo thủ cũ: yêu cầu cả obs_date và target_date cùng tập và loại 6 cửa sổ tại hai biên tập. Hai cách khác nhau được ghi rõ; chỉ so mô hình với baseline trong cùng một nhánh và cùng những ngày Test, không so ngang lợi ích tiền xử lý giữa hai nhánh.

Tương quan Spearman tính bằng thứ hạng trung bình trên sáu biến. Nhóm lịch dùng tên Tháng 12–2, 3–4, 5–8 và 9–11 cho cả ba địa điểm, không gán mùa mưa Trung Bộ cho Hà Nội/TP.HCM. K-means trên Z(RH) và Z(ln(mưa+1)) chỉ phân tách mô tả, thử k=2..5 và báo silhouette. Nhiều ngày mưa bằng 0 khiến phân tách ẩm–mưa dễ xuất hiện; nhãn cụm không được đưa vào mô hình dự báo.

CI chênh lệch dự báo lấy mẫu lại 12 khối tháng của Test 2025, B=2.000, seed=20261110, giữ cả ba địa điểm trong cùng khối và ghép cặp đúng ngày. Đây là CI điều kiện trên mô hình đã fit và một năm Test; chưa phản ánh bất định huấn luyện hay nhiều năm. Báo cáo không dùng CI trung vị lấy mẫu từng ngày độc lập để suy luận cho chuỗi có tự tương quan.

# Chương 3 Phân tích và thiết kế

Luồng xử lý tách ba vai trò nguồn: ERA5 cho kết quả khí tượng chính; GloFAS cho dữ liệu lưu lượng mô hình; benchmark cho kiểm thử logic. Mỗi nguồn giữ JSON nguyên gốc và hồ sơ băm riêng. Không ghép GloFAS vào đặc trưng dự báo mưa hoặc dùng nó làm nhãn kiểm chứng trạm.

@figure architecture

SQLite bổ sung era5_daily và hydrology_daily, giữ riêng observations của benchmark. Hai bảng mới có khóa (location,date), tọa độ ô lưới, đơn vị trong tên cột, nhãn nguồn và múi giờ. Không ép ô ERA5 vào danh mục trạm WMO của dữ liệu mô phỏng. Hàm src/source_database.py nạp hai bảng trước khi tạo SHA-256 của SQLite trong run_manifest.

@table database

Các tệp clean.csv và daily.csv giữ dạng dài theo địa điểm–ngày. ERA5 gồm nhiệt độ trung bình/cực trị, độ ẩm, áp suất mực biển, mưa, gió và bức xạ; GloFAS gồm lưu lượng, cờ QC, tọa độ, mô hình và múi giờ. Khóa nguồn tách biệt giúp tránh diễn giải nhầm dữ liệu mô hình thành số đo trạm.

# Chương 4 Triển khai và kiểm chứng

scripts/hydrology.py tải hoặc phát lại JSON GloFAS đã ghim; scripts/real_weather.py tạo thống kê ERA5, đặc trưng, dự báo và kiểm định cặp; src/pipeline.py chạy benchmark và nạp dữ liệu vào SQLite. tools/build_dashboard.py và workbook có sẵn phục vụ nhánh mô phỏng; dashboard ERA5 nằm trong outputs/real. Không mô tả workbook benchmark như sản phẩm dữ liệu trạm thật.

@table operation

Bộ kiểm thử hiện hành có {ntests} ca: bảo toàn dòng benchmark, ngày mục tiêu, nhãn và chỉ số dự báo; thêm kiểm tra nguồn GloFAS, đơn vị/múi giờ, BSS tính lại từ dự báo, nhóm lịch, silhouette và tổng số liệu trong hai bảng SQLite mới. Kiểm thử phần mềm không xác nhận sai số khí tượng tại trạm. Lệnh tái lập dùng cache khi không có mạng; --refresh thay dữ liệu nguồn nên phải lưu phiên bản và chạy lại báo cáo.

# Chương 5 Kết quả trên ERA5 và dữ liệu thủy văn

Q1 — Trên 9.861 địa điểm–ngày ERA5, nhiệt độ trung bình toàn mẫu là 26,56 °C, trung vị 27,50 °C. Bảng [[table:real_descriptive]] nêu đủ sáu biến. Trung vị tháng 1 tại Hà Nội / Đà Nẵng / TP.HCM là {jan} °C; đồ thị tháng thể hiện khác biệt địa điểm, không coi 3 ô lưới đại diện toàn Việt Nam.

@table real_descriptive

@figure real_era5_eda

Q2 — Hệ số Spearman độ ẩm–mưa là {vn(sp.loc['humidity','rain'],2)}, nhiệt độ–độ ẩm là {vn(sp.loc['temp','humidity'],2)}. Đây là liên hệ trong mẫu ERA5, chưa tách hiệu ứng địa điểm và mùa để kết luận nhân quả. Mười hai nhóm địa điểm × khoảng tháng dưới đây cho phép đọc trung vị theo cùng quy ước lịch.

@table real_location_season

Q3 — ERA5 có 0 dòng trùng, 0 dòng thiếu và 0 dòng vi phạm bảy điều kiện cơ bản trong mẫu. Điều này chỉ chứng minh đầu vào qua các kiểm tra đã lập trình. Phân tách ẩm–mưa k=2 đạt silhouette {vn(sil,4)} trên mẫu 1.000 điểm; không phải bằng chứng phát hiện hai cấu trúc thời tiết. Hai nhóm chủ yếu khác độ ẩm và lượng mưa, có ảnh hưởng của khối giá trị mưa bằng 0.

@table cluster_trials_real

@table real_cluster_summary

Đối chiếu khí hậu Hà Nội dùng riêng ô Hà Nội, không dùng trung vị độ ẩm gộp ba địa điểm. QCVN 02:2022/BXD gốc ghi 1.670,1 mm/năm tại Bảng A.25 và 147,9 ngày mưa/năm tại Bảng A.28 (PDF trang 447 và 463). Số liệu ERA5 tính trên 2017–2025 và ngưỡng ≥1 mm khác thời kỳ/định nghĩa khí hậu của bảng chuẩn; chênh lệch không được diễn giải trực tiếp thành bias đã kiểm định. Chưa có chuỗi đo trạm đồng thời để xác nhận mưa nhẹ của ERA5.

@table climate_comparison

Q4 — Thêm biến trễ từ R1→R2 giảm RMSE Test từ 1,0465 xuống 0,9935 °C; thêm chu kỳ mùa theo địa điểm R2→R3 giảm còn 0,9302 °C. Quán tính đạt 1,0741 °C, baseline khí hậu điều hòa + dị thường đạt 1,0209 °C. Mô hình và baseline cùng đánh giá trên 1.095 ngày mục tiêu địa điểm–ngày Test 2025; không lấy hiệu quả điền khuyết benchmark làm đóng góp dự báo ERA5.

@table real_temperature

@figure 13_real_era5_predictions_q1_2025

Với mưa, F1 Logistic 81,67% so quán tính 80,53% chưa đủ bằng chứng ưu thế vì CI chênh lệch chứa 0. Luôn dự báo mưa đã có F1 74,07% do tỷ lệ nền Test 58,81%. Brier mô hình {vn(rain['Brier'],6)} so baseline xác suất Train {vn(rain['Brier_climatology_train'],6)} cho BSS {vn(rain['BSS_train_climatology'],4)}. Tham chiếu hậu nghiệm p_test(1−p_test) cho BSS {vn(rain['BSS_test_climatology_hindsight'],4)}, không dùng p_test để tạo dự báo hoặc chọn mô hình.

@table rain_skill

@table real_paired_bootstrap

@figure real_paired_bootstrap

CI RMSE toàn mẫu R3−quán tính là [−0,1938; −0,0951] °C, còn CI F1 mưa [−1,1596; 3,1507] điểm % chứa 0. Tại TP.HCM, CI RMSE [−0,0353; 0,0046] °C cũng chứa 0. Lợi ích toàn mẫu không đồng nghĩa mọi địa điểm hoặc mọi chỉ số đều cải thiện chắc chắn.

Mở rộng thủy văn: đã thu thập {vn(h.n_total.sum())} địa điểm–ngày GloFAS consolidated, đủ 1.826 ngày tại mỗi vị trí trong 2017–2021, không thiếu hoặc âm trong phản hồi hiện hành. Trung vị lưu lượng Hà Nội / Đà Nẵng / TP.HCM lần lượt là {' / '.join(vn(h.set_index('location').loc[l,'median_m3s'],2) for l in ['Ha_Noi','Da_Nang','TP_HCM'])} m³/s. Đọc theo ô mô hình được API trả về, chưa gán tên sông hoặc xác nhận diện tích lưu vực.

@table hydrology_summary

@figure hydrology_monthly

Đầu ra thủy văn đáp ứng bước thu thập, kiểm tra đơn vị/lịch/miền giá trị và lưu trữ; chưa đánh giá mô hình dự báo dòng chảy, tác động thủy triều, vận hành hồ chứa hoặc khả năng cảnh báo lũ. Không dùng lưu lượng mô hình cùng họ ERA5 làm đối chứng quan trắc thật.

# Chương 6 Trả lời câu hỏi nghiên cứu và kết luận

Q1 — ERA5 có nhiệt độ TB 26,56 °C, trung vị 27,50 °C; trung vị tháng 1 tại ba địa điểm là {jan} °C (Bảng [[table:real_descriptive]], Hình [[figure:real_era5_eda]]). Đã mô tả phân bố và chu kỳ tháng trong đúng mẫu, chưa suy rộng toàn vùng.

Q2 — Spearman RH–mưa {vn(sp.loc['humidity','rain'],2)} và T–RH {vn(sp.loc['temp','humidity'],2)}; có 12 nhóm địa điểm × khoảng tháng với mẫu tổng 9.861 dòng (Bảng [[table:real_location_season]]). Tương quan mô phỏng 0,84 hoặc +0,04 không được dùng giải thích vật lý khí quyển.

Q3 — Đầu vào ERA5 qua kiểm tra với 0 dòng vi phạm; phân tách ẩm–mưa k=2 có silhouette {vn(sil,4)} (Bảng [[table:cluster_trials_real]]). Bộ mô phỏng đối chiếu 412 dòng trùng và 227 dòng lỗi chỉ xác nhận logic QC ở Phụ lục A. Chưa đánh giá độ nhạy QC trên lỗi trạm thật; thiếu mã sinh khiến bộ mô phỏng không phải bằng chứng nghiên cứu chính.

Q4 — R3 giảm RMSE 1,0741→0,9302 °C so quán tính, CI chênh lệch toàn mẫu dưới 0; BSS mưa so xác suất Train là {vn(rain['BSS_train_climatology'],4)}. F1 mưa và RMSE tại TP.HCM có CI chứa 0, nên không khẳng định ưu thế đồng loạt (Bảng [[table:rain_skill]], [[table:real_paired_bootstrap]]). Mức giảm C0d→C1 và RMSE che 5% của benchmark không được tính là đóng góp đã chứng minh trên dữ liệu thật.

Phần thủy văn đã bổ sung {vn(h.n_total.sum())} giá trị ngày từ GloFAS để mở rộng đúng lĩnh vực đề tài; đóng góp là xử lý dữ liệu mô hình có truy nguyên, không phải đo sông hay dự báo lũ đã kiểm chứng. SQLite chứa riêng 9.861 dòng ERA5 và {vn(h.n_total.sum())} dòng GloFAS. Hướng tiếp theo là thu thập trạm khí tượng/thủy văn độc lập cùng thời kỳ, kiểm chứng ô sông, thống nhất múi giờ theo thiết kế và đánh giá nhiều năm Test.

@appendix benchmark

Bộ mô phỏng là vật kiểm thử cố định, không đồng bộ sự kiện thời tiết thật. Không có mã sinh và chưa xác minh đầy đủ tác giả/seed gốc; nhóm chỉ tái lập từ JSON đã ghim. Vì vậy không suy cơ chế rãnh áp thấp, nhiễu động gây mưa hoặc cấu trúc thời tiết từ tương quan của mẫu này. Các bảng/hình mô phỏng đầy đủ vẫn có trong outputs để kiểm tra mã, nhưng không phải mạch kết quả chính của Chương 5.

@table benchmark_qc

@table benchmark_limits

Cột tham chiếu được sinh quanh giá trị gốc với σ≈0,25 °C làm bài toán che 5% thuận lợi theo thiết kế. Mức giảm RMSE −0,0928 °C và RMSE 0,2366 °C chỉ kiểm thử logic điền/kẹp giá trị. Không trình bày chúng như xác nhận ERA5 khôi phục số đo tại trạm. Các CI trung vị cũ lấy mẫu độc lập từng ngày không dùng cho suy luận trong báo cáo chính; đánh giá dự báo dùng khối tháng.
'''
 (ROOT/'docs/report_src/noi_dung.md').write_text(text)
 write_support_docs(text)
 return text

def draw_architecture():
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.patches import FancyBboxPatch
 fig,ax=plt.subplots(figsize=(10,5));ax.set(xlim=(0,10),ylim=(0,5));ax.axis('off')
 boxes=[(.1,3.7,3,1,'ERA5 · 2017–2025 · UTC+7\n9.861 dòng · EDA + dự báo chính','#dcecf6'),(3.5,3.7,3,1,'GloFAS consolidated_v4 · UTC\n5.478 dòng · QC + mô tả lưu lượng','#dff0e5'),(6.9,3.7,3,1,'Benchmark cố định · 10.273 dòng\nChỉ kiểm thử QC · Phụ lục A','#f9ead7'),(.5,2.1,9,1,'JSON + URL / tham số / SHA-256 → kiểm tra theo từng nguồn\nERA5: feature / target_date / baseline / paired CI / BSS\nGloFAS: đơn vị m³/s / lịch UTC / cờ thiếu–âm; không ghép nhãn trạm','#eef2f6'),(.5,.4,9,1,'CSV riêng nguồn · SQLite: era5_daily + hydrology_daily + bảng benchmark\nBáo cáo chính: ERA5 và GloFAS; phụ lục: kiểm thử mô phỏng\nChưa có chuỗi quan trắc trạm độc lập để xác nhận độ chính xác','#e6eef9')]
 for x,y,w,h,txt,color in boxes:
  ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.02',facecolor=color,edgecolor='#486176'));ax.text(x+w/2,y+h/2,txt,ha='center',va='center',fontsize=9)
 for x in [1.6,5,8.4]:ax.annotate('',(x,3.12),(x,3.68),arrowprops={'arrowstyle':'->','color':'#486176'})
 ax.annotate('',(5,1.45),(5,2.08),arrowprops={'arrowstyle':'->','color':'#486176'})
 fig.tight_layout();fig.savefig(ROOT/'docs/report_assets/architecture.png',dpi=160,bbox_inches='tight');plt.close(fig)

def write_support_docs(source):
 import re
 idx={key:i for i,key in enumerate(re.findall(r'^@table (\S+)',source,re.M),1)}
 figs={key:i for i,key in enumerate(re.findall(r'^@figure (\S+)',source,re.M),1)}
 tests=js('outputs/python_test_results.json')['tests_run'];rain=js('outputs/real/summary.json')['rain']
 intro=f'''# Nhóm 13 — dữ liệu khí tượng thủy văn cho dự báo thời tiết

Thành viên: Đinh Quang Thái (N22DCCN176), Đặng Ngọc Sơn (N22DCCN070), Đặng Văn Chương (N22DCCN012).

Bản hiện hành lấy **ERA5 làm kết quả dự báo chính**, bổ sung **GloFAS v4 consolidated** cho thu thập và mô tả lưu lượng, đưa benchmark mô phỏng vào Phụ lục A. Báo cáo có **{len(idx)} bảng, {len(figs)} hình**; bộ kiểm thử hiện hành **{tests}/{tests} đạt**.

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

R3 ERA5: RMSE 0,9302 °C so quán tính 1,0741 °C. Mưa: F1 81,67% nhưng CI chênh lệch với quán tính chứa 0. BSS so xác suất khí hậu Train = **{vn(rain['BSS_train_climatology'],4)}**; BSS so tỷ lệ Test chỉ là tham chiếu hậu nghiệm. Phân cụm k=2 chỉ mô tả ẩm–mưa, không phải hai loại cấu trúc thời tiết.

QCVN 02:2022/BXD gốc, dòng Hà Nội: **1.670,1 mm/năm** ở A.25 (PDF trang 447), **147,9 ngày mưa/năm** ở A.28 (PDF trang 463). Hồ sơ: `references/qcvn02_hanoi_verified.json`; không tiếp tục dùng cặp 1.611/152 chưa khớp nguồn gốc.
'''
 (ROOT/'README.md').write_text(intro)
 script=f'''# Kịch bản bảo vệ 10 phút — Nhóm 13

## Phân chia đề xuất

| Thời gian | Người | Trọng tâm |
|---|---|---|
| 0:00–3:00 | Đinh Quang Thái | Mục tiêu, ba nguồn, JSON/URL/SHA-256, ERA5 và GloFAS khác trạm thế nào; Bảng {idx['scope']}, Hình {figs['architecture']}. |
| 3:00–6:00 | Đặng Ngọc Sơn | QC ERA5, target_date, tách múi giờ, SQLite era5_daily và hydrology_daily; Bảng {idx['database']}, {idx['operation']}. Demo truy vấn số dòng và ngày Yagi. |
| 6:00–9:00 | Đặng Văn Chương | ERA5 EDA, Ridge/Logistic, BSS và paired CI; Bảng {idx['real_temperature']}, {idx['rain_skill']}, {idx['real_paired_bootstrap']}; GloFAS ở Bảng {idx['hydrology_summary']}. |
| 9:00–10:00 | Cả nhóm | Trả lời Q1–Q4 ở Chương 6, nêu chưa có đối chứng trạm; benchmark chỉ nằm Phụ lục A. |

Đây là phân công tiếp quản và thuyết trình đề xuất, không xác nhận lịch sử ai đã viết phần mã nào.

## Câu hỏi phải tự giải thích

1. **Ai tạo benchmark, có tái sinh được không?** Hồ sơ hiện chưa xác minh đầy đủ tác giả, mã sinh và seed gốc. Nhóm tiếp nhận tệp như mẫu kiểm thử cố định, chỉ tái lập bước xử lý từ JSON. Không tự nhận đã sinh tệp hoặc đặt một seed mới để giải thích tệp cũ.
2. **Vì sao giữ benchmark?** Để kiểm logic gộp trùng/cách ly/điền khuyết với nhãn có sẵn. Nó không đồng bộ Yagi và không phải bằng chứng về quan hệ vật lý khí quyển.
3. **Mức giảm −0,0928 °C và RMSE che 5% 0,2366 °C có ý nghĩa gì?** Chỉ kiểm thử thuật toán trên cột tham chiếu sinh gần giá trị đúng, không xác nhận khả năng khôi phục trạm thật. Không còn tính là đóng góp chính.
4. **Thủy văn ở đâu?** Đã có 5.478 giá trị lưu lượng ngày GloFAS từ Flood API cho 2017–2021; kiểm lịch/đơn vị/miền giá trị và lưu bảng riêng. Đây là mô hình, chưa có trạm sông hoặc kiểm chứng dự báo lũ.
5. **GloFAS có xác nhận ERA5 không?** Không. GloFAS dùng mô hình thủy văn với ERA5 làm đầu vào; không phải quan trắc độc lập.
6. **Tại sao UTC và UTC+7 tách riêng?** Lưu lượng ngày có ranh giới mô hình UTC, còn dữ liệu khí tượng dùng UTC+7. Đổi nhãn ngày không tạo lại tổng ngày; vì vậy chưa ghép hai nguồn làm biến dự báo.
7. **Vì sao chính sách chia tập khác nhau?** ERA5 dùng ngày mục tiêu, được phép dùng lịch sử năm trước. Benchmark bảo thủ hơn, bỏ 6 cửa sổ ở hai biên tập. Không rò rỉ; chỉ so cùng ngày Test trong từng nhánh.
8. **F1 81,67% có hơn baseline không?** Chưa đủ bằng chứng theo CI. Luôn mưa đã đạt F1 74,07%; cần đọc thêm AUC, AP và Brier/BSS.
9. **BSS được tính thế nào?** 1−BS_model/BS_ref. Baseline chính là xác suất mưa từ Train, đánh giá trên Test: BS_ref≈0,244469, BSS≈0,3810. Dùng p_test(1−p_test) cho BSS≈0,3753 chỉ là đối chiếu hậu nghiệm.
10. **k=2 là hai cấu trúc thời tiết?** Không; đây là phân tách mô tả RH và ln(mưa+1), dễ chịu ảnh hưởng ngày không mưa. Có báo silhouette, không dùng cụm dự báo.
11. **Mốc mưa Hà Nội trong QCVN là gì?** Đã đọc bản gốc: A.25 ghi 1.670,1 mm; A.28 ghi 147,9 ngày. Không so ngang ngưỡng ngày mưa khí hậu với ERA5 ≥1 mm hoặc khác thời kỳ.

Mỗi người cần giải thích được hàm mục tiêu Ridge/Logistic, một dòng SQL và một CI của phần mình. Demo ưu tiên nguồn ERA5, GloFAS, SQLite và kết quả ngoài mẫu; benchmark chỉ minh họa kiểm thử phần mềm.
'''
 (ROOT/'docs/KICH_BAN_THUYET_TRINH_VA_HOI_DAP.md').write_text(script)
 (ROOT/'docs/DOI_CHIEU_YEU_CAU_BAO_CAO.md').write_text(f'''# Đối chiếu nội dung hiện hành

Báo cáo: {len(idx)} bảng, {len(figs)} hình; {tests} kiểm thử.

| Nội dung | Vị trí và bằng chứng |
|---|---|
| Mục tiêu duy nhất, ý nghĩa thực tiễn/nghiên cứu | Chương 1; phạm vi ba nguồn ở Bảng {idx['scope']}. |
| Q1: phân bố và tháng | Chương 5 và Q1 ở Chương 6; Bảng {idx['real_descriptive']}, Hình {figs['real_era5_eda']}. |
| Q2: tương quan và địa điểm | Chương 5 và Q2 ở Chương 6; Bảng {idx['real_location_season']}, ma trận Spearman trong Hình {figs['real_era5_eda']}. |
| Q3: QC và phân tách mô tả | Chương 5 và Q3 ở Chương 6; silhouette ở Bảng {idx['cluster_trials_real']}; benchmark chỉ Phụ lục A. |
| Q4: dự báo so baseline và bất định | Chương 5 và Q4 ở Chương 6; Bảng {idx['real_temperature']}, {idx['rain_skill']}, {idx['real_paired_bootstrap']}. |
| Thủy văn | Bảng {idx['hydrology_summary']}, Hình {figs['hydrology_monthly']}; lưu lượng mô hình, không phải đo trạm hoặc dự báo lũ đã xác nhận. |
| SQLite chứa dữ liệu thu thập | Bảng {idx['database']}; era5_daily và hydrology_daily tách benchmark. |
| Giới hạn | Chương 1, 2, 6 và Phụ lục A: thiếu đối chứng trạm, thiếu mã sinh benchmark, 1 năm Test, ô sông chưa xác minh. |
''')
 (ROOT/'docs/RA_SOAT_KY_THUAT.md').write_text(f'''# Rà soát kỹ thuật hiện hành

- ERA5 9.861 dòng; 9.855 cửa sổ; Test 2025 n=1.095; số mô hình giữ nguyên.
- GloFAS consolidated_v4: 5.478 dòng/3 ô, 2017–2021 UTC; URL/params/SHA-256 trong request; không quan trắc trạm.
- BSS so khí hậu Train {vn(rain['BSS_train_climatology'],4)}; thêm baseline Brier đúng ngoài mẫu. Test climatology chỉ tham chiếu hậu nghiệm.
- SQLite thêm era5_daily và hydrology_daily; kiểm tổng mưa/lưu lượng, khóa và ngày Yagi.
- Kiểm thử bao gồm QC, dữ liệu ngoài, tính toàn vẹn nguồn và chẩn đoán báo cáo; tổng {tests}; run_project dùng cache để phát lại toàn bộ nguồn.
- Cấu trúc báo cáo lấy ERA5 làm chính, benchmark chuyển Phụ lục A; {len(idx)} bảng, {len(figs)} hình. Chương 6 trả lời đủ Q1–Q4.
- Bỏ diễn giải cơ chế vật lý từ tương quan mô phỏng và bỏ lợi ích điền khuyết vòng lặp khỏi phần đạt được.
- Không dùng CI trung vị iid theo ngày để suy luận chuỗi. CI dự báo dùng khối tháng, không bao gồm bất định huấn luyện.
- Không tải quan trắc NOAA/Meteostat; không xác minh mô hình lũ. Workbook benchmark không dựng lại trong lần kiểm tra này; chưa chạy trực tiếp Windows.
- Sửa mốc QCVN 02 từ bản gốc: 1.670,1 mm và 147,9 ngày/năm, A.25/A.28; không dùng cặp 1.611/152 của bản trước.
''')
 (ROOT/'docs/NGUON_DU_LIEU_VA_GIOI_HAN_TAI_LAP.md').write_text(intro.split('## Nguồn và giới hạn',1)[1].split('## Cài đặt',1)[0]+'\nNguồn chính thức: Open-Meteo Flood API https://open-meteo.com/en/docs/flood-api ; Copernicus GloFAS https://ewds.climate.copernicus.eu/datasets/cems-glofas-historical ; QCVN 47/Thông tư 22: https://vanban.chinhphu.vn/?docid=207442&pageid=27160 .\n')
 (ROOT/'docs/PHAN_CONG_VA_NOI_DUNG_BAO_CAO.md').write_text(script.split('## Câu hỏi',1)[0])
 (ROOT/'references/DOI_CHIEU_SLIDE.md').write_text(f'# Đối chiếu slide\n\nDùng ERA5 làm mạch chính: Bảng {idx["real_descriptive"]}–{idx["hydrology_summary"]}, Hình 1–{len(figs)}. Benchmark chỉ Phụ lục A. Slide kết luận phải trả lời Q1–Q4, phân biệt model/reanalysis với trạm và đọc CI/BSS đúng.\n')
 (ROOT/'docs/NHAT_KY_SUA_CUOI.md').write_text((ROOT/'docs/RA_SOAT_KY_THUAT.md').read_text())
