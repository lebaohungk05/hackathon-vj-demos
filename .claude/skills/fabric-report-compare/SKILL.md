---
name: fabric-report-compare
description: Kiểm chứng report Power BI / Microsoft Fabric chạy giống hệt nhau trước và sau khi tối ưu semantic model, bằng cách chụp và so sánh tự động qua Playwright rồi xuất một file HTML kèm ảnh base64 khoanh đỏ vùng khác biệt. Hỗ trợ ba chế độ - so một bản, so một nhóm bản, hoặc so tất cả các bản với bản gốc v0. Dùng skill này khi user nói "verify Fabric Model Analyzer output", "so sánh report", "so sánh semantic model", "kiểm tra report sau khi tối ưu model", "compare report versions", "verify model output", "chạy verification cho version mới", "kiểm chứng bản tối ưu", hoặc khi có version semantic model mới cần đối chiếu với bản gốc.
---

# Kiểm chứng report Fabric giữa các bản semantic model

Mỗi lần ra một bản semantic model tối ưu mới, phải chứng minh report **chạy giống hệt nhau**
so với bản gốc. Skill này đóng gói toàn bộ quy trình đó thành một lệnh.

Khó không nằm ở chỗ chụp ảnh — nằm ở chỗ **phân biệt khác biệt thật với lỗi chụp**.
Lần chạy thủ công đầu tiên gặp **21 lỗi**; tất cả đã được cài sẵn chốt chặn trong script.
Chi tiết từng lỗi: [`reference/pitfalls.md`](reference/pitfalls.md).

---

## 1. Khi nào dùng skill này

Kích hoạt khi người dùng muốn kiểm chứng report sau khi tối ưu semantic model — ví dụ:

- "verify Fabric Model Analyzer output cho v4"
- "so sánh report bản mới với bản gốc"
- "kiểm tra xem tối ưu model có làm sai report không"
- "chạy verification cho v2 và v3"
- "có version mới, chạy kiểm chứng đi"

**Không dùng** cho: so sánh dữ liệu bằng DAX/SQL, kiểm hiệu năng model, hay so sánh
định nghĩa model. Skill này chỉ so **những gì hiển thị trên report**.

---

## 2. Đầu vào bắt buộc

| Đầu vào | Là gì | Lấy ở đâu |
|---|---|---|
| **Chrome đã đăng nhập Fabric** | Trình duyệt mở sẵn kèm cổng gỡ lỗi | Xem lệnh mở ở [`README.md`](README.md) |
| **`inventory.json`** | Danh sách version, workspace, report id, page id | Mẫu: `config/inventory.example.json` |
| **`filters.json`** | Slicer và giá trị dùng cho 2 lượt filter của từng page | Sinh từ `--discover`, xem bước 2 |
| **Capacity đang bật** | Fabric không mở được report khi capacity tắt | Người dùng tự bật |

`v0` là **bản gốc** và luôn được đưa vào mọi phép so, kể cả khi không liệt kê.

**Việc phải để người dùng tự làm:** bật/tắt capacity, đăng nhập Fabric.

**Refresh semantic model** thì skill làm được qua Power BI REST API (`--refresh api`),
hoặc người dùng tự bấm tay (`--refresh manual`). Chế độ `api` cần trường `dataset`
(GUID của semantic model) trong `inventory.json` và một access token Power BI.

**Tự kiểm tra mốc refresh trước mỗi lần chụp.** Với `--refresh no` (mặc định), script
tự gọi Power BI REST API xem lần refresh **thành công** gần nhất của mỗi bản là ngày
nào, rồi so ngày đó giữa các bản. Lệch ngày thì **dừng lại** và in ra hai lựa chọn
(refresh lại, hoặc chấp nhận lệch mốc bằng `--skip-refresh-check`) thay vì âm thầm so
những bản đang ở mốc dữ liệu khác nhau — kết quả kiểu đó không kết luận được gì.
Không lấy được token/không có trường `dataset` thì bỏ qua bước này và ghi rõ lý do,
không suy đoán.

---

## 3. Hỏi gì trước khi chạy

Chỉ hỏi **đúng hai câu** này, không hỏi gì thêm:

**Câu 1 — So bản nào?**

