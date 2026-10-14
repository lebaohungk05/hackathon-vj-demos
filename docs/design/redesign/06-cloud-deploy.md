# 06 · Triển khai lên Azure Container Apps (DEP)

Tổng: 39 giờ (35 giờ nếu bỏ DEP-06 tùy chọn). Nhánh: `feat/dep-aca`. Phụ thuộc: M0, INF-02 và AGT-13 cho context duyệt. DEP-11/AGT-13 làm sớm; deploy khi M0 và các task nền này xong, không đợi M1/M2, để phát hiện lỗi môi trường rồi cập nhật dần.

## Mục tiêu

Demo chạy trên một URL HTTPS công khai, ổn định trong ngày thi, chỉ người trình bày điều khiển được, và tắt được sạch sau cuộc thi.

## Thiết kế

### Container

- Image `python:3.12-slim`, chạy bằng user không phải root, `pip install .` (không cài Playwright).
- Entrypoint dạng exec: `python -m ricebridge.server.app --host 0.0.0.0 --port 8080`; server đọc `RICEBRIDGE_MODE` từ env và có CLI override. Không đặt `${...}` trong JSON CMD rồi kỳ vọng shell tự mở rộng.
- `RICEBRIDGE_DATA_DIR=/app/data` chứa fixture/scenario/recording cố định, chỉ đọc. `RICEBRIDGE_RUNTIME_DIR=/app/runtime` chứa upload, cache và recording mới, user ứng dụng có quyền ghi. `WEB_DIR` lấy từ package đã cài; không suy data từ vị trí site-packages.
- Local mặc định dùng data/ và .cache/ ở source checkout. Runtime cloud là ổ tạm: mất khi restart, kể cả tin khán giả/bản ghi live; chỉ bản ghi demo đóng gói sẵn dùng để khôi phục. Đây là lựa chọn cho demo, không đáp ứng lưu bằng chứng thực địa.

### Container App

| Thiết lập | Giá trị |
| --- | --- |
| Replica/revision | `minReplicas: 1`, `maxReplicas: 1`, `activeRevisionsMode: single`, không chia traffic (trạng thái trong bộ nhớ) |
| Ingress | external, `targetPort: 8080`, chỉ HTTPS |
| Tài nguyên | 0,5 vCPU / 1 GiB |
| Secret | `aoai-key` (đặt bằng lệnh lấy key từ account Azure OpenAI), `presenter-token`, `audience-code` |
| Env | Azure/mode, data/runtime paths và budgets; key/token/code qua `secretRef` |
| Probe | liveness và readiness gọi `GET /api/health` |
| Registry | ACR qua user-assigned identity (INF-02) |

### Bảo vệ URL công khai

| Đối tượng | Cách vào | Được làm |
| --- | --- | --- |
| Người trình bày | Mở `https://<app>/?k=<PRESENTER_TOKEN>` → cookie `HttpOnly; Secure; SameSite=Strict`, redirect bỏ k; không ghi token vào log/referrer | Xem state/media, next, duyệt, reset, what-if, xuất bằng chứng |
| Khán giả | QR tới `/m?c=<AUDIENCE_CODE>` → phiên thiết bị server cấp, redirect bỏ c | POST message/photo và `GET /api/m/status/<item_id>` của chính thiết bị; không đọc state/log/media người khác |
| Người khác | – | Trang thông báo, không có dữ liệu |

Khi không đặt token, chỉ cho bind loopback. Server từ chối khởi động nếu bind địa chỉ ngoài loopback mà thiếu token; bật audience phải có mã tham gia. `/api/health` chỉ trả thông tin vận hành không nhạy cảm, không gọi Azure và không phụ thuộc worker đang chạy.

Phân quyền theo allowlist endpoint, gồm `/api/state`, `/api/verify`, `/api/testset`, `/api/forecast`, `/api/evidence.*`, `/media/*`, `/api/upload` và mọi API điều khiển. POST kiểm Origin cùng site. Duyệt bắt buộc gửi `plan_id`, `epoch`, `state_version`, chỉ nhận kế hoạch hiện tại đã commit và còn proposed; thiếu trường hoặc bản sao what-if/provisional đều bị từ chối.

## Task

