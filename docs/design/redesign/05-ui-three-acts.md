# 05 · Giao diện 3 màn (UI)

Tổng: 42 giờ. Nhánh: `feat/ui-acts`. Phụ thuộc: INB-05. UI-02 và UI-03 bắt đầu được từ dữ liệu mẫu của AGT-03.

## Mục tiêu

Người xem lúc nào cũng biết agent đang làm gì và vì sao. `app.js` không còn câu kết luận nghiệp vụ nào.

## Thiết kế

### 3 màn

| Màn | Đầu vào | Khán giả thấy |
| --- | --- | --- |
| 1 · Ngày bình thường | cảm biến F2, dự báo | Agent xem toàn cụm, chiếu cân bằng nước, lập lịch lượt bơm thứ Sáu |
| 2 · Dữ liệu lộn xộn | mưa 44 mm, ảnh F2 cũ, ống đo thứ hai, giọng nói cho Bà Sáu | Agent tự phát hiện ảnh cũ, tìm người đo độc lập, hiểu "nước ba phân" |
| 3 · Sự cố và duyệt | trạm dời lịch bơm | Lập lại kế hoạch → người phụ trách trạm duyệt → bằng chứng carbon, kiểm tra chuỗi hash |

### Dải 4 bước

```text
[ Quan sát ] → [ Kiểm tra ] → [ Quyết định ] → [ Cần người duyệt ]
 đầu vào +      công cụ read    công cụ propose   needs_human + nút duyệt
 prechecks
```

Mỗi lệnh gọi công cụ hiện thành một dòng theo thứ tự publish. Giữ màu: tím là LLM, xanh ngọc là công cụ tất định, vàng hổ phách là con người. Đây là trace công cụ/bằng chứng, không hiển thị suy luận nội bộ của model. Mỗi run/bước ghi rõ live/replay/rules và provisional/committed/aborted; nhánh bị bỏ không được trình bày như kết quả đã ghi.

Nút duyệt chỉ mở cho kế hoạch hiện tại đã commit, gửi đủ plan_id/epoch/state_version. Lời giải thích phải tham chiếu đúng kế hoạch này. Snapshot progress và queue hiển thị được khi worker bận; không chờ LLM để phản hồi việc đã nhận tin.

### Ô dựng theo kết quả công cụ

| Kết quả | Ô hiển thị |
| --- | --- |
| `read_gauge_photo` | Ảnh, số đọc, độ tin cậy, thời gian EXIF, cờ |
| `compare_sources` | Thanh so sánh các nguồn với ngưỡng 5 cm |
| `project_water_balance` | Biểu đồ nhỏ mực nước tới lượt bơm |
| `submit_reading` | Kết luận của rào chắn và lý do |
| `find_independent_measurers` + `request_remeasure` | Người được chọn, người bị loại, lý do |
| `draft_plan` | Bảng kế hoạch và thay đổi so với kế hoạch trước |

Thông tin đặc thù như "Bà Sáu 74 tuổi, không có điện thoại thông minh" lấy từ `FieldSpec.note` qua `get_field_state`, không viết trong JS.

### Những phần phải giữ khi viết lại `app.js`

Các phần dưới đây không thuộc luồng agent nhưng nằm trong `app.js`, nên dễ bị hỏng khi viết lại phần giữa màn hình:

| Phần | Chỗ trong code hiện tại | Task |
| --- | --- | --- |
| Màn carbon (phím **C**): mức đủ bằng chứng từng thửa, kiểm tra chuỗi hash, giả lập sửa dữ liệu, xuất CSV/JSON | `renderCarbon()`, `verify()`, `/api/verify`, `/api/evidence.*` | UI-08 |
| Phòng what-if (phím **W**): mưa, trổ bông, dời bơm, ảnh | `Demo.what_if()` với 4 loại `rain`, `flowering`, `pump`, `photo` | UI-09 |
| Hàng đợi tin nhắn khi agent bận, nút "Skip LLM" | hiện là queue phía JS; chuyển sang queue/receipt server ở AUD-09, `/api/cancel` hủy theo run | UI-03, UI-11 |
| Biểu đồ thời tiết, chuyển ngôn ngữ, phím tắt | `weather-chart.js`, `setLang()`, xử lý phím | UI-03, UI-04 |

### Đối chiếu với các luồng hiện tại

Mỗi luồng trong kịch bản 3 phút hiện nay ([demo-guide.md](../../manual/demo-guide.md)) phải còn chạy được sau khi đổi. UI-10 biến bảng này thành test e2e.

| Luồng hiện tại | Trong cấu trúc mới |
| --- | --- |
| Cảm biến F2 + dự báo → lập lịch | `InboxItem(sensor)` → `draft_plan` |
| Mưa 44 mm → hoãn bơm | `InboxItem(weather)` → `project_water_balance` |
| Ảnh −8 cm → giữ ảnh, xin đo độc lập | `read_gauge_photo`, `compare_sources`, `submit_reading`, `find_independent_measurers`, `request_remeasure` |
| Ống đo thứ hai → đóng xung đột, ảnh bị đánh dấu đọc sai và vẫn lưu | `submit_reading` (gọi `resolve_pending`) |
| Bà Sáu, HTX ghi hộ bằng giọng nói | `InboxItem(voice)` + `FieldSpec.note` |
| Trạm dời lịch → lập lại kế hoạch | `InboxItem(station_notice)`, ngày lấy từ thông báo |
| Chỉ người phụ trách trạm duyệt | Không có công cụ duyệt (AGT-04); bỏ tự duyệt khi đến ngày bơm (INB-08) |
| Tin nhắn chèn chỉ dẫn bị từ chối; "thửa 4 âm năm phân" bị giữ | `prechecks` + cùng luồng `InboxItem` |
| What-if | UI-09 + AUD-05 |
| Màn carbon, chuỗi hash, giả lập sửa dữ liệu | UI-08 |
| Chuyển EN/JA/VI, bản dịch tin nhắn đến | PERF-02, PERF-06 |
| Skip LLM, hàng đợi | AGT-11, UI-03 |