| Lựa chọn | Nghĩa là |
|---|---|
| Một bản cụ thể | `--versions v4` |
| Một nhóm bản | `--versions v1,v3` |
| Tất cả các bản | `--versions all` |

**Câu 2 — Có cần refresh semantic model trước không?**

| Lựa chọn | Nghĩa là |
|---|---|
| Không cần | `--refresh no` — dùng khi vừa refresh xong, hoặc chắc chắn các bản đang ở cùng một mốc dữ liệu |
| Có, tôi tự refresh tay | `--refresh manual` — script in ra danh sách bản cần refresh rồi dừng; refresh xong thì chạy lại |
| Có, refresh bằng API | `--refresh api` — script tự gọi Power BI REST API và chờ chạy xong mới chụp |

Nếu chọn "Không cần" mà script tự phát hiện các bản đang **lệch mốc refresh**, nó sẽ
dừng lại và hỏi lại — xem "Tự kiểm tra mốc refresh" ở mục 2. Đó không phải một câu hỏi
riêng cần hỏi trước, chỉ là script tự phát hiện và báo khi thực sự lệch.

**Không hỏi về khoảng ngày.** Cửa sổ ngày là chuyện của dữ liệu, không phải của người
chạy — nếu các bản cùng mốc refresh thì không cần ép, còn nếu lệch mốc thì phải refresh
chứ ép ngày chỉ che bớt triệu chứng. Tham số `--date-from` / `--date-to` vẫn còn để dùng
khi có lý do riêng, nhưng đừng đem ra hỏi.

---

## 4. Ba chế độ so sánh

```bash
python scripts/run.py --versions v1          # một bản       v0 ↔ v1
python scripts/run.py --versions v1,v3       # một nhóm bản  v0 ↔ v1, v0 ↔ v3
python scripts/run.py --versions all         # tất cả        v0 ↔ mọi bản trong inventory
```

Thêm `--work <thư mục>` nếu chạy ngoài thư mục hiện tại.
Chạy `python scripts/run.py --help` để xem hết tham số.

**Mỗi lần chạy đầy đủ ghi ra một thư mục kết quả riêng, có timestamp, chỉ ở local.**
`--work` chỉ còn chứa cấu hình dùng chung (`inventory.json`, `filters.json`) — không
đổi giữa các lần chạy. Kết quả thật (ảnh chụp, `diff_results.json`, báo cáo HTML...)
nằm ở `<work>/runs/<YYYYMMDD-HHMMSS>/`, một thư mục mới mỗi lần, **không bao giờ đè**
lên kết quả lần trước. `<work>/runs/` nằm trong `verify/`, đã gitignore toàn bộ.

```bash
python scripts/run.py --versions v1                  # tu tao runs/20260924-143000/
python scripts/run.py --versions v1 --run baseline   # dat ten thay vi timestamp
```

`--pick` / `--confirm` / `--report-only` **làm tiếp** trên một lần chạy đã có (không
tạo thư mục mới) — mặc định lấy lần chạy **mới nhất** dưới `runs/`, hoặc chỉ đích danh
bằng `--run <tên>` nếu cần làm tiếp một lần chạy cũ hơn.

---

## 5. Các bước kiểm chứng

### Bước 1 — Chuẩn bị `inventory.json`

Copy `config/inventory.example.json` vào thư mục làm việc, đổi tên thành `inventory.json`,
điền GUID thật. GUID lấy từ URL Fabric:

```
https://app.fabric.microsoft.com/groups/<ws>/reports/<report-id>/<page-id>
```

### Bước 2 — Dò slicer rồi phân công filter

```bash
python scripts/run.py --discover
```

Sinh `slicers.json` liệt kê mọi slicer thật của từng page kèm các giá trị chọn được.
Từ đó viết `filters.json` theo bốn quy tắc:

1. Mỗi page dùng **hai slicer khác nhau** cho hai lượt — không phải cùng slicer đổi giá trị.
2. Slicer **khác nhau giữa các page** để có độ phủ.
3. Cùng một page thì **mọi version dùng y hệt** slicer và giá trị. Khác đi là so sánh vô nghĩa.
4. Nếu có ép ngày, giá trị filter phải **nằm trong** khoảng ngày đó.

Page chỉ có một slicer dùng được thì ghi `note`, nội dung sẽ hiện trong báo cáo.

### Bước 3 — Chạy

