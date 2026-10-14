---
name: context-relay
description: >-
  Duy trì trí nhớ dài hạn về một hệ thống code bằng hai file `architecture.md` +
  `task_on_progress.md`, khám phá code theo kiểu "thuốc trúng đích" (grep/sed
  từng đoạn thay vì đọc cả file), và bàn giao nguyên vẹn context sang session /
  tài khoản / công cụ AI khác khi phiên hiện tại đứt giữa chừng. Dùng khi người
  dùng nói "tìm hiểu hệ thống này", "ghi lại kiến trúc", "cập nhật
  architecture.md", "lưu task đang làm dở", "chuẩn bị bàn giao", "sắp hết
  limit", "tiếp tục task từ context cũ", "handoff sang tài khoản khác", "resume
  where the last session left off", "document the architecture", "save progress
  before I run out of context", hoặc khi mở project đã có sẵn
  `task_on_progress.md`. Cũng dùng khi phải làm việc qua SSH terminal và người
  dùng là người chạy lệnh hộ.
allowed-tools: Read Write Edit Glob Grep Bash(grep *) Bash(sed *) Bash(rg *) Bash(ls *) Bash(find *) Bash(wc *) Bash(git *) Bash(cat *) Bash(head *) Bash(tail *)
---

# Context Relay

Một task lớn hiếm khi xong trong một session. Session bị compact, context đầy, phiên đứt,
người tiếp theo (một session khác, một công cụ khác, hoặc chính bạn ngày mai) mở project lên
với đầu óc trắng tinh. Skill này giữ cho **kiến thức không chết theo session**.

Hai file là toàn bộ bộ nhớ:

| File | Vòng đời | Nội dung |
|---|---|---|
| `architecture.md` | vĩnh viễn, chỉ lớn dần | Sự thật đã kiểm chứng về hệ thống |
| `task_on_progress.md` | sinh ra khi bắt đầu task, **xoá khi task xong** | Trạng thái của đúng một task đang dở |

Cả hai đặt ở gốc repo (hoặc `docs/` nếu repo đã có quy ước đó). Nếu chưa có, copy từ
`assets/templates/`.

## Ba luật không được phá

**1. Không ghi điều chưa nhìn thấy.** Mọi dòng trong `architecture.md` phải truy ngược được
về một output cụ thể. Chưa chắc thì đánh dấu `⚠️ chưa verify` chứ không ghi như sự thật. Một
file kiến trúc chứa suy đoán còn tệ hơn không có file nào — session sau sẽ tin nó.

**2. Tìm trúng đích, đừng nuốt cả file.** Mặc định là `grep` ra vị trí → `sed -n` ra đúng
đoạn cần. Chỉ đọc nguyên file khi nó dưới ~200 dòng hoặc bạn thật sự cần toàn bộ luồng.
Xem `references/probing.md`.

**3. Ghi lại trước khi hết chỗ, không phải sau.** Đừng đợi đến lúc context sắp cạn mới nhớ
ra phải cập nhật `task_on_progress.md`. Cập nhật sau mỗi bước có kết quả — xem
"Nhịp cập nhật" bên dưới.

## Mở đầu mỗi session

Trước khi làm bất cứ việc gì khác:

1. Đọc `architecture.md` nếu có. Đây là những gì đã biết — đừng đi khám phá lại.
2. Đọc `task_on_progress.md` nếu có. Có file này nghĩa là **có task đang dở**; đọc phần
   "Bước tiếp theo" và tiếp tục từ đó, đừng bắt đầu lại từ đầu.
3. Nói lại trong một đoạn ngắn: task là gì, đã tới đâu, bước kế tiếp bạn định làm. Chờ người
   dùng xác nhận trước khi sửa code — context cũ có thể đã lỗi thời.
4. Nếu `architecture.md` nhắc tới file/hàm/flag mà bạn sắp dựa vào, **verify nó còn tồn tại**
   (một lệnh grep) trước khi tin.

Không có file nào cả → đây là session đầu tiên: tạo `architecture.md` từ template và bắt đầu
vòng thăm dò.

## Vòng thăm dò (discovery loop)

Lặp cho tới khi trả lời được câu hỏi hiện tại:

