# Chương 1 Giới thiệu đề tài

## 1.1 Bối cảnh và vấn đề cần giải quyết

Một hệ thống dự báo thời tiết cần dữ liệu đầu vào được hiểu đúng trước khi cần một thuật toán phức tạp. Cùng một tên biến nhiệt độ có thể chỉ giá trị tức thời, trung bình ngày hoặc cực trị ngày; cùng một ngày lịch có thể được tổng hợp theo UTC hoặc giờ địa phương. Nếu bỏ qua những khác biệt này, dữ liệu vẫn có thể đọc được bằng Python nhưng phép so sánh phía sau không còn cùng ý nghĩa. Vì vậy, trọng tâm của đề tài là nghiên cứu dữ liệu, thu thập có truy nguyên, chuẩn hóa, kiểm tra và tổ chức dữ liệu phục vụ thực nghiệm dự báo.

Đề tài xây dựng một nguyên mẫu xử lý ba nguồn có vai trò khác nhau. ERA5 là nguồn khí tượng chính cho phân tích và dự báo hồi cứu. GloFAS bổ sung chuỗi lưu lượng để thực hiện phần thu thập và xử lý dữ liệu thủy văn. Một tệp mô phỏng cố định có lỗi chèn sẵn được dùng kiểm thử logic bộ lọc. Phân biệt ba nguồn ngay từ đầu giúp tránh dùng kết quả thuận lợi trên dữ liệu nhân tạo để thay cho bằng chứng trên chuỗi khí tượng tải từ bên ngoài.

Sản phẩm của đề tài là một quy trình có thể phát lại từ JSON, các bảng CSV và SQLite có nhãn nguồn, biểu đồ, dashboard và báo cáo thực nghiệm. Mô hình dự báo đóng vai trò phép thử xem đầu vào đã chuẩn bị có mang thông tin hữu ích ngoài baseline hay không. Đây chưa phải dịch vụ dự báo trực tuyến, chưa vận hành trạm đo và chưa có đánh giá với chuỗi quan trắc độc lập cùng thời kỳ.

## 1.2 Mục tiêu duy nhất và các nhiệm vụ triển khai

Mục tiêu duy nhất là xây dựng và thẩm định quy trình thu thập, kiểm tra, xử lý và chuẩn hóa dữ liệu khí tượng thủy văn có truy nguyên, nhằm cung cấp đầu vào có thể tái lập cho hệ thống dự báo thời tiết ngày kế tiếp.

Để thực hiện mục tiêu này, quy trình gồm các bước liên hoàn: xác định phạm vi và ý nghĩa từng biến; lưu phản hồi API kèm thông tin truy vấn; kiểm tra lịch, đơn vị và tính hợp lệ; tổ chức dữ liệu sạch; tạo biến trễ đúng ngày lịch; chia tập theo thời gian; và so sánh mô hình với các baseline trên cùng ngày mục tiêu.

Hai bài toán thực nghiệm trên ERA5 là dự báo nhiệt độ trung bình ngày kế tiếp và phân lớp ngày có giáng thủy từ 1 mm trở lên. Với GloFAS, phạm vi xử lý bao gồm thu thập chuỗi lưu lượng, kiểm soát chất lượng, thống kê theo tháng và lưu trữ cơ sở dữ liệu.

## 1.3 Phạm vi dữ liệu và đơn vị phân tích

@table scope

Một bản ghi ERA5 là một địa điểm–ngày tại tâm ô lưới do API trả về. Tên Hà Nội, Đà Nẵng và TP.HCM chỉ vị trí truy vấn đại diện, không phải toàn bộ địa giới thành phố. Các tâm ô lưới ERA5 lần lượt là 21,00°B–105,75°Đ; 16,00°B–108,25°Đ; 10,75°B–106,75°Đ. Chuỗi gồm 3.287 ngày mỗi địa điểm trong 2017–2025, tổng cộng 9.861 bản ghi.

GloFAS có 1.826 ngày mỗi vị trí trong 2017–2021, tổng cộng 5.478 bản ghi. Ngày GloFAS giữ theo UTC, còn ngày ERA5 theo UTC+7. Không ghép hai bảng chỉ bằng nhãn ngày rồi coi đó là hai phép đo cùng khoảng 24 giờ. Phần mở rộng thủy văn cũng chưa xác nhận ô sông được chọn tương ứng chính xác với lưu vực hoặc trạm quan trắc nào.

Bộ chuẩn kiểm thử có 10.273 dòng thô, bao gồm bản sao và lỗi mô phỏng. Hồ sơ không có mã sinh, seed và đầy đủ tham số gốc; vì vậy khả năng tái lập của nhánh này bắt đầu từ tệp đầu vào đã ghim. Các ký hiệu WMO hoặc SYNOP còn trong schema cũ không xác nhận đã tải dữ liệu trạm NOAA ISD hay Meteostat. Toàn bộ kết quả của nhánh này được giới hạn trong Phụ lục A.

## 1.4 Bốn câu hỏi nghiên cứu

Q1 — Trong phạm vi mẫu, các biến khí tượng ERA5 phân bố và biến động theo tháng như thế nào giữa ba địa điểm? Chuỗi lưu lượng GloFAS cho thấy những đặc điểm mô tả nào sau khi kiểm tra lịch và đơn vị?

Q2 — Tương quan hạng và thống kê theo các nhóm tháng cố định thể hiện sự khác biệt nhiệt độ, độ ẩm và giáng thủy ra sao? Kết quả gộp có che khuất khác biệt giữa các địa điểm hay không?

Q3 — Quy trình kiểm tra và tổ chức dữ liệu xác nhận được những thuộc tính chất lượng nào? Phân tách ẩm–mưa bằng K-means mô tả được dữ liệu đến mức nào, và kết quả đó có giới hạn gì?

Q4 — Thêm biến trễ và chu kỳ năm theo địa điểm có cải thiện dự báo ngoài mẫu so với baseline không? Mức cải thiện có đồng nhất giữa chỉ số nhiệt độ, chỉ số mưa và từng địa điểm khi xét khoảng tin cậy hay không?

Bốn câu hỏi nghiên cứu trên được phân tích định lượng qua các bảng và biểu đồ tại Chương 5, sau đó tổng hợp đối chiếu trực tiếp tại Chương 6.

## 1.5 Ý nghĩa thực tiễn và ý nghĩa nghiên cứu

Ý nghĩa thực tiễn của quy trình là tạo được đầu vào có thể truy lại nguồn, giải thích được đơn vị và phát lại được phép xử lý. Người tiếp quản có thể kiểm một ngày cụ thể từ JSON sang CSV và SQLite, xem lý do cách ly ở nhánh kiểm thử, hoặc đối chiếu dự báo với nhãn ngày mục tiêu. Những khả năng này có ích ngay cả khi mô hình chưa đủ điều kiện triển khai ngoài thực tế.

Ý nghĩa nghiên cứu nằm ở thiết kế so sánh có đối chứng: giữ cùng tập Test, chọn tham số trên Validation, dùng baseline quán tính và khí hậu, đồng thời trình bày những kết quả chưa đủ bằng chứng. Ví dụ, F1 mưa cao hơn baseline theo điểm ước lượng không tự động chứng minh mô hình tốt hơn nếu khoảng tin cậy của chênh lệch còn chứa 0.

Đề tài không khẳng định phát hiện quy luật khí tượng mới. Các thống kê mô tả phản ánh đúng mẫu và định nghĩa biến đang dùng; các kết quả dự báo phản ánh khả năng dự báo giá trị ERA5 ngày kế tiếp. Giá trị này cần được phân biệt với độ chính xác dự báo số đo tại trạm hoặc lợi ích trong một hệ thống cảnh báo vận hành.

## 1.6 Cấu trúc báo cáo và tiêu chí hoàn thành

Chương 2 trình bày khái niệm dữ liệu và phương pháp. Chương 3 mô tả thu thập, kiến trúc và kho dữ liệu. Chương 4 giải thích cách triển khai, chia tập, kiểm thử và phát lại. Chương 5 trình bày kết quả ERA5 và GloFAS cùng các giới hạn suy luận. Chương 6 trả lời bốn câu hỏi và xác định việc cần làm tiếp. Phụ lục A dành riêng cho kiểm thử trên bộ mô phỏng.

Toàn bộ quy trình từ tệp dữ liệu gốc, mã nguồn xử lý đến các bảng kết quả và biểu đồ được đồng bộ hóa tự động nhằm bảo đảm tính nhất quán số học và khả năng tái lập của nghiên cứu.

# Chương 2 Cơ sở lý thuyết và phương pháp