```bash
python scripts/run.py --versions all
```

Script tự kiểm trước mọi điều kiện (Chrome, thư viện, file cấu hình) và báo hết một thể
nếu thiếu. Sau đó chạy tuần tự: chụp → đối chiếu bố cục → phân loại → dựng HTML → tự kiểm.

Mỗi version một lane song song trong cùng browser. **Không tăng lên 10 lane** — đã thử, không chạy được.

> Trong lúc chạy, **đừng đưa chuột vào cửa sổ Chrome**. Con trỏ lạc vào visual sẽ làm hiện
> thanh công cụ và hỏng ảnh.

**Zoom bị ép về 100% cho mọi version — đây là mặc định, không phải tuỳ chọn.**

Fabric **tự tính** mức "Fit to page" từ kích thước khung, nên hai bản copy của cùng một report ra
hai mức khác nhau. Lệch 1% làm **mọi phần tử** đổi kích thước và sinh ra hàng chục nghìn pixel
khác trên hàng trăm vùng nhỏ, trong khi **từng con số trên trang y hệt nhau**. Đo được trên một
lần chạy v0-vs-v1: **15 ô bị chấm "khác" mà không có gì khác thật.**

Đừng cho rằng mức zoom cố định theo version: lần chạy sau nó **đảo chiều** (v0 113% / v1 114%
thay vì 114% / 113%), và số ô lệch từ 15 xuống 5. Nó dao động theo từng lần chạy.

100% là con số tuyệt đối, không phụ thuộc khung nhìn, nên mọi version chắc chắn bằng nhau.
Kết quả thật ghi vào `rec.zoomSet`, và `check_layout.py` **đối chiếu zoom giữa các version** —
bước này trước đây hoàn toàn không có, và đó chính là lý do 15 ô artifact đi qua được mọi cổng
kiểm rồi vào tới báo cáo.

Cần refresh trước thì thêm `--refresh api` (script tự gọi API và chờ xong) hoặc
`--refresh manual` (dừng lại để người dùng tự bấm):

```bash
python scripts/run.py --versions all --refresh api
```

**Theo dõi khi chạy nền, báo lại mỗi 15 phút bằng Monitor (không phải ScheduleWakeup).**
`--versions all` có thể chạy hàng chục phút (nhiều report/page × nhiều bản). Chạy `run.py`
bằng Bash nền (`run_in_background`) rồi đặt **một Monitor** làm vòng lặp báo cáo — Monitor
tự đẩy mỗi dòng stdout thành một thông báo, không cần tự hỏi lại/tự sleep chờ:

Tính trước **tổng số ảnh kỳ vọng** (từ `inventory.json`, để biết đang ở đâu chứ không chỉ
biết "còn sống"): `số page × 3 trạng thái × số bản đang so (kể cả v0)`.

```bash
# Monitor command — moi 900s in 1 dong, thoat khi tien trinh ket thuc
RUN_DIR=/duong/dan/toi/verify/runs/<timestamp>
LOG=/duong/dan/toi/verify/<ten-log>.log
PID=<pid cua tien trinh python run.py, lay tu $! luc khoi dong>
TOTAL_EXPECTED=<so page x 3 trang thai x so ban>
last=$(date +%s)
while ps -p "$PID" > /dev/null 2>&1; do
    sleep 900
    now=$(date +%s)
    n=$(find "$RUN_DIR/shots" -type f -newermt "@$last" 2>/dev/null | wc -l)
    tong=$(find "$RUN_DIR/shots" -type f -name "*.png" 2>/dev/null | wc -l)
    echo "$(date '+%H:%M') dang chay | tong anh: $tong/$TOTAL_EXPECTED | anh moi trong 15' qua: $n | PID $PID con song"
    last=$now
done
tong=$(find "$RUN_DIR/shots" -type f -name "*.png" 2>/dev/null | wc -l)
echo "$(date '+%H:%M') tien trinh $PID da ket thuc | tong anh: $tong/$TOTAL_EXPECTED"
tail -n 60 "$LOG"
```

`timeout_ms` của Monitor tối đa 1800000 (30 phút) — nếu lần chạy dài hơn thế, Monitor tự
báo hết hạn một lần, đặt lại (re-arm) bằng đúng lệnh trên là theo dõi tiếp được ngay,
không mất tiến độ đã đếm.

