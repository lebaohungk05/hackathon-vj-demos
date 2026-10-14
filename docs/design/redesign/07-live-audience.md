# 07 · Khán giả tham gia trực tiếp (AUD)

Tổng: 40 giờ. Nhánh: `feat/aud-live`. Phụ thuộc: DEP-02, AGT-06, UI-03. Queue/status/limits là bắt buộc khi bật audience, không phải tính năng tùy chọn.

## Mục tiêu

Giám khảo tự thử agent: quét QR, nhắn tin như nông dân, chụp thước đo thật, hỏi giả định bằng câu tự nhiên, và thấy agent xử lý ngay trên màn hình lớn.

## Thiết kế

- Trang `/m` cho điện thoại: chọn vai trò (Hộ thửa 1–6 hoặc "Khách"), ô nhắn tin, nút chụp ảnh (`<input type="file" accept="image/*" capture="environment">`), hiển thị trạng thái tin nhắn của chính mình.
- Mỗi điện thoại có phiên thiết bị ngẫu nhiên do server cấp trong cookie HttpOnly/Secure/SameSite; mã tham gia được đổi thành phiên rồi bỏ khỏi URL. Phiên này kiểm quyền xem receipt và giới hạn tần suất, không chứng minh danh tính nông dân. Cookie mới không vượt được giới hạn tổng/IP.
- Tin nhắn thành InboxItem với source/channel/received_at/evidence_id do server gán. Chọn vai trò chỉ là mô phỏng; không được tự khai kind station_notice/sensor, nguồn trusted hay independent. Kết quả là dữ liệu demo, không tính là người đo thực địa trong completeness.
- API nhận trả `202` cùng `item_id`, `epoch`, `status_url` và vị trí hàng đợi trong ≤ 1 giây; chờ worker không giữ kết nối POST. `GET /api/m/status/<item_id>` chỉ trả trạng thái/kết quả ngắn của chính thiết bị. Không mở `/api/state` cho khán giả.
- Hàng đợi FIFO ở server, một worker ghi trạng thái. Giới hạn mặc định: 20 mục chờ tổng, 2 mục đang chờ/thiết bị, 1 lần gửi/10 giây/thiết bị, 10 lần/phút/IP và 30 lần/phút/phiên demo. Giá trị cấu hình được; queue đầy hoặc quá tần suất trả 429 với retry-after. Giới hạn token/request của AGT-16 vẫn áp dụng bên dưới.
- Client gửi khóa idempotency cho mỗi thao tác; retry cùng khóa/nội dung trả lại cùng receipt, khác nội dung bị từ chối. Reset hủy mục chờ và đánh dấu receipt cancelled; item_id epoch cũ không chạy lại. Công tắc tắt nhận mới không tự mất các mục đã nhận; reset/hủy có thao tác riêng.
- Ảnh validate decode JPEG/PNG, kích thước byte và số pixel trước xử lý; trích giờ EXIF (đánh dấu metadata người gửi, không phải giờ đã xác thực), hash bản gốc rồi bỏ metadata GPS trước lưu/gửi model. Lưu hash bản đã chuẩn hóa; không lưu byte ảnh gốc có GPS. Ảnh không phải thước/không đọc được thì hỏi lại, không suy số từ kịch bản.
- What-if bằng câu tự nhiên chỉ có trên dashboard của người trình bày: model có thêm công cụ `run_what_if(kind, params)` **chỉ trong chế độ what-if**. Công cụ gọi `Demo.what_if()`, vẫn bị chặn bởi `MAX_WHATIF_RAIN_MM`, `MAX_PUMP_SHIFT_DAYS`, không ghi nhật ký, không duyệt được.

## Task

