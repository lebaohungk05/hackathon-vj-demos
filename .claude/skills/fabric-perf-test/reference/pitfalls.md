# Bẫy đã gặp khi đo hiệu năng DAX trên Fabric

Tài liệu tra cứu của skill `fabric-perf-test`. Gộp từ hai nguồn thật đã chạy:
`docs/manual/25-how-to-capture-dax-workload.md` và `docs/reports/25-performance-load-testing/`.
Mỗi mục: triệu chứng → nguyên nhân gốc → cách chặn.

> Các bẫy về Load Test (đẩy tải, đọc throttle capacity) đã bị bỏ khỏi tài liệu này (2026-09-17) —
> skill không còn bao gồm Load Test. Tham khảo lịch sử: `docs/reports/27-load-test-v0.md`.

---

## Performance Test (capture, trích DAX, chạy notebook/pipeline)

### 1. `_x000D_` làm hỏng mọi query — lỗi nguy hiểm nhất, dễ chẩn đoán nhầm

**Triệu chứng**: mọi combo (model × cache type × queryId) fail đồng loạt với
`QueryBegin event with SspropInitAppName 'SemPy' not found yet` sau khi hết toàn bộ ngân sách retry
(60 lần × 3s) — nhìn giống hệt lỗi "AS trace không kịp subscribe".

**Đường dò sai đã đi qua trước khi tìm ra nguyên nhân thật** (mất thời gian, để tránh lặp lại):
1. Tăng `delay` của trace 3s → 8s — không đổi gì, và bản chất retry (không thấy event vs thấy
   muộn) vốn không khớp với một vấn đề delay ngay từ đầu.
2. Nghi ngờ quyền workspace/capacity-admin — loại trừ bằng notebook chẩn đoán chạy một query
   `EVALUATE {1}` đơn giản qua đúng cơ chế trace, bắt được `QueryBegin`/`QueryEnd` hoàn hảo trên cả
   hai workspace.
3. **Nguyên nhân thật**: `openpyxl` escape ký tự `\r` thành chuỗi `_x000D_` khi ghi cell Excel, và
   **không ai giải mã ngược** khi đọc lại (kể cả `pandas.read_excel` lẫn Fabric). Performance
   Analyzer luôn xuất `\r\n`, nên mọi DAX multi-line sau khi qua Excel bị chèn literal `_x000D_` —
   không phải DAX hợp lệ, engine từ chối trước khi kịp phát sinh trace event. Vì sao cơ chế trace
   tự nó test sạch: query test `EVALUATE {1}` không có `\r` nên không bị dính lỗi.

**Cách chặn**: `extract_dax_queries_for_perf_test.py` đã tự
`query_text.replace("\r\n", "\n").replace("\r", "\n")` trước khi ghi mỗi dòng. Nếu viết lại script
trích DAX tương tự, nhớ làm bước này trước — DAX không phân biệt CR vs LF thuần.

### 2. `queryId` dạng chuỗi làm `TypeError` giữa lúc chạy

**Triệu chứng**: crash giữa lúc chạy notebook, liên quan phép so `queryId`.

**Nguyên nhân**: notebook gọi `int(row["queryId"])` khi tổng hợp log table và so
`start_query_id <= qid <= stopQueryIdsAt` với giá trị int trong config.

**Cách chặn**: cột `queryId` luôn là số nguyên `1..N`, không phải chuỗi kiểu `"q0001"`.
`extract_dax_queries_for_perf_test.py` và `select_sample_queries.py` đều đã làm đúng — đừng sửa
lại thành chuỗi.

### 3. `stopQueryIdsAt` mặc định 99

**Triệu chứng**: notebook báo "hoàn tất" dù file Excel có hàng trăm query.

**Nguyên nhân**: tham số `stopQueryIdsAt` trong `additional_arguments` mặc định chỉ 99 — không tự
suy ra từ số dòng file.

**Cách chặn**: set đúng bằng tổng số query của model đó (`create_dax_perf_notebooks.py` đã tính từ
`query_count`/`stop_at` trong `PHASES`).

### 4. Gộp nhiều model vào một file Excel làm fail toàn bộ