## 2.1 Dữ liệu quan trắc và dữ liệu tái phân tích

ERA5 là sản phẩm tái phân tích khí quyển theo ô lưới; API lịch sử cung cấp các biến khí tượng được lựa chọn theo vị trí và thời gian [1], [2]. Trong đề tài, nhóm yêu cầu rõ models=era5 để giữ nhất quán nguồn mô hình. Dữ liệu được gọi là dữ liệu thu thập từ nguồn bên ngoài, không gọi là quan trắc trạm mặt đất. Tính liên tục của chuỗi là một thuộc tính của sản phẩm tái phân tích, không phải bằng chứng một trạm đo đã hoạt động không gián đoạn.

Một phép đo tại trạm mô tả vị trí và thiết bị cụ thể, trong khi một giá trị ô lưới có ý nghĩa không gian và phương pháp ước lượng khác. Vì vậy, tọa độ truy vấn và tọa độ trả về đều cần được lưu. Báo cáo không gắn mã trạm WMO trong bộ mô phỏng cho ô ERA5, cũng không suy rộng thống kê một ô lưới thành khí hậu trung bình của cả thành phố.

GloFAS cung cấp lưu lượng mô hình theo ô lưới; sản phẩm lịch sử được tạo bằng LISFLOOD sử dụng đầu vào khí tượng ERA5 [22], [23]. Do có quan hệ nguồn như vậy, GloFAS không phải đối chứng quan trắc độc lập cho ERA5. Trong báo cáo, hai nguồn bổ sung phạm vi dữ liệu khí tượng và thủy văn, nhưng không được tính như hai phép xác nhận độc lập về độ chính xác của thời tiết.

## 2.2 Ý nghĩa biến và quy ước tổng hợp theo ngày

@table data_dictionary

Biến nội bộ rain được dùng cho precipitation_sum. Theo định nghĩa của API, đó là giáng thủy tổng; báo cáo dùng cách gọi ngắn “mưa” trong bài toán phân lớp nhưng luôn giữ định nghĩa nhãn là precipitation_sum ≥1 mm. Không đổi tên này thành số ngày mưa đo tại trạm hoặc lấy nó làm bằng chứng riêng cho loại giáng thủy mà chưa kiểm tra thành phần.

Áp suất pressure_msl_mean là áp suất trung bình quy về mực biển, khác với surface_pressure. Gió trong bảng ERA5 là tốc độ trung bình ở độ cao 10 m, khác với gió giật cực đại. Những khác biệt này đặc biệt quan trọng khi đọc một ngày thời tiết mạnh: giá trị trung bình ngày không biểu diễn cường độ tức thời lớn nhất.

Với dữ liệu ngày, tổng giáng thủy và bức xạ phụ thuộc khoảng thời gian tổng hợp. Đề tài dùng trực tiếp biến daily của API cho nhánh chính, không tự cộng một ngày có thiếu giờ rồi coi là tổng đủ 24 giờ. Nếu mở rộng sang thu thập giờ, cần kiểm tra số giá trị hợp lệ theo từng biến; chỉ đếm đủ 24 mốc thời gian chưa đủ để xác nhận đủ dữ liệu cho tổng ngày.

## 2.3 Kiểm soát chất lượng và truy nguyên

Chất lượng dữ liệu được xét theo nhiều lớp: tệp có toàn vẹn không, schema có đúng không, lịch có trùng hoặc thiếu không, đơn vị có nhất quán không, và các quan hệ nội tại có hợp lý không. Mỗi lớp trả lời một câu hỏi riêng. SHA-256 xác nhận bytes không đổi so với hồ sơ ghim; nó không xác nhận giá trị khí tượng là phép đo đúng ngoài thực địa.

@table quality_rules

Bảy điều kiện miền giá trị của ERA5 được liệt kê cụ thể trong bảng trên. Việc ghi nhận 0 vi phạm chỉ có nghĩa không có dòng bị các điều kiện đó phát hiện trong tệp hiện hành. Những sai lệch do độ phân giải, phương pháp tái phân tích hoặc vị trí ô lưới vẫn có thể tồn tại. Vì thế “0 lỗi phát hiện” không được đổi thành “dữ liệu chính xác 100%”.

QCVN 46:2022/BTNMT và QCVN 47:2022/BTNMT cung cấp bối cảnh chuyên ngành quan trắc khí tượng và thủy văn [6], [24]. Báo cáo không chứng nhận API đáp ứng toàn bộ yêu cầu về vị trí công trình, thiết bị hoặc quy trình đo của các quy chuẩn. Các ngưỡng và phép kiểm phần mềm phải được phân biệt với yêu cầu của hệ thống quan trắc thực địa.

## 2.4 Thống kê mô tả và tương quan hạng

Trung bình phản ánh mức tổng thể nhưng nhạy với giá trị lớn; trung vị và các tứ phân vị mô tả phần giữa của phân bố. Với giáng thủy hoặc lưu lượng lệch phải, báo cáo trình bày nhiều đại lượng để tránh kết luận chỉ từ một trung bình. Số mẫu của từng nhóm luôn đi kèm để người đọc biết các phép tổng hợp sử dụng bao nhiêu ngày.

Spearman được tính bằng tương quan Pearson của thứ hạng, với các giá trị bằng nhau nhận thứ hạng trung bình [21]. Trong code, ma trận được tạo bằng rank().corr(), nên không dùng công thức rút gọn chỉ phù hợp khi không có đồng hạng. Điều này cần thiết với giáng thủy vì nhiều ngày có giá trị bằng 0.

@equation spearman

Hệ số dương hoặc âm mô tả liên hệ đơn điệu trong mẫu. Tương quan gộp có thể chịu tác động của sự khác nhau về địa điểm và thời gian trong năm; vì vậy phần kết quả bổ sung hệ số theo từng địa điểm. Báo cáo không suy cơ chế khí quyển từ hệ số này và không công bố p-value giả định các ngày độc lập.

Các nhóm lịch cố định gồm tháng 12–2, 3–4, 5–8 và 9–11. Cách đặt tên này chỉ quy định cách gom nhóm, không gán cùng một mùa mưa hay hình thái gió mùa cho cả ba miền. Các tháng 12, 1 và 2 được gộp theo tháng trong năm qua toàn bộ thời kỳ, không phải chuỗi ba tháng của một năm cụ thể.

## 2.5 Chuẩn hóa và phân tách mô tả bằng K-means

K-means trong nhánh mô tả sử dụng hai đầu vào: độ ẩm tương đối và logarit tự nhiên của 1 cộng giáng thủy. Phép log giúp giảm tác động của các giá trị mưa lớn lên khoảng cách Euclid; chuẩn hóa Z-score giúp hai biến có thang đo tương đương. Đây là lựa chọn biểu diễn để mô tả dữ liệu, không chứng minh phân bố tuân theo một mô hình vật lý cụ thể.

@equation zscore

@equation kmeans

Thuật toán được cài bằng NumPy, gán từng điểm vào tâm gần nhất rồi cập nhật tâm bằng trung bình các điểm trong cụm. Khởi tạo K-means++ và seed cố định giúp kết quả có thể phát lại. Báo cáo khảo sát k từ 2 đến 5; silhouette được ước lượng trên một mẫu cố định 1.000 dòng để hạn chế chi phí tính khoảng cách.

@equation silhouette

Với mỗi điểm, a là khoảng cách trung bình đến các điểm cùng cụm và b là khoảng cách trung bình nhỏ nhất đến một cụm khác. Silhouette lớn hơn cho biết sự tách biệt tốt hơn theo chính biểu diễn đang dùng. Chọn k=2 tốt nhất trong bốn giá trị đã thử không đồng nghĩa khí quyển chỉ có hai trạng thái. Nhãn cụm chỉ phục vụ mô tả toàn mẫu, không đưa vào các đặc trưng dự báo.

## 2.6 Hồi quy Ridge và đặc trưng chuỗi thời gian

Ridge dự báo nhiệt độ ngày kế tiếp bằng tổ hợp tuyến tính của đặc trưng, kèm phạt L2 để hạn chế hệ số quá lớn [20]. Trong code, các cột được điền thiếu bằng trung vị Train nếu cần, rồi chuẩn hóa bằng trung bình và độ lệch chuẩn Train. Nhãn nhiệt độ được trừ trung bình Train; hệ số chặn được khôi phục sau dự báo và không bị phạt.

@equation ridge_obj

