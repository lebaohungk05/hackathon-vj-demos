# 08 · Tốc độ và đa ngôn ngữ (PERF)

Tổng: 21 giờ. Nhánh: `feat/perf-i18n`. PERF-01 là P0 làm trước AGT-06; schema vi/en/ja chốt ở AGT-05. Các task đo/hiển thị hoàn thành cùng M2–M3.

## Mục tiêu

- Receipt nhận tin/hàng đợi hiện trên màn hình trong ≤ 1 giây. Khi job bắt đầu, prechecks publish trong < 1 giây; phản hồi hiển thị đầu tiên tính từ lúc gửi ≤ 5 giây. Các mốc này không thay thế thời gian hoàn thành hay thời gian chờ hàng đợi.
- Model trả thẳng vi/en/ja trong cùng một lần chạy; bỏ lượt dịch riêng và `llm/translate.py`.

## Task

| ID | Việc | File chính | Xong khi | Giờ | Phụ thuộc |
| --- | --- | --- | --- | --- | --- |
| PERF-01 | **P0**: prechecks read-only trước runner, chặn input nguy hiểm/nguồn giả, parser quy tắc và giới hạn vật lý/thời gian; publish progress tách state, không ghi log accepted | `agent/prechecks.py`, `engine.py` | Publish < 1 giây khi job bắt đầu; reject không advance/đổi plan/log; quy tắc an toàn không phụ thuộc model/filter | 4 | AGT-01, LLM-11 |
| PERF-02 | Hoàn thiện text vi/en/ja theo schema AGT-05; glossary đã kiểm và mẫu tất định; validation ngữ nghĩa AGT-14 cho từng ngôn ngữ, kể cả số viết bằng chữ | `agent/prompts.py`, `agent/validation.py`, `i18n.py` | J sau live/replay/rules thấy đủ ngôn ngữ; sai dấu/đơn vị/thửa/ngày/hành động bị thay bằng mẫu tất định | 4 | AGT-05, AGT-14 |
| PERF-06 | Thêm `input_gloss {en, ja}` vào `FINAL_SCHEMA`: bản dịch tin nhắn đến (câu nông dân, cán bộ HTX gửi) để giữ mục "Original Vietnamese" trong giao diện (`app.js`, `translationLine`). Ở `RulesPolicy` thì để trống và giao diện chỉ hiện bản gốc | `agent/prompts.py`, `agent/runner.py`, `web/app.js` | Ở EN/JA, tin nhắn "Thửa bà Sáu, nước ba phân." hiện bản dịch, mở ra thấy bản gốc tiếng Việt | 2 | PERF-02 |
| PERF-03 | Sau khi recording mới đủ vi/en/ja, xóa bộ dịch tương thích đã port ở LLM-10 và translations.json; publish không gọi model; giữ editorial còn dùng | `llm/translate.py`, `server/app.py` | Không còn job model dịch riêng; cả 3 ngôn ngữ offline/live/rules qua; import cũ đã gỡ hết | 2 | PERF-02, PERF-06, INB-07, LLM-10 |
| PERF-04 | Benchmark ≥ 10 lần/loại/deployment, lượt đồng thời và provider chậm/429: receipt, queue_wait, precheck, tool/vision, final, total, token/request/fallback; trung vị/p95/max | `scripts/latency_bench.py`, `docs/report/qa-report.md` | Text không chờ queue: median hoàn thành ≤ 20 giây, job ≤ 60 giây gồm fallback; receipt ≤ 1 giây, hiển thị đầu ≤ 5 giây; công bố lỗi/fallback và cỡ mẫu | 4 | AGT-07, AGT-16, AUD-09, AUD-10 |
| PERF-05 | Giảm chu kỳ poll `/api/state` khi có job đang chạy (ví dụ 300 ms), trở lại bình thường khi rảnh | `web/app.js` | Bước mới hiện ≤ 0,5 giây sau khi server publish | 2 | UI-02 |
| PERF-07 | Bộ kiểm ngữ nghĩa đa ngôn ngữ: cặp số/thửa, dấu/đơn vị, ngày bơm, hành động và thuật ngữ; review thủ công mẫu VI/EN/JA, không chỉ check đủ key | `data/evals/i18n.json`, `tests/unit/test_i18n_semantics.py`, `docs/report/qa-report.md` | Các ca đổi nghĩa/viết số bằng chữ bị bắt; mẫu reviewed giữ nghĩa qua live/replay/rules; không ghi câu chưa validate | 3 | PERF-02, PERF-06 |

## Rủi ro

- Viết đủ ba ngôn ngữ làm đầu ra dài hơn. Giới hạn độ dài/tokens, dùng glossary và mẫu tất định vi/en/ja khi vượt ngân sách; không đổi sang JA viết nền vì sẽ vi phạm hợp đồng M2–M3. Muốn thay đổi phải sửa schema, UI, recording và tiêu chí nghiệm thu cùng một PR.
- Model `fast` chọn công cụ kém ở ca khó. Đã có cơ chế nâng lên `strong` ở AGT-07.

Đo theo [09](09-acceptance.md): một receipt sớm không được báo cáo như agent đã hoàn thành. P95 trên cỡ mẫu nhỏ chỉ mang tính mô tả; không dùng để suy ra độ tin cậy triển khai thực địa.
