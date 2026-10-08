# Hackathon VJ — MinnaAccess & RiceBridge Ops

Hai demo AI agent với giao diện tiếng Việt, tiếng Nhật và tiếng Anh. Repo chứa mã nguồn, dữ liệu mẫu, câu trả lời LLM đã cache và các mô-đun mô phỏng cần thiết để chạy demo.

| Demo | Nội dung | Địa chỉ mặc định |
| --- | --- | --- |
| **MinnaAccess** | Agent dùng bàn phím để tìm rào cản tiếp cận trên cổng dịch vụ công giả lập, đề xuất bản sửa, chờ người duyệt và kiểm tra lại. | http://127.0.0.1:8765 |
| **RiceBridge Ops** | Hỗ trợ HTX điều phối tưới lúa, đối chiếu thời tiết và số đo, xử lý dữ liệu mâu thuẫn và trình lịch tưới cho người duyệt. | http://127.0.0.1:8766 |

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

Cài thư viện và trình duyệt cho MinnaAccess/kiểm thử:

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## Chạy MinnaAccess

```bash
python 32-minnaaccess/demo/start_demo.py
```

Trình duyệt tự mở dashboard. Chọn **Recorded run** để xem bản ghi hoặc **Live run** để agent chạy trên trang giả lập. Chế độ **Cached replies** dùng câu trả lời có sẵn; người dùng duyệt từng bản sửa. CAPTCHA được chuyển cho người xử lý.

Kiểm tra điều kiện chạy:

```bash
python 32-minnaaccess/demo/start_demo.py --check
```

[Hướng dẫn chi tiết MinnaAccess](32-minnaaccess/demo/README.md)

## Chạy RiceBridge Ops

Mở terminal thứ hai nếu muốn chạy đồng thời cả hai demo:

```bash
python 06-ricebridge-ops/demo/start_demo.py --stage --open
```

`--stage` dùng cache và bộ luật, không cần gọi LLM trực tiếp. Dùng phím mũi tên để đi qua kịch bản, **W** mở thử nghiệm giả định, **C** đổi góc nhìn, **J** đổi ngôn ngữ và **R** đặt lại.

[Hướng dẫn chi tiết RiceBridge Ops](06-ricebridge-ops/demo/README.md)

## LLM trực tiếp (tùy chọn)

Hai demo hỗ trợ Claude CLI đã cài đặt và đăng nhập. Với MinnaAccess, chọn **Live Claude calls** trong giao diện. Với RiceBridge Ops, chạy `python 06-ricebridge-ops/demo/start_demo.py --mode auto --open` (ưu tiên cache) hoặc `--mode live` (gọi trực tiếp). Các cuộc gọi này cần mạng và tài khoản phù hợp.

## Cấu trúc

```text
32-minnaaccess/
  demo/   # Dashboard, agent, mock portal, cache và replay
  sim/    # Mô phỏng, kết quả và axe-core dùng trong demo
06-ricebridge-ops/
  demo/   # Backend, web UI, cache, thời tiết và ảnh thước đo mẫu
  sim/    # Mô hình cân bằng nước, giai đoạn cây trồng và lập lịch
```

Giữ nguyên quan hệ giữa `demo/` và `sim/` khi di chuyển. Log, kết quả chạy trực tiếp, ảnh chụp kiểm thử và video có thể được tạo lại tại máy và được bỏ qua bởi Git.

## Kiểm thử

Chạy trong từng thư mục demo:

```bash
python tests/test_api_contract.py
python tests/e2e_test.py
```

Kiểm thử E2E cần Playwright và Chromium; xem README từng demo để biết các tùy chọn.

## Phạm vi

Đây là nguyên mẫu trình diễn. MinnaAccess dùng cổng dịch vụ công giả lập và dữ liệu giả; không gửi hồ sơ thật. RiceBridge Ops dùng kịch bản HTX và cảm biến mô phỏng, dữ liệu thời tiết đã cache và ảnh thước đo tổng hợp. Chỉ số mô phỏng không phải kết quả triển khai thực địa. Quyết định sửa trang hoặc duyệt lịch tưới cần con người xác nhận.