Hàm mục tiêu ở đây dùng tổng bình phương sai số cộng α nhân bình phương chuẩn hệ số. Vì cách chuẩn hóa hàm mất mát ảnh hưởng ý nghĩa của α, không so trực tiếp α của dự án với một thư viện dùng quy ước khác. Nghiệm được tính qua hệ tuyến tính bằng numpy.linalg.solve, thay vì viết phép nghịch đảo ma trận một cách tường minh.

Biến trễ luôn gắn với ngày lịch. T(t−1) là nhiệt độ ngày ngay trước t, không phải dòng đứng trước trong một bảng đã xóa ngày lỗi. Δáp suất bằng áp suất ngày t trừ ngày t−1. Chu kỳ năm dùng sin và cos của ngày trong năm chia 365,25; các tương tác với địa điểm cho phép biểu diễn chu kỳ khác nhau ở ba ô lưới.

## 2.7 Logistic và đánh giá xác suất mưa

Mô hình hồi quy Logistic ước lượng xác suất mưa p từ tổ hợp tuyến tính của các đặc trưng thông qua hàm sigmoid. Hàm mục tiêu kết hợp trung bình log-loss với thành phần điều chuẩn L2 bằng bình phương chuẩn hệ số chia 2Cn (không phạt hệ số chặn b) và được tối ưu bằng thuật toán L-BFGS-B của thư viện SciPy [19], với siêu tham số C chọn trên tập Validation.

@equation logistic_obj

Một xác suất chỉ trở thành nhãn mưa/không mưa sau khi chọn ngưỡng. Ngưỡng được dò trên Validation 2024 và khóa trước khi đánh giá Test 2025. Do mục tiêu chọn là F1, ngưỡng tối ưu không bắt buộc bằng 0,5. Kết quả xác suất vẫn được lưu riêng để đọc ROC-AUC, Average precision, Brier và đồ thị hiệu chuẩn.

F1 tổng hợp Precision và Recall nhưng không dùng số dự báo đúng lớp khô trong mẫu số. Khi tỷ lệ mưa cao, dự báo luôn mưa có thể có F1 khá cao. Vì vậy báo cáo đặt F1 cạnh baseline luôn mưa và quán tính; ma trận TP, FP, FN, TN giúp đọc cụ thể loại lỗi mà một giá trị tổng hợp có thể che khuất.

## 2.8 Baseline và chỉ số đánh giá

Ba mô hình cơ sở (baseline) cho bài toán dự báo nhiệt độ gồm: (1) Baseline quán tính dự báo T̂(t+1) = T(t); (2) Baseline khí hậu tháng dùng nhiệt độ trung bình theo từng địa điểm và tháng ước lượng trên tập Train; và (3) Baseline khí hậu điều hòa cộng dị thường quán tính dự báo theo công thức c(t) + γ[T(t) − c(t)], trong đó hàm chu kỳ mùa c(t) theo địa điểm và hệ số γ được ước lượng trên dữ liệu trước tập Test.

MAE đo sai số tuyệt đối trung bình; RMSE nhấn mạnh hơn các sai số lớn; R² được đọc trong phạm vi biến thiên của tập đánh giá. Vì độ biến thiên nhiệt độ khác nhau giữa các địa điểm, R² gộp không thay thế bảng sai số theo địa điểm. Các baseline và mô hình được so sánh trên cùng ngày mục tiêu để tránh thay đổi mẫu số giữa các phép so.

@equation forecast_metrics

Brier score là trung bình bình phương chênh lệch giữa xác suất và nhãn nhị phân. Brier skill score so với xác suất khí hậu Train được tính theo Công thức [[equation:brier_skill]]. Một BSS dương biểu thị Brier thấp hơn baseline đã nêu, không phải tỷ lệ số ngày dự báo đúng.

@equation brier_skill

Xác suất Train là baseline có thể cố định trước khi thấy Test. Ngược lại, p_test(1−p_test) sử dụng tỷ lệ nhãn của chính tập Test và chỉ dùng làm tham chiếu hậu nghiệm. Hai mẫu số này được báo cáo riêng, tránh dùng một baseline nhìn trước nhãn Test rồi gọi là dự báo khí hậu ngoài mẫu.

## 2.9 Chia tập thời gian và khoảng tin cậy theo khối

ERA5 được chia theo target_date: Train 2017–2023, Validation 2024 và Test 2025. Lịch sử ngày t có thể nằm ngay trước ranh giới năm khi dự báo ngày t+1. Đây là thông tin quá khứ được phép dùng, miễn mọi bước ước lượng tham số đều chỉ dùng Train và việc lựa chọn mô hình chỉ dùng Validation.

Khoảng tin cậy chênh lệch lấy mẫu lại 12 khối tháng trong Test 2025, với 2.000 lần lặp và seed 20261110. Mỗi khối giữ cả ba địa điểm và cặp dự báo của các mô hình. Ở mỗi lần lặp, chương trình tính lại chênh lệch RMSE hoặc F1 trên mẫu ghép; các phân vị 2,5% và 97,5% tạo khoảng 95%.

Cách lấy mẫu theo khối giữ được cấu trúc phụ thuộc bên trong tháng tốt hơn lấy từng ngày độc lập, nhưng vẫn có giới hạn: chỉ có 12 khối, các tháng có tính mùa, và khoảng tin cậy có điều kiện trên các mô hình đã fit. Nó không bao gồm bất định do huấn luyện lại, không xác nhận khả năng dự báo ở nhiều năm tương lai, và không loại bỏ mọi dạng phụ thuộc giữa các khối.

# Chương 3 Thu thập và tổ chức dữ liệu

## 3.1 Kiến trúc ba nguồn dữ liệu

@figure architecture

Kiến trúc bắt đầu từ các tệp nguồn riêng, sau đó đi qua quy trình kiểm tra phù hợp với từng nguồn. ERA5 tạo dữ liệu mô tả và các cửa sổ dự báo; GloFAS tạo chuỗi lưu lượng có cờ chất lượng; benchmark tạo các tình huống kiểm thử và truy nguyên quyết định. Chỉ các đầu ra đã xử lý mới được nạp vào SQLite và dùng để tạo biểu đồ, dashboard, bảng báo cáo.

Việc dùng chung một kho mã không yêu cầu trộn mọi bản ghi thành một bảng duy nhất. Ba nguồn khác nhau về ý nghĩa, lịch và mức bằng chứng nên cần giữ nhãn nguồn xuyên suốt. Một truy vấn thống kê khí tượng chính phải đọc era5_daily; một truy vấn benchmark đọc observations. Quy tắc này giúp người dùng không vô tình tổng hợp dữ liệu nhân tạo chung với dữ liệu đã tải từ API.

## 3.2 Thiết kế truy vấn ERA5

Mô đun scripts/real_weather.py dùng Historical Weather API với khoảng ngày 2017-01-01 đến 2025-12-31. Tham số models được chỉ định là era5; timezone là Asia/Bangkok tương ứng UTC+7 trong phạm vi dữ liệu; wind_speed_unit là ms. Danh sách daily gồm các biến đã định nghĩa ở Bảng [[table:data_dictionary]]. Mỗi địa điểm có JSON phản hồi và một tệp request đi kèm.

Tọa độ yêu cầu lần lượt là Hà Nội 21,02–105,80; Đà Nẵng 16,04–108,20; TP.HCM 10,82–106,67. Tọa độ trả về được lấy từ chính JSON, không làm tròn rồi dùng lại như thể đó là tọa độ yêu cầu. Cả hai có vai trò khác nhau: tọa độ yêu cầu cho phép gọi lại API, còn tọa độ trả về giúp hiểu ô dữ liệu thực sự được phân tích.

@table source_coordinates

Khoảng 2017–2025 được giữ cố định để chia Train, Validation và Test theo năm. Mặc định chương trình phát lại từ các JSON kèm bài; chỉ dùng tùy chọn refresh khi chủ động tải phiên bản mới. Một lần tải mới có thể làm thay đổi bytes hoặc giá trị nguồn; do đó không nên ghi đè cache trong lúc chỉ muốn tái tạo đúng kết quả đã nộp.

## 3.3 Thu thập lưu lượng GloFAS

Mô đun scripts/hydrology.py dùng Flood API với các tham số daily=river_discharge, models=consolidated_v4, cell_selection=nearest và timezone=GMT. Giai đoạn 2017–2021 được chọn làm chuỗi lịch sử cố định nhằm bảo đảm tính đồng nhất của dữ liệu tái phân tích hợp nhất [22], [23].

