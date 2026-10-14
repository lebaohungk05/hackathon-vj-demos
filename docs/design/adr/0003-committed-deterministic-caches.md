# ADR 0003: Commit cache LLM và dữ liệu thử một cách có chủ đích

- Trạng thái: chấp nhận
- Ngày: 2026-10-14

## Bối cảnh

Demo phải chạy ổn định, nhanh và offline trên sân khấu. Câu trả lời LLM chậm và thay đổi giữa các lần gọi.

## Quyết định

Commit vào git: `data/llm_cache/` (khóa là sha256 của model, prompt, dữ liệu và schema), `data/i18n/` (bản dịch), `data/vision/cache/` (kết quả đọc ảnh, khóa theo sha256 của ảnh), `data/fixtures/` (thời tiết). Chế độ `replay` chỉ dùng các file này; thiếu thì dùng bộ quy tắc và giao diện báo "rules fallback".

## Hệ quả

- Không đổi chuỗi prompt, schema hay byte của ảnh thử trong `data/vision/testset/` nếu không sinh lại cache, vì khóa cache sẽ không còn khớp. Kiểm tra bằng tổng số lần "fallback" trong chế độ replay phải bằng 0 (test `tests/e2e/test_smoke.py` kiểm điều này).
- Sửa prompt hoặc kịch bản thì chạy lại `python scripts/capture.py --mode auto --no-video` và `python -m ricebridge.llm.translate` để làm nóng cache rồi commit.
- Repo nặng thêm khoảng 0,7 MB cache và 1,3 MB ảnh thử.
- File sinh khi chạy (dự báo mới, ảnh tải lên, log) đi vào `.cache/` và không được commit.
