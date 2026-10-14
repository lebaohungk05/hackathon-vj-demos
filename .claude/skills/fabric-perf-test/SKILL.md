---
name: fabric-perf-test
description: Đo hiệu năng DAX (Performance Test) cho semantic model trên Microsoft Fabric, dùng bộ công cụ microsoft/fabric-toolbox (`DAXPerformanceTesting`), chạy qua một Fabric Data Pipeline duy nhất cho tất cả model/version. Dùng skill này khi user nói "chạy performance test", "đo hiệu năng DAX", "run DAX performance test", "so sánh tốc độ query v0 vs v1 vs v2".
---

# Đo hiệu năng DAX (Performance Test) cho semantic model trên Fabric

So **thời gian chạy DAX query thật** giữa các bản model (v0/v1/v2...) trên cùng capacity, cùng bộ
query, dùng `DAXPerformanceTesting` (`microsoft/fabric-toolbox`).

> **Đã bỏ Load Test khỏi skill này (2026-09-17).** Trước đây skill này gộp cả Performance Test và
> Load Test (đẩy tải tìm điểm throttle capacity). Load Test đã bị bỏ vì quy trình đó chưa từng được
> cập nhật theo tình trạng data mới và không có script tự động trong repo — nội dung cũ vẫn còn ở
> `docs/reports/27-load-test-v0.md` làm tham khảo lịch sử, nhưng skill này **không còn hướng dẫn
> chạy load test**. Nếu cần load test lại, viết một skill/quy trình riêng, đừng gộp lại đây.

---

## 1. Khi nào dùng skill này — và khi nào KHÔNG

Dùng khi:
- "chạy performance test cho model X"
- "so sánh tốc độ DAX query v0 vs v1 vs v2"

**Không dùng cho:**
- **Đo tác động của việc xoá measure/khử "measure killer"** — đó là một quy trình riêng, xem
  `docs/reports/24-measure-killer-external-tool-vs-v1-cleanup-comparison.md`. Skill này không bao
  gồm bước xoá measure.
- **So sánh report có render giống nhau không (kiểm chứng sau tối ưu model)** — dùng skill
  [`fabric-report-compare`](../fabric-report-compare/SKILL.md) thay vào đó. Skill đó so **hình
  ảnh/số liệu hiển thị trên report**; skill này so **tốc độ chạy DAX**, không liên quan tới việc
  report có đúng hay không.

---

## 2. Điều kiện cần trước khi chạy

| Đầu vào | Là gì | Lấy ở đâu |
|---|---|---|
| Power BI Desktop | Ghi lại DAX thật report sinh ra | Cài sẵn, xem bước 1 |
| Workspace + model đã deploy trên Fabric | Model v0 (và v1/v2 nếu so version) đã tồn tại | `dynam-baseline-test` / `dynam-variant-test` hoặc tương đương |
| Quyền Contributor trở lên trên workspace test | Tạo Lakehouse, upload file, tạo/sửa notebook, tạo pipeline | Người dùng tự xin |
| Capacity đang bật | Không chạy được notebook/pipeline khi capacity tắt | Người dùng tự bật |
| `az login` | Script dùng token của chính người chạy (Storage + Fabric REST) | `az account get-access-token` |

**Việc phải để người dùng tự làm:** bật/tắt capacity, cấp quyền workspace, đăng nhập `az`, bấm
Run cho pipeline trong Fabric UI (không có API tự động trigger + theo dõi trạng thái pipeline).

---

## 3. Chạy Performance Test (so tốc độ DAX giữa các version)

Mục tiêu: so **thời gian chạy DAX query thật** giữa v0, v1 và v2 (3 chiều cùng lúc), trên cùng
capacity, cùng bộ query. **Cập nhật 2026-09-16**: trước đây chỉ so v0 vs v1; đã thêm v2 vào
`models` trong `create_dax_perf_notebooks.py` sau khi v2 được xác nhận tối ưu xong
(`docs/reports/33-v2-final-status-and-bpa-snapshot.md`). Notebook Fabric vẫn giữ tên cũ
`DAXPerfTest_<model>_v0_vs_v1` (không đổi tên — script chỉ update theo đúng tên có sẵn, đổi tên sẽ
làm script không tìm thấy notebook) dù giờ chạy cả 3 bản — đừng để tên đánh lừa.

