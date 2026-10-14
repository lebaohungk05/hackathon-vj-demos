# 09 · Hợp đồng và nghiệm thu redesign

Tài liệu này là tiêu chí dùng chung của 01–08, không phải kế hoạch triển khai thứ chín có ước lượng riêng. Phạm vi là yêu cầu demo trong repo; Idea Proposal/rubric đầy đủ chưa được đưa vào đây. Code hiện tại chưa thực hiện các hợp đồng mới.

## 1. Ánh xạ yêu cầu

| Yêu cầu | Hành vi cần chứng minh | Task chịu trách nhiệm | Gate |
| --- | --- | --- | --- |
| R01 · Agent điều phối | Model tự chọn công cụ, nhận output, điều tra tiếp; kết luận từ bằng chứng, không nhánh theo id kịch bản | AGT-03/05/06/14/15, INB-04 | M1, M2 |
| R02 · An toàn tưới | FAO-56, giai đoạn lúa/ngưỡng và công suất trạm do mã tính; kế hoạch đúng phiên bản dữ liệu | AGT-01/03/14, INB-09 | M1 |
| R03 · Bằng chứng đầu vào | Nguồn/giờ/thửa/evidence do server gắn; ảnh có cờ chặn không accepted, người đo độc lập được xác nhận | INB-01/09/10, AGT-04, AUD-02 | M1, M3 |
| R04 · Con người duyệt | Không tự duyệt/bơm khi chưa approved; duyệt đúng plan_id/epoch/state_version đã commit | INB-08, DEP-02, UI-11 | M1, M3 |
| R05 · Offline | Stage/replay/rules không gọi mạng ở LLM/vision/forecast/translation/pre-flight; miss/drift hỏi lại hoặc rules | LLM-11, AGT-08/09 | M0, M1 |
| R06 · Ba ngôn ngữ | VI/EN/JA đầy đủ, cùng nghĩa số/thửa/ngày/hành động; bản gốc giữ nguyên | AGT-05/14, PERF-02/03/06/07, UI-04/05 | M2 |
| R07 · Cloud demo | Package cài thường, non-root, data read-only/runtime writable, auth mọi route, recovery có diễn tập | DEP-01..05/07..12 | M3 |
| R08 · Khán giả trực tiếp | Receipt/status riêng thiết bị, queue giới hạn, gửi lại không chạy trùng, vai trò chỉ mô phỏng | AUD-01..04/07..11 | M3 |
| R09 · What-if | 4 loại có cấu trúc và câu tự nhiên; giới hạn tham số, sandbox không ghi nghiệp vụ/không duyệt | UI-09, AUD-05, AGT-13 | M2, M3 |
| R10 · Hồ sơ demo | Hash/tamper/export/completeness đúng kế hoạch/kỳ bằng chứng, rõ nguồn mô phỏng và giới hạn kiểm chứng | INB-11, UI-08 | M2 |
| R11 · Phản hồi/thời gian | Tách receipt/queue/prechecks/tools/final/commit; ngân sách gồm vision/retry, hủy và kết quả muộn có kiểm | AGT-11/16, PERF-01/04/05, AUD-09/10 | M1, M3 |
| R12 · Tính đúng của toàn lần chạy | Fallback/replay/reset không ghi trùng; lời giải thích khớp kế hoạch; eval ngoài kịch bản và lỗi có báo cáo | AGT-13/14/15, INB-06/07, UI-10 | M1, M2 |

## 2. Các hợp đồng bắt buộc

