# Prompt bootstrap cho phiên mới

Dán nguyên khối dưới đây vào phiên/công cụ mới. Nếu công cụ mới **không** có skill
`context-relay`, dán kèm cả nội dung hai file.

---

```
Tôi đang tiếp tục một task đang làm dở từ phiên trước.

Dùng skill context-relay.

Project: <đường dẫn / repo>
Hai file bộ nhớ nằm ở: ./architecture.md và ./task_on_progress.md

Trước khi sửa bất cứ dòng code nào, làm đúng thứ tự sau:
1. Đọc cả hai file.
2. Nói lại bằng lời của bạn: task là gì, đã tới đâu, bước kế tiếp bạn định làm.
3. Verify bằng grep 2–3 tuyên bố quan trọng nhất trong architecture.md mà bạn sắp dựa vào —
   file có thể cũ hơn code. Sai thì sửa file trước.
4. Hỏi tôi xác nhận rồi mới làm tiếp.

Chế độ chạy lệnh: <CHỌN MỘT>
  (a) Bạn tự chạy grep/sed trong project.
  (b) Tôi làm việc qua SSH — bạn soạn lệnh, tôi chạy trên server và dán output lại.
      Mỗi lượt tối đa 3 lệnh, chỉ đọc, luôn chặn output bằng head/-m.

Cập nhật task_on_progress.md sau mỗi bước có kết quả, đừng đợi tôi nhắc.
```

---

## Nếu công cụ mới không có skill

Thêm vào sau prompt trên:

```
Nội dung architecture.md:
<dán>

Nội dung task_on_progress.md:
<dán>
```

Và bổ sung luật cốt lõi, vì công cụ đó không đọc được SKILL.md:

```
Luật làm việc:
- Không ghi vào architecture.md điều chưa nhìn thấy bằng chứng. Chưa chắc thì đánh dấu
  "⚠️ chưa verify".
- Tìm code bằng grep định vị rồi sed cắt đúng đoạn, không đọc cả file trừ khi file dưới
  200 dòng.
- Mỗi lượt hỏi tối đa 3 lệnh, luôn chặn output.
- architecture.md = sự thật bền vững. task_on_progress.md = hiện trạng task, không phải nhật ký.
- Task xong: gộp phần giá trị lâu dài vào architecture.md rồi xoá task_on_progress.md.
```