Phản hồi nguyên gốc được lưu trước khi chuyển sang DataFrame. Hồ sơ request chứa URL, tham số, thời điểm tải UTC và mã băm của bytes phản hồi. Chương trình xác nhận đơn vị m³/s, UTC, chuỗi ngày đúng lịch và gắn cờ cho giá trị thiếu hoặc âm. Giá trị bằng 0 không tự động bị coi là lỗi vì điều kiện kiểm tra đang dùng chỉ phân biệt thiếu, âm và hợp lệ về miền.

Do tham số cell_selection=nearest trả về tâm ô lưới mô hình gần tọa độ truy vấn nhất [22], báo cáo ký hiệu các vị trí này theo tọa độ ô lưới tương ứng là ô gần Hà Nội, ô gần Đà Nẵng và ô gần TP.HCM.

## 3.4 Hồ sơ truy nguyên và bảo toàn bản gốc

Một hồ sơ nguồn hữu ích cần trả lời được bốn vấn đề: truy vấn gì, nhận dữ liệu gì, nhận lúc nào, và tệp hiện tại có còn đúng phiên bản đã ghim không. URL và tham số trả lời câu hỏi thứ nhất; JSON nguyên gốc và đơn vị trả lời câu hỏi thứ hai; thời điểm tải trả lời câu hỏi thứ ba; SHA-256 hỗ trợ câu hỏi cuối. Đổi định dạng JSON hoặc thứ tự khóa cũng có thể đổi hash dù giá trị số không đổi, nên phải phân biệt kiểm bytes với kiểm nội dung.

Hồ sơ truy nguyên chi tiết được lưu tại các thư mục data/era5, data/hydrology và tệp outputs/report_evidence/source_inventory.csv. Khi phát lại quy trình, chương trình tự động kiểm tra mã băm SHA-256 của từng tệp JSON đầu vào để bảo đảm dữ liệu nguyên bản không bị biến đổi ngoài ý muốn.

Việc thu thập có thể thực hiện bằng ít truy vấn nhưng vẫn bao phủ nhiều ngày và nhiều biến. Số lần gọi API không phải thước đo duy nhất của công sức thu thập. Tuy vậy, đề tài mới dùng một đơn vị cung cấp API cho hai sản phẩm mô hình; chưa có nguồn trạm độc lập. Giới hạn về đa dạng nguồn này vẫn tồn tại dù số bản ghi khá lớn.

## 3.5 Mô hình lưu trữ và khóa dữ liệu

@table database

Bảng era5_daily dùng khóa ghép location và date để nhận diện duy nhất một ô lưới–ngày, lưu các biến khí tượng cùng tọa độ, nguồn mô hình và múi giờ. Bảng hydrology_daily lưu lưu lượng, cờ chất lượng, tọa độ và nguồn GloFAS. Hai bảng tách biệt giúp truy vấn được dữ liệu thu thập mà không sử dụng nhầm danh mục trạm và hình thái thời tiết của benchmark.

Ba bảng stations, weather_regimes và observations phục vụ bộ mô phỏng. Các liên kết và ràng buộc trong nhánh đó là bài thực hành tổ chức dữ liệu quan hệ; chúng không chứng minh có ba trạm vật lý đang truyền số liệu. Mã trạm tồn tại trong một schema có thể là khóa phân loại của tệp kiểm thử mà không phải bằng chứng về nguồn đo.

Một thuận lợi của SQLite là giữ được dữ liệu và truy vấn trong một tệp có thể bàn giao. Với quy mô hiện tại, đề tài không cần một máy chủ cơ sở dữ liệu riêng. Tuy nhiên, kết quả chạy trên vài nghìn bản ghi chưa cho phép khẳng định đáp ứng tải lớn, nhiều người dùng đồng thời hoặc luồng dữ liệu thời gian thực.

## 3.6 Truy vấn kiểm tra và đối chiếu độc lập

Truy vấn nhóm theo location kiểm số dòng và tổng giáng thủy trong era5_daily. Kết quả được đối chiếu với CSV cùng nguồn. Truy vấn này kiểm đường đi từ dữ liệu sạch vào cơ sở dữ liệu; nó không phải phép xác nhận độc lập về khí tượng vì hai phía vẫn bắt nguồn từ cùng JSON.

@table sql_totals

Tổng giáng thủy trong Bảng [[table:sql_totals]] bao phủ chín năm, nên không được đưa thẳng vào một câu nói về lượng mưa trung bình năm. Muốn tính trung bình năm cần nhóm theo năm trước hoặc chia theo số năm đủ lịch, đồng thời giữ rõ cách xử lý năm nhuận. Báo cáo sử dụng annual_climate.csv cho phép tổng hợp theo từng năm.

Bên cạnh kiểm tra tổng hợp theo địa điểm, quy trình thực hiện đối chiếu chéo từng bản ghi cụ thể (như ngày 07/09/2024 tại Hà Nội) giữa tệp JSON gốc, tệp CSV sạch và bảng era5_daily trong SQLite để xác nhận tính toàn vẹn xuyên suốt các bước biến đổi dữ liệu.

## 3.7 Tổ chức mã và hợp đồng đầu ra

Hệ thống phần mềm được thiết kế theo kiến trúc mô đun hóa với hợp đồng đầu vào và đầu ra tách biệt giữa khâu thu thập dữ liệu, tiền xử lý – tạo đặc trưng, huấn luyện – đánh giá mô hình và lưu trữ cơ sở dữ liệu.

Các kết quả dự báo sau khi lựa chọn siêu tham số trên tập Validation được cố định tại tệp predictions.csv làm đầu vào duy nhất cho các mô đun phân tích sai số, kiểm định thống kê và trực quan hóa trên Dashboard, bảo đảm sự đồng bộ số liệu trên toàn hệ thống.

@table modules

# Chương 4 Triển khai quy trình và kiểm chứng

## 4.1 Trình tự chạy từ nguồn đến kết quả

Lệnh run_project điều phối theo thứ tự GloFAS, ERA5, benchmark, nạp cơ sở dữ liệu, dashboard, kiểm thử và các bước đối soát. Khi phát lại bản nộp, tùy chọn skip-download giữ nguyên đầu vào ghim. Nếu cần dựng lại tài liệu, chạy công cụ báo cáo sau khi các đầu ra dữ liệu đã được tạo và kiểm tra.

@table operation

Tách việc chạy dữ liệu khỏi việc xuất Word/PDF giúp phân biệt lỗi tính toán với lỗi định dạng. LibreOffice cần cho khâu xuất PDF và tính lại workbook khi chọn tùy chọn tương ứng; bản thân thống kê và mô hình chạy bằng Python. Người tiếp quản nên đọc lỗi đầu tiên của quá trình chạy, thay vì tiếp tục sử dụng một báo cáo cũ khi bước dữ liệu mới đã thất bại.

## 4.2 Từ dữ liệu ngày đến cửa sổ dự báo

Dữ liệu từng địa điểm được sắp theo thời gian và căn chỉnh lên lưới lịch ngày liên tục trước khi tạo biến trễ. Một cửa sổ dùng lịch sử đến ngày t và nhãn của ngày t+1. Tại đầu chuỗi không có ngày t−1, hoặc cuối chuỗi không có nhãn t+1, cửa sổ tương ứng bị loại. Với chuỗi ERA5 đủ ngày, điều này làm giảm từ 9.861 bản ghi xuống 9.855 cửa sổ.

Nếu một ngày ở giữa chuỗi bị cách ly, phép shift trên lưới lịch sẽ tạo giá trị thiếu đúng vị trí. Nó không nhảy sang ngày hợp lệ gần nhất rồi gọi đó là t−1. Đây là khác biệt quan trọng giữa lùi một dòng và lùi một ngày. Bộ kiểm thử của dự án kiểm tra lịch và ranh giới tập để tránh nhầm lẫn này.

@table split_detail

Tập Train có 7.662 cửa sổ, Validation có 1.098 và Test có 1.095. Chênh lệch giữa Validation và Test liên quan số ngày của năm 2024 và 2025; không phải thao tác lấy mẫu ngẫu nhiên. Các giá trị thiếu còn lại trong biến giải thích được xử lý bằng trung vị Train trong hàm fit, còn các cửa sổ thiếu nhiệt độ lịch sử hoặc nhãn mục tiêu không được giữ để đánh giá.

## 4.3 Đặc trưng và chống rò rỉ thời gian

@table features

R1 kiểm tra mức dự báo chỉ từ trạng thái ngày hiện tại. R2 thêm ký ức một ngày và một số biến liên quan đến thay đổi thời tiết. R3 thêm biểu diễn chu kỳ năm và tương tác địa điểm. So sánh ba cấu hình giúp tách đóng góp theo nhóm đặc trưng ở mức mô tả; không coi mọi chênh lệch điểm số nhỏ là kết luận có ý nghĩa thống kê nếu chưa tính khoảng tin cậy cho phép so đó.