1. **Đầu vào có nguồn rõ.** Nhãn tên người gửi/kind/source/independent do client hoặc model khai không cấp quyền. Mỗi bằng chứng thuộc đúng item; giữ riêng received_at, thời điểm đo, metadata EXIF và clock mô hình. Không dùng GPS thửa cấu hình như GPS thu thật từ ảnh.
2. **Công cụ tự kiểm an toàn.** Model có thể bỏ công cụ read gợi ý, nhưng submit_reading vẫn kiểm bằng chứng/flags/range/confidence/time/source. Content filter, dấu phân cách prompt và danh sách tên tool không thay được kiểm tại công cụ.
3. **Một lần xử lý, một commit.** RunContext chứa bản sao trước đầu vào; effect keys chống lặp; finalize kiểm epoch/state_version. Lỗi/Skip/drift bỏ hiệu ứng tạm; RulesPolicy chạy từ checkpoint, dùng bằng chứng hợp lệ đã có và không gọi mạng. Input rejection không đổi trạng thái nghiệp vụ. Reset hủy hẳn nhánh cũ.
4. **Một kế hoạch cuối.** Sau sửa dữ liệu phải draft_plan lại; final tham chiếu kế hoạch và refs của nhánh sẽ commit. Finish không tạo plan mới sau final. Câu thiếu cơ sở dùng mẫu tất định; số có trong payload vẫn phải đúng thửa/đơn vị/giờ/hành động.
5. **Offline bao trùm.** Replay adapter output, chạy lại code nghiệp vụ; hash ảnh và phiên bản policy/schema nằm trong manifest. Epoch không làm cache miss sau reset nhưng vẫn chặn commit cũ. Không đưa thời gian thật hoặc transport live/cache vào so ngữ nghĩa.
6. **What-if cách ly.** Chỉ cấp run_what_if cho sandbox; không cấp công cụ commit/duyệt. Trạng thái nghiệp vụ chính giống nhau trước/trong/sau thử nghiệm, kể cả cancel/lỗi/reset; progress và số liệu vận hành có thể thay đổi. Callback muộn không sửa phiên chính.
7. **Ngân sách hữu hạn.** ≤ 8 công cụ/run; mặc định dừng request LLM/vision/final/retry ở 50 giây, hoàn tất job ≤ 60 giây. Token/request/run/session giới hạn bằng config đã đo ở INF-08; số request gồm cả retry. Một lớp retry; không reset budget phiên vận hành bằng phím reset nghiệp vụ.
8. **Quyền đọc tách biệt.** Presenter đọc snapshot/media/evidence và điều khiển; audience chỉ gửi và xem status của mình. Approval thiếu hoặc stale plan/epoch/version, provisional và sandbox đều bị từ chối. Health công khai không lộ dữ liệu/bí mật.

## 3. Bộ ca tối thiểu

CI dùng provider/clock/transport giả, không cần secret. Chặn kết nối ra ngoài trong test offline; loopback của HTTP/e2e vẫn được phép. Live eval dùng dữ liệu demo, có model/prompt/policy version và tách rõ live/replay/rules.

| Nhóm | Ca cần có | Kết quả bắt buộc |
| --- | --- | --- |
| Parser | “đang bón phân”, “không còn nước ba phân”, “hôm qua ba phân, hôm nay chưa đo”, nhiều số/thửa hoặc thiếu đơn vị | Không ghi accepted; hỏi lại/từ chối rõ; câu nước ba phân hiện tại hợp lệ vẫn ra +3 cm |
| Nguồn | Vai khán giả giả HTX/trạm, cờ independent tự khai, evidence_id từ item khác, station_notice nguồn giả | Không đổi quyền/lịch/resolve conflict; không đọc receipt người khác |
| Ảnh | Ảnh cũ, không đọc được, không phải thước, thiếu giờ/offset, low confidence, source disagree; ảnh mới ngày thi ánh xạ vào clock mô hình; model bỏ compare_sources | Không accepted trái cờ; không so nhầm ngày thực với fixture; giữ dấu vết hợp lệ và hỏi lại/đo độc lập |
| Đo lại | Đúng/sai người, request, thửa, ống/phương pháp; ảnh chụp lại cùng ống | Chỉ nguồn và phương pháp được server xác nhận mới đóng xung đột |
| Lịch | Thông báo dời sang ngày chưa có trong runs; ngày ngoài cửa sổ; event trùng/đến muộn | Tạo lượt mới/hủy cũ đúng một lần hoặc reject; không tiến ngày tùy ý |
| Safety tưới | Trổ bông/bón thúc, số vượt range, lệch > 5 cm, công suất trạm, số đo cũ | Chính sách tất định giữ; dữ liệu không đủ tạo needs_human, không lời model vượt gate |
| Final | Đổi số F2/F3, sai dấu/đơn vị/ngày/hành động, ref không có hoặc từ nhánh aborted, thiếu draft sau sửa dữ liệu | Validator chặn/fallback; plan và giải thích cuối khớp; đủ ngôn ngữ đúng nghĩa |
| Giao dịch | Lỗi sau mỗi propose, gọi công cụ lặp, Skip trong vision/final/commit, response muộn, reset giữa run | Không trùng log/plan/asks; không hiệu ứng chạy dở; phiên cũ không ghi vào phiên mới |
| Duyệt | Bỏ duyệt, reject, thiếu context, context cũ, plan superseded, plan sandbox/provisional | Không tự approval/irrigation; chỉ plan hiện tại approved đúng context được mô phỏng bơm |
| Replay | Sau nhiều reset/goto; đổi byte ảnh/policy; drift sau propose; recording miss; GET forecast offline | Không request ra ngoài; trúng bản ghi hợp lệ, miss/drift rules an toàn không ghi trùng |
| Mobile | 3 máy đồng thời, queue đầy, retry/reload, cookie mới, IP spoof, item_id người khác, reset khi queued | Receipt nhanh, FIFO/bounded queue, đúng chủ status, không chạy trùng/cũ; limits trả 429 |
| What-if | 4 loại + câu tự nhiên hợp lệ/vượt giới hạn, cancel/lỗi/đóng/reset | Trạng thái nghiệp vụ chính không bị sửa; không có approval hay log bằng chứng sandbox |
| Cloud | pip install . từ cwd khác, data read-only, user non-root, image upload/cache, probes khi agent bận, restart | Paths/quyền đúng; health không treo; recovery ≤ 60 giây bằng recording, yêu cầu duyệt lại |
| Hồ sơ | Duyệt cũ rồi tạo plan mới, audience giả người đo, metadata thiếu, tamper/export | Completeness không báo đủ sai; nguồn mô phỏng rõ; hash phát hiện sửa phần, không tuyên bố chống tính lại chuỗi |
| Ngân sách | Timeout/429 nhiều lần, retry-after dài, final/vision chậm, token budget hết, Skip rồi live lại | Một lớp retry; giới hạn request/deadline hiệu lực, hủy ≤ 2 giây; rules hoàn tất và không đóng hỏng client chung |

