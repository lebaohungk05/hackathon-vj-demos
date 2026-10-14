# 03 · Vòng lặp agent (AGT)

Tổng: 84 giờ. Nhánh: `feat/agt-loop`. Phụ thuộc: M0 (kế hoạch 02). INB-01, INB-08..10 và PERF-01 phải làm sớm theo bảng phụ thuộc; không chờ hoàn thành toàn bộ INB/PERF.

## Mục tiêu

Mốc **M1**: với một đầu vào, model tự chọn công cụ, dùng kết quả để điều tra tiếp rồi đề xuất. Mọi phép tính và mọi lần ghi vẫn là mã tất định. Cảnh ảnh F2 là bài thử đầu tiên; M1 còn phải qua bộ eval ngoài kịch bản, kiểm an toàn và lỗi giữa chừng.

## Thiết kế

```text
src/ricebridge/
  guards.py          check_reading() tách từ Demo.intake(): 6 kiểm tra, trả Verdict
  agent/
    tools.py         Tool(name, kind, params_schema, fn); 11 công cụ (bảng ở README mục 2)
    prompts.py       System prompt, schema kết quả cuối
    runner.py        AgentRunner: vòng lặp function calling, ngân sách, chọn model, stream bước
    context.py       RunContext: bản sao trạng thái, bằng chứng, hiệu ứng tạm, epoch/state_version
    validation.py    Kiểm hậu điều kiện, tham chiếu bằng chứng và kế hoạch cuối
    policy.py        RulesPolicy: chuỗi công cụ cố định theo loại đầu vào, dùng làm dự phòng
    recording.py     Ghi / phát lại lần chạy
    record.py        python -m ricebridge.agent.record: ghi lại cả kịch bản
```

### Vòng lặp

```text
ctx = RunContext(before_state, item, evidence, epoch, state_version)
apply_trusted_input(ctx)                              # INB-09; chỉ sửa bản sao
messages = [system, user(item + get_cluster_overview(ctx))]
while ctx.can_call_tool():                            # tối đa 8 công cụ, kể cả gọi lặp
    resp = llm.chat_with_tools(role, messages, tools, parallel_tool_calls=False,
                               deadline=ctx.llm_deadline)
    messages.append(resp.assistant_message)           # giữ nguyên tool_call id
    if không có tool_calls: break
    for call in resp.tool_calls:
        result = TOOLS[call.name].run(ctx, validate(call.args))
        ctx.trace.append(step); runtime.publish_progress(ctx)  # kết quả tạm
        messages.append(tool(call.id, result))
validate_required_outcome(ctx)                        # thiếu kiểm tra/kế hoạch → fallback
final = llm.complete_json(role, messages + ctx.final_payload(), FINAL_SCHEMA,
                          deadline=ctx.llm_deadline)   # nằm trong cùng ngân sách
validate_final(final, ctx)                            # số, thửa, giờ, hành động, tool_ref
finish(ctx, final)                                    # commit một lần; không lập kế hoạch lại
```

- Ngân sách: tối đa 8 lần thực thi công cụ, mặc định cắt các lời gọi LLM sau 50 giây và hoàn thành xử lý trong 60 giây tính từ khi job bắt đầu. Thời gian này gồm vision bên trong công cụ, retry/backoff, structured output cuối, validation và commit; thời gian chờ hàng đợi đo riêng. Dùng đồng hồ monotonic, truyền deadline còn lại tới mọi adapter và chừa thời gian chạy quy tắc.
- Lỗi Azure, hết ngân sách, đầu ra bị content filter, tool không hợp lệ hoặc thiếu hậu điều kiện đều bỏ bản sao chạy dở rồi chạy `RulesPolicy` từ cùng trạng thái trước đầu vào. Đầu vào bị content filter/chặn chỉ dẫn thì từ chối, không diễn giải lại bằng quy tắc. Reset đổi epoch thì hủy hẳn job cũ, không fallback trên phiên mới.
- Gọi từng công cụ một (`parallel_tool_calls=False`) để thứ tự hiển thị dễ theo dõi.
- Nội dung tin nhắn của người dân luôn nằm trong khối dữ liệu được đánh dấu, không bao giờ nằm trong system prompt.
- Chọn model: tin nhắn chữ, giọng nói và thông báo của trạm dùng `fast`; ảnh dùng `strong`. Khi `submit_reading` trả `suspicious` thì các lượt sau chuyển lên `strong`.

### Giao dịch trạng thái và bằng chứng