Các tham số tiền xử lý (trung vị điền khuyết, trung bình và độ lệch chuẩn chuẩn hóa Z-score) cùng trọng số mô hình chỉ được ước lượng trên tập Train (2017–2023). Tập Validation (2024) được giữ riêng để lựa chọn cấu hình đặc trưng và siêu tham số trước khi đánh giá một lần trên tập Test (2025).

Đề tài dùng tái phân tích hồi cứu, nên thông tin ngày t trong thí nghiệm chưa chứng minh sẵn có đúng giờ phát hành ngoài thực tế. Chống rò rỉ giữa Train và Test là điều kiện cần cho đánh giá hồi cứu, nhưng vẫn phải kiểm tra độ trễ nguồn và thời điểm khả dụng trước khi chuyển thành một hệ thống vận hành.

## 4.4 Lựa chọn siêu tham số và khóa đánh giá

@table hyperparameters

Lựa chọn trên Validation giúp tránh dùng chính Test để tối ưu ngưỡng rồi báo một điểm số quá thuận lợi. Sau khi chọn R3, α, C và ngưỡng mưa, các dự báo được lưu thành predictions.csv. Tệp này là đầu vào cho cả bảng điểm tổng, điểm theo vùng, bootstrap và chẩn đoán sai số. Việc dùng chung một tệp cũng giúp các bảng không vô tình đánh giá trên những tập ngày khác nhau.

Lưới ngưỡng mưa ERA5 từ 0,20 đến 0,80 với bước 0,05 cho kết quả chọn 0,45, nằm trong lưới. Đây là tìm kiếm trên tập giá trị rời rạc đã nêu; không khẳng định 0,45 là tối ưu trên mọi ngưỡng thực hoặc mọi chi phí sai báo. Nếu nghiệp vụ cần phạt bỏ sót mưa mạnh hơn báo động giả, mục tiêu chọn ngưỡng phải được thiết kế lại và đánh giá bằng dữ liệu ngoài mẫu mới.

## 4.5 Kiểm thử tự động và đối soát sản phẩm

Bộ kiểm thử hiện hành có 48 ca. Các nhóm kiểm tra bao gồm tính toàn vẹn nguồn, logic bộ lọc benchmark, lịch và chia tập, tính điểm dự báo, dữ liệu ngoài trong SQLite và các bằng chứng bổ sung của báo cáo. Nhật ký kiểm thử lưu số ca chạy, số lỗi, số thất bại và trạng thái; báo cáo sử dụng con số thực tế của lần chạy kèm bộ nộp.

Test phần mềm và kết quả nghiên cứu cần được đọc riêng. Một hàm vượt qua test cho các trường hợp đã thiết kế không bảo đảm hoạt động đúng trên mọi lỗi cảm biến ngoài thực địa. Tương tự, chạy lại ra cùng RMSE cho thấy khả năng tái lập phép tính; nó không bổ sung một tập đánh giá độc lập mới cho mô hình.

@table reproducibility_levels

Bên cạnh các kiểm thử đơn vị cấp hàm, kịch bản đối soát tự động kiểm tra chéo sự khớp nối số liệu giữa tệp JSON gốc, bảng CSV, cơ sở dữ liệu SQLite (era5_daily, hydrology_daily, observations) và các chỉ số đánh giá mô hình trên tập Test.

## 4.6 Dashboard và cách đọc kết quả khi trình diễn

Dashboard ERA5 đặt tại outputs/real/DASHBOARD.html; dashboard benchmark đặt tại outputs/DASHBOARD_KHI_TUONG.html. Khi trình diễn, cần nêu rõ đang mở nguồn nào trước khi đọc một chỉ số. Một biểu đồ benchmark đẹp và có thể lọc không làm dữ liệu đó trở thành số đo ngoài thực tế.

Một trình tự demo phù hợp là chỉ hồ sơ nguồn, mở dữ liệu sạch, kiểm một ngày cụ thể, xem phân bố theo địa điểm rồi chuyển sang kết quả dự báo. Sau đó mới dùng nhánh benchmark để giải thích cơ chế phát hiện lỗi. Trình tự này giúp người xem phân biệt phần nghiên cứu dữ liệu thu thập với phần kiểm thử phần mềm.

Giao diện Dashboard HTML ngoại tuyến (outputs/real/DASHBOARD.html cho nhánh ERA5 và outputs/DASHBOARD_KHI_TUONG.html cho nhánh kiểm thử QC) kết xuất trực tiếp từ các bảng CSV và JSON của quy trình, cho phép tra cứu trực quan bảng chỉ số đánh giá của các mô hình cùng biểu đồ đối chiếu chuỗi nhiệt độ thực tế – dự báo theo từng địa điểm.

## 4.7 Quản lý phiên bản và tính nhất quán tái lập

Quy trình tái lập đảm bảo tính tất định khi giữ cố định tệp đầu vào, mã nguồn, cấu hình siêu tham số và quy ước chia tập theo thời gian. Khi cập nhật nguồn dữ liệu hoặc thay đổi cấu hình đặc trưng, toàn bộ các tệp đầu ra, cơ sở dữ liệu SQLite và bảng chỉ số đánh giá đều được tái tạo tự động thông qua kịch bản điều phối chung.

# Chương 5 Kết quả thực nghiệm và thảo luận

## 5.1 Chất lượng và quy mô dữ liệu sau xử lý

Tệp ERA5 hiện hành có 9.861 bản ghi, không có khóa địa điểm–ngày trùng, không có ô thiếu và không có dòng vi phạm bảy điều kiện miền giá trị đã công bố. Tệp GloFAS có 5.478 bản ghi, đủ lịch tại cả ba vị trí, không thiếu và không âm. Đây là kết quả kiểm tra trên các phản hồi đang lưu, không phải kết luận mọi giá trị mô hình đều đúng như số đo ngoài thực địa.

Phần kết quả chính dưới đây chỉ dùng ERA5 và GloFAS. Các thí nghiệm trên bộ mô phỏng được chuyển sang phụ lục để tránh nhầm giữa kiểm thử phần mềm và nghiên cứu khí tượng. Mọi bảng được đọc từ CSV hoặc JSON của lần chạy; các biểu đồ chẩn đoán bổ sung dùng dự báo đã khóa, không huấn luyện hoặc chọn lại tham số trên Test.

## 5.2 Phân bố chung của các biến ERA5

@table real_descriptive

Nhiệt độ trung bình toàn mẫu là 26,56 °C và trung vị 27,50 °C. Giáng thủy trung bình 5,85 mm/ngày trong khi trung vị 1,40 mm/ngày cho thấy hai đại lượng tóm tắt mô tả những phần khác nhau của phân bố. Vì ba địa điểm có cùng số ngày, mẫu gộp trao cùng trọng số theo số bản ghi, không phải theo diện tích hoặc dân số của ba miền.

@table location_profile

@figure location_distributions

Hà Nội có nhiệt độ trung bình 24,82 °C, thấp hơn Đà Nẵng 26,86 °C và TP.HCM 27,99 °C trong đúng thời kỳ này. Tỷ lệ ngày có giáng thủy ít nhất 1 mm tương ứng là 45,70%, 59,23% và 58,96%. Khác biệt này cần được giữ khi đọc điểm mưa theo địa điểm; một mô hình dự báo luôn mưa sẽ không có cùng F1 ở cả ba nơi.

Boxplot trong Hình [[figure:location_distributions]] ẩn các điểm nằm ngoài râu để phần giữa phân bố dễ đọc. Dữ liệu đó vẫn có trong các phép tính và mô hình; ẩn ký hiệu trên hình không phải xóa ngoại lệ. Cực trị giáng thủy ngày trong mẫu là 196,6 mm tại ô Hà Nội, 204,1 mm tại ô Đà Nẵng và 107,4 mm tại ô TP.HCM, cần đối chiếu theo nguồn thay vì tự động xóa vì lớn.

## 5.3 Biến thiên theo tháng và nhóm lịch

@figure real_era5_eda

Trung vị nhiệt độ tháng 1 lần lượt là 18,0 °C tại Hà Nội, 22,7 °C tại Đà Nẵng và 27,1 °C tại TP.HCM. Hình [[figure:real_era5_eda]] mô tả chu kỳ trong mẫu và là cơ sở thực nghiệm để xem xét biến sin/cos theo địa điểm. Tuy nhiên, quan sát một chu kỳ rõ không đủ để biết đặc trưng mùa có cải thiện dự báo ngoài mẫu bao nhiêu; câu hỏi đó cần bảng so sánh R2 và R3.

