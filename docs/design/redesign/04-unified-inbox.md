# 04 · Hộp thư chung (INB)

Tổng: 47 giờ. Nhánh: `feat/inb-inbox`. INB-01, INB-08..10 làm trước M1 để cung cấp hợp đồng đầu vào và rào chắn cho AGT; phần chuyển toàn bộ kịch bản/giao diện hoàn thành sau M1.

## Mục tiêu

Kịch bản và tin nhắn trực tiếp đi chung **một** luồng. Kịch bản chỉ còn là danh sách tin nhắn đến theo thời gian. Mọi tiêu đề kết quả và kết luận được tạo ra từ lần chạy của agent.

## Thiết kế

```python
@dataclass(frozen=True)
class InboxItem:
    id: str
    at: datetime             # giờ mô hình đã chuẩn hóa; server chọn cho đầu vào live
    kind: Literal["sensor", "weather", "photo", "text", "voice", "station_notice"]
    sender: str | None        # nhãn hiển thị, không phải căn cứ phân quyền
    channel: str              # server gán từ adapter/endpoint, client không tự khai
    received_at: datetime     # giờ server nhận; tách khỏi giờ đo và giờ mô hình
    source_id: str            # danh tính/adapter do server xác nhận
    evidence_id: str          # tham chiếu bằng chứng server quản lý
    text: str | None = None
    image: str | None = None
    data: dict = field(default_factory=dict)   # ví dụ {"from": "2026-03-03", "to": "2026-03-06"}
```

```text
Demo.handle(item):
    pre = prechecks(item, immutable_snapshot) ; publish_progress(pre)
    if pre.rejects_input: return rejected_run(item, pre)  # không đổi trạng thái nghiệp vụ
    ctx = RunContext(before_state, item, evidence, epoch, state_version)
    advance_to(ctx, item.at)
    apply_trusted_input(ctx, item)   # cảm biến/thời tiết/thông báo trạm đã validate
    run = agent.run(ctx, pre)        # lỗi → bỏ bản sao, chạy quy tắc từ before_state
    finish(ctx, run)                 # commit đúng kế hoạch draft, một lần
    history.append({item, run})      # thao tác thuộc cùng commit
```

- `station_notice` chỉ nhận từ adapter trạm hoặc người trình bày đã xác thực. Validate `from/to`, khoảng ngày và phiên bản lịch; trên bản sao hủy lượt cũ, tạo lượt mới, ghi nguồn thông báo và vô hiệu kế hoạch cũ. Model chỉ đọc ý định, không quyết định ngày.
- Cảm biến/thời tiết giữ **giá trị đầu vào thật** và thời điểm đo/hiệu lực. Chỉ bỏ số đo ảnh/kết luận viết sẵn; không xóa giá trị cảm biến hay lượng mưa khỏi JSON. Mỗi kind có schema riêng, giới hạn số/ngày và xử lý sự kiện trùng hoặc đến muộn; dữ liệu ngoài cửa sổ mô phỏng hỏi lại, không tiến đồng hồ tùy ý.
- `voice` là transcript do cán bộ HTX nhập/ghi hộ. Nhận file âm thanh và speech-to-text không thuộc backlog này. `zalo`/`sensor` là nhãn nguồn mô phỏng, chưa phải tích hợp tài khoản hay thiết bị thật.
- Người gửi không có trong danh sách vẫn được nhận; endpoint khán giả gán nguồn `audience` và vai mô phỏng. Không tin nhãn tên hoặc cờ `independent` trong nội dung. Bằng chứng khán giả được đánh dấu mô phỏng, không thỏa tiêu chí người đo thực địa.
- Xác nhận đo lại lưu `request_id`, `source_id`, phương pháp/ống đo và liên hệ với bằng chứng tranh chấp. Vai trò của người đo lấy từ danh sách server, không lấy từ model hay lựa chọn trên `/m`.
- Mọi timestamp có timezone, chuẩn hóa qua múi giờ địa điểm đã cấu hình. Fixture kịch bản dùng giờ đo/giờ mô hình cố định. Với ảnh live tại buổi thi, giữ EXIF gốc, tính tuổi ảnh từ received_at thực rồi ánh xạ tuổi đó vào clock mô hình để so trận mưa mô phỏng; không so trực tiếp ngày thi với ngày tháng 2 trong fixture. Metadata thiếu offset/không xác định tuổi đáng tin thì hỏi lại, không là bằng chứng duy nhất; server nhận giờ gốc không có nghĩa đã xác thực EXIF.

## Task