- Runtime chỉ có một worker thay đổi trạng thái. Mỗi lần chạy giữ bản sao trạng thái nghiệp vụ từ **trước** `advance_to` và áp đầu vào; công cụ `propose` sửa bản sao, chưa ghi nhật ký chính. Progress nằm riêng trong snapshot, có nhãn `provisional`; không duyệt được.
- Mỗi hiệu ứng có khóa nghiệp vụ ổn định, ví dụ `(item_id, effect_kind, field_id, evidence_id/request_id)`. Gọi lặp trả lại hiệu ứng đã tạo; `tool_call_id` dùng để nối hội thoại, không phải cơ chế duy nhất chống ghi trùng. `finish` kiểm epoch/state_version và chỉ commit một lần. Job hoàn tất muộn sau Skip/reset không được ghi.
- `submit_reading` nhận `evidence_id`, không nhận người gửi/cờ độc lập do model tự khai. Server gắn bằng chứng với đúng đầu vào, thửa, nguồn, thời điểm, hash ảnh và trạng thái kiểm tra; giá trị diễn giải phải có đoạn trích/vị trí trong bằng chứng và qua validator. Bằng chứng của đầu vào khác bị từ chối.
- Công cụ bắt buộc kiểm cờ ảnh, độ tin cậy, giới hạn vật lý, thời điểm và nhất quán nguồn, kể cả model không gọi `compare_sources`. Ảnh thiếu giờ chụp không là bằng chứng duy nhất; ảnh cũ, không đọc được hoặc có cờ chặn không được `accepted`. Confidence do model tự báo không đủ để vượt rào chắn.
- Đóng xung đột cần `request_id`, danh tính người đo và ống/phương pháp đo do server xác nhận (INB-10). Khán giả tự chọn vai trò không được biến thành người đo độc lập hay cán bộ trạm.
- Sau thay đổi dữ liệu, kế hoạch tạm cũ bị vô hiệu. `draft_plan` tạo kế hoạch cho đúng phiên bản bản sao; trước đầu ra cuối phải có kế hoạch mới nếu dữ liệu/lịch thay đổi. `finish` nhận chính kế hoạch này, không gọi `make_plan` lần nữa. Tin nhắn từ `reply_to_sender` và `FINAL_SCHEMA` chỉ là bản nháp trên dashboard, được hợp nhất và kiểm trước commit, không gửi ra Zalo hay ứng dụng ngoài.
- Validator kiểm `tool_ref` tồn tại và thuộc nhánh được commit; số phải gắn đúng thửa, đơn vị, thời điểm, lịch và hành động. `needs_human` lấy các việc bắt buộc từ trạng thái tất định. Nội dung không chứng minh được dùng mẫu câu quy tắc; không đổi quyết định để khớp lời model.

### Ghi và phát lại

- Khóa: sha256 của phiên bản prompt/schema, định nghĩa công cụ, phiên bản policy/cấu hình nghiệp vụ, model/version, nội dung đầu vào và hash byte ảnh, cùng trạng thái nghiệp vụ trước lần chạy. Chuẩn hóa JSON; không đưa epoch, lock, received_at thuần vận hành, thời gian chạy thật hay bản dịch giao diện vào hash. Thời điểm đo/tuổi ảnh đã chuẩn hóa ảnh hưởng verdict phải có trong khóa; clock mô hình, số đo, lịch, thời tiết và xung đột vẫn nằm trong trạng thái nghiệp vụ. Epoch vẫn được kiểm khi commit.
- Bản ghi cố định nằm trong `data/agent_runs/`, có schema version, adapter outputs (gồm kết quả vision đã validate), tool calls/results, kết quả cuối, deployment/model/version và các nhánh aborted/fallback. Bản ghi live mới lưu trong thư mục runtime; chỉ bản ghi đã review, không chứa thông tin cá nhân mới được đưa vào repo.
- Phát lại adapter bằng kết quả đã ghi, **không gọi vision/LLM/thời tiết qua mạng**. Chạy lại kiểm tra và công cụ nghiệp vụ trên bản sao; so kết quả ngữ nghĩa và trạng thái cuối. Loại timing, request id của provider và nguồn vận chuyển `live/cache` khỏi phép so; giữ nguyên nguồn bằng chứng, verdict và kế hoạch. Lệch thì bỏ bản sao rồi chạy `RulesPolicy` offline từ trạng thái trước đầu vào.
- Cùng kịch bản sau nhiều lần reset vẫn trúng bản ghi. Đổi byte ảnh, prompt/schema/policy hoặc cấu hình ảnh hưởng nghiệp vụ phải làm mất hiệu lực bản ghi. Nhịp hiển thị nén còn khoảng 0,6 giây mỗi bước; không giữ lock khi chờ hiệu ứng hiển thị.