## Task

| ID | Việc | File chính | Xong khi | Giờ | Phụ thuộc |
| --- | --- | --- | --- | --- | --- |
| UI-01 | `renderRail()` hiện 3 màn từ `acts`, chấm nhỏ cho từng đầu vào; phím 1–3 nhảy theo màn | `web/app.js`, `web/index.html` | Điều hướng bằng phím đúng ở cả 3 màn | 4 | INB-01 |
| UI-02 | Thành phần `pipelineStrip(run)`: 4 ô, ô đang chạy sáng lên, mỗi ô hiện 3 dòng mới nhất, phần còn lại thu gọn; mỗi dòng có "Vì sao?" mở tham số và kết quả | `web/app.js`, CSS | Bước mới hiện trong ≤ 1 nhịp poll sau khi server publish | 6 | AGT-03 (dữ liệu mẫu) |
| UI-03 | cardFor 6 loại kết quả từ tool output; bỏ focal/kết luận viết sẵn; giữ trải nghiệm queued/Skip/biểu đồ, dùng receipt server khi AUD-09 có, tránh flush tạo lần gửi thứ hai | `web/app.js` | Không kết luận nghiệp vụ viết sẵn; Skip/rules/replay có nhãn; queued message retry không gửi trùng | 8 | UI-02, INB-05 |
| UI-04 | Nhãn mới cho vi/en/ja | `web/i18n.js` | Không còn nhãn thiếu ở cả 3 ngôn ngữ (test e2e kiểm) | 2 | UI-03 |
| UI-05 | Cập nhật `test_smoke.py` và `run_e2e.py`: 4 cỡ màn hình (1920×1080 → 1280×720) × 3 ngôn ngữ, đi hết 3 màn và duyệt | `tests/e2e/` | Qua | 4 | UI-04 |
| UI-06 | Viết lại kịch bản 3 phút trong `demo-guide.md`; chụp lại ảnh màn hình bằng `scripts/capture.py` | `docs/manual/demo-guide.md`, `outputs/` | Diễn tập vừa 3 phút | 3 | UI-05 |
| UI-07 | Thử với 2–3 người ngoài nhóm: xem một lần rồi kể lại 3 màn và vai trò của con người; ghi lại chỗ khó hiểu và sửa | `docs/report/qa-report.md` | Có ghi chép và các sửa đổi theo đó | 2 | UI-06 |
| UI-08 | Carbon view/hash/tamper/export; provenance tool/deployment/run/evidence; completeness theo kế hoạch hiện tại; nhãn dữ liệu mô phỏng/khán giả và giới hạn hash rõ ràng | `web/app.js` (`renderCarbon`, `verify`) | C → verify/tamper/export qua; duyệt cũ không làm plan mới đủ; không gọi ảnh audience là bằng chứng thực địa | 3 | UI-03, INB-11 |
| UI-09 | 4 what-if rain/flowering/pump/photo trên RunContext sandbox riêng; cùng cardFor, nhãn thử nghiệm không ghi bằng chứng/không duyệt; callback muộn không chạm phiên chính | `web/app.js`, `server/app.py` | Cả 4 chạy; trước/trong/sau, cancel/lỗi/đóng/reset đều không đổi trạng thái nghiệp vụ chính; request duyệt sandbox bị chặn | 3 | UI-03, AGT-13 |
| UI-10 | E2E luồng cũ theo bảng đối chiếu, với các bước duyệt tường minh và baseline sửa lỗi; thêm no-approval, Skip/fallback và bật lại replay sau reset | `tests/e2e/test_legacy_flows.py` | Qua CI dưới 60 giây; check kết quả nghiệp vụ và kế hoạch/ref, không khóa câu chữ của model | 4 | UI-08, UI-09, UI-11, INB-06, INB-07 |
| UI-11 | Trạng thái queued/provisional/aborted/committed và provenance; approval context đầy đủ; nhánh lỗi vẫn xem trace nhưng không duyệt/hiển thị đã ghi | `web/app.js`, `tests/e2e/test_run_states.py` | Worker bận vẫn có progress; Skip/reset không hiện approval stale; giải thích và plan_id khớp; không nhầm replay thành live | 3 | UI-03, AGT-11, DEP-02 |

## Rủi ro

- Ô dựng chung kém đẹp hơn ô dựng tay. Có thể thêm biến thể "hero" cho `read_gauge_photo` và `draft_plan`.
- Poll chậm làm mất cảm giác "đang suy nghĩ". Giảm chu kỳ poll khi có job đang chạy (PERF-05).
