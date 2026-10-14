# RiceBridge Ops

Demo AI agent giúp hợp tác xã (HTX) ở Đồng bằng sông Cửu Long điều phối tưới ướt khô xen kẽ (AWD) cho cả cụm ruộng dùng chung một trạm bơm, và lưu bằng chứng từng thửa để bán tín chỉ carbon. Giao diện tiếng Việt, tiếng Nhật và tiếng Anh.

Agent đọc tin nhắn của nông dân, ảnh ống đo mực nước và dự báo mưa, rồi đề xuất lịch bơm. Con người duyệt mọi lịch. LLM chỉ hiểu ngôn ngữ và viết lời giải thích; cân bằng nước, an toàn theo giai đoạn lúa và xếp lịch do công cụ tất định tính.

## Cài đặt

Yêu cầu **Python 3.10+**. Chạy tại thư mục gốc repo:

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows PowerShell
# source .venv/bin/activate         # macOS/Linux
python -m pip install -e ".[test]"
python -m playwright install chromium
```

## Chạy demo

```bash
python -m ricebridge --stage --open
```

Mở http://127.0.0.1:8766. `--stage` dùng cache và bộ luật, không cần mạng hay LLM trực tiếp. Phím: mũi tên đi qua kịch bản, **W** thử giả định, **C** đổi góc nhìn, **J** đổi ngôn ngữ, **R** đặt lại.

Dùng Claude CLI đã đăng nhập để gọi LLM trực tiếp: `python -m ricebridge --mode auto --open` (ưu tiên cache) hoặc `--mode live` (luôn gọi).

## Cấu trúc

```text
src/ricebridge/   Mã nguồn: engine, llm/, vision/, server/, sim/, web/
data/             Dữ liệu cố định: thời tiết, cache LLM, bản dịch, ảnh thử
outputs/          Kết quả mô phỏng và đánh giá
tests/            unit/ (pytest) và e2e/ (Playwright)
scripts/          Công cụ phụ: chụp màn hình, đánh giá đọc ảnh
docs/             research/, design/, manual/, report/
```

Chi tiết trong [docs/](docs/README.md). Kiến trúc: [docs/design/architecture.md](docs/design/architecture.md).

## Kiểm thử

```bash
pytest                          # unit test
pytest tests/e2e -m e2e         # Playwright: chạy cả kịch bản trên trình duyệt (khoảng 5 giây)
python tests/e2e/run_e2e.py     # bộ kiểm thử đầy đủ: nhiều cỡ màn hình, ngôn ngữ, what-if (vài phút)
```

## Phạm vi

Đây là nguyên mẫu trình diễn. RiceBridge Ops dùng kịch bản HTX và cảm biến mô phỏng, dữ liệu thời tiết đã cache và ảnh thước đo tổng hợp. Chỉ số mô phỏng không phải kết quả triển khai thực địa. Duyệt lịch tưới cần con người xác nhận.