```
Đặt MỘT câu hỏi cụ thể về hệ thống
  → đề xuất 1–3 lệnh grep/sed trả lời đúng câu đó
  → chạy (hoặc đưa người dùng chạy, xem "Chế độ SSH")
  → đọc output, nói ra bạn kết luận được gì VÀ chưa kết luận được gì
  → nếu là sự thật bền vững: ghi ngay vào architecture.md kèm bằng chứng
  → câu hỏi tiếp theo
```

Câu hỏi phải cụ thể. "Hệ thống này hoạt động sao?" là câu hỏi tồi. "Request `/api/orders`
đi qua những handler nào trước khi chạm DB?" là câu hỏi tốt — nó dịch thẳng ra được lệnh grep.

Mỗi lượt tối đa 3 lệnh. Nhiều hơn là bạn đang đoán bừa chứ không phải đang truy vết.

## Chế độ SSH (người dùng chạy lệnh hộ)

Khi code nằm trên server mà bạn không có quyền chạy lệnh, hoặc người dùng nói rõ họ muốn
tự chạy: bạn **soạn lệnh, họ chạy, họ dán output lại**.

Trong chế độ này:

- Mỗi lệnh nằm trong một block riêng, copy-paste được, đường dẫn tuyệt đối, không placeholder
  kiểu `<path>` — nếu chưa biết path thì lệnh đầu tiên phải là lệnh đi tìm path.
- Nói trước bạn **mong đợi thấy gì**. Nếu output khác dự đoán, đó là thông tin quan trọng,
  đừng lặng lẽ bỏ qua.
- Giới hạn output: thêm `| head -n 40`, `-m 20`, hoặc `-l` khi chỉ cần biết file nào.
- Không bao giờ đề xuất lệnh ghi/sửa/xoá trong vòng thăm dò. Chỉ đọc.
- Sau mỗi output, giải thích ngắn gọn nó nói lên điều gì — người dùng đang học hệ thống
  cùng bạn, đó là một nửa giá trị của cách làm này.

## Nhịp cập nhật

**`architecture.md`** — ghi ngay khi vừa xác nhận một sự thật bền vững (một luồng, một
điểm vào, một quy ước đặt tên, một chỗ hay gài bẫy). Không đợi cuối task. Format và luật
chống phình xem `references/writing-architecture.md`.

**`task_on_progress.md`** — ghi lại sau mỗi mốc sau:

- vừa xác định xong phạm vi task
- vừa đọc xong một vùng code quan trọng
- vừa sửa xong một file
- vừa bị chặn / vừa sai hướng phải quay lại
- người dùng nói sắp hết limit, sắp nghỉ, hoặc sắp đổi máy/đổi session

Ghi kiểu *thay thế*, không kiểu nhật ký chảy dài: file này luôn mô tả **hiện trạng**, không
phải lịch sử. Phần đã lỗi thời thì xoá.

## Bàn giao

Khi phiên sắp đứt (hết limit, đổi máy, đổi công cụ, context sắp compact), làm đúng ba việc
và nói rõ đã làm xong:

1. Cập nhật `task_on_progress.md` đầy đủ — đặc biệt là phần "Bước tiếp theo" và "Bẫy đã gặp".
2. Đẩy mọi sự thật đã verify từ task này sang `architecture.md`.
3. Đưa người dùng **prompt bootstrap** trong `assets/templates/handoff-prompt.md` để dán vào
   phiên mới.

Phiên mới chỉ cần: hai file đó + prompt bootstrap. Đừng cố tóm tắt lại hội thoại — hội thoại
không phải là bộ nhớ, hai file kia mới là.

Chi tiết và checklist: `references/handoff.md`.

## Đóng task

Khi task hoàn thành và người dùng xác nhận:

1. Rút mọi thứ có giá trị lâu dài từ `task_on_progress.md` sang `architecture.md` — luồng mới
   phát hiện, chỗ gài bẫy, quyết định thiết kế và **lý do**.
2. Xoá `task_on_progress.md`. Không có file này = không có task dở. Giữ lại một file cũ mèm
   là cách nhanh nhất để session sau đi làm lại việc đã xong.
3. Báo lại một dòng: đã gộp gì vào `architecture.md`, đã xoá file tiến độ.

## Khi architecture.md sai

Chuyện này sẽ xảy ra — code đổi, file cũ không đổi. Phát hiện sai thì **sửa tại chỗ ngay**,
không ghi chú "à cái này giờ khác rồi" ở đâu đó rồi đi tiếp. Nếu một mục sai, quét nhanh các
mục liền kề: sai thường đi theo cụm.