Ba lỗi đã gặp thật, tránh lặp lại:
- **Đừng dò tiến trình bằng grep dòng lệnh** (`ps aux | grep run.py`) — trên
  Windows/Git-Bash, `ps aux` không hiện đủ tham số dòng lệnh nên luôn báo "không thấy"
  dù script vẫn chạy. Dò bằng **PID cụ thể** (`ps -p "$PID"`), lấy PID của **tiến trình
  python thật** (không phải PID của shell/nohup bọc ngoài — hai cái khác nhau, kiểm bằng
  `ps -ef | grep run.py` một lần lúc mới khởi động để lấy đúng PID con).
- **`ps -ef`/`ps aux` của Git-Bash có thể KHÔNG liệt kê được tiến trình node.exe con** dù
  nó chạy thật — node được python `subprocess.run()` khởi động qua CreateProcess của
  Windows, nằm ngoài cây tiến trình msys mà `ps` của Git-Bash quét. Đã gặp thật: ảnh mới
  chững lại 7 phút, `ps -ef | grep node` không ra dòng nào → tưởng lầm là treo — nhưng
  `tasklist //FI "IMAGENAME eq node.exe"` và PowerShell `Get-CimInstance Win32_Process`
  vẫn thấy đúng tiến trình `driver.js`/`capture.js` đang chạy. Khi nghi ngờ treo, xác nhận
  lại bằng `tasklist`/PowerShell trước khi kết luận, đừng chỉ tin `ps` của Git-Bash.
- **Đừng đếm tổng số file trong `shots/` để đo tiến độ** — nếu chạy lại đúng report/page
  đã chụp trước đó, tên file trùng nên bị **ghi đè**, tổng số file đứng yên dù script
  đang chụp thật. Đếm file có **mtime trong N phút gần nhất** (`-newermt`), không đếm tổng.

### Bước 4 — Xử lý ô chưa sạch

Nếu kết luận là `CHUA KET LUAN DUOC`, chụp lại đúng những ô đó thay vì chạy lại cả bộ:

```bash
python scripts/run.py --pick "v3|R1|P2,v1|R4|P3"
```

Log được gộp ngược vào log chính, những ô khác giữ nguyên.

### Bước 5 — Tự soi trước khi báo cáo

**Bắt buộc, không bỏ qua.** Mở từng ảnh còn báo khác trong `shots/annot/` ra nhìn tận mắt.
Máy chỉ nói *có khác*, không nói *khác cái gì*. Đã có trường hợp một ô bị chấm là
"khác model" trong khi thật ra chỉ là filter không áp được lên một bản.

**Có ô nào báo `VALUE` hoặc `UI` thì KHÔNG được dừng ở một phép kiểm gián tiếp (DOM-dump,
so màu, so text qua script) — luôn nghi ngờ và tự soi ảnh chụp thật trước, rồi mới thao
tác tay trên trình duyệt thật để kết luận.** Cả ảnh chụp tự động lẫn DOM-state-check đều
có thể SAI mà không tự biết mình sai — đã gặp cả hai kiểu: log ghi "đã áp filter thành
công" trong khi ảnh cho thấy filter chưa hề đổi; và một script DOM-check so 23 control
báo "0 khác biệt tuyệt đối" trong khi ảnh chụp cho thấy 3 control khác nhau rõ ràng bằng
mắt (script chỉ đơn giản không hề kiểm tra đúng 3 control đó — xem
`reference/pitfalls.md` mục 17). **Ảnh chụp là bằng chứng gốc; DOM-state chỉ là một cách
diễn giải có thể sai và bỏ sót.** Quy trình bắt buộc cho mỗi ô còn khác:

1. **Mở ảnh chụp thật trước tiên** (`shots/annot/.../full__<report>__<page>__<version>__
   {v0,vX}.png` qua tool đọc ảnh trực tiếp), nhìn kỹ toàn bộ trang bằng mắt — không chỉ
   vùng đã khoanh đỏ sẵn, vì thuật toán khoanh vùng có thể không biết một control nào đó
   tồn tại để mà khoanh. Ghi lại mọi khác biệt nhìn thấy được, dù nhỏ.
