# Thăm dò trúng đích bằng grep/sed

Mục tiêu: đưa vào context đúng 20 dòng cần thiết thay vì 2000 dòng file. Ít token hơn, ít
hiểu nhầm hơn, và người dùng nhìn được chính xác bạn đang tìm gì.

## Thứ tự chuẩn: định vị → cắt lát → mở rộng

**1. Định vị** — chỉ lấy tên file và số dòng, chưa lấy nội dung.

```bash
grep -rn "createOrder" /srv/app/src --include="*.ts" -l
grep -rn "def process_payment" /srv/app -m 20
```

**2. Cắt lát** — biết dòng rồi thì lấy đúng đoạn.

```bash
sed -n '120,175p' /srv/app/src/orders/service.ts
```

**3. Mở rộng có chọn lọc** — chỉ khi đoạn vừa đọc gọi sang chỗ khác mà bạn thật sự cần theo.

## Các lệnh đáng thuộc lòng

| Cần gì | Lệnh |
|---|---|
| File nào có nhắc tới X | `grep -rl "X" DIR --include="*.py"` |
| X xuất hiện ở dòng nào | `grep -rn "X" DIR -m 30` |
| Xem kèm ngữ cảnh quanh match | `grep -rn -C 5 "X" FILE` |
| Chỉ lấy dòng khai báo, bỏ lời gọi | `grep -rn "^\s*\(def\|function\|class\) .*X" DIR` |
| Đoạn từ dòng A đến B | `sed -n 'A,Bp' FILE` |
| Từ một mốc tới mốc kế tiếp | `sed -n '/^class OrderService/,/^class /p' FILE \| head -n 80` |
| Khung xương của file (chỉ signature) | `grep -n "^\(def\|class\|function\|export\)" FILE` |
| File to cỡ nào (quyết định có nên đọc cả không) | `wc -l FILE` |
| Ai import module này | `grep -rn "from .*orders import\|require(.*orders" DIR` |
| Biến môi trường nào được đọc | `grep -rn "process\.env\.\|os\.environ\|getenv" DIR -m 40` |
| Route/endpoint được đăng ký ở đâu | `grep -rn "app\.\(get\|post\|put\)\|@router\.\|urlpatterns" DIR` |
| Đổi gần đây ở vùng này | `git log --oneline -15 -- PATH` |
| Ai sửa dòng này và vì sao | `git log -L A,B:FILE --oneline \| head -n 40` |

## Kỷ luật

- **Luôn chặn output.** `| head -n 40` hoặc `-m N`. Một lệnh grep không chặn trên repo lớn
  có thể nuốt sạch context — đúng thứ skill này sinh ra để tránh.
- **Một câu hỏi, một lệnh.** Nếu phải chạy 5 lệnh mới trả lời được, câu hỏi còn quá rộng;
  chẻ nhỏ ra.
- **`-l` trước `-n` trước nội dung.** Mỗi nấc mới đắt hơn nấc trước.
- **Escape ký tự đặc biệt.** `grep "config\[.debug.\]"`, và `grep -F` cho chuỗi cố định.
- **Windows / Git Bash:** đường dẫn dùng `/d/du-an/...` hoặc forward slash; `rg` nếu có sẵn
  thì nhanh hơn và tự bỏ qua `node_modules`, `.git`.
- **Có ripgrep thì dùng:** `rg -n "X" -g "*.ts" -m 30` — mặc định tôn trọng `.gitignore`.

## Khi nào thì đọc cả file

Đọc nguyên file là hợp lý khi: file dưới ~200 dòng; hoặc bạn sắp sửa nó và cần chắc không
phá thứ khác; hoặc đó là file cấu hình/schema mà mọi dòng đều đáng kể. Ngoài ba trường hợp
đó, cắt lát.

## Ghi lại dấu vết

Khi một lệnh cho ra kết luận đáng nhớ, ghi kèm chính lệnh đó vào `architecture.md`. Session
sau chạy lại một lệnh là verify được ngay thay vì phải đi dò lại từ đầu.