**Ảnh hưởng thời gian chạy**: thêm 1 bản (v2) nghĩa là mỗi query giờ chạy ×3 model thay vì ×2 —
tăng ~50% tổng thời gian so với ước tính cũ. Tính lại thời gian dự kiến trước khi chạy full-scope.

**Bắt buộc kiểm tra trước khi chạy — refresh đồng bộ giữa các version.** Đã gặp thật (2026-09-17):
so size v1 vs v2 của `PS設定データ_s` cho kết quả ngược lý thuyết (v2 lớn hơn v1), và trước khi tin
số đó phải loại trừ khả năng 2 bản refresh ở 2 thời điểm khác nhau với data volume khác nhau (data
dummy project này liên tục bị reseed/scale — x20 đã từng xảy ra). Quy trình bắt buộc trước MỌI lần
chạy performance test hoặc so size:

1. Kiểm tra lịch sử refresh của từng version (Power BI REST API
   `GET /v1.0/myorg/groups/{ws}/datasets/{id}/refreshes` — lấy `startTime` mới nhất mỗi bản).
2. Nếu thời điểm refresh gần nhau (cùng ngày/vài giờ) VÀ không có sự kiện reseed/scale data nào
   được ghi nhận xảy ra giữa 2 mốc đó → coi là an toàn để so sánh.
3. Nếu lệch nhiều (vài ngày) hoặc không chắc có reseed ở giữa → **refresh lại tất cả version cần so
   sánh ngay trước khi chạy test**, đừng giả định "chắc vẫn giống nhau".
4. Việc này từng bị bỏ sót một lần trước đó trong dự án (AB#6673: PS-v1/v2 lệch 3 ngày so với v0,
   suýt kết luận sai) — đây không phải lần đầu gặp, nên coi là bước chuẩn bắt buộc, không phải
   optional.

**Trạng thái dữ liệu (2026-09-16)**: bảng `dax_perf_log` đã được xóa sạch hoàn toàn (data cũ chỉ có
v0/v1, từ 2026-09-09/10, không còn giá trị vì dummy data đã bị thay đổi/reseed) — chạy lại từ đầu,
không phải resume.

### Bước 1 — Ghi lại DAX thật bằng Performance Analyzer (thủ công)

Làm bằng tay trong Power BI Desktop, không có script. Xem hướng dẫn đầy đủ kèm ảnh chụp màn hình:
[`docs/manual/25-how-to-capture-dax-workload.md`](../../../docs/manual/25-how-to-capture-dax-workload.md).

Tóm tắt: mở report → View → Performance Analyzer → Start recording → Refresh visuals → thao tác
filter đi hết các page → Stop → Export ra JSON, đặt tên `PowerBIPerformanceData_<tên report>.json`,
copy vào `docs/reports/25-performance-load-testing/payloads/`.

### Bước 2 — Trích DAX ra file Excel (1 file/model)

```bash
python scripts/measure/extract_dax_queries_for_perf_test.py
```

Đọc mọi `PowerBIPerformanceData_*.json` trong `payloads/`, lọc trùng theo cấu trúc query (bỏ giá
trị filter literal), gộp theo model (biến `REPORT_TO_MODEL` đầu script — có report mới thì khai
thêm ở đó), ghi ra `DAXQueries_<model>.xlsx` (sheet `DAXQueries`, cột `queryId`/`daxQuery`/`report`).

### Bước 3 — (Tuỳ chọn) Rút mẫu nếu chạy full quá lâu

Nếu số query đầy đủ quá lớn để chạy hết (ví dụ ~866 query cho một model dự kiến >10 giờ), rút mẫu
theo tỉ lệ mỗi report:

```bash
python scripts/measure/select_sample_queries.py
```

Sửa `SAMPLE_FRACTION` đầu script cho từng model, chạy ra `DAXQueries_<model>_sampled.xlsx` (queryId
đánh số lại 1..N, sạch, không phải tập con resumable của file đầy đủ).

### Bước 4 — Upload lên Lakehouse

