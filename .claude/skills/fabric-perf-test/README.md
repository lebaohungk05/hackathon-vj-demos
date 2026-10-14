# fabric-perf-test — cài đặt và sử dụng

Đo hiệu năng DAX (Performance Test, v0 vs version khác), dùng `microsoft/fabric-toolbox`
(`DAXPerformanceTesting`), chạy qua một Fabric Data Pipeline duy nhất cho cả 3 model/version. Đọc
file này một lần trước khi chạy lần đầu; những lần sau chỉ cần mục [Chạy](#chạy).

> Skill này trước đây tên `fabric-perf-load-test`, gộp cả Performance Test và Load Test. Load Test
> đã bị bỏ (2026-09-17) — xem `docs/reports/27-load-test-v0.md` nếu cần tham khảo lịch sử.

---

## Cài đặt

### 1. Skill

Skill nằm ở `.claude/skills/fabric-perf-test/` trong repo. Đã có sẵn, không cần cài gì thêm.
Claude Code tự nạp khi bạn nói câu liên quan (ví dụ *"chạy performance test cho model X"*).

Muốn dùng ở repo khác thì copy cả thư mục sang `.claude/skills/` của repo đó — nhưng lưu ý các
script (`scripts/measure/*.py`) nằm ở repo `fabric-model-analyzer`, không đóng gói kèm skill này.

### 2. Phần mềm cần có

| Thứ | Kiểm bằng | Nếu thiếu |
|---|---|---|
| Python 3.9+ | `python -V` | Cài từ python.org |
| pandas, openpyxl, requests | `python -c "import pandas,openpyxl,requests"` | `pip install pandas openpyxl requests` |
| Azure CLI, đã `az login` | `az account show` | Cài Azure CLI rồi `az login` |
| Power BI Desktop | Mở app | Cài từ Microsoft Store / powerbi.microsoft.com |

### 3. Quyền trên Fabric

- **Contributor trở lên** trên workspace test (tạo Lakehouse, upload file `Files/`, sửa
  notebook, tạo/chạy pipeline).
- Tài khoản `az login` phải có quyền tương ứng — script dùng token của chính người đang đăng nhập,
  không dùng service principal.

### 4. Bật capacity

Không chạy được notebook/pipeline hay upload file khi capacity tắt. Việc này người dùng tự làm.

---

## Chuẩn bị lần đầu

Làm một lần cho mỗi model có report mới cần đo. Xem đầy đủ (kèm ảnh chụp màn hình Performance
Analyzer): [`docs/manual/25-how-to-capture-dax-workload.md`](../../../docs/manual/25-how-to-capture-dax-workload.md).

1. Mở report trong Power BI Desktop → View → Performance Analyzer → Start recording → Refresh
   visuals → thao tác filter đi hết các page → Stop.
2. Export ra JSON, đặt tên `PowerBIPerformanceData_<tên report>.json`, copy vào
   `docs/reports/25-performance-load-testing/payloads/`.
3. Nếu model mới chưa có trong `REPORT_TO_MODEL` (đầu
   `scripts/measure/extract_dax_queries_for_perf_test.py`), thêm mapping report → model model vào đó.
4. Tạo sẵn notebook rỗng tên `DAXPerfTest_<model>_v0_vs_v1` trong workspace test bằng cách import
   notebook gốc `DAXPerformanceTesting` (microsoft/fabric-toolbox) — `create_dax_perf_notebooks.py`
   chỉ update cell config, không tạo notebook mới.
5. Tạo Fabric Data Pipeline (`DAXPerfTest`), 3 activity `TridentNotebook` (Model 1/2/3) nối tuần tự
   bằng `dependsOn`, mỗi activity trỏ đúng notebook của từng model, `timeout` 12h+.

---

## Chạy

```bash
# 1. Trích DAX từ mọi PowerBIPerformanceData_*.json thành 1 Excel/model
python scripts/measure/extract_dax_queries_for_perf_test.py

# 2. (Tuỳ chọn) rút mẫu nếu full quá lâu — sửa SAMPLE_FRACTION đầu script trước
python scripts/measure/select_sample_queries.py

# 3. Upload lên Lakehouse
python scripts/measure/upload_dax_queries_to_lakehouse.py
python scripts/measure/upload_dax_queries_to_lakehouse.py --only-sampled   # chỉ đổi file sampled

# 4. Đẩy cấu hình vào notebook (chỉ update cell 6, notebook phải đã tồn tại)
python scripts/measure/create_dax_perf_notebooks.py --phase sampled
python scripts/measure/create_dax_perf_notebooks.py --phase sampled --model PS設定データ_s

# 5. Chạy pipeline DAXPerfTest trong Fabric UI (bấm Run 1 lần, chạy tuần tự cả 3 model)
```

---

## Đầu ra

| Nơi | Nội dung |
|---|---|
| `dax_perf_log` (Delta, Lakehouse `perf_load_testing`) | Mỗi dòng một lần chạy một query: model, version, cache type, `queryId`, thời lượng, trace event |

Đọc bằng Spark SQL/pandas trong notebook, hoặc mở trực tiếp trong Fabric Lakehouse explorer, hoặc
poll qua SQL Analytics Endpoint (pyodbc + token `az`) để theo dõi tiến độ khi pipeline đang chạy.
Cách tổng hợp/diễn giải thực tế (median vs mean, tách warm/hot, xử lý outlier cold-start):
[`docs/reports/25-performance-load-testing/performance-test-report.md`](../../../docs/reports/25-performance-load-testing/performance-test-report.md).

---

## Khắc phục sự cố

| Triệu chứng | Xử lý |
|---|---|
| Query fail hàng loạt sau khi hết retry, log `QueryBegin event ... not found yet` | DAX bị hỏng bởi `_x000D_` (escape `\r` của Excel) — đã fix trong script trích DAX, kiểm lại đã chạy đúng bản mới nhất chưa |
| `TypeError` liên quan `queryId` giữa lúc chạy | `queryId` phải là số nguyên — không sửa lại thành chuỗi |
| Notebook "hoàn tất" sớm ở query 99 | `stopQueryIdsAt` mặc định 99, set lại bằng đúng tổng số query |
| `create_dax_perf_notebooks.py` báo "notebook not found" | Tạo sẵn notebook rỗng đúng tên trong Fabric trước |
| Model tiếp theo báo "all done" ngay dù chưa chạy | Set `forceStartQueriesAt1: True` — bug tool tính "xong" trên toàn bộ `dax_perf_log`, không lọc theo model |
| `%pip magic command is disabled` khi chạy qua pipeline | Fabric chặn inline install cho notebook non-interactive — tạo Fabric Environment, cài lib qua `environment.yml`, gắn vào notebook |

Trục trặc lạ hơn: tra [`reference/pitfalls.md`](reference/pitfalls.md).

---

## Cấu trúc thư mục

```
fabric-perf-test/
  SKILL.md                    sổ tay vận hành — trigger, khi nào dùng/không dùng, quy trình, khắc phục sự cố
  README.md                   file này
  reference/pitfalls.md       danh sách lỗi đã gặp kèm cách chặn, gộp từ docs/manual/25 + docs/reports/25
```

Không có `scripts/` riêng — skill này chạy trực tiếp `scripts/measure/*.py` đã có sẵn trong repo,
cộng bước chạy pipeline thủ công trong Fabric UI.
