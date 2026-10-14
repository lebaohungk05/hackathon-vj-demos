# RiceBridge Ops

Demo AI agent giúp hợp tác xã (HTX) ở Đồng bằng sông Cửu Long điều phối tưới ướt khô xen kẽ (AWD) và lưu bằng chứng từng thửa ruộng. Giao diện tiếng Việt, tiếng Nhật và tiếng Anh. Repo chứa mã nguồn, dữ liệu mẫu, câu trả lời LLM đã cache và mô-đun mô phỏng cần thiết để chạy demo.

| Demo | Nội dung | Địa chỉ mặc định |
| --- | --- | --- |
| **RiceBridge Ops** | Hỗ trợ HTX điều phối tưới lúa, đối chiếu thời tiết và số đo, xử lý dữ liệu mâu thuẫn và trình lịch tưới cho người duyệt. | http://127.0.0.1:8766 |

## Giao diện

UI lấy phong cách từ slide thuyết trình (navy và vàng). Họa tiết Việt–Nhật được vẽ bằng SVG, dùng được offline. Theme nằm trong `demo/web/deck-theme.css`, có bố cục dọc cho màn hình điện thoại.

## Cài đặt

Yêu cầu **Python 3.10+**. Chạy các lệnh sau tại thư mục gốc repo:

```bash
python -m venv .venv
```

Kích hoạt môi trường trên Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Trên macOS/Linux:

```bash
source .venv/bin/activate
```

Cài thư viện và trình duyệt cho kiểm thử:

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## Chạy RiceBridge Ops

```bash
python 06-ricebridge-ops/demo/start_demo.py --stage --open
```

`--stage` dùng cache và bộ luật, không cần gọi LLM trực tiếp. Dùng phím mũi tên để đi qua kịch bản, **W** mở thử nghiệm giả định, **C** đổi góc nhìn, **J** đổi ngôn ngữ và **R** đặt lại.

[Hướng dẫn chi tiết RiceBridge Ops](06-ricebridge-ops/demo/README.md)

## LLM trực tiếp (tùy chọn)

RiceBridge Ops hỗ trợ Claude CLI đã cài đặt và đăng nhập. Chạy `python 06-ricebridge-ops/demo/start_demo.py --mode auto --open` (ưu tiên cache) hoặc `--mode live` (gọi trực tiếp). Các cuộc gọi này cần mạng và tài khoản phù hợp.

## Cấu trúc

```text
06-ricebridge-ops/
  demo/   # Backend, web UI, cache, thời tiết và ảnh thước đo mẫu
  sim/    # Mô hình cân bằng nước, giai đoạn cây trồng và lập lịch
```

Giữ nguyên quan hệ giữa `demo/` và `sim/` khi di chuyển. Log, kết quả chạy trực tiếp, ảnh chụp kiểm thử và video có thể được tạo lại tại máy và được bỏ qua bởi Git.

## Kiểm thử

Chạy trong thư mục `06-ricebridge-ops/demo`:

```bash
python tests/test_api_contract.py
python tests/e2e_test.py
```

Kiểm thử E2E cần Playwright và Chromium; xem README của demo để biết các tùy chọn.

## Phạm vi

Đây là nguyên mẫu trình diễn. RiceBridge Ops dùng kịch bản HTX và cảm biến mô phỏng, dữ liệu thời tiết đã cache và ảnh thước đo tổng hợp. Chỉ số mô phỏng không phải kết quả triển khai thực địa. Duyệt lịch tưới cần con người xác nhận.