## Task

| ID | Việc | File chính | Xong khi | Giờ | Phụ thuộc |
| --- | --- | --- | --- | --- | --- |
| AGT-01 | Tách 6 kiểm tra trong `intake()` thành `check_reading(text_or_value, parsed, rule, model_level, ...) -> Verdict` thuần; `intake()` gọi lại hàm này | `guards.py`, `engine.py` | Test cho từng kiểm tra trong 6 kiểm tra; `test_baseline` vẫn qua | 4 | M0 |
| AGT-02 | Dữ liệu người đo lại cho cả 6 thửa (người nhà, hàng xóm, cán bộ HTX, cán bộ kỹ thuật, cờ `independent`); thêm `FieldSpec.note` (ví dụ Bà Sáu 74 tuổi, không có điện thoại thông minh) | `engine.py` | `candidates_for(fid)` trả ≥ 2 người độc lập cho mỗi thửa | 2 | – |
| AGT-03 | Khung `Tool` + 11 công cụ trên `RunContext`; strict schema, validate bằng chứng tại công cụ, hiệu ứng chống ghi trùng; JSON có `summary_t` vi/en/ja; xuất `examples/tool_results.json` | `agent/tools.py` | Test mỗi công cụ với dữ liệu đúng/sai, thiếu bằng chứng, gọi lặp và ảnh có cờ chặn; trạng thái chính chưa đổi | 10 | AGT-01, AGT-02, AGT-13, LLM-05 |
| AGT-04 | Test không có công cụ duyệt/bơm/xóa log; bằng chứng giả/nhầm đầu vào, ảnh cũ/không đọc được, số ngoài giới hạn, người đo không độc lập và vai khán giả đều không vượt rào chắn | `tests/unit/test_agent_safety.py` | Mọi ca an toàn trong 09 qua; bỏ các công cụ read gợi ý vẫn không ghi số đo không hợp lệ | 4 | AGT-03, INB-10 |
| AGT-05 | Prompt + `FINAL_SCHEMA`: `summary_t`, `findings[{tool_ref, text_t}]`, `needs_human`, `plan_id`, `messages[{fid, text_t}]`, `input_gloss`; mọi text là vi/en/ja, glossary en/ja. Chốt schema ngay để frontend không đợi PERF | `agent/prompts.py` | Strict schema hợp lệ; review; thông điệp chứa chỉ dẫn vẫn chỉ là dữ liệu | 4 | AGT-03 |
| AGT-06 | Runner giữ nguyên assistant message/tool_call id, vòng lặp, hậu điều kiện, trace provisional, fallback từ checkpoint và deadline chung | `agent/runner.py`, `server/app.py` | Ảnh F2 live ra từng bước; kết quả cuối đúng kế hoạch commit; lỗi công cụ/đầu ra không làm worker chết | 10 | AGT-05, AGT-13, AGT-14, AGT-16, PERF-01, INB-09, LLM-02 |
| AGT-07 | Chọn model theo loại đầu vào, nâng lên `strong` khi có `suspicious`; ghi deployment đã dùng vào từng bước | `agent/runner.py` | Test với provider giả | 2 | AGT-06 |
| AGT-08 | `RulesPolicy` dùng cùng công cụ và kiểm hậu điều kiện; parser phân biệt bón phân/đơn vị đo, phủ định, số đo cũ, nhiều giá trị và thửa mơ hồ; thiếu bằng chứng thì hỏi lại | `agent/policy.py`, `llm/interpreter.py` | `rules` không gọi mạng; bón phân/phủ định/số đo hôm qua không ghi accepted; baseline đã sửa lỗi qua | 8 | AGT-03, LLM-11, INB-09, INB-10 |
| AGT-09 | Ghi/phát lại adapter outputs và công cụ theo hợp đồng trên; version manifest, chuẩn hóa phép so, overlay runtime và phát hiện drift | `agent/recording.py`, `agent/record.py` | Chặn mạng: toàn kịch bản/ảnh qua; reset vẫn trúng; đổi ảnh/policy báo miss/drift; drift sau công cụ ghi không để hiệu ứng trùng | 8 | AGT-06, AGT-08 |
| AGT-10 | Nối cảnh ảnh F2 vào runner: `on_photo` gọi `AgentRunner` thay cho chuỗi cố định (bước trung gian trước khi có kế hoạch 04) | `engine.py` | Live 5/5 lần: agent gọi ít nhất `read_gauge_photo`, `compare_sources`, `find_independent_measurers`, giữ ảnh và xin đo độc lập | 4 | AGT-06, AGT-09 |
| AGT-11 | Skip hủy request của đúng run, bỏ bản sao chạy dở, chạy quy tắc từ checkpoint; reset hủy job cũ không fallback | `agent/runner.py`, `server/app.py` | Hủy trong ≤ 2 giây; thử tại mỗi công cụ ghi và lúc final/vision; response muộn không commit, lần live kế tiếp vẫn gọi được | 3 | AGT-06, AGT-08, AGT-13 |
| AGT-12 | Cập nhật architecture theo phần đã triển khai tại M1: loop/giao dịch/validator/recording/budgets; giữ rõ INB/UI/cloud còn chưa xong và giới hạn demo | `docs/design/architecture.md` | Review: hiện trạng và thiết kế mục tiêu không bị trộn; không tuyên bố M2/M3 đã triển khai | 2 | AGT-10 |
| AGT-13 | `RunContext` + checkpoint trước đầu vào, bản sao nghiệp vụ, khóa hiệu ứng, commit một lần có epoch/state_version; progress tách trạng thái chính | `agent/context.py`, `engine.py`, `server/app.py` | Fault injection sau từng hiệu ứng; fallback/reset/retry không ghi trùng, không đổi phiên mới; worker ngoài deadline không ghi được | 8 | INB-01, LLM-11 |
| AGT-14 | `validate_required_outcome` và `validate_final`: bằng chứng đúng thửa/đơn vị/giờ, refs tồn tại, kế hoạch đúng draft version, hành động/ngày và needs_human khớp dữ liệu tất định | `agent/validation.py`, `tests/unit/test_agent_validation.py` | Đổi số F2/F3, dùng ref của nhánh aborted, bỏ draft_plan sau đổi dữ liệu hoặc viết sai ngày/hành động đều bị giữ/fallback | 5 | AGT-03, AGT-05 |
| AGT-15 | Bộ eval ngoài kịch bản + fault injection theo 09; lưu fixtures, tiêu chí nghiệp vụ, kết quả live và metadata phiên bản; CI dùng provider giả | `data/evals/`, `tests/unit/test_agent_eval.py`, `scripts/agent_evaluate.py` | ≥ 30 ca phủ cả 6 thửa/loại đầu vào; toàn bộ ca an toàn qua; báo cáo live nêu số đạt/tổng, lỗi và fallback thay vì chỉ 5/5 ảnh F2 | 6 | AGT-04, AGT-06, AGT-08, AGT-09, AGT-11, AGT-14, INB-08 |
| AGT-16 | Ngân sách 50/60 giây, token/request, token/run và số request LLM/phiên; tính cả vision/final/retry, giữ dự toán trước request; hết ngân sách chuyển quy tắc | `config.py`, `agent/context.py`, `llm/azure.py` | Provider giả chậm/429/output dài không vượt số request đã đặt; hết hạn hủy được; log token thực tế và lý do dừng | 4 | LLM-01, LLM-02, AGT-13 |

