# ADR 0005: Chạy demo trên Azure Container Apps

- Trạng thái: đề xuất
- Ngày: 2026-10-14

## Bối cảnh

Khán giả cần nhắn tin và gửi ảnh từ điện thoại trong buổi trình diễn. Nếu chạy trên laptop, điện thoại phải vào cùng mạng LAN, mà Wi-Fi hội trường thường chặn kết nối giữa các máy. Server hiện là `ThreadingHTTPServer` giữ trạng thái trong bộ nhớ và chỉ nghe `127.0.0.1` ([ADR 0002](0002-stdlib-http-server.md)).

## Quyết định

- Chạy server trong một Azure Container App, minReplicas = maxReplicas = 1, activeRevisionsMode = single, không traffic split, ingress HTTPS. Không deploy giữa demo cần giữ phiên; single revision không đảm bảo không restart/mất RAM.
- Image lưu trong Azure Container Registry, Container App kéo image bằng user-assigned managed identity có role AcrPull.
- Mọi tài nguyên tạo bằng tay bằng Azure CLI theo hướng dẫn trong `docs/manual/azure-create-resources.md`, nằm trong một resource group để xóa một lần.
- URL được bảo vệ bằng PRESENTER_TOKEN đổi sang cookie dashboard và AUDIENCE_CODE đổi sang phiên thiết bị. Audience chỉ POST message/photo và GET status item của chính mình; không đọc state/log/media chung. Token/code được bỏ khỏi URL và không ghi log.
- Auth theo allowlist route/media; POST kiểm Origin; approval bắt buộc plan_id/epoch/state_version đã commit. Vai khán giả không cấp quyền làm cán bộ/người đo độc lập.
- Image pip install . với data chỉ đọc tại RICEBRIDGE_DATA_DIR và runtime writable tại RICEBRIDGE_RUNTIME_DIR, không dựa vào site-packages để tìm data. Runtime chứa upload/cache/recording mới, không commit dữ liệu cá nhân.
- Queue FIFO/receipt/idempotency/bounded memory ở server; limits thiết bị/IP/tổng phiên và token/request bổ sung. Health không gọi Azure hay chờ worker. CLI/env mode thống nhất.
- Chạy local mặc định nghe 127.0.0.1 không cần token. Server từ chối bind địa chỉ ngoài loopback nếu thiếu token; bật audience phải có mã tham gia.

## Hệ quả

- Giám khảo dùng 4G hoặc bất kỳ mạng nào; không phụ thuộc Wi-Fi hội trường.
- Không scale ngang được vì trạng thái nằm trong bộ nhớ. Đủ cho một buổi demo; triển khai thật cần lưu trạng thái ra ngoài.
- Restart/redeploy mất trạng thái, tin khán giả và recording runtime; runbook diễn tập khôi phục từ bản ghi đóng gói trong ≤ 60 giây, hủy receipt/job cũ và yêu cầu duyệt lại. Không hứa lưu bền hồ sơ thực địa.
- Có chi phí chạy liên tục cho 1 replica và ACR; tắt bằng `infra/teardown` sau cuộc thi.
- M3 cần container chạy đủ scenario/ảnh/what-if offline, ma trận auth, mobile queue/status/limits và diễn tập 4G/provider-error/restart theo [09](../redesign/09-acceptance.md); health 200 chưa đủ.