| ID | Việc | File chính | Xong khi | Giờ | Phụ thuộc |
| --- | --- | --- | --- | --- | --- |
| DEP-01 | CLI host/port/mode và env PORT/RICEBRIDGE_MODE; chặn bind ngoài loopback khi thiếu token; health không gọi mạng/không giữ mutate lock | `server/app.py` | Test local, cloud có/thiếu token và mode override; health trả nhanh lúc agent/vision bận | 2 | M0 |
| DEP-02 | Cookie/token, constant-time compare, Origin, allowlist route/media; duyệt bắt buộc plan_id/epoch/state_version, cấm what-if/provisional; tách phiên audience | `server/app.py`, `web/` | Ma trận route người lạ/khán giả/presenter/local qua; thiếu/stale approval context bị từ chối; không lộ token trong log | 7 | DEP-01, AGT-13 |
| DEP-03 | Dockerfile/.dockerignore, exec entrypoint, data chỉ đọc/runtime writable, non-root; kiểm package sau pip install . | `Dockerfile`, `.dockerignore` | Container chạy hết stage, forecast offline, ảnh/what-if; ghi upload/cache đúng runtime; signal dừng tới Python | 4 | DEP-01, DEP-11, LLM-11 |
| DEP-04 | Container App theo bảng: single revision/không traffic split, paths/budgets, probes/secretRef; imageTag và output URL | Lệnh `az containerapp create` (mẫu ở [azure-create-resources.md](../../manual/azure-create-resources.md)) | Health HTTPS qua; chỉ revision hiện tại nhận traffic; restart được ghi nhận là mất phiên | 4 | INF-02, DEP-03 |
| DEP-05 | Script build và deploy: `az acr build -t ricebridge:<git-sha>` rồi `az containerapp update --image <acr>/ricebridge:<git-sha>`; sinh `presenter-token` và `audience-code` ngẫu nhiên nếu chưa có; in URL người trình bày | `infra/release.ps1`, `infra/release.sh` | Một lệnh từ máy dev ra bản mới trong < 5 phút | 3 | DEP-04 |
| DEP-06 | (Tùy chọn) GitHub Actions deploy khi merge vào `main`, đăng nhập Azure bằng OIDC (federated credential), không lưu secret Azure trong GitHub | `.github/workflows/deploy.yml` | Merge vào `main` tự ra bản mới | 4 | DEP-05 |
| DEP-07 | JSON stdout: run/item id, epoch/state_version, engine/source/fallback, queue/precheck/tool/final/total ms, token/request, commit/aborted; KQL chậm/fallback/lỗi | `agent/runner.py`, `docs/manual/cloud-runbook.md` | Truy vấn có dữ liệu; không log key/token, nội dung riêng tư hay ảnh base64 | 2 | DEP-04, AGT-06 |
| DEP-08 | Runbook deploy/key rotation/mode/reset/recovery/teardown; Skip cho lỗi live tại chỗ; đổi mode bằng env gây restart nên phải khôi phục phiên; budget không tự ngắt | `docs/manual/cloud-runbook.md` | Người khác theo được; mode replay đúng CLI/env; restart không âm thầm khôi phục approval cũ | 3 | DEP-05, DEP-12, AGT-09, AGT-11 |
| DEP-09 | Diễn tập trên URL cloud từ mạng 4G (giống điều kiện hội trường), đủ kịch bản 3 phút, kèm 1 lần giả lập Azure lỗi | `docs/report/qa-report.md` | Có ghi chép thời gian và sự cố | 2 | DEP-05, UI-06 |
| DEP-10 | Cập nhật `SECURITY.md` cho chế độ triển khai công khai: token, mã khán giả, giới hạn tần suất, xoay key | `SECURITY.md` | Review | 1 | DEP-02 |
| DEP-11 | Paths/config cho data và runtime; source checkout và package cài thường; đọc fixture cố định + cache overlay, tạo thư mục có quyền ghi | `paths.py`, `config.py`, `tests/unit/test_paths.py` | Test từ cwd khác/source checkout/site-packages; data read-only; upload/cache/recording chỉ ghi runtime | 4 | LLM-01 |
| DEP-12 | Diễn tập restart/redeploy/recovery với bản ghi đóng gói; đánh dấu session mới, hủy hàng đợi cũ và yêu cầu duyệt lại tường minh | `docs/manual/cloud-runbook.md`, `docs/report/qa-report.md` | Sau restart quay lại màn demo trong ≤ 60 giây; không tự duyệt, không nhận receipt/approval của epoch cũ | 3 | DEP-05 |

## Rủi ro

| Rủi ro | Cách giảm |
| --- | --- |
| Container khởi động lại giữa buổi làm mất trạng thái | 1 replica không ngăn được restart; DEP-12 diễn tập khôi phục bản ghi, báo mất phiên và duyệt lại |
| Lộ link người trình bày | Token chỉ nằm trong URL một lần rồi chuyển thành cookie; xoay bằng cách deploy lại với token mới |
| API key nằm trong secret của Container App | Chỉ người có quyền trên resource group đọc được; xoay key sau cuộc thi (runbook) |
| Mạng hội trường kém | URL công khai nên dùng được 4G; vẫn mang laptop chạy local `--stage` làm dự phòng |

Theo [Azure Container Apps revisions](https://learn.microsoft.com/en-us/azure/container-apps/revisions), revision mới có thể chạy trước khi chuyển traffic ngay cả ở single revision; không deploy giữa buổi nếu cần giữ phiên trong RAM.