```bash
python scripts/measure/upload_dax_queries_to_lakehouse.py
python scripts/measure/upload_dax_queries_to_lakehouse.py --only-sampled   # nếu chỉ đổi file sampled
```

Upload qua OneLake DFS API bằng token `az` của người đang đăng nhập, vào `Files/` của Lakehouse
`perf_load_testing` (hoặc Lakehouse tương ứng — sửa `WORKSPACE_ID`/`LAKEHOUSE_ID` đầu script nếu
dùng môi trường khác).

### Bước 5 — Tạo/cập nhật notebook `DAXPerfTest_<model>_v0_vs_v1`

```bash
python scripts/measure/create_dax_perf_notebooks.py --phase sampled
python scripts/measure/create_dax_perf_notebooks.py --phase sampled --model PS設定データ_s
```

Script chỉ thay **cell config** (cell 6) của notebook gốc `DAXPerformanceTesting`
(microsoft/fabric-toolbox) — không sửa logic. Notebook phải **đã tồn tại từ trước** trong workspace
(script không tạo mới, chỉ update — xem lỗi ở bảng khắc phục sự cố). Sửa `PHASES["sampled"]` đầu
script khi đổi model/số query/số lần lặp.

`--phase original` bị chặn cứng trong script — đó là cấu hình full-scope cũ, chạy lại sẽ tốn nhiều
giờ không cần thiết.

### Bước 6 — Chạy qua Fabric Data Pipeline (không mở tay từng notebook)

**Cập nhật 2026-09-17**: thay vì mở tay từng notebook `DAXPerfTest_<model>_v0_vs_v1` và bấm Run,
dùng một Fabric Data Pipeline (`DAXPerfTest`) chạy tuần tự cả 3 notebook — 3 `TridentNotebook`
activity (Model 1/2/3), nối nhau bằng `dependsOn: [{"activity": "Model N-1", "dependencyConditions":
["Completed"]}]`, mỗi activity `timeout: "0.12:00:00"` trở lên (12h+ — cần tăng nếu
`pauseBetweenRuns`/`pauseAfterSettingCache` đang ở giá trị mặc định của tool, xem bảng tham số bên
dưới). Chạy pipeline này 1 lần là đủ cho cả 3 model, không cần vào từng notebook.

Trước khi chạy pipeline: nếu notebook cần cài thư viện ngoài (`semantic-link-labs`), **đừng dùng
`%pip install` trong cell** — Fabric chặn inline install cho notebook chạy qua pipeline (không chặn
khi chạy tay qua UI). Tạo một Fabric **Environment** item, cài thư viện qua `environment.yml`
(không phải `requirements.txt`), publish, rồi gắn vào notebook qua
`metadata.dependencies.environment` — xem chi tiết cách làm trong lịch sử commit hoặc hỏi lại nếu
cần làm lại từ đầu.

**Tham số quan trọng — đừng cắt giảm so với mặc định của tool nếu không đo lại kỹ:** dự án này từng
cắt `numberOfRunsPerQueryId` 15→4, `pauseAfterSettingCache` 5s→3s, `pauseBetweenRuns` 30s→3s để
"tiết kiệm thời gian chạy", và việc cắt `pauseBetweenRuns`/`pauseAfterSettingCache` tương quan với
một lỗi đo thật (một phía luôn ra SE=0ms, sai lệch một chiều) — đã revert cả 3 về mặc định của tool
(15/5s/30s) sau khi phát hiện. Coi mặc định của tool là điểm khởi đầu an toàn; chỉ cắt giảm khi có
lý do rõ và đã kiểm tra không gây lệch kết quả.

**Theo dõi tiến độ pipeline (không có API resumable-run riêng cho notebook, nhưng đọc trực tiếp
`dax_perf_log` được)**: poll bảng `dax_perf_log` theo `modelName`, đếm
`COUNT(DISTINCT queryId)`/`MAX(currentTime)` mỗi model — timestamp không nhích trong khoảng vượt xa
nhịp ~5-7 phút/query mới là dấu hiệu treo thật, đừng kết luận treo chỉ vì đứng yên 1-2 lần poll.