@figure monthly_rain

Hình [[figure:monthly_rain]] trình bày hai đại lượng khác nhau: lượng giáng thủy trung bình của một ngày trong tháng và tỷ lệ ngày đạt ngưỡng 1 mm. Một tháng có nhiều ngày mưa không nhất thiết có cùng mức giáng thủy trung bình với tháng có ít ngày nhưng mưa lớn. Không đọc trục mm/ngày thành tổng lượng mưa của tháng.

@table real_location_season

Mười hai nhóm gồm ba địa điểm nhân bốn khoảng tháng. Tên nhóm cố định giúp so sánh cùng quy ước lịch, nhưng mỗi khoảng có số tháng khác nhau; vì vậy số mẫu không bằng nhau giữa các nhóm. Thống kê ở đây gộp các năm, không chứng minh xu thế biến đổi khí hậu trong chín năm và không tách tác động của từng sự kiện thời tiết.

## 5.4 Tương quan gộp và tương quan theo địa điểm

Trong mẫu gộp, Spearman độ ẩm–giáng thủy xấp xỉ 0,60, còn nhiệt độ–độ ẩm xấp xỉ −0,31. Hai hệ số này được tính trên cùng bộ ERA5 nhưng có thể thay đổi đáng kể khi phân theo địa điểm. Vì vậy cần đọc ma trận gộp cùng bảng bên dưới thay vì coi một hệ số toàn mẫu là quy luật đồng nhất cho cả nước.

@table spearman_location

Ví dụ, Spearman độ ẩm–giáng thủy lần lượt khoảng 0,6583 ở Hà Nội, 0,2969 ở Đà Nẵng và 0,8336 ở TP.HCM. Nhiệt độ–độ ẩm tại Hà Nội chỉ khoảng 0,0183, trong khi Đà Nẵng là −0,5846. Các kết quả này cho thấy việc gộp mẫu che khuất khác biệt nội bộ, nhưng bản thân chúng chưa xác định nguyên nhân của khác biệt.

Các ngày liền kề có phụ thuộc thời gian và nhiều biến cùng biến thiên theo tháng. Báo cáo không diễn giải tương quan thành quan hệ nhân quả, không suy ra độ trễ tối ưu từ ma trận cùng ngày, và không dùng p-value theo giả định các ngày độc lập để tăng mức chắc chắn của diễn giải.

## 5.5 Phân tách mô tả trên không gian độ ẩm và giáng thủy

@table cluster_trials_real

@table real_cluster_summary

Silhouette lớn nhất trong các giá trị đã khảo sát đạt 0,4803 với k=2; các giá trị k=3, 4 và 5 lần lượt khoảng 0,4693, 0,4098 và 0,3881. Hai nhóm có 4.410 và 5.451 bản ghi, phân biệt chủ yếu theo độ ẩm và lượng giáng thủy. Không diễn giải hai nhãn thành hai hình thái thời tiết đã được chuyên gia xác nhận.

Sự tách biệt chịu ảnh hưởng của nhiều giá trị giáng thủy bằng 0 và phép log. Nếu đổi biến đầu vào, độ phân giải thời gian hoặc tiêu chuẩn khoảng cách, kết quả có thể khác. Do đó, đóng góp của bước phân cụm là một cách tóm tắt dữ liệu dễ quan sát, không phải phát hiện cấu trúc khí quyển hoặc cải thiện mô hình dự báo đã được kiểm định.

## 5.6 Đối chiếu mốc khí hậu tại Hà Nội

@table climate_comparison

Mốc QCVN 02:2022/BXD được đọc từ Bảng A.25 và A.28 trong bản gốc: tổng giáng thủy trung bình năm của dòng Hà Nội là 1.670,1 mm và số ngày mưa trung bình năm là 147,9 [16]. Số trang PDF tương ứng là 447 và 463. Đây là mốc khí hậu tham chiếu, không phải chuỗi số đo từng ngày được đưa vào mô hình của đề tài.

ERA5 Hà Nội trong 2017–2025 có trung bình tổng giáng thủy năm khoảng 1.880,5 mm và 166,9 ngày/năm đạt ngưỡng 1 mm. Sự khác biệt về thời kỳ, vị trí và định nghĩa ngày mưa làm phép so này chỉ có giá trị bối cảnh. Chưa thể lấy chênh lệch làm ước lượng bias của ERA5 hoặc kết luận nguồn nào đúng hơn nếu thiếu chuỗi trạm đồng thời và cùng định nghĩa.

## 5.7 Kiểm tra một cửa sổ sự kiện cụ thể

@table event_window

@figure event_window

Ngày 07/09/2024 tại ô lưới Hà Nội ghi nhận lượng giáng thủy 196,6 mm, áp suất mực biển trung bình 993,2 hPa và tốc độ gió 10 m trung bình 8,16 m/s. Các giá trị này khớp nhất quán giữa tệp JSON gốc (data/era5/Ha_Noi.json), bảng CSV sạch và bảng era5_daily trong SQLite, phản ánh rõ tín hiệu giảm áp suất và mưa lớn diện rộng khi bão Yagi đi qua khu vực Bắc Bộ [17].

Trong thiết kế chia tập, năm 2024 thuộc tập Validation và các đại lượng trong Bảng [[table:event_window]] là giá trị trung bình hoặc tổng ngày trên ô lưới 0,25° (khác với trị số gió giật tức thời tại trạm đo mặt đất). Việc đối chiếu cửa sổ thời gian này giúp xác nhận chuỗi tái phân tích ERA5 ghi nhận đúng diễn biến thời tiết lịch sử, khác biệt hoàn toàn với chuỗi mô phỏng tại Phụ lục A.

## 5.8 Kết quả dự báo nhiệt độ toàn mẫu

@table real_temperature

Trên Test 2025, RMSE giảm từ 1,0465 °C ở R1 xuống 0,9935 °C ở R2 và 0,9302 °C ở R3. Các cấu hình đều được chọn α trên Validation, còn R3 là cấu hình được chọn theo RMSE Validation thấp nhất. Kết quả phù hợp với việc lịch sử gần và chu kỳ năm có ích trong thí nghiệm, nhưng chưa có CI riêng cho mọi cặp R1–R2–R3.

Quán tính đạt RMSE 1,0741 °C và baseline khí hậu tháng đạt 1,7797 °C. Baseline khí hậu điều hòa cộng dị thường đạt 1,0209 °C, mạnh hơn khí hậu tháng. Việc đưa baseline này vào giúp phép so khó hơn và giảm nguy cơ tuyên bố mô hình có ích chỉ vì so với một đối chứng quá yếu.

@figure 13_real_era5_predictions_q1_2025

Hình [[figure:13_real_era5_predictions_q1_2025]] chỉ vẽ Quý I/2025 để chuỗi dễ đọc; các chỉ số trên đầu biểu đồ được tính trên toàn Test 2025. Mô hình thường đi theo diễn biến chung nhưng vẫn có các ngày lệch đáng kể. Một đường dự báo có vẻ sát ở thang toàn quý không thay thế các chỉ số sai số và việc kiểm những ngày khó.

## 5.9 Khác biệt theo địa điểm và các ngày sai số lớn

@table regional_models

Ở Hà Nội, RMSE R3 là 1,3290 °C so với quán tính 1,5690 °C; ở Đà Nẵng là 0,6671 so với 0,7706 °C. TP.HCM có R3 0,6202 °C so với quán tính 0,6366 °C, nhưng baseline khí hậu cộng dị thường còn thấp hơn, khoảng 0,6045 °C. Vì vậy không thể viết R3 vượt qua mọi baseline ở mọi địa điểm.

@figure monthly_errors

@figure error_ecdf

Hai hình chẩn đoán bổ sung cho điểm số toàn năm. Sai số theo tháng cho biết thời đoạn khó; đường tích lũy cho biết tỷ lệ các ngày đạt một mức sai số tuyệt đối nhất định. Chúng được tính sau khi khóa mô hình để mô tả hạn chế, không được dùng chỉnh mô hình rồi tiếp tục coi cùng Test là đánh giá độc lập.

@table largest_errors

Sáu sai số lớn nhất đều rơi vào Hà Nội trong tệp dự báo hiện hành. Ngày 29/03/2025 có nhiệt độ mục tiêu ERA5 18,10 °C trong khi R3 dự báo 24,60 °C, lệch khoảng 6,50 °C. Điều này cho thấy RMSE trung bình dưới 1 °C không bảo đảm mọi ngày đều sai dưới 1 °C. Chưa có phân tích trường khí quyển để quy kết nguyên nhân vật lý của từng trường hợp sai số.

