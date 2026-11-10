# Tích hợp và kiểm chứng bản báo cáo mở rộng

Nguồn đối chiếu: `KHDL-KhiTuongThuyVan-main (8).zip`, `KHDL-KhiTuongThuyVan-fixed(1).zip` và PDF (8) được cung cấp trong cuộc trao đổi. Bộ mã hiện hành giữ mạch ERA5/GloFAS đã kiểm chứng, cập nhật các phần sau.

- Viết lại nội dung sáu chương, có mục tiêu duy nhất, ý nghĩa thực tiễn và nghiên cứu, phương pháp, nguồn, triển khai, phân tích kết quả và trả lời Q1–Q4. Không ghép các bảng mô phỏng vào kết luận khí tượng thật.
- Bổ sung chẩn đoán có mã chạy: thống kê theo địa điểm, tương quan riêng từng ô, sai số tháng, các ngày sai số lớn, ma trận nhầm lẫn, hiệu chuẩn xác suất, phân vị/đường tần suất vượt GloFAS và truy vấn kiểm tổng SQLite. Tệp sinh: `tools/report_evidence.py`.
- Đối chiếu GloFAS: 5.478 giá trị ngày trong ZIP (8) khác phản hồi API tải trực tiếp với cùng tham số, dù các số tổng hợp gần nhau. Chưa xác định nguyên nhân hay tác giả thay đổi. Bản hiện hành dùng nguyên bytes phản hồi mới, giữ URL/thời điểm/SHA-256. Hồ sơ so sánh: `references/hydrology_revision_comparison.json`. Không dùng chuỗi khác đó như dữ liệu API đã xác minh.
- Tăng kiểm tra đầu vào ERA5: mã băm ghim trong hồ sơ request, kiểm model/timezone, đơn vị và lịch. Thời điểm tải ERA5 cũ giữ nguyên; việc ghim hash bổ sung không được ghi thành tải mới.
- Tích hợp luồng kiểm tra thủ công từ bản fixed: tạo mẫu 60 dòng và bảng ngữ cảnh đã bỏ nhãn nguồn; chặn chấm khi nhãn chưa đầy đủ; kappa không xác định được để null. Chưa có người gán nhãn, nên không công bố tỷ lệ đồng thuận.
- Không nhập collector theo giờ của bản fixed vào nhánh chính. Nhánh hiện hành dùng daily của API; tránh cộng ngày thiếu giờ và tránh đổi model âm thầm thành best_match. Các số mô hình của benchmark cũ không thay kết quả ERA5.
- Số test cuối cùng lấy từ outputs/python_test_results.json; logs/ chứa nhật ký chạy. Công cụ audit đối chiếu BSS, GloFAS, SQLite, Yagi, QCVN, metadata và danh mục bảng/hình.
- Chưa chạy trực tiếp trên máy Windows của nhóm, chưa đánh giá người dùng, chưa có trạm quan trắc đối chứng và chưa xác minh lưu vực. Xem docs/VIEC_NHOM_CAN_XAC_NHAN.md.