**Resumable theo thiết kế**: `onlyRunNewQueries: True` nghĩa là chạy lại notebook (sau khi bị dừng,
hết session, hoặc chạy theo đợt) sẽ tự tiếp tục từ queryId dở dang trong `dax_perf_log`, không chạy
lại từ đầu. Ngoại lệ: nếu vừa chạy xong một model khác ghi vào **cùng** bảng `dax_perf_log`, đặt
`forceStartQueriesAt1: True` cho lần chạy tiếp theo (xem mục 5 bảng khắc phục sự cố). Muốn chạy lại
sạch từ đầu (vd sau khi đổi tham số quan trọng), xoá hẳn dữ liệu cũ trong `dax_perf_log` trước —
**backup CSV toàn bộ dữ liệu thô trước khi xoá**, vì chỉ giữ số liệu tổng hợp (median/average) là
không đủ để trả lời sau này "queryId X có bị bất thường ở lần chạy cũ không".

### Bước 7 — Đọc kết quả

Kết quả nằm trong bảng Delta `dax_perf_log` (Lakehouse `perf_load_testing`), mỗi dòng là một lần
chạy một query, gồm cột thời lượng và trace event (`QueryEnd` = tổng thời gian, tách được FE/SE).
Đọc bằng Spark SQL/pandas trong notebook, hoặc mở trực tiếp trong Fabric Lakehouse explorer.

Tham khảo cách tổng hợp/diễn giải thực tế (median vs mean, tách warm/hot, xử lý outlier cold-start):
[`docs/reports/25-performance-load-testing/performance-test-report.md`](../../../docs/reports/25-performance-load-testing/performance-test-report.md).

---

## 4. Khi gặp trục trặc

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| Query fail hàng loạt, log show `QueryBegin event ... not found yet` sau khi hết retry | DAX chứa `_x000D_` — `openpyxl` escape ký tự `\r` khi ghi Excel, không ai giải mã ngược khi đọc lại | Đã fix trong `extract_dax_queries_for_perf_test.py` (`replace("\r\n","\n")`); nếu tự viết script trích DAX khác, nhớ làm bước này |
| `TypeError` giữa lúc chạy notebook, liên quan `queryId` | `queryId` phải là **số nguyên**, không phải chuỗi (`"q0001"`) | Đảm bảo cột `queryId` là int 1..N — script hiện tại đã làm đúng |
| Notebook dừng "hoàn tất" ở query thứ 99 dù file có nhiều hơn | `stopQueryIdsAt` mặc định chỉ 99 | Set đúng bằng tổng số query của model đó trong cell config |
| Một file Excel gộp nhiều model chạy fail hàng loạt, lỗi tham chiếu bảng không tồn tại | Vòng lặp của notebook chạy **mọi dòng × mọi model** trong `models`, không lọc theo cột nào | Tách 1 file Excel cho mỗi model, không gộp chung |
| `create_dax_perf_notebooks.py` báo "notebook not found - expected it to already exist" | Script chỉ **update**, không tạo mới notebook | Tạo sẵn notebook rỗng tên `DAXPerfTest_<model>_v0_vs_v1` trong Fabric UI trước, rồi chạy lại script |
| Sau khi một model chạy xong, model tiếp theo báo "all done" ngay dù chưa có dữ liệu thật | `get_starting_query_id` của tool tính "đã xong" trên **toàn bộ** `dax_perf_log`, không lọc theo model đang chạy — bug đã biết của `DAXPerformanceTesting` | Set `forceStartQueriesAt1: True` cho lần chạy của model tiếp theo |
| Theo dõi tiến độ tưởng bị treo, đếm dòng không khớp `numberOfRunsPerQueryId` | Tool coi một combo (model, cacheType, queryId) là xong khi có **1 lần chạy thành công**, không phải đủ N lần | Không phải lỗi — kiểm bằng `success_count >= 1`, không kiểm bằng đếm dòng thô |
| `%pip magic command is disabled` khi notebook chạy qua pipeline | Fabric chặn inline `%pip install` cho notebook chạy không tương tác (qua pipeline) | Tạo Fabric Environment, cài lib qua `environment.yml`, publish, gắn vào notebook qua `metadata.dependencies.environment`; comment dòng `%pip install` trong notebook |

Đầy đủ hơn: [`reference/pitfalls.md`](reference/pitfalls.md).