| ID | Việc | File chính | Xong khi | Giờ | Phụ thuộc |
| --- | --- | --- | --- | --- | --- |
| AUD-01 | Trang /m: vai mô phỏng, text/ảnh, receipt và poll status có backoff, queued/running/done/rejected/cancelled/error; vi/en/ja | `web/m.html`, `web/m.js`, CSS | Android/iOS qua; reload/retry không gửi trùng; chỉ thấy receipt của mình | 6 | DEP-02, AUD-02, AUD-10 |
| AUD-02 | Message/photo API theo phiên thiết bị; text ≤ 300 ký tự, ảnh ≤ 5 MB và MAX_IMAGE_PIXELS; validator ảnh dùng chung với upload presenter; bỏ GPS/giữ giờ riêng; provenance và enqueue | `server/app.py`, `agent/inbox.py` | Mã sai, source/kind giả, quá byte/pixel, ảnh hỏng/không phải thước đều xử lý rõ; POST nhận receipt ≤ 1 giây | 6 | DEP-02, AUD-09, AUD-11, INB-01 |
| AUD-03 | Mã QR trên dashboard trỏ tới URL công khai + mã khán giả; sinh SVG phía server bằng thư viện `segno` (thuần Python) | `server/app.py`, `web/app.js`, `pyproject.toml` | Quét bằng điện thoại mở đúng `/m` | 2 | AUD-01 |
| AUD-04 | Công tắc của người trình bày: bật/tắt nhận tin nhắn khán giả (phím **A**); khi tắt, `/m` báo tạm dừng | `server/app.py`, `web/app.js` | E2E: tắt → API trả 423, trang `/m` hiện thông báo | 2 | AUD-02 |
| AUD-05 | Công cụ `run_what_if` + ô câu tự nhiên trong phòng what-if (phím **W**), đặt cạnh form có cấu trúc của UI-09; câu không chuyển được thành tham số hợp lệ thì gợi ý 3 mẫu câu | `agent/tools.py`, `agent/runner.py`, `web/app.js` | 5 câu mẫu (mưa 60 mm, thửa 2 trổ bông, dời bơm 2 ngày…) ra đúng tham số; câu vượt giới hạn bị chặn | 5 | AGT-06, UI-09 |
| AUD-06 | Đạo cụ: ống nhựa dán thước trong hộp nước; chụp 10 ảnh trong nhiều điều kiện ánh sáng, lưu vào `data/vision/props/`; chạy đánh giá đọc ảnh | `data/vision/props/`, `scripts/vision_evaluate.py`, `docs/manual/demo-guide.md` | ≥ 8/10 ảnh đọc đúng trong khoảng ±1 cm | 4 | LLM-05 |
| AUD-07 | 3 điện thoại đồng thời, retry/reload, cookie mới, queue đầy, ảnh không phải thước/chèn chỉ dẫn; Skip/reset khi có mục chờ; chạy qua cloud 4G | `docs/report/qa-report.md`, `tests/unit/test_audience.py` | Không ghi trùng/nhầm chủ receipt; input bị từ chối không đổi log/plan; queue không tăng vô hạn; số liệu queue/latency có trong báo cáo | 3 | AUD-02, AUD-09, AUD-10, AUD-11, DEP-05, AGT-15 |
| AUD-08 | Cập nhật kịch bản 3 phút: thêm đoạn 30 giây cho giám khảo tự nhắn và chụp thước | `docs/manual/demo-guide.md` | Diễn tập vừa giờ | 1 | AUD-07 |
| AUD-09 | Queue FIFO server, item receipt, khóa idempotency, quota queue và worker đơn; dashboard thấy queued item ngay; reset hủy queue theo epoch | `server/app.py`, `tests/unit/test_queue.py` | Agent đang bận vẫn nhận nhanh; retry chỉ chạy một lần; reset không chạy job cũ; đầy queue trả 429 | 5 | DEP-02, AGT-13, INB-01 |
| AUD-10 | GET status theo item_id + chủ phiên thiết bị; TTL/quota receipt, trả kết quả ngắn, không lộ state/ảnh/người gửi khác | `server/app.py`, `tests/unit/test_audience.py` | Thiết bị khác không đọc được dù biết item_id; receipt cũ báo cancelled/expired, không kích hoạt job | 3 | AUD-02 |
| AUD-11 | Limiter thiết bị/IP/tổng phiên và byte/pixel/queue; tôn trọng reverse proxy tin cậy; reset nghiệp vụ không xóa budget token/request phiên vận hành | `config.py`, `server/app.py` | Cookie mới không vượt limit tổng; source header tự khai không đổi quyền/IP; queue và receipt giữ bounded memory | 3 | DEP-02, LLM-01 |

## Rủi ro

| Rủi ro | Cách giảm |
| --- | --- |
| Khán giả spam hoặc gửi nội dung xấu | Limit thiết bị/IP/tổng phiên + queue/token budgets; kiểm tại công cụ; filter và công tắc bổ sung |
| Ảnh có thông tin cá nhân | Bỏ GPS, giới hạn truy cập/TTL, không log base64, không commit upload hay recording cá nhân |
| Gọi live chậm khi nhiều người nhắn | Receipt/progress sớm, giới hạn queue, đo queue_wait riêng; thời gian hoàn thành không được gọi là phản hồi đầu tiên |

Tiêu chí nghiệm thu đầy đủ ở [09](09-acceptance.md). Trong stage, giám khảo gửi ảnh/câu chưa có recording vẫn nhận receipt nhưng chạy quy tắc/hỏi lại offline; muốn thử vision trực tiếp phải dùng auto có cấu hình hoặc live.
