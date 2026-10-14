# ADR 0004: Agent gọi công cụ tất định qua Azure OpenAI

- Trạng thái: đề xuất
- Ngày: 2026-10-14
- Thay thế: [ADR 0001](0001-claude-cli-as-llm-client.md) khi được chấp nhận; thay một phần [ADR 0003](0003-committed-deterministic-caches.md)

## Bối cảnh

Luồng hiện tại là chuỗi hàm `on_<sự kiện>` gọi công cụ theo thứ tự cố định, kèm kết luận viết sẵn. LLM chỉ làm 3 việc nhỏ qua Claude CLI; mỗi lần gọi mất 10–50 giây, đọc ảnh phải cấp quyền đọc file. Demo vì thế giống bản trình chiếu hơn một agent. Chi tiết ở [kế hoạch làm lại](../redesign/README.md).

## Quyết định

- Dùng **Azure OpenAI** với function calling, gọi bằng SDK `openai` ngay trong tiến trình server. Gỡ hẳn Claude CLI.
- Hai deployment: `fast` cho tin nhắn chữ, transcript HTX, what-if; `strong` (có vision) cho ảnh và ca xung đột. Model/version/API và capacity → TPM/RPM chốt bằng INF-01/08, không suy TPM cố định cho mọi model.
- Xác thực bằng API key: `.env` ở máy dev, secret của Container App trên cloud.
- Model nhận InboxItem, chọn công cụ, dùng output để điều tra tiếp rồi đề xuất. Read chỉ đọc; propose tạo hiệu ứng trên RunContext. Không có công cụ duyệt lịch, bật bơm, sửa bản ghi cũ hay gửi tin ra ứng dụng ngoài.
- Server gán nguồn/danh tính/thời điểm/evidence_id. Công cụ tự kiểm nguồn, số đo, cờ ảnh và độc lập của người/ống đo; model không được tự khai quyền. prechecks và content filter không thay thế kiểm tại công cụ.
- RunContext giữ checkpoint trước đầu vào, epoch/state_version và khóa hiệu ứng chống lặp. Kế hoạch tạo trước lời giải thích cuối, validator kiểm số/thửa/giờ/hành động/refs; finish commit đúng bản sao và kế hoạch đó một lần, luôn proposed. Đến giờ bơm chưa duyệt thì bỏ lượt, không tự duyệt.
- Ngân sách ≤ 8 công cụ, cắt request LLM mặc định 50 giây, job ≤ 60 giây gồm vision/retry/final/validation/commit; queue_wait đo riêng. Token/request/run/session có giới hạn; một lớp retry và cancel theo run. Reset nghiệp vụ không xóa budget phiên vận hành.
- Lỗi/Skip/quá giờ/output filter/replay drift bỏ bản sao chạy dở rồi RulesPolicy chạy offline từ checkpoint; input filter/chỉ dẫn bị chặn thì từ chối, reset hủy run cũ. Không commit response muộn.
- Recording có adapter outputs, hash ảnh và phiên bản prompt/schema/policy/model. Fixture đã review ở data/agent_runs; recording live mới ghi runtime. Replay adapter không gọi mạng, chạy lại công cụ nghiệp vụ trên bản sao và so kết quả ngữ nghĩa; không so timing/transport source, không bỏ nguồn bằng chứng. Miss/drift fallback an toàn, reset không làm cache miss chỉ vì epoch.
- Mode live thiếu cấu hình fail startup; auto thiếu cấu hình cảnh báo rồi cache/rules; replay/stage/rules offline cả vision/forecast/translation/pre-flight. Bỏ dịch riêng sau PERF-03; ở M0 phải port bộ dịch sang Azure trước khi xóa client cũ.

## Hệ quả

- Khán giả thấy trace công cụ và bằng chứng cùng nhãn live/replay/rules, provisional/committed/aborted; không hiển thị suy luận nội bộ của model. Kịch bản và đầu vào trực tiếp chung inbox.
- Bỏ được tiến trình con, quyền đọc file cho model và lượt dịch riêng.
- Cần subscription Azure/quota và chi phí token. TPM giới hạn tốc độ, budget alert không tự ngắt; ứng dụng cần giới hạn lời gọi và runbook teardown.
- Kết quả live có thể khác giữa các lần, nhưng kết quả nghiệp vụ vẫn do rào chắn tất định quyết định.
- API key là bí mật phải quản lý và xoay; không bao giờ commit.
- M1 cần eval ngoài kịch bản và fault injection, không chỉ ảnh F2 5/5. Nghiệm thu theo [09](../redesign/09-acceptance.md); thiết kế đủ cho demo, chưa cho thiết bị/hồ sơ carbon thực địa.

## Model

Điền sau INF-01; kiểm năng lực và đo token ở INF-07.

| Deployment | Model/version | API/client | Region | Capacity → TPM/RPM | Thời gian trung vị |
| --- | --- | --- | --- | --- | --- |
| `fast` | | | | | |
| `strong` | | | | | |