**Triệu chứng**: DAX của model A chạy fail trên model B, lỗi tham chiếu bảng/cột không tồn tại.

**Nguyên nhân**: vòng lặp thực thi query của notebook chạy **mọi dòng trong file × mọi model
trong `models`**, không có cột lọc theo model nào. Ba model của dự án này lệch số query
(866/241/392), nên gộp vào 1 sheet nhiều cột (cách tool hỗ trợ) sẽ để lại hàng nghìn ô trống mà
vòng lặp vẫn chạy qua và log fail.

**Cách chặn**: luôn tách 1 file Excel riêng cho mỗi model, và chỉ liệt kê đúng model đó trong
`models` khi trỏ notebook vào file đó.

### 5. Bug resume của tool: model sau báo "đã xong" ngay dù chưa chạy

**Triệu chứng**: chạy xong model A, chuyển sang chạy model B thì notebook báo tất cả combo đã
hoàn tất ngay từ đầu, dữ liệu `dax_perf_log` của B trống trơn.

**Nguyên nhân**: `get_starting_query_id` của `DAXPerformanceTesting` tính "combo đã xong" trên
**toàn bộ** bảng `dax_perf_log` dùng chung, không lọc theo model của lần chạy hiện tại — sau khi
model A ghi đầy log, model B đọc nhầm là đã có đủ dữ liệu.

**Cách chặn**: set `forceStartQueriesAt1: True` cho lần chạy notebook của model tiếp theo trong
cùng một bảng log.

### 6. Đếm tiến độ nhầm tiêu chí "hoàn tất"

**Triệu chứng**: giám sát tưởng notebook bị treo/lỗi vì số dòng log không khớp
`numberOfRunsPerQueryId` (ví dụ 4).

**Nguyên nhân**: tool coi một combo (model, cacheType, queryId) là xong khi có **1 lần chạy thành
công**, không phải khi đủ N lần — số lần lặp là ngân sách retry cho lỗi thoáng qua, không phải yêu
cầu bắt buộc N mẫu độc lập.

**Cách chặn**: kiểm bằng tiêu chí thật của tool (`success_count >= 1`), không kiểm bằng đếm dòng
thô so với `numberOfRunsPerQueryId`.

### 7. Outlier cold-start làm méo trung bình (FE time)

**Triệu chứng**: một combo (cache/version) có trung bình FE time cao bất thường so với các combo
khác cùng model.

**Nguyên nhân**: query đầu tiên notebook chạy sau khi vừa khởi động thường dính chi phí
session/model cold-start (thời gian tổng lớn, CPU time gần 0) — không phải chi phí thực thi DAX
thật.

**Cách chặn**: dùng **median**, không dùng mean, làm chỉ số so sánh chính; khi cần giải thích một
số trung bình bất thường, kiểm tra p50/p90/p95 riêng trước khi kết luận có regression thật.

### 8. `create_dax_perf_notebooks.py` không tạo notebook mới

**Triệu chứng**: script báo `notebook 'DAXPerfTest_<model>_v0_vs_v1' not found - expected it to
already exist`.

**Nguyên nhân**: script chỉ gọi `updateDefinition`, không có nhánh tạo mới — buộc notebook phải đã
tồn tại trong workspace từ trước (import từ notebook gốc `DAXPerformanceTesting`).

**Cách chặn**: import notebook gốc vào workspace, đặt đúng tên `DAXPerfTest_<model>_v0_vs_v1`,
rồi mới chạy script.

---

## Liên quan

- Cách capture DAX gốc: [`docs/manual/25-how-to-capture-dax-workload.md`](../../../../docs/manual/25-how-to-capture-dax-workload.md)
- Kế hoạch/quyết định phạm vi performance test: [`docs/design/25-performance-load-testing-plan.md`](../../../../docs/design/25-performance-load-testing-plan.md)
- Kết quả performance test thật: [`docs/reports/25-performance-load-testing/performance-test-report.md`](../../../../docs/reports/25-performance-load-testing/performance-test-report.md)
- Kết quả load test thật (lịch sử, không còn thuộc phạm vi skill này): [`docs/reports/27-load-test-v0.md`](../../../../docs/reports/27-load-test-v0.md)