## Tiêu chí xong (M1)

- AGT-10 đạt 5/5 cho cảnh F2; AGT-15 bổ sung bằng chứng từ ca ngoài kịch bản và lỗi giữa chừng. Mọi ca an toàn bắt buộc trong [09](09-acceptance.md) phải qua.
- `--stage` phát lại toàn bộ phần đã ghi, kể cả vision, với transport mạng bị chặn; không drift ở bản ghi hợp lệ. Miss/drift chạy quy tắc offline, không ghi trùng.
- `test_agent_safety.py`, validation, giao dịch, eval, baseline đã sửa lỗi và e2e đều qua. Không tự duyệt, không commit bản sao khi epoch/state_version cũ.

## Rủi ro

| Rủi ro | Cách giảm |
| --- | --- |
| Model đi đường vòng, gọi thừa công cụ | Gửi kèm `get_cluster_overview` ngay từ đầu; prompt có thứ tự gợi ý; ngân sách 8 lệnh gọi |
| Kết quả live khác nhau giữa các lần | Validator và hậu điều kiện bắt buộc; eval ngoài kịch bản; trên sân khấu dùng bản ghi và hiển thị rõ replay |
| Chèn chỉ dẫn qua tin nhắn/ảnh/tool output | Prechecks, giới hạn quyền theo nguồn, bằng chứng server quản lý, kiểm tại công cụ và trước commit; content filter/khối dữ liệu chỉ là lớp bổ sung |

Tham khảo: vòng lặp trong [OpenAI Docs — Function calling](https://developers.openai.com/api/docs/guides/function-calling), giới hạn của [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs#handling-mistakes) và [Agent safety](https://developers.openai.com/api/docs/guides/agent-builder-safety#combine-techniques).
