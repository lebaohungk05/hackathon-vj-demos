# ADR 0002: Máy chủ HTTP bằng thư viện chuẩn

- Trạng thái: chấp nhận
- Ngày: 2026-10-14

## Bối cảnh

Demo chỉ cần một API JSON nhỏ và phục vụ file tĩnh, chạy trên máy trình diễn, nghe `127.0.0.1`. Các điều kiện: cài nhanh, ít phụ thuộc, dễ kiểm soát luồng.

## Quyết định

Dùng `http.server.ThreadingHTTPServer`. Trạng thái nằm trong một đối tượng `Demo`; `Runtime` xuất snapshot JSON sau mỗi thay đổi và chỉ cho một job thay đổi chạy cùng lúc.

## Hệ quả

- Phụ thuộc thời chạy chỉ gồm numpy, pandas và Pillow (cho mô hình và đọc ảnh).
- Việc đọc không bao giờ chờ LLM, vì snapshot được dựng sẵn.
- Không có xác thực, phân quyền hay nhiều người dùng. Hợp lý cho demo cục bộ; nếu đưa lên mạng cần framework có xác thực và một kho dữ liệu thật.
- Chuẩn nội bộ của công ty ưu tiên FastAPI. Nếu demo thành sản phẩm, chuyển sang FastAPI theo cấu trúc `api/schemas/services/models` và tách `engine.py` theo miền.
