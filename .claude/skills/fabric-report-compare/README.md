# fabric-report-compare — cài đặt và sử dụng

Kiểm chứng report Power BI / Fabric chạy giống hệt nhau trước và sau khi tối ưu semantic model.
Đọc file này một lần trước khi chạy lần đầu; những lần sau chỉ cần mục [Chạy](#chạy).

---

## Cài đặt

### 1. Skill

Skill nằm ở `.claude/skills/fabric-report-compare/` trong repo. Đã có sẵn, không cần cài gì thêm.
Claude Code tự nạp khi bạn nói câu liên quan (ví dụ *"so sánh report bản v4 với bản gốc"*).

Muốn dùng ở repo khác thì copy cả thư mục sang `.claude/skills/` của repo đó.

### 2. Phần mềm cần có

| Thứ | Kiểm bằng | Nếu thiếu |
|---|---|---|
| Node.js | `node -v` | Cài từ nodejs.org |
| Playwright | `node -e "require('playwright')"` | `npm i -g playwright` |
| Python 3.9+ | `python -V` | Cài từ python.org |
| numpy, scipy, pillow | `python -c "import numpy,scipy,PIL"` | `pip install numpy scipy pillow` |

Playwright cài ở chỗ khác thì trỏ đường dẫn bằng biến môi trường:

```bash
set FRC_PLAYWRIGHT=C:\duong\dan\toi\node_modules\playwright
```

`run.py` tự kiểm hết những thứ trên trước khi chạy và báo một thể nếu thiếu.

### 3. Chrome đã đăng nhập Fabric

Skill **không bao giờ tự đăng nhập**. Nó gắn vào một cửa sổ Chrome bạn đã đăng nhập sẵn.

Đóng hết Chrome đang mở, rồi mở lại bằng lệnh này:

**PowerShell** — phải có dấu `&` ở đầu, thiếu là PowerShell báo
`Unexpected token 'remote-debugging-port=9222'`:

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\fabric-profile"
```

**Command Prompt (cmd.exe)** — không dùng `&`:

```bat
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\fabric-profile"
```

Trong cửa sổ vừa mở, vào https://app.fabric.microsoft.com và đăng nhập.
Profile được nhớ nên các lần sau chỉ cần mở lại đúng lệnh trên.

> Cửa sổ này phải để yên trong lúc chạy. Đừng đổi kích thước, đừng đưa chuột vào —
> con trỏ lạc vào visual sẽ làm hiện thanh công cụ và hỏng ảnh.

**Bắt buộc set `FRC_PROBE_WORKSPACE` mỗi terminal session mới**, TRƯỚC khi chạy `run.py`
(biến môi trường không tự nhớ giữa các session/terminal khác nhau, kể cả khi Chrome vẫn
đăng nhập từ trước):

```powershell
$env:FRC_PROBE_WORKSPACE = "<id một workspace CỦA PROJECT NÀY, bất kỳ, ví dụ dynam-baseline-test>"
```

```bash
export FRC_PROBE_WORKSPACE=<id một workspace CỦA PROJECT NÀY>
```

Script tự kiểm tra đăng nhập bằng cách mở workspace này; không set (hoặc set sai project)
→ 404 → báo nhầm `NOT_SIGNED_IN` dù Chrome đã đăng nhập thật (đã gặp nhiều lần, xem
`reference/pitfalls.md`).

### 4. Bật capacity

Fabric không mở được report khi capacity tắt. Việc này người dùng tự làm.

---

## Chuẩn bị lần đầu cho một bộ report

Làm một lần, những lần sau chỉ chỉnh khi có version mới.

### `inventory.json`

```bash
mkdir verify && cd verify
copy ..\.claude\skills\fabric-report-compare\config\inventory.example.json inventory.json
```

Điền GUID thật, lấy từ URL khi mở report trên Fabric:

```
https://app.fabric.microsoft.com/groups/<ws>/reports/<report-id>/<page-id>
                                         ▲              ▲            ▲
                                         ws             ids          pid
```

`v0` bắt buộc là bản gốc. Các bản tối ưu đặt tên tuỳ ý (`v1`, `v2`, `v35`…).

**Có version mới thì chỉ cần thêm một mục vào `versions` và thêm một khoá vào `ids` của
từng report.** Không phải sửa gì khác.

### `filters.json`

```bash
python ..\.claude\skills\fabric-report-compare\scripts\run.py --discover
```

Sinh `slicers.json` liệt kê mọi slicer thật của từng page kèm các giá trị chọn được.
Dựa vào đó viết `filters.json` (mẫu ở `config/filters.example.json`), theo bốn quy tắc:

1. Mỗi page dùng **hai slicer khác nhau** cho hai lượt.
2. Slicer **khác nhau giữa các page** để có độ phủ.
3. Cùng một page thì **mọi version dùng y hệt** slicer và giá trị.
4. Có ép ngày thì giá trị filter phải **nằm trong** khoảng ngày đó.

---

## Chạy

```bash
cd verify

# So một bản với bản gốc
python ..\.claude\skills\fabric-report-compare\scripts\run.py --versions v4

# So một nhóm bản
python ..\.claude\skills\fabric-report-compare\scripts\run.py --versions v1,v3

# So tất cả các bản có trong inventory
python ..\.claude\skills\fabric-report-compare\scripts\run.py --versions all
```

Kết quả: `comparison_report.html` trong `verify/runs/<timestamp>/` — một thư mục mới mỗi
lần chạy đầy đủ, không đè lên lần trước (xem mục Cấu trúc thư mục bên dưới).

### Tham số hay dùng

| Tham số | Dùng khi |
|---|---|
| `--refresh api` | Tự gọi Power BI REST API refresh mọi bản, chờ xong mới chụp |
| `--refresh manual` | Dừng lại để tự bấm Refresh trên Fabric, rồi chạy lại |
| `--skip-refresh-check` | Bỏ qua bước tự kiểm mốc refresh (mặc định script tự kiểm và dừng nếu lệch ngày) |
| `--date-from "8/21/2026" --date-to "9/3/2026"` | Ép mọi bản về cùng một khoảng ngày |
| `--reports R1,R3` | Chỉ chạy vài report |
| `--pick "v3\|R1\|P2"` | Chụp lại đúng vài ô hỏng, không chạy lại cả bộ |
| `--confirm` | Lượt đối chứng độc lập, chụp vào `shots2/` của lần chạy đang làm tiếp |
| `--report-only` | Dựng lại HTML từ ảnh đã có, không chụp lại |
| `--work <thư mục>` | Thư mục chứa `inventory.json`/`filters.json` dùng chung, mặc định thư mục hiện tại |
| `--run <tên>` | Chỉ đích danh thư mục kết quả dưới `runs/` — mặc định tự đặt tên theo timestamp (lần chạy mới) hoặc lấy lần mới nhất (`--pick`/`--confirm`/`--report-only`) |

### Đọc kết quả

| In ra | Mã thoát | Nghĩa là |
|---|---|---|
| `[DAT]` | 0 | Report chạy giống nhau. Nộp báo cáo. |
| `[KHONG DAT]` | 1 | Có ô khác về số liệu. Chạy `--confirm`, tự soi ảnh, tìm nguyên nhân gốc. |
| `[CHUA KET LUAN DUOC]` | 2 | Còn ô chưa sạch. Chụp lại bằng `--pick`. **Chưa được kết luận.** |
| `[DUNG]` | 3 | Thiếu cấu hình hoặc phần mềm. Thông báo chỉ rõ thiếu gì. |

---

## Đầu ra

### `comparison_report.html`

Một file HTML duy nhất, mở bằng trình duyệt, không cần mạng — mọi ảnh nhúng base64 sẵn.

| Mục | Nội dung |
|---|---|
| Phát hiện chính | Chỉ hiện khi có khác biệt: page nào, bản nào lệch, lệch ở trạng thái nào, khác chỗ nào cụ thể, kết quả lượt đối chứng |
| 0 | Nguồn và cách chụp — workspace, thời điểm, kích thước cửa sổ |
| 1 | Tên đầy đủ mọi report, và report đó **có tồn tại ở version đó không** |
| 2 | Filter đã dùng: slicer 1 / giá trị 1 / slicer 2 / giá trị 2 cho từng page |
| 3 | Bảng kết quả — chỉ **Giống / Khác**, không có phần trăm |
| 4 | Ảnh chụp, gập hai tầng (report → page), mặc định đóng |
| 5 | Chất lượng lần chụp — ô lỗi, filter không ăn, ảnh không ổn định, lệch zoom |
| 5b | Nhật ký truy nguyên: mỗi lần máy báo "khác" thì nguyên nhân thật là gì |
| 6 | Kết luận |

Ảnh **chỉ kèm cho ô khác nhau**; ô giống thì không kèm ảnh. Vùng khác biệt được khoanh đỏ
trên **cả ảnh bản gốc lẫn ảnh bản đem so**, kèm một cặp ảnh phóng to vào đúng vùng đó.

Dung lượng tham khảo: 240 ảnh với 13 ô khác cho ra file khoảng **17 MB**.
Ảnh lưu JPEG chất lượng cao — PNG nét hơn không đáng kể mà nặng gấp đôi.

Giao diện báo cáo (head, CSS) lấy từ **`templates/report_shell.html`**, trích nguyên văn
từ bản mẫu đã duyệt nên mọi lần chạy đều ra đúng một khuôn. Muốn đổi giao diện thì sửa
file đó, không phải sửa Python.

### File trung gian (để tra khi cần)

| File | Dùng để |
|---|---|
| `allstates_out.json` | Nhật ký chụp từng ô: reset, filter đã áp, mức zoom, ảnh có ổn định không |
| `diff_results.json` | Kết quả phân loại từng phép so, kèm mô tả khác biệt |
| `shots/text/*.txt` | Toàn bộ chữ trên canvas mỗi ảnh — căn cứ phân loại khác số liệu |
| `shots/annot/` | Ảnh đã khoanh đỏ, dùng khi cần tự soi tận mắt |
| `slicers.json` | Slicer thật của từng page, sinh bởi `--discover` |

---

## Quy trình đầy đủ cho một version mới

```bash
# 1. Thêm version vào inventory.json (một mục trong versions + một khoá trong ids mỗi report)

# 2. Chạy. Nếu các bản chưa cùng mốc dữ liệu thì thêm --refresh api
python ...\run.py --versions v4 --refresh api

# 3. Còn ô chưa sạch thì chụp lại đúng ô đó
python ...\run.py --pick "v4|R1|P2"

# 4. Mở từng ảnh trong shots/annot/ còn báo khác ra NHÌN TẬN MẮT
#    Máy chỉ nói CÓ khác, không nói khác CÁI GÌ.

# 5. Có khác biệt thì chạy lượt đối chứng
python ...\run.py --confirm
#    Chỉ khác biệt lặp ở CẢ HAI lượt mới tính là thật.

# 6. Nộp comparison_report.html
```

Thời gian tham khảo: 5 report × 16 page × 3 trạng thái × 5 version = 240 ảnh,
mất khoảng **30 phút** chụp và **3 phút** phân loại.

---

## Cấu trúc thư mục

```
fabric-report-compare/
  SKILL.md                       sổ tay vận hành — trigger, đầu vào, các bước, tiêu chí đạt
  README.md                      file này
  reference/pitfalls.md          21 lỗi đã gặp kèm cách chặn
  templates/
    report_shell.html          khuôn HTML cố định: head + CSS + mở body
  config/
    inventory.example.json       mẫu khai báo version / report / page
    filters.example.json         mẫu phân công slicer
  scripts/
    run.py                       ĐIỂM VÀO DUY NHẤT — chạy file này
    refresh.py                   refresh semantic model qua Power BI REST API
    driver.js                    gắn vào Chrome qua CDP
    capture.js                   chụp 3 trạng thái mỗi page
    discover.js                  dò slicer thật
    check_layout.py              đối chiếu bố cục và phạm vi ngày
    diff.py                      phân loại khác biệt, khoanh đỏ
    build_report.py              dựng HTML
    quality_check.py             tự kiểm 6 tín hiệu chất lượng
    confirm_pass2.py             đối chiếu hai lượt chụp
```

Thư mục làm việc sau khi chạy — cấu hình dùng chung ở `verify/`, kết quả từng lần chạy
tách riêng dưới `runs/<timestamp>/` (không bao giờ đè lên lần trước, chỉ ở local):

```
verify/
  inventory.json  filters.json  slicers.json     cau hinh dung chung, khong doi giua cac lan chay
  runs/
    20260924-090000/                              lan chay day du dau tien
      run_config.json  allstates_out.json  diff_results.json  comparison_report.html
      shots/          load/ filter1/ filter2/ text/ annot/
      shots2/         anh luot doi chung (--confirm)
    20260924-143000/                              lan chay day du sau, KHONG de len lan tren
      ...
```

---

## Khắc phục sự cố

| Triệu chứng | Xử lý |
|---|---|
| `Khong ket noi duoc Chrome qua CDP` | Chrome chưa mở kèm `--remote-debugging-port=9222` |
| `Phien Fabric chua dang nhap` | Đăng nhập trong chính cửa sổ Chrome đang mở |
| `KHONG_TIM_THAY_PLAYWRIGHT` | `npm i -g playwright` hoặc đặt `FRC_PLAYWRIGHT` |
| `Thieu inventory.json` / `Thieu filters.json` | Xem mục Chuẩn bị lần đầu |
| Nhiều ô `filter khong an` | Slicer không mở được trên page đó — đổi slicer trong `filters.json` |
| Nhiều ô `anh khong on dinh` | Report vẽ chậm — chụp lại bằng `--pick` |
| Toàn bộ ảnh lệch nhau | Cửa sổ Chrome bị đổi kích thước giữa chừng |
| `MOC REFRESH CHUA KHOP GIUA CAC BAN` | Các bản refresh khác ngày — `--refresh api`/`manual` để refresh lại, hoặc `--skip-refresh-check` nếu chủ ý so bất chấp lệch mốc |

Trục trặc lạ hơn: tra `reference/pitfalls.md`.
