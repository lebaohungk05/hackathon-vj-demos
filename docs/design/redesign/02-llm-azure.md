# 02 · Chuyển sang Azure OpenAI, gỡ Claude CLI (LLM)

Tổng: 51 giờ. Nhánh: `feat/llm-azure`. Phụ thuộc: INF-06 cho các test live; config, baseline và provider giả làm trước được.

## Mục tiêu

Mốc **M0**: demo **hiện tại** (vẫn luồng 6 bước) chạy hoàn toàn trên Azure OpenAI và không còn dấu vết Claude CLI. Đổi nhà cung cấp trước, đổi kiến trúc sau, để nếu có lỗi thì biết ngay do bước nào.

## Thiết kế

```text
src/ricebridge/
  config.py        Settings đọc từ env / .env: endpoint, key, deployment fast/strong, mode, timeout
  llm/
    azure.py       AzureLLM: complete_json(), complete_with_image(), chat_with_tools() (dùng ở AGT)
    store.py       Lưu/đọc theo khóa hash (tách từ client.py), provider-agnostic
    interpreter.py Giữ API cũ, gọi AzureLLM thay cho LLMClient
    client.py      XÓA
    translate.py   Port sang Azure ngay ở LLM-10; giữ đến PERF-03 rồi xóa
```

- Lỗi gồm `LLMTimeout`, `LLMRateLimited`, `ContentFiltered(scope=input/output)` và `LLMUnavailable`; schema/refusal/response bị cắt cũng phải có kết quả xử lý rõ ràng. Lỗi/đầu ra bị chặn dùng quy tắc; đầu vào bị chặn thì từ chối, không phân tích lại. Trên agent, bỏ bản sao chạy dở trước fallback (AGT-13).
- Chỉ một lớp retry: chọn retry SDK có giới hạn hoặc tắt bằng `max_retries=0` rồi tự retry tối đa 2 lần. Tôn trọng retry-after/retry-after-ms, deadline còn lại và ngân sách request; không nhân retry của adapter với retry SDK.
- Request vision/final dùng cùng deadline của run. Cancel theo run_id, không đóng client dùng chung hoặc làm hỏng lần live kế tiếp; response muộn bị bỏ bởi epoch/state_version. Adapter không có quyền tự commit.
- Schema dùng structured outputs chế độ strict: mọi thuộc tính phải nằm trong `required`, `additionalProperties: false`, trường không bắt buộc thì cho kiểu `null`. Vẫn giữ validator hiện có vì structured outputs không kiểm logic nghiệp vụ.
- Khóa lưu: sha256 của deployment, model/version, prompt/schema version, payload chuẩn hóa và hash byte ảnh (nếu có). Dữ liệu cố định chỉ đọc ở data/; cache mới ghi vào runtime overlay (DEP-11), không ghi vào image.

### Hợp đồng chế độ và cấu hình

| Chế độ | Cấu hình Azure | Lỡ cache/bản ghi | Mạng |
| --- | --- | --- | --- |
| `live` | Bắt buộc; thiếu thì từ chối khởi động, nêu tên biến nhưng không lộ key | Gọi provider | Có, trong ngân sách |
| `auto` | Có thì gọi được; thiếu thì cảnh báo và tiếp tục offline | Thiếu cấu hình hoặc provider lỗi → quy tắc | Chỉ khi có cấu hình và adapter cho phép |
| `replay`, `--stage` | Không bắt buộc, không pre-flight live | Quy tắc; ảnh chưa có kết quả thì hỏi lại, không đoán số | Cấm mọi kết nối ra ngoài |
| `rules` | Không bắt buộc | Quy tắc; chỉ dùng dữ liệu/bằng chứng đã có | Cấm mọi kết nối ra ngoài |

Hợp đồng áp dụng tới vision, forecast, translation và pre-flight, không chỉ client LLM. Trong M0 vẫn dùng cache LLM cũ theo provider mới; AGT-09 thay bằng recording cấp run ở M1.

## Task