## 5.10 Phân lớp mưa và ý nghĩa của F1

@table rain_confusion

Trên 1.095 mẫu Test, mô hình có 519 lần dự báo đúng mưa, 108 báo mưa khi nhãn khô, 125 bỏ sót mưa và 343 lần dự báo đúng khô. F1 là 81,67%, nhưng Hà Nội chỉ khoảng 71,76%, thấp hơn Đà Nẵng 82,89% và TP.HCM 87,89%. Bảng đếm giúp làm rõ rằng cùng một mô hình có thể gặp khó khăn khác nhau giữa các địa điểm.

@table rain_skill

Tỷ lệ nhãn mưa Test là 58,81%; dự báo luôn mưa đã đạt F1 khoảng 74,07%. Logistic có F1 cao hơn quán tính theo điểm ước lượng, nhưng cần đọc khoảng tin cậy của chênh lệch trước khi khẳng định ưu thế. Average precision 0,8839 được đọc cùng tỷ lệ nền, không gọi nó là xác suất mỗi dự báo sẽ đúng và không thay bằng diện tích hình thang PR nếu chưa thống nhất cách tính.

Brier mô hình là 0,151316 so với baseline dùng xác suất Train có Brier khoảng 0,244469, tương ứng BSS 0,3810. Đây là mức cải thiện tương đối của sai số xác suất so với baseline được xác định trước Test. BSS 0,3753 dùng tỷ lệ Test là một tham chiếu hậu nghiệm riêng; hai giá trị không mâu thuẫn vì dùng mẫu số khác nhau.

## 5.11 Chẩn đoán xác suất và khoảng tin cậy

@figure rain_calibration

@table calibration

Trong khoảng xác suất 0,4–0,5, xác suất trung bình khoảng 0,4488 nhưng tỷ lệ ngày mưa thực nghiệm là 0,5900; khoảng này có 100 mẫu. Ở khoảng 0,9–1,0, hai giá trị tương ứng khoảng 0,9549 và 0,9299 với 214 mẫu. Đồ thị cho thấy cần đọc khả năng xếp hạng và hiệu chuẩn như hai thuộc tính khác nhau của mô hình.

Báo cáo chưa fit một phép hiệu chỉnh xác suất mới. Nếu thực hiện, cần dùng một phần dữ liệu phù hợp trước Test và đánh giá lại trên tập chưa dùng để chọn hiệu chỉnh. Tần suất trong từng khoảng ở bảng trên chỉ là thống kê mô tả của một năm, không phải một xác suất khí hậu chính xác không có bất định.

@table real_paired_bootstrap

@figure real_paired_bootstrap

CI 95% của chênh lệch RMSE R3 trừ quán tính toàn mẫu là [−0,1938; −0,0951] °C; với baseline khí hậu cộng dị thường là [−0,1403; −0,0419] °C. Trong thiết kế khối tháng hiện hành, cả hai khoảng đều dưới 0, hỗ trợ kết luận cải thiện nhiệt độ toàn mẫu so với hai baseline này.

Chênh lệch F1 mưa có CI [−1,1596; 3,1507] điểm phần trăm, chứa 0. Riêng RMSE tại TP.HCM có CI [−0,0353; 0,0046] °C cũng chứa 0. Do đó kết luận phù hợp là có bằng chứng cải thiện RMSE toàn mẫu trong phép đánh giá đã nêu, còn ưu thế F1 mưa và cải thiện tại TP.HCM chưa được xác nhận chắc chắn.

## 5.12 Kết quả thu thập và mô tả lưu lượng GloFAS

@table hydrology_summary

@table hydrology_quantiles

Trung vị lưu lượng tại ba ô gần Hà Nội, Đà Nẵng và TP.HCM lần lượt là 2.038,39; 19,99; 90,41 m³/s. Khác biệt về quy mô không được giải thích đơn giản như thành phố này nhiều nước hơn thành phố kia, vì chưa có xác nhận lưu vực, diện tích thượng lưu hoặc ảnh hưởng vận hành tại vị trí được API chọn.

Ô gần TP.HCM có 230 ngày lưu lượng bằng 0 trong chuỗi 1.826 ngày. Theo bộ kiểm miền giá trị hiện hành, 0 không bị loại như giá trị âm. Tuy nhiên, số ngày bằng 0 là tín hiệu cần kiểm tra thêm về ô sông và mức đại diện của mô hình trước khi ứng dụng; không được tự gán thành kết luận sông thực tế đã khô trong những ngày đó.

@figure hydrology_monthly

@table hydrology_monthly_table

Trung vị theo tháng ở ô Hà Nội cao nhất trong bảng vào tháng 8, khoảng 9.056,33 m³/s; Đà Nẵng cao nhất vào tháng 11, khoảng 76,18 m³/s; TP.HCM cao nhất vào tháng 10, khoảng 354,63 m³/s. Đây là kết quả mô tả những ngày cùng tháng qua năm năm dữ liệu, không phải dự báo đỉnh lũ của một năm cụ thể.

@figure flow_duration

Đường tần suất vượt được dựng bằng cách sắp lưu lượng giảm dần và gắn thứ hạng thực nghiệm m/(n+1). Đồ thị giúp nhìn mức độ lệch và sự khác biệt trong phân bố của từng ô. Nó không phải đường tần suất lũ thiết kế, không dùng để suy chu kỳ lặp nhiều năm hoặc thiết lập ngưỡng cảnh báo mà chưa có quy trình thủy văn phù hợp.

## 5.13 Đánh giá mức đáp ứng đề tài

Kết quả đã bao gồm cả dữ liệu khí tượng và thủy văn: thu thập nguồn, kiểm tra, chuẩn hóa, lưu trữ và phân tích. Phần dự báo thời tiết dùng ERA5 làm dữ liệu đầu vào và nhãn hồi cứu; phần GloFAS đáp ứng mở rộng dữ liệu thủy văn nhưng chưa được ghép vào mô hình thời tiết vì khác múi giờ và chưa có thiết kế vật lý phù hợp.

Những hạn chế còn lại không được che bằng thêm thuật toán. Thiếu trạm đối chứng làm giới hạn kết luận về độ chính xác ngoài thực địa; chỉ một năm Test làm giới hạn khả năng suy rộng theo thời gian; thiếu xác minh ô sông làm giới hạn ứng dụng lưu lượng. Những điểm này được chuyển thành hướng phát triển cụ thể ở Chương 6.

# Chương 6 Trả lời câu hỏi nghiên cứu và kết luận

## 6.1 Trả lời bốn câu hỏi nghiên cứu

Q1 — Đã mô tả 9.861 bản ghi ERA5 và 5.478 bản ghi GloFAS có nguồn truy nguyên. Nhiệt độ trung bình toàn mẫu ERA5 là 26,56 °C; trung vị tháng 1 tại Hà Nội, Đà Nẵng và TP.HCM là 18,0 / 22,7 / 27,1 °C. Lưu lượng trung vị tại ba ô GloFAS là 2.038,39 / 19,99 / 90,41 m³/s. Đây là mô tả mẫu theo ô lưới và thời kỳ đã nêu, không phải kết luận đại diện toàn vùng.

Q2 — Spearman độ ẩm–giáng thủy toàn mẫu khoảng 0,60 nhưng theo địa điểm lần lượt khoảng 0,6583, 0,2969 và 0,8336. Mười hai nhóm địa điểm × khoảng tháng cố định cho phép so sánh cùng quy ước lịch. Chênh lệch giữa hệ số gộp và riêng cho thấy cần phân tầng khi diễn giải, còn quan hệ nhân quả và cơ chế khí quyển chưa được kiểm định.

Q3 — Các phản hồi ERA5/GloFAS hiện hành đủ lịch, không có giá trị thiếu trong các biến phân tích và không có vi phạm được bộ kiểm tương ứng phát hiện. Phân tách ẩm–mưa k=2 có silhouette khoảng 0,4803 trong không gian đã chọn. Kết quả xác nhận tính hợp lệ theo hợp đồng và một cách tóm tắt mẫu; chưa xác nhận độ chính xác số đo tại trạm hoặc hai hình thái thời tiết ngoài thực tế.

