# Kịch bản bảo vệ 10 phút — Nhóm 13

## Phân chia đề xuất

| Thời gian | Người | Trọng tâm |
|---|---|---|
| 0:00–3:00 | Đinh Quang Thái | Mục tiêu, ba nguồn, JSON/URL/SHA-256, ERA5 và GloFAS khác trạm thế nào; Bảng 1, Hình 1. |
| 3:00–6:00 | Đặng Ngọc Sơn | QC ERA5, target_date, tách múi giờ, SQLite era5_daily và hydrology_daily; Bảng 5, 8. Demo truy vấn số dòng và ngày Yagi. |
| 6:00–9:00 | Đặng Văn Chương | ERA5 EDA, Ridge/Logistic, BSS và paired CI; Bảng 21, 25, 27; GloFAS ở Bảng 28. |
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