AGT-15 phải có ít nhất 30 ca ngoài kịch bản, phủ cả 6 thửa và 6 kind; mỗi nhóm rủi ro ở bảng trên có kiểm tương ứng trong bộ test/task chuyên trách. Không ép mọi ca gọi cùng một chuỗi tool. Ghi số đạt/tổng, ca thất bại, fallback và lý do; toàn bộ ca an toàn bắt buộc phải qua, không dùng tỷ lệ trung bình để bỏ qua lỗi an toàn.

## 4. Bằng chứng qua gate

| Gate | Bằng chứng phải lưu trong PR/qa-report | Không đủ để coi là qua |
| --- | --- | --- |
| M0 | Baseline/version; unit/e2e/ruff; import không CLI; smoke Azure; mode/config/retry/cancel/offline có transport bị chặn | Chỉ chạy một tin nhắn Azure |
| M1 | F2 5/5 và eval ≥ 30 ca; an toàn/transaction/fault injection/final/skip qua; replay vision + reset offline; không tự duyệt | Chỉ 5/5 ảnh F2 hoặc test danh sách tên tool |
| M2 | Scenario có duyệt tường minh; baseline sửa lỗi có giải thích; e2e 3 màn/3 ngôn ngữ/carbon/what-if; provenance và kế hoạch/approval context đúng | Chỉ giao diện đẹp hoặc đủ key vi/en/ja |
| M3 | Docker non-root chạy đủ kịch bản; route auth/mobile queue/status/limits; cloud 4G và restart/provider-error rehearsal; bảng latency/token/queue/fallback | Chỉ health 200 hoặc receipt nhanh |

Latency: receipt ≤ 1 giây, phản hồi hiển thị đầu ≤ 5 giây; prechecks < 1 giây từ lúc job bắt đầu; text không chờ queue có median hoàn thành ≤ 20 giây; mỗi job gồm fallback ≤ 60 giây. Báo cáo riêng queue_wait và tổng thời gian từ khi gửi, trung vị/p95/max, cỡ mẫu, lỗi và fallback. Mỗi loại/deployment ít nhất 10 lượt đo; không gọi receipt là thời gian agent hoàn thành.

## 5. Ranh giới nghiệm thu

Đạt M3 nghĩa là đủ bằng chứng cho demo theo phạm vi trên, chưa chứng minh an toàn tưới ngoài ruộng hay hồ sơ đủ để bán tín chỉ carbon. Triển khai thực tế cần thêm tích hợp dữ liệu/thiết bị, xác thực nguồn/người đo, lưu bền và khôi phục giao dịch, vận hành nhiều phiên, chữ ký/neo hash, kiểm định nghiệp vụ thực địa và phương pháp MRV được bên thẩm định chấp nhận. Các việc này chưa nằm trong 342 giờ của 01–08.