Q4 — R3 đạt RMSE 0,9302 °C so với quán tính 1,0741 °C; CI chênh lệch toàn mẫu nằm dưới 0. BSS mưa so với xác suất Train là 0,3810. Tuy nhiên, CI chênh lệch F1 chứa 0, TP.HCM chưa có bằng chứng cải thiện rõ so với quán tính và baseline khí hậu cộng dị thường còn tốt hơn R3 theo RMSE điểm ở địa điểm này. Kết luận không phải mọi mô hình đều vượt mọi baseline.

## 6.2 Những kết quả đạt được

Đề tài đã tổ chức được đường đi từ nguồn có hồ sơ truy vấn đến dữ liệu sạch, đặc trưng, dự báo, cơ sở dữ liệu và báo cáo. Các bảng era5_daily và hydrology_daily chứa dữ liệu thu thập thực sự, tách khỏi observations của benchmark. Phép kiểm một ngày cụ thể và kiểm tổng qua SQL giúp phát hiện lỗi truyền số giữa các sản phẩm.

Phần thực nghiệm đã so sánh nhiệt độ và xác suất mưa với các baseline có thể giải thích, dùng Test theo thời gian và trình bày khoảng tin cậy theo khối. Báo cáo cũng giữ các kết quả bất lợi như sai số lớn tại một số ngày Hà Nội và hạn chế ở TP.HCM. Giá trị đạt được là quy trình và bằng chứng đánh giá có thể kiểm tra, không phải cam kết độ chính xác vận hành.

## 6.3 Hạn chế còn tồn tại

Nguồn khí tượng và thủy văn đều là sản phẩm mô hình; GloFAS dùng ERA5 làm đầu vào nên không xác nhận độc lập cho nguồn khí tượng. Chưa có đối chiếu trạm cùng thời kỳ, chưa xác minh lưu vực, chưa đánh giá dự báo dòng chảy và chưa kiểm tra ảnh hưởng thủy triều hoặc vận hành hồ. Các quy chuẩn được dẫn làm bối cảnh, không thay bằng chứng thực địa.

Đánh giá dự báo mới dùng một năm Test. Bootstrap theo tháng không bao gồm biến động do fit lại mô hình hoặc biến động giữa nhiều năm kiểm tra. Thêm phân tích chi tiết trên Test giúp hiểu lỗi nhưng cũng làm tập này trở nên quen thuộc; nếu dựa vào các lỗi đó để cải tiến mô hình, cần một tập đánh giá mới cho tuyên bố cải thiện tiếp theo.

Benchmark thiếu mã sinh gốc và chỉ có lỗi theo thiết kế đã biết. Kết quả phát hiện khớp nhãn lỗi hoặc lợi ích điền khuyết trên đó chỉ xác nhận logic phần mềm trong phạm vi mẫu. Những kết quả này không được tính thành cải thiện đã chứng minh trên số đo khí tượng thực.

## 6.4 Hướng phát triển và điều kiện sử dụng

Ưu tiên tiếp theo là thu thập chuỗi trạm khí tượng và thủy văn độc lập có thông tin đơn vị, tọa độ, lịch và thời điểm khả dụng. Khi có dữ liệu, cần thiết kế phép ghép cùng thời kỳ và định nghĩa biến trước khi tính bias hoặc skill. Với GloFAS, kiểm tra bản đồ và diện tích lưu vực cần đi trước việc gán tên sông hoặc dùng ngưỡng cảnh báo.

Về mô hình, có thể đánh giá nhiều năm theo cửa sổ thời gian, huấn luyện lại trong từng fold và khảo sát hiệu chuẩn xác suất bằng dữ liệu dành riêng. Chỉ mở rộng thuật toán sau khi giữ được baseline và quy trình đánh giá công bằng. Với vận hành, cần thêm kiểm tra độ trễ nguồn, lỗi tải, nhật ký, giám sát thay đổi phân bố và thử nghiệm trên môi trường thật.

Trong phạm vi học phần, báo cáo hoàn thành nguyên mẫu thu thập và xử lý dữ liệu có minh chứng, kèm thực nghiệm dự báo hồi cứu. Bộ mã và dữ liệu cho phép thành viên tiếp quản, giải thích từng bước và trình diễn lại. Khả năng áp dụng trực tiếp vào cảnh báo ngoài thực tế vẫn cần các bước xác minh tiếp theo đã nêu.

@appendix benchmark

## A.1 Vai trò và nguồn gốc của tệp kiểm thử

Tệp mô phỏng 10.273 dòng được giữ nguyên để kiểm thử các quy tắc chuẩn hóa và QC. Không có mã sinh, seed hoặc hồ sơ đầy đủ xác nhận tác giả của bộ sinh; vì vậy báo cáo không mô tả một quá trình sinh dữ liệu mà nhóm chưa tái tạo được. Việc giữ tệp này chỉ có ý nghĩa như một bộ đầu vào cố định cho kiểm thử hồi quy phần mềm.

@table benchmark_qc

412 dòng trùng và 227 dòng lỗi được đối chiếu bằng nhãn đã có trong dữ liệu. Bộ lọc ra quyết định từ trường giá trị và khóa trùng, còn nhãn lỗi được dùng kiểm toán hậu nghiệm. Khớp toàn bộ nhãn trong mẫu là kết quả kiểm thử logic, không phải độ nhạy hay độ đặc hiệu đã được ước lượng trên lỗi của trạm thực.

## A.2 Các phép chuẩn hóa riêng của benchmark

Trong tập sạch có 234 dòng gió được quy đổi từ km/h sang m/s. Số 242 là số dòng không trùng được đổi trước QC, trong đó 8 dòng bị cách ly; 255 là số dòng thô gồm các bản sao. Ba con số cùng đúng với ba mẫu số khác nhau, nên không được dùng thay nhau trong tóm tắt hoặc bảng kiểm đếm.

Benchmark có 183 ô nhiệt độ và 146 ô áp suất được phục hồi có điều kiện từ cột tham chiếu. Các cột có tên reanalysis trong schema cũ là thành phần của bộ kiểm thử, không tự chứng minh được tải từ ERA5 độc lập. Mọi diễn giải lợi ích điền thiếu cần giữ giới hạn này.

## A.3 Phép kiểm Magnus và giới hạn áp dụng

Phép kiểm điểm sương dùng quan hệ Magnus với các hệ số 17,62 và 243,12 °C trong nhánh benchmark [3]. Nó được dùng cùng các điều kiện thứ tự nhiệt độ và miền hợp lệ để phát hiện lỗi chèn sẵn. Nhánh ERA5 chính không chạy phép kiểm Magnus trên các đại lượng trung bình ngày.

@equation magnus

Không được lấy quan hệ giữa các đại lượng tức thời rồi đòi hỏi nó đúng tuyệt đối sau mọi phép lấy trung bình ngày. Đây là một lý do giữ bộ quy tắc benchmark riêng thay vì sao chép toàn bộ sang dữ liệu API. Các ngưỡng phần mềm như dung sai điểm sương cũng không được mô tả như một tiêu chuẩn pháp lý áp dụng tự động cho mọi nguồn.

## A.4 Hai kết quả phụ thuộc thiết kế bộ mô phỏng

@table benchmark_limits

Mức nhiễu σ≈0,25 °C là mô tả thiết kế được ghi trong hồ sơ bộ kiểm thử, chưa được xác minh bằng mã sinh gốc. Sai số che 5% gần mức này và tác động điền thiếu chỉ cho thấy thuật toán hoạt động trên các giá trị tham chiếu thuận lợi theo thiết kế. Không dùng chúng làm bằng chứng ERA5 phục hồi được cảm biến thật với độ chính xác tương ứng.

Cùng ngày 07/09/2024, benchmark có giáng thủy 0,0 mm trong khi ERA5 Hà Nội là 196,6 mm. Sự khác biệt cụ thể này cho thấy không thể dùng diễn biến, tương quan hoặc nhãn hình thái của benchmark để diễn giải sự kiện thời tiết thật. Các kết quả đầy đủ vẫn nằm trong outputs để kiểm tra mã, nhưng không nằm trong mạch kết luận khí tượng chính.

## A.5 Công cụ trích mẫu và quy trình đối soát độc lập

Bên cạnh bước đối soát tự động trên toàn bộ 10.273 bản ghi, kho mã cung cấp công cụ tools/manual_audit.py để trích xuất ngẫu nhiên có phân tầng mẫu kiểm tra (ẩn trường nhãn nguồn source_channel) kèm tệp ngữ cảnh tra cứu khóa trùng manual_audit_context.csv.

Cấu trúc tệp mẫu cho phép thực hiện gán nhãn độc lập và tính toán tỷ lệ đồng thuận với quyết định của đường ống làm sạch khi mở rộng quy trình kiểm định chất lượng dữ liệu.