2. Tự nối vào đúng phiên Chrome đang mở (qua CDP, `connectOverCDP('http://127.0.0.1:9222')`
   — không mở Chrome/profile khác), mở đúng URL report/page của **cả hai bản** (v0 và bản
   đang so), mỗi bản một tab.
3. Tự bấm "Reset to default", tự áp lại đúng slicer/filter/nút bấm mà `filters.json` khai
   báo cho ô đó — **so sánh bằng mắt mọi control nhìn thấy được trên trang** (không chỉ
   2 slicer chính, không chỉ tin một phép DOM-dump tự động), không chỉ tin `ok: true`
   trong log.
4. Nếu phát hiện một control khác mặc định giữa hai bản mà `filters.json` chưa khai báo
   (đã gặp: nút bookmark, slicer phụ, danh sách chọn nhiều số liệu, nút khoảng ngày nhanh,
   dropdown filter, nút chọn nhóm trong panel `列選択区分`/`行選択区分`) — thử bấm cho
   khớp bằng Playwright `.locator(...).click()` thật (KHÔNG dùng `element.click()` qua
   `page.evaluate()` — click kiểu này có thể báo "thành công" mà không hề tác động UI thật
   của Power BI/React, xem mục 17). Bấm được và số liệu khớp thì thêm vào `filters.json`
   (`bookmarks`/`pin`) và chụp lại. Bấm mãi không thấy nút dù chắc chắn nó có tồn tại
   (đã gặp — xem `reference/pitfalls.md` mục 15) thì dừng, không đoán mò tiếp, ghi rõ
   đây là hạn chế công cụ.
5. Chỉ sau khi tự tay xác nhận (khớp thật hoặc xác nhận hạn chế công cụ) mới được viết
   kết luận cho ô đó trong báo cáo — không suy diễn từ số pixel/kind/DOM-check một mình.

### Bước 6 — Lượt đối chứng độc lập

Khi có bất kỳ khác biệt nào, chạy thêm một lượt chụp độc lập:

```bash
python scripts/run.py --confirm
```

Chụp vào `shots2/` nên không phá bằng chứng lượt đầu, rồi so hai chiều:
khác biệt có lặp lại không, và ô từng báo giống có lộ khác biệt mới không.

> **Chỉ khác biệt lặp ở cả hai lượt mới được tính là thật.**

---

## 6. Tiêu chí đạt / không đạt

`run.py` in kết luận và trả về mã thoát:

| Mã | Kết luận | Điều kiện | Phải làm gì |
|---|---|---|---|
| **0** | `DAT` | 0 ô khác về số liệu, và mọi chỉ số nhiễu bằng 0 | Report chạy giống nhau. Nộp báo cáo. |
| **1** | `KHONG DAT` | ≥ 1 ô khác về số liệu | Đây là kết luận CƠ HỌC của script, chưa phải kết luận cuối. Chạy `--confirm`, rồi với **mỗi ô còn khác (VALUE hoặc UI)**, tự tay thao tác lại trên trình duyệt thật để verify (bắt buộc — xem Bước 5) trước khi viết kết luận thật cho người đọc. Có thể kết quả cuối là "không phải regression, do hạn chế công cụ" — nhưng phải chứng minh bằng thao tác tay, không suy diễn. |
| **2** | `CHUA KET LUAN DUOC` | Còn ô thiếu ảnh / chụp lỗi / filter không ăn / ảnh không ổn định / chưa phân loại được | Dữ liệu chưa đủ tin cậy. Chụp lại bằng `--pick` rồi chạy lại. **Không được kết luận khi còn ở trạng thái này.** |
| **3** | Lỗi | Thiếu cấu hình, không nối được Chrome, thiếu thư viện | Đọc thông báo, script chỉ rõ thiếu gì. |

**Khác biệt được chia hai loại:**

- **khác về số liệu** — chữ trên canvas khác nhau. Đây là thứ quyết định đạt / không đạt.
- **khác giao diện** — chữ giống hệt từng ký tự mà pixel vẫn khác.
  Chỉ ghi nhận khi **mắt thường nhìn thấy được**. Lệch dưới ngưỡng nhìn thấy được **tính là giống**.

**Nguyên tắc phân loại:** chữ trước, pixel sau. Chữ khác nhau ⇒ **luôn** là khác về số liệu,
bất kể lệch bao nhiêu pixel. Đã từng để ngưỡng pixel quyết định trước và giấu mất 8 ô
thiếu số liệu thật.

