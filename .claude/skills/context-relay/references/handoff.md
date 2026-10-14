# Bàn giao giữa các phiên

Bàn giao là lúc dễ mất mát nhất. Phiên mới không có hội thoại cũ — nó chỉ có những gì đã
nằm trên đĩa. Bất cứ điều gì chỉ tồn tại trong đầu phiên cũ đều mất sạch.

Áp dụng cho mọi kiểu đứt gãy: context sắp compact, hết quota, đổi máy, đổi công cụ AI, hoặc
đơn giản là mai làm tiếp.

## Checklist trước khi đứt phiên

Chạy khi người dùng báo sắp dừng, **hoặc** khi bạn tự thấy context đã dùng quá nhiều và task
còn dài. Đừng đợi được nhắc.

- [ ] `task_on_progress.md` khớp với hiện trạng thật: file nào đã sửa, sửa gì, đang kẹt ở đâu.
- [ ] Phần "Bước tiếp theo" viết ở dạng **hành động thực thi được**, không phải ý định mơ hồ.
      Tồi: "tiếp tục làm phần auth". Tốt: "sửa `middleware/auth.ts:88` để đọc token từ header
      `X-Api-Key`; test bằng `npm test -- auth.spec.ts`".
- [ ] Mọi sự thật đã verify trong task này đã được đẩy sang `architecture.md`.
- [ ] Mọi ngõ cụt đã thử được ghi vào "Bẫy đã gặp" — nếu không, phiên sau sẽ thử lại y hệt.
- [ ] Code đang dở: hoặc commit lên nhánh riêng, hoặc ghi rõ trong file tiến độ là đang có
      thay đổi chưa commit ở những file nào.
- [ ] Đưa người dùng prompt bootstrap (`assets/templates/handoff-prompt.md`).

## Cái phiên mới cần

Đúng ba thứ:

1. `architecture.md`
2. `task_on_progress.md`
3. Prompt bootstrap

Nếu phiên mới nằm trên máy/tài khoản khác, hai file trên phải đi cùng — qua git, qua thư mục
chia sẻ, hoặc dán trực tiếp. Bộ skill cũng nên đi kèm nếu quy trình phụ thuộc vào nó.

**Đừng** cố tóm tắt lại hội thoại thành một đoạn văn dài rồi dán sang. Tóm tắt hội thoại bị
lẫn thứ tự thời gian với hiện trạng, và phiên mới không phân biệt được cái gì còn đúng. Hai
file kia luôn mô tả hiện tại.

## Nhận bàn giao

Phiên mới, trước khi gõ một dòng code:

1. Đọc cả hai file.
2. Nói lại bằng lời của mình: task là gì, đã tới đâu, bước kế tiếp. Đây là bài kiểm tra xem
   bàn giao có đủ không — nếu bạn phải đoán chỗ nào, chỗ đó là lỗ hổng, hỏi người dùng ngay.
3. Verify 2–3 tuyên bố quan trọng nhất trong `architecture.md` bằng grep. File có thể cũ hơn
   code. Sai thì sửa file trước, rồi mới làm task.
4. Chỉ sửa code sau khi người dùng xác nhận hướng đi vẫn đúng.

## Khi bàn giao thất bại

Dấu hiệu: phiên mới hỏi lại những câu phiên cũ đã trả lời, hoặc đi khám phá lại vùng code đã
khám phá. Đừng chịu đựng — dừng lại, bổ sung đúng phần còn thiếu vào `architecture.md` hoặc
`task_on_progress.md` ngay lúc đó. Lỗ hổng bàn giao không tự lành, và lần đứt phiên sau nó
vẫn nằm nguyên ở đấy.
