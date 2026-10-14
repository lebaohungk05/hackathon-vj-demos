# ADR 0001: Gọi LLM qua Claude CLI

- Trạng thái: chấp nhận
- Ngày: 2026-10-14

## Bối cảnh

Demo cần LLM để hiểu tin nhắn tiếng Việt, chọn người đo lại và viết giải thích, và phải chạy được trên máy trình diễn không có khóa API riêng. Nhóm đã dùng Claude Code đăng nhập sẵn.

## Quyết định

`ricebridge.llm.client.LLMClient` gọi `claude -p --output-format json` như một tiến trình con, với `--tools ""`, `--strict-mcp-config`, `--no-session-persistence`. Đầu ra phải là một JSON khớp schema và qua validator; sai thì thử lại một lần với lỗi của validator, vẫn sai thì dùng bộ quy tắc.

## Hệ quả

- Không cần quản lý khóa API trong repo.
- Mỗi lần gọi mất 10–50 giây, nên có cache (ADR 0003), tiến độ trên giao diện và nút "Skip LLM".
- LLM không có công cụ nào, nên không thể hành động ngoài việc trả JSON.
- Phụ thuộc vào CLI được cài và đăng nhập; thiếu thì demo tự chuyển sang chế độ offline.
- Đọc ảnh là ngoại lệ: `gauge_reader.py` cấp quyền `Read` để mô hình mở file ảnh. Cần thay bằng gửi ảnh trực tiếp khi triển khai thật.