| ID | Việc | File chính | Xong khi | Giờ | Phụ thuộc |
| --- | --- | --- | --- | --- | --- |
| LLM-00 | Chụp baseline trước thay đổi: stage lưu kế hoạch/completeness/log đã chuẩn hóa; ghi riêng lỗi parser/tự duyệt/completeness và các ca có/không có thao tác duyệt | `tests/unit/baseline/cluster_a.json`, `tests/unit/test_baseline.py` | Baseline tái hiện code hiện tại; danh sách lỗi có test để sửa, không buộc giữ lỗi | 3 | – |
| LLM-01 | Settings endpoint/key/deployment/mode/timeout/deadline/token/request budgets; đọc env/.env, env ưu tiên; xử lý thiếu cấu hình theo bảng chế độ | `config.py`, `.env.example` | Test cả 4 mode; live thiếu biến fail, auto cảnh báo rồi offline; key không nằm trong log/repr | 3 | – |
| LLM-02 | AzureLLM complete_json/complete_with_image/chat_with_tools; ánh xạ lỗi theo scope, một lớp retry, deadline, cancel theo run và response muộn; thêm SDK openai | `llm/azure.py`, `pyproject.toml` | Transport giả cho 429/timeout/filter/refusal/schema/truncation; cancel xong lần live tiếp vẫn dùng được; smoke thật qua | 8 | LLM-01, INF-08 |
| LLM-03 | Tách store/trace; chuẩn hóa cache key có model version/ảnh/schema; đọc data cố định + runtime overlay, ghi nguyên tử trong runtime | `llm/store.py` | Replay cũ qua; ảnh/prompt thay đổi không trúng cache; data read-only vẫn chạy | 5 | LLM-02 |
| LLM-04 | Port `parse_message`, `choose_remeasurer`, `plan_brief` sang `AzureLLM`; sửa 3 schema cho strict mode; `parse_message` và `choose_remeasurer` dùng `fast`, `plan_brief` dùng `strong` | `llm/interpreter.py` | Cả 5 tin nhắn mẫu và kịch bản chạy ở `--mode live`; kết quả qua validator | 4 | LLM-03 |
| LLM-05 | Port đọc ảnh: gửi ảnh base64 lên `strong` thay cho `claude -p --allowedTools Read`; giữ đọc EXIF, sha256, cờ của `consistency.py` | `vision/gauge_reader.py`, `vision/hook.py` | 28 ảnh thử đọc được; không còn tiến trình con nào được tạo | 4 | LLM-02 |
| LLM-06 | Sau khi mọi consumer đã port, xóa client.py và đường CLI; cập nhật engine/runtime/pre-flight/modelName/i18n cùng scripts; pre-flight không gọi mạng ở chế độ offline | `engine.py`, `cli.py`, `server/app.py`, `web/`, `scripts/` | Import/server khởi động được; không còn import client cũ hay chạy Claude trong src/tests/scripts; không còn binary/run_cli dependency | 5 | LLM-04, LLM-05, LLM-10 |
| LLM-07 | Sinh cache Azure ở runtime cho kịch bản + 5 tin mẫu + 28 ảnh; export fixture đã review vào data sau khi so với baseline; vision_evaluate so độ chính xác/ảnh không đọc được với kết quả cũ | `data/llm_cache/`, `data/vision/`, `docs/report/qa-report.md` | Stage đủ cache không fallback; model/prompt/schema version có trong manifest; không cần quyền ghi data lúc chạy | 4 | LLM-06 |
| LLM-08 | Provider giả: mode/error scope/refusal/schema/cancel/deadline, retry không nhân đôi và cache key; CI không cần secret | `tests/unit/test_llm_azure.py` | Chặn mạng vẫn qua; mọi đường lỗi có outcome rõ, không lộ key | 5 | LLM-03, LLM-10, LLM-11 |
| LLM-09 | README/setup/demo-guide/vision-tools/architecture mô tả provider mới; cập nhật trạng thái ADR khi implementation được chấp nhận, giữ nội dung ADR cũ làm lịch sử | `README.md`, `docs/**` | Hướng dẫn vận hành hiện hành không yêu cầu Claude CLI; lịch sử và thiết kế chưa triển khai được ghi nhãn rõ | 3 | LLM-06 |
| LLM-10 | Port translate.py sang AzureLLM/store/config ngay trong M0; bỏ import client.py/run_cli/binary; giữ bộ dịch tương thích tới PERF-03 | `llm/translate.py`, `server/app.py` | Xóa client.py rồi server và bản dịch VI/EN/JA vẫn chạy; offline chỉ đọc cache; live translation có deadline/cancel | 4 | LLM-02, LLM-03 |
| LLM-11 | Chính sách offline tập trung cho LLM/vision/weather/translation/pre-flight; forecast đọc fixture khi offline; transport bị chặn trong test | `config.py`, `weather_source.py`, `vision/hook.py`, `cli.py`, `tests/unit/test_offline.py` | Stage/replay/rules và auto thiếu cấu hình không tạo request mạng ở mọi endpoint; ảnh chưa cache yêu cầu đo lại | 3 | LLM-01 |

## Tiêu chí xong (M0)

- Baseline giữ hành vi hợp lệ; INB-08 sửa tự duyệt được ghi rõ nếu thực hiện trong M0. Parser/completeness được cập nhật ở task tương ứng, không âm thầm thay fixture.
- `pytest`, `tests/e2e -m e2e` và `ruff` đều qua.
- Rút key khỏi `.env` rồi chạy `--mode auto`: demo báo rõ thiếu cấu hình và chạy tiếp bằng dữ liệu đã lưu và quy tắc.
- Import không còn client cũ; translate đã chạy bằng Azure/cache; stage/replay/rules bị chặn mạng vẫn qua cả forecast/vision. Live thiếu cấu hình phải fail trước khi mở server.

## Rủi ro

| Rủi ro | Cách giảm |
| --- | --- |
| Model Azure hiểu tiếng miền Tây kém hơn ("nước ba phân" = +3 cm) | 5 tin nhắn mẫu trong LLM-04 là test bắt buộc; thêm ví dụ vào prompt nếu sai |
| Đọc ảnh kém chính xác hơn | LLM-07 đo trước khi gỡ hẳn; nếu kém, đổi `strong` sang model khác qua tham số Bicep |
| Content filter chặn nhầm tin nhắn bình thường | Ghi lại mọi lần bị chặn trong log; dùng bộ lọc mặc định, chỉ xin nới khi có bằng chứng chặn nhầm |