---

## 7. Sản phẩm giao

Một file HTML duy nhất, ảnh nhúng base64, cấu trúc bám theo bản mẫu đã được duyệt ở Task 6409:

| Mục | Nội dung |
|---|---|
| Phát hiện chính | Chỉ hiện khi có khác biệt: page nào, bản nào lệch, khác chỗ nào, kết quả đối chứng |
| 0 | Nguồn và cách chụp |
| 1 | Tên đầy đủ mọi report và **report đó có tồn tại ở version đó không** |
| 2 | Filter đã dùng: slicer 1 / giá trị 1 / slicer 2 / giá trị 2 |
| 3 | Bảng kết quả — chỉ **Giống / Khác**, không có phần trăm |
| 4 | Ảnh chụp, gập hai tầng (report → page), mặc định đóng |
| 5 | Chất lượng lần chụp |
| 5b | Nhật ký truy nguyên từng khác biệt |
| 6 | Kết luận |

Ảnh chỉ kèm cho **ô khác nhau**; ô giống thì không kèm ảnh. Vùng khác biệt được khoanh đỏ
trên **cả ảnh bản gốc lẫn ảnh bản đem so**, kèm một cặp ảnh phóng to vào đúng vùng đó.

### Khuôn HTML cố định

Phần `<head>`, CSS và thẻ mở `<body>` nằm ở **`templates/report_shell.html`** — trích
nguyên văn từ bản mẫu đã duyệt ở Task 6409, nên mọi lần chạy đều cho ra **đúng một khuôn**.

Khuôn để ở file riêng chứ không nhúng trong Python, để sửa giao diện thì sửa file đó
chứ không phải sửa mã. Thứ tự tìm khuôn: biến `FRC_TEMPLATE` → `templates/report_shell.html`
cạnh script → cùng thư mục script → thư mục làm việc. Không tìm thấy thì dừng và báo rõ
đã tìm ở đâu, chứ không âm thầm dựng ra một khuôn khác.

Đã kiểm: khuôn sinh ra **trùng từng byte** với bản mẫu.

---

## 8. Khi gặp trục trặc

| Triệu chứng | Nguyên nhân thường gặp |
|---|---|
| `Khong ket noi duoc Chrome qua CDP` | Chrome chưa mở kèm `--remote-debugging-port=9222` |
| `Phien Fabric chua dang nhap` | Đăng nhập trong chính cửa sổ Chrome đang mở, rồi chạy lại |
| `KHONG_TIM_THAY_PLAYWRIGHT` | `npm i -g playwright`, hoặc đặt biến `FRC_PLAYWRIGHT` |
| Nhiều ô `filter khong an` | Slicer không mở được trên page đó — đổi sang slicer khác trong `filters.json` |
| Nhiều ô `anh khong on dinh` | Report vẽ chậm; chụp lại bằng `--pick` |
| Ảnh trong báo cáo nhỏ và mờ | Page vẽ trong một góc của khung lớn — script tự cắt nền, nếu vẫn mờ xem `reference/pitfalls.md` |
| Toàn bộ ảnh lệch nhau | Cửa sổ Chrome bị đổi kích thước giữa chừng. Đừng chạm vào cửa sổ khi đang chạy |
| `MOC REFRESH CHUA KHOP GIUA CAC BAN` | Các bản refresh ở ngày khác nhau — refresh lại cho khớp (`--refresh api`/`manual`) hoặc chấp nhận lệch bằng `--skip-refresh-check` |

Trục trặc lạ hơn: tra [`reference/pitfalls.md`](reference/pitfalls.md) — 21 lỗi đã gặp kèm cách chặn.

---

## 9. Những câu không được viết nếu chưa kiểm

Một lời giải thích nghe hợp lý mà không đo được thì phải ghi **"chưa xác định"**,
không được ghi thành kết luận. Đã có hai lần viết kết luận sai và phải gỡ khỏi báo cáo.

Bằng chứng đo **trước** một lần refresh thì **hết hiệu lực sau** lần refresh đó.

Khi không kiểm được (capacity tắt, mất kết nối), ghi rõ là **để ngỏ** kèm việc cụ thể
cần làm để kết luận.