| ID | Việc | File chính | Xong khi | Giờ | Phụ thuộc |
| --- | --- | --- | --- | --- | --- |
| INB-01 | InboxItem/registry bằng chứng/schema từng kind; nguồn/giờ/ID server gán, timezone và ánh xạ tuổi ảnh live sang clock mô hình; giữ số liệu thô, bỏ kết luận/số đo ảnh viết sẵn | `agent/inbox.py`, `data/scenario/cluster_a.json` | Nguồn/số/ngày sai bị reject; ảnh mới tại ngày thi không bị so nhầm với fixture; ảnh cũ/giờ mơ hồ được giữ; acts/short_t và giá trị sensor/mưa vẫn có | 5 | – |
| INB-02 | Viết lại handle/next/goto/post_message theo prechecks và giao dịch; lịch sử/progress dùng đúng run_id và trạng thái provisional/committed/aborted | `engine.py` | Cả kịch bản stage; đầu vào bị từ chối không advance/đổi log/kế hoạch; reset bỏ job cũ | 8 | INB-01, INB-09, M1 |
| INB-03 | `agent/present.py`: từ một lần chạy suy ra `focal`, `verdict`, tiêu đề bước (`summary_t`) | `agent/present.py` | Test cho 6 bước kịch bản + 3 tin nhắn mẫu | 5 | INB-02 |
| INB-04 | Xóa on_start..on_pump_change và kết luận viết sẵn; giữ danh tính/người đo trong dữ liệu cấu hình; chuyển áp đầu vào sang INB-09, điều tra sang công cụ/RulesPolicy | `engine.py` | Không còn nhánh theo id kịch bản; thông báo trạm vẫn đổi lịch và weather/sensor vẫn được áp | 4 | INB-03, INB-09, INB-10 |
| INB-05 | `snapshot()`: thêm `run` cho mỗi mục `history` (`steps`, `summary_t`, `needs_human`, `engine`, `deployment`, `source`); giữ `trace` cũ đến khi xong UI-03 | `engine.py` | Test hợp đồng API cập nhật | 2 | INB-02 |
| INB-06 | Baseline stage/rules với thao tác duyệt tường minh; lập danh sách thay đổi do sửa parser, bỏ tự duyệt và sửa completeness; so hành vi hợp lệ, không khóa lỗi cũ | `tests/unit/test_baseline.py`, baseline fixtures | Qua cả luồng có duyệt và không duyệt; mỗi thay đổi baseline có lý do/test riêng | 5 | INB-04, INB-08, INB-11 |
| INB-07 | Ghi toàn bộ agent_runs và adapter outputs cho kịch bản + 5 tin mẫu; cập nhật API contract và manifest phiên bản | `data/agent_runs/`, `tests/unit/` | Chặn mạng vẫn chạy hết; reset/goto trúng bản ghi; byte ảnh sai không dùng bản ghi cũ | 4 | INB-04, AGT-09 |
| INB-08 | **P0, làm trước M1**: bỏ tự duyệt ngay trong run_pump_if_due hiện tại; chưa approved thì không bơm, ghi pump_skipped_unapproved một lần/lượt, hiện needs_human | `engine.py`, `docs/design/architecture.md` | Bỏ duyệt/đã reject/plan mới supersede không tạo approval hay irrigation; lịch đã approved đúng phiên bản mới chạy | 3 | LLM-00 |
| INB-09 | `apply_trusted_input(ctx, item)` cho sensor/weather/station_notice; validate nguồn, ngày, đơn vị, giới hạn; thay lịch trên bản sao, xử lý trùng/đến muộn | `agent/intake.py`, `engine.py` | Test ngày dời không có sẵn trong lịch, nguồn giả, event trùng/đến muộn; fallback không áp thông báo hai lần | 4 | INB-01, AGT-13 |
| INB-10 | Registry source/person/instrument và xác nhận đo độc lập theo request_id; khán giả không thể giả cán bộ hay đóng xung đột | `agent/inbox.py`, `agent/tools.py` | Tên/cờ độc lập tự khai bị bỏ; sai request/ống đo/người gửi không resolve_pending; người hợp lệ xác nhận được | 4 | INB-01, AGT-03 |
| INB-11 | Completeness tham chiếu đúng kế hoạch hiện tại/kỳ bằng chứng, nguồn người đo hợp lệ, metadata và xung đột; GPS thửa cấu hình không phải GPS thu từ ảnh | `engine.py`, `tests/unit/test_evidence.py` | Duyệt cũ không làm kế hoạch mới đủ bằng chứng; audience không thỏa đo thực địa; thiếu metadata vẫn chưa đủ | 3 | INB-04, INB-10 |

## Tiêu chí xong

- Kịch bản 6 đầu vào chạy hết bằng `handle(InboxItem)`; baseline giữ hành vi hợp lệ và ghi rõ các thay đổi sửa lỗi đã duyệt trong review.
- Một tin nhắn trực tiếp và một bước kịch bản tạo ra cùng dạng `run` trong snapshot.
- Mọi hiệu ứng đi qua giao dịch; thông báo trạm/sensor/weather có nguồn server xác nhận. Không có số đo/kết luận ảnh viết sẵn làm phương án dự phòng.

## Rủi ro

- Mất các ô hiển thị đặc thù (ô Bà Sáu). Thông tin chuyển vào `FieldSpec.note` để agent và giao diện tự dùng (UI-03).
