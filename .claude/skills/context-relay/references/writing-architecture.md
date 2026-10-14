# Viết architecture.md cho đúng

File này sẽ được đọc bởi một AI chưa biết gì về hệ thống, với ngân sách context có hạn. Viết
cho người đọc đó.

## Cái gì được vào, cái gì không

**Vào:**

- Điểm vào của hệ thống: chạy bằng lệnh gì, request đi vào ở đâu, cron/worker nào tồn tại.
- Luồng xử lý end-to-end của các nghiệp vụ chính, kèm file:dòng ở mỗi chặng.
- Ranh giới giữa các module, và ai gọi ai.
- Quy ước không đoán được từ code: cách đặt tên, chỗ để config, kiểu migration, quy trình deploy.
- **Bẫy**: chỗ trông có vẻ đúng nhưng sẽ hỏng. Đây là mục có giá trị cao nhất cả file.
- Quyết định thiết kế **kèm lý do**. "Dùng queue vì API bên thứ ba giới hạn 5 req/s" giữ cho
  session sau khỏi đi gỡ cái queue đó.

**Không vào:**

- Bất cứ thứ gì một lệnh grep 5 giây là ra: danh sách file, chữ ký hàm, tên cột.
- Dán code dài. Dẫn `file:dòng` thay vì copy.
- Nhật ký làm việc ("hôm nay đã sửa…"). Cái đó thuộc `task_on_progress.md` và chết cùng task.
- Suy đoán. Chưa verify thì gắn `⚠️ chưa verify` hoặc đừng viết.

## Format mỗi mục

```markdown
### Luồng tạo đơn hàng

POST /api/orders → `routes/orders.ts:42` → `OrderService.create()` `services/order.ts:118`
→ validate ở `validators/order.ts:30` → ghi DB `repo/order.ts:77` → đẩy event vào queue
`queue/publisher.ts:25`.

Giao dịch mở ở service, **không** ở repo — repo gọi ngoài transaction sẽ commit lẻ.

Verified 2026-09-17 · `grep -rn "OrderService" src/ -m 20`
```

Ba thứ bắt buộc: **đường đi có file:dòng**, **điều cần cảnh giác**, **ngày + cách verify**.

## Bố cục file

Giữ đúng thứ tự này; session mới đọc từ trên xuống và thường dừng giữa chừng, nên thứ quan
trọng nhất phải nằm trên.

1. `## Hệ thống này là gì` — 3–5 dòng. Làm gì, cho ai, chạy ở đâu.
2. `## Chạy & deploy` — lệnh chạy dev, chạy test, deploy.
3. `## Bản đồ` — bảng thư mục → trách nhiệm, mỗi dòng một câu.
4. `## Các luồng chính` — mục quan trọng nhất, format như trên.
5. `## Quy ước` — những thứ phải theo khi viết code mới.
6. `## Bẫy` — danh sách gạch đầu dòng, mỗi cái một dòng, cụ thể.
7. `## Vùng chưa khám phá` — thành thật liệt kê chỗ chưa đụng tới. Ngăn session sau tưởng
   file này đã đầy đủ.

## Chống phình

File này chỉ hữu ích khi còn đọc nổi. Khi vượt ~500 dòng:

- Gộp các mục trùng lặp.
- Tách phần chi tiết của một domain ra `docs/arch/<domain>.md`, để lại một dòng trỏ sang.
- Xoá mục nói về code đã bị xoá — đừng giữ làm "lịch sử", git giữ hộ rồi.

Mỗi lần đóng task, dành một phút quét lại toàn file. Rẻ hơn nhiều so với việc để nó thối dần.
