# Bay loi da gap khi so sanh report Fabric

Tai lieu tra cuu cua skill `fabric-report-compare`. **21 loi that** gap trong lan chay
dau tien (Task 6409), moi loi kem trieu chung, nguyen nhan va cach chan.
Phan lon da duoc cai san vao script — tai lieu nay de tra khi gap trieu chung la,
hoac khi can sua/mo rong script.

---

Mục tiêu: chứng minh report **chạy giống hệt nhau** trước và sau khi tối ưu semantic model.
Khó không nằm ở chỗ chụp ảnh — nằm ở chỗ **phân biệt khác biệt thật với lỗi chụp**.
Lần chạy thật đã gặp **21 lỗi**, trong đó lỗi nguy hiểm nhất là những lỗi khiến công cụ **báo "sạch" trong khi sản phẩm hỏng**.

---

## 0. Ba nguyên tắc bao trùm

1. **Chữ trước, pixel sau.** Chữ trên canvas là tín hiệu khách quan. Pixel thì bị nhiễu bởi zoom, dịch khung, khử răng cưa. Chữ khác nhau ⇒ **luôn** là khác về số liệu, bất kể lệch bao nhiêu pixel.
2. **Máy báo khác thì phải mở ảnh ra nhìn rồi mới kết luận.** Không suy nguyên nhân từ chỉ số (% pixel, số vùng lệch). Cắt vùng lệch, phóng to, dùng tool Read xem tận mắt.
3. **Không viết câu nào chưa kiểm được.** Một lời giải thích nghe hợp lý mà không đo được thì phải ghi "chưa xác định", không được ghi thành kết luận.

---

## 1. Kiến trúc đã chạy được

**Chrome mở sẵn, đã đăng nhập Fabric** — driver chỉ gắn vào qua CDP, **không bao giờ tự đăng nhập**:

```
chrome.exe --remote-debugging-port=9222 --user-data-dir=<profile-da-login>
```

```js
const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
```
Driver phải kiểm phiên đăng nhập trước, chưa đăng nhập thì thoát mã 4 và báo người dùng tự đăng nhập. Không bao giờ đóng browser.

**Một lần mở page → chụp cả 3 trạng thái.** Đây là điểm quyết định tốc độ:
240 ảnh mà chỉ cần **80 lần điều hướng** thay vì 240. Tốc độ đạt ~9 ảnh/phút.

```
mở page → reset về default → chụp "load"
        → reset → ép ngày → áp slicer 1 → chụp "filter1"
        → reset → ép ngày → áp slicer 2 → chụp "filter2"
        → đóng tab (Fabric giới hạn 20 item mở cùng lúc)
```

**5 lane song song — mỗi version một lane, trong CÙNG một browser đã login.**
Đã thử 10 lane: không chạy được. **Chốt 5.**

**Đóng tab sau mỗi report** qua `[data-testid="horizontal-navbar-item-<id>"]` → `[data-testid="tab-close"]`, nếu không Fabric chặn khi vượt 20 item.

---

## 2. Thứ tự thi hành

| Bước | Việc | Ghi chú |
|---|---|---|
| 1 | Dò slicer thật của từng page (`discover_slicers.js`) | Không tự bịa tên slicer |
| 2 | Phân công slicer vào `filters.json` | Xem mục 4 |
| 3 | Chụp 240 ảnh (`driver.js allstates.js`) | 5 lane |
| 4 | Đối chiếu bố cục + phạm vi ngày (`check_layout.py`) | Bắt canvas dịch |
| 5 | Phân loại khác biệt (`diff.py`) | Xem mục 5 |
| 6 | **Tự mở từng ảnh còn báo khác ra nhìn** | Bắt buộc |
| 7 | Chụp lại các ô hỏng (`make_fix.py` + driver) | Không chụp lại cả bộ |
| 8 | Lượt đối chứng độc lập vào thư mục khác | Xem mục 7 |
| 9 | Dựng HTML (`build_report.py`) | Xem mục 8 |
| 10 | **Mở HTML ra nhìn như người đọc** trước khi nói xong | Xem mục 9 |

---

## 3. Chốt chặn khi chụp — `assertClean`

Không bao giờ chụp khi còn một trong các thứ sau. Ném lỗi rồi thử lại, hết lượt thử mới báo hỏng.

```js
// Lop phu / hop thoai con treo tren trang
'.mat-mdc-dialog-surface, .cdk-overlay-backdrop, [role="dialog"], ' +
'[data-testid="dailog-ok-btn"], .slicer-dropdown-popup'
```

Kèm hai chốt nữa: **vị trí cuộn phải bằng 0** và **chữ ký bố cục không đổi**.

### Bảng lỗi chụp đã gặp

| # | Triệu chứng | Nguyên nhân | Cách chặn |
|---|---|---|---|
| 1 | Lệch 20,9% quanh header bảng | Thanh công cụ hover của visual hiện ra vì con trỏ nằm trên visual | `page.mouse.move(2, 2)` trước mỗi lần chụp |
| 2 | Lệch 22,1%, dropdown che nội dung | Dropdown slicer bỏ ngỏ, **Escape không đóng được** | `closePop()`: bấm lại chính combobox có `aria-expanded="true"` |
| 3 | Slicer vẫn hiện `All` ở một bản | Popup không mở, filter chưa áp — **lỗi chụp, không phải khác model** | Xác minh chữ hiển thị chứa đúng giá trị đã chọn, và không phải "Multiple selections" |
| 5 | Lệch ~0,1% gọn trong viền ô slicer | Viền focus của trình duyệt | Chèn CSS `*:focus,*:focus-visible,*:focus-within{outline:none!important;box-shadow:none!important}` + `blur()`. Chỉ `blur()` là **không đủ** vì Power BI vẽ lại |
| 6 | Lệch 17,6%, canvas đẩy ngang 185px | Canvas dịch sau thao tác filter, **`scrollLeft` vẫn bằng 0** nên chốt cũ không bắt được | Chuẩn hoá bằng `scrollIntoView` + so **chữ ký bố cục** (toạ độ mọi visual so với `.displayArea`) |
| 7 | Lệch 28,1%, mọi thứ to nhỏ khác nhau | Fabric **tự tính** mức "Fit to page" từ kích thước khung, nên hai bản copy của cùng một report ra hai mức khác nhau. Đo được: v0 114% / v1 113% và v0 128% / v1 127%; lần chạy sau thì **đảo chiều** (v0 113% / v1 114%) — tức **không cố định theo version**, đừng kết luận sớm như vậy. `norm_sig()` không cứu được vì nó chỉ trừ độ **dịch**, còn zoom là phép **tỉ lệ** nên `w/h` cũng đổi | **Ép zoom về 100% là mặc định khi chụp** (`setZoom100` trong `capture.js`) — 100% là số tuyệt đối, không phụ thuộc khung nhìn. Đo được 12/12 ô thành công. Kèm bước **đối chiếu zoom giữa các version** trong `check_layout.py` (trước đây hoàn toàn không có, nên 15 ô artifact đi qua hết mọi cổng kiểm) |
| 8 | 35 pixel xám góc trên trái | Vệt spinner đang mờ dần — ảnh chụp non | Chụp lặp tới khi **hai lần liên tiếp trùng khớp byte** |
| 12 | `DIRTY_OVERLAY: cdk-overlay-backdrop` | Menu Fabric để lại lớp phủ trong suốt, Escape không đóng | Bấm thẳng vào `.cdk-overlay-backdrop` |
| 13 | Hết giờ chụp sau 30 giây | Bản v3 vẽ chậm hơn hẳn | Nâng timeout lên **90 giây** và cho thử lại |
| 24 | `--pick` làm log chính từ 29 bản ghi còn 3 | `--pick` ghi thẳng vào `allstates_out.json`, sau đó `merge_log()` thoát ngay vì `fix_json == main_p`. Bước gộp mà tài liệu hứa **không bao giờ chạy được**. Ảnh vẫn còn trên đĩa nhưng `check_layout`/`quality_check`/`build_report` đều đọc log chính → mục 5 và số ô lệch bố cục biến mất, báo cáo từ 23 MB còn 6,7 MB. **Mất bằng chứng, không phải mất hiển thị** | `--pick` ghi ra `pick_out.json` rồi mới gộp. Ô có trong lượt pick mà log chính chưa từng có thì **thêm vào**, không bỏ im lặng. Cả hai đường thất bại đều in cảnh báo |

### Cửa sổ hiển thị phải khớp cửa sổ thật

Đây là lỗi làm hỏng cả một lượt chạy: script ép `setViewportSize({3200, 1800})` trong khi cửa sổ Chrome đang maximize trên màn 1536×960 → Fabric render lệch, ảnh chụp sai toàn bộ.

**Phải đo cửa sổ thật rồi mới đặt viewport**, và mỗi lane kiểm lại:

```js
const cdp = await page.context().newCDPSession(page);
await cdp.send('Emulation.clearDeviceMetricsOverride');
const { windowId } = await cdp.send('Browser.getWindowForTarget');
await cdp.send('Browser.setWindowBounds', { windowId, bounds: { windowState: 'maximized' } });
await page.waitForTimeout(1200);
const m = await page.evaluate(() => ({ iw: innerWidth, ih: innerHeight }));
// moi lane: setViewportSize(m) roi kiem lai, khong khop thi NEM LOI
```

---

## 4. Chọn slicer và áp filter

**Yêu cầu về slicer:**
- Mỗi page dùng **2 slicer khác nhau** cho 2 lượt (không phải cùng slicer đổi giá trị).
- Slicer **khác nhau giữa các page** để có độ phủ.
- Cùng một page thì **cả 5 version dùng y hệt** slicer và giá trị — nếu không thì so sánh vô nghĩa.
- Page chỉ có một slicer dùng được thì ghi rõ vào `note` và giải thích trong báo cáo.

**Tìm slicer bằng `aria-label`, tuyệt đối không dùng toạ độ.**
Lỗi #4: toạ độ lấy ở viewport 3200px, sang màn 1920px thì nằm ngoài màn hình → filter không áp được cho bất kỳ bản nào.

| # | Bẫy | Cách tránh |
|---|---|---|
| 19 | Cùng một slicer chạy tốt ở page này nhưng **không mở được popup** ở page khác | Thử trước; hỏng thì đổi sang slicer khác, đừng cố |
| 20 | **Chính việc ép ngày làm hỏng filter**: ép về 21/08–03/09 thì slicer `日` không còn giá trị `15` | Chọn giá trị filter **nằm trong** cửa sổ ngày đã ép |
| 3, 18 | Filter không áp mà vẫn chụp → bị chấm nhầm là "khác model" | Xác minh sau khi áp; ghi `apF1/apF2 = false` + lý do vào log |

**Xác minh sau khi áp filter** — đọc lại chữ hiển thị trên slicer, phải chứa đúng giá trị và không phải `Multiple selections`. Thử tối đa 5 lần.

---

## 5. Ép khoảng ngày

Power BI có hai chế độ: **`期間`** (tuyệt đối) và **`相対`** (tương đối). Muốn ép cứng thì phải chuyển sang `期間`.

```js
// PHAI bam bang chuot that cua Playwright.
// element.click() trong page.evaluate() thi Power BI KHONG NHAN.
// Go phim cung KHONG commit — phai dung fill() roi Tab.
await box.fill('8/21/2026');
await page.keyboard.press('Tab');
```

**Lỗi #14:** nhiều page có **nhiều chữ `期間`** (vừa là nhãn vừa là nút). Code cũ bấm phần tử cuối cùng → trúng nhãn → ô nhập ngày không bao giờ hiện ra.
→ **Thử lần lượt từng ứng viên** cho tới khi hai ô `input.item-fill` xuất hiện.

**Có page chỉ có chế độ tương đối**, không chuyển sang tuyệt đối được. Đừng gọi đó là "thất bại": đọc dải ngày đang hiển thị, nếu nó đã kết thúc đúng ngày cần và **giống nhau ở cả 5 bản** thì hợp lệ.

**Cảnh báo:** ô nhập ngày đọc ngược về đúng giá trị **không có nghĩa là** slicer đang hiển thị đã đổi — page có thể có nhiều slicer ngày và bạn vừa điền vào cái khác. Phải đối chiếu với dải ngày hiển thị trên canvas.

---

## 6. Phân loại khác biệt

### Thứ tự bắt buộc

```python
t0, tv = canvas_text(v0), canvas_text(vX)
text_differs = (t0 is not None and tv is not None and t0 != tv)

# CHU TRUOC. Nguong pixel KHONG duoc quyet dinh truoc chu.
if pct <= SAME_PCT and not text_differs:
    status = "SAME"
else:
    status = "DIFF"
    kind = "VALUE" if text_differs else ("UNKNOWN" if t0 is None else "UI")
```

**Lỗi #21 — lỗi nguy hiểm nhất cả dự án.** Ngưỡng pixel được xét **trước** chữ. Một page vẽ rất nhỏ trong khung lớn nên một con số chỉ chiếm ~100 pixel trên ảnh 9,3 triệu pixel → dưới ngưỡng 0,02% → **8 ô thiếu số liệu thật bị đóng dấu GIỐNG**. Không phép kiểm nào bắt được vì tất cả đều xét pixel.

### Mặt nạ chịu được dịch 1 pixel

Canvas Power BI vẽ lại có thể lệch tròn 1px giữa hai lần chụp, khiến **mọi đường kẻ và chữ** đều bị báo khác (79.803 pixel ở hai ảnh giống hệt nhau — lỗi #10).

```python
def robust_mask(a, b, tol=26, r=1):
    """Lay do lech NHO NHAT so voi vung lan can 3x3 ben kia."""
    d = np.abs(a - b).max(axis=2)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx == 0 and dy == 0:
                continue
            bs = np.roll(np.roll(b, dy, axis=0), dx, axis=1)
            d = np.minimum(d, np.abs(a - bs).max(axis=2))
    return ndimage.binary_opening(d > tol, np.ones((2, 2), bool))
```

**Nhưng phải có đường lui:** ở cỡ chữ nhỏ, phép này có thể xoá gần hết một con số (con số bên cạnh cũng khớp khi dịch). Ô đã xác định là KHÁC mà mặt nạ rỗng thì **dùng phép trừ thô để định vị**, nếu không sẽ không khoanh đỏ được gì.

### Khác mức zoom, không phải khác nội dung

Lỗi #11: Power BI **nhớ mức zoom riêng cho từng bản report** (v0 98%, v3.5 113%). Chữ trùng khớp từng ký tự mà 230.571 pixel lệch.
→ Chữ giống hệt thì thử khớp lại ở một loạt tỉ lệ; lệch giảm rõ rệt ở tỉ lệ khác 1.0 ⇒ **lỗi chụp**, chụp lại ô đó.

### Dưới ngưỡng nhìn thấy thì tính là GIỐNG

Quy tắc user đã chốt: **mắt thường không thấy thì bỏ qua, không ghi "khác giao diện"**.
Áp dụng khi chữ giống hệt VÀ lệch nhỏ (chỉ đường mảnh 1–4px, hoặc dưới ~2000 pixel với vùng lớn nhất dưới ~4000 px²).
**Không bao giờ hạ cấp một ô đã xác định là khác VALUE.**

### Đối chiếu bố cục phải trừ độ dịch chung

Chữ ký bố cục = toạ độ mọi visual so với `.displayArea`. Nhưng canvas dịch 1px làm **mọi visual lệch +1** → báo động giả.
→ Neo theo visual đầu tiên rồi mới so.

---

## 7. Lượt đối chứng độc lập

Quy tắc user đã chốt: **chỉ khác biệt lặp ở cả hai lượt mới tính là thật.**

Chụp lại các ô liên quan vào **thư mục khác** (`shots2/`) để không phá bằng chứng lượt 1, rồi so hai chiều:

- Khác biệt ở lượt 1 có lặp lại ở lượt 2 không? (bắt dương tính giả)
- Ô từng báo giống có lộ khác biệt mới không? (bắt âm tính giả)

---

## 8. Tự kiểm — `quality_check.py`

**Monitor đếm tiến độ là vô dụng.** Nó bắn `anh=171/240` suốt đêm trong khi báo cáo đầy lỗi. Monitor phải in ra **những con số quyết định kết luận cuối cùng**, mỗi lần một dòng, kết thúc bằng `SACH` hoặc `CAN SUA: <cái gì>`.

Sáu tín hiệu tối thiểu:

| Tín hiệu | Bắt được gì |
|---|---|
| `o-thieu` | Ô chưa có ảnh cả hai bên |
| `o-chup-loi` | `ok = false` trong log |
| `filter-khong-an` | `apF1/apF2 = false` |
| `anh-khong-on-dinh` | `stable = false` — trang còn đang đổi |
| `bao-giong-nhung-chu-khac` | **Âm tính giả** — đối chiếu chữ cho MỌI ô gán SAME |
| `html-cu-hon-du-lieu` | Có thay đổi chưa được dựng lại |

### Hai bài học về chính phép kiểm

**Lỗi #17 — phép kiểm dò nhầm tên trường.** Đoạn kiểm dò `applyF1/applyF2` trong khi tên thật trong log là `apF1/apF2`. Nó chạy trơn tru và **luôn báo 0 lỗi** suốt nhiều lượt, che mất 11 ô filter không ăn.

> **Sau khi viết phép kiểm, lấy một trường hợp hỏng đã biết cho nó chạy và xác nhận nó kêu.** Một phép kiểm chưa bao giờ kêu không phải bằng chứng mọi thứ ổn — nó chỉ là một phép kiểm chưa được thử.
> Cách nhanh nhất: in toàn bộ tên trường có thật trong log (`collections.Counter` trên keys) rồi đối chiếu với tên phép kiểm đang dò.

**Tiêu chí phải đúng bản chất.** Cảnh báo "HTML cũ hơn 45 phút" là báo động giả — một bản đã hoàn tất thì để lâu không sao. Chỉ cảnh báo khi **dữ liệu mới hơn báo cáo**.

---

## 9. Báo cáo HTML

**Bắt buộc có:**
1. Tên đầy đủ mọi report + **có tồn tại ở version đó không**.
2. Mọi page, cả 3 trạng thái.
3. Ảnh nhúng base64. **Bản nào giống v0 thì không kèm ảnh.**
4. Khoanh đỏ đúng vùng khác biệt, **trên cả ảnh v0 lẫn ảnh bản đem so**, kèm cặp ảnh phóng to.
5. Nhãn rõ đâu là v0, đâu là bản nào.
6. Bảng filter đã dùng: slicer 1 / giá trị 1 / slicer 2 / giá trị 2.
7. Mục ảnh gập **hai tầng** (report → page), mặc định đóng.
8. Nhật ký truy nguyên: mỗi lần máy báo "khác" thì nguyên nhân thật là gì.

**Không được có:**
- Phần trăm chênh lệch. User chỉ cần **Giống / Khác**.
- Nhãn "khác giao diện" cho thứ mắt thường không thấy.
- Bất kỳ suy diễn nào chưa kiểm được.

### Bẫy khi dựng HTML

| # | Bẫy | Cách tránh |
|---|---|---|
| 16 | Ghi `26/08` → người đọc hiểu là ngày 26 tháng 8 | Canvas ghi kiểu Nhật năm/tháng. Ghi đầy đủ **tháng 08/2026** |
| 15 | Bảng phạm vi ngày báo khống đã chạm mốc | Phép đo bắt cả **dải ngày do slicer tự hiển thị** — đó là ngày ta YÊU CẦU, không phải ngày có trong dữ liệu. Phải loại dải đó trước khi đo |
| — | Ngày bị bỏ sót | Canvas có ít nhất 3 dạng: `26/08/12`, `8/4/2026`, `08/12 Wed` (không có năm). Nhận thiếu một dạng là báo nhầm "không có dòng nào" |
| — | Ảnh nhỏ và mờ | Nhiều page chỉ vẽ trong một góc của khung rất lớn. **Cắt bỏ nền thừa trước khi nhúng.** Nền ngoài canvas của Fabric là xám **235**, không phải trắng 255 — lấy ngưỡng 245 thì không cắt được gì |
| — | Ảnh phóng to cắt sát quá, không thấy ngữ cảnh | Ép khung tối thiểu (~900×520) quanh vùng lệch, rồi phóng to bằng LANCZOS cho đọc được chữ |
| — | Chữ nhoè | **Dùng JPEG cho mọi ảnh**, đừng dùng PNG. Ảnh đầy đủ: chất lượng ~90, bề ngang 2400. Ảnh phóng to: chất lượng ~95, bề ngang 2000. PNG nét hơn không đáng kể mà **nặng gấp đôi** — cùng bộ ảnh, PNG cho file 23,5 MB còn JPEG chỉ 17,2 MB |
| — | Đếm nhầm số ô | Log có bản ghi telemetry không phải ô chụp (ví dụ `{_view: ...}`) — lọc bằng `if "v" in r` |

---

## 10. Những câu KHÔNG được viết nếu chưa kiểm

Đã có hai lần viết kết luận nghe hợp lý mà sai, phải gỡ khỏi báo cáo:

- ~~"Bảng dữ liệu không chứa dòng nào của tháng 09"~~ — chính bản gốc hiện dữ liệu tới 01/09. Sai.
- ~~"Slicer chỉ có hai lựa chọn, không có tháng 09"~~ — đo trước lần refresh, không còn giá trị.

> Bằng chứng đo **trước** một lần refresh thì **hết hiệu lực sau** lần refresh đó. Phải đo lại hoặc ghi "chưa xác định".

Khi không kiểm được (capacity tắt, MCP không kết nối), **ghi rõ là để ngỏ** kèm việc cụ thể cần làm để kết luận.

---

## 11. Chụp lại có chọn lọc

Đừng chụp lại cả 240 ảnh vì vài ô hỏng. Sinh script chỉ chụp đúng những ô cần:

```
python make_fix.py "v0|R1|P1" "v3|R4|P2"
node driver.js allstates_fix.js fixN_out.json
```

Rồi **gộp log ngược vào** log chính theo khoá `(v, rk, pk)`. Nhớ đổi `const OUT` nếu muốn giữ nguyên bằng chứng lượt cũ.

---

## 12. Việc phải để user tự làm

- **Refresh semantic model** — user tự làm bằng tay. Không thao tác vào model.
- **Bật/tắt capacity** — không kiểm được gì trên Fabric khi capacity tắt.
- **Đăng nhập Fabric** — driver chỉ gắn vào phiên có sẵn.

---

## 13. Đính kèm file lên Azure DevOps

MCP azure-devops **chỉ có tải xuống**, không có tải lên. `az account get-access-token` có thể bị MFA chặn (`AADSTS50076`), và `az devops invoke` ép body phải là JSON nên không gửi được file nhị phân.

Đường đi được: nhờ user chạy `az login --scope 499b84ac-1321-427f-aa17-267ca6975798/.default` (hiện MFA) rồi mới upload qua REST — hoặc user kéo thả file vào ticket, thường nhanh hơn.

Comment lên work item thì dùng MCP bình thường, chạy tốt.

**Meo: dinh kem ma khong can token.** Neu file DA nam tren ADO (dinh kem o mot work
item khac), khong can tai len lai — tro thang lien ket toi chinh blob do:

```bash
az boards work-item relation add --id <work-item> --relation-type "Attached File"   --target-url "https://dev.azure.com/<org>/<project-guid>/_apis/wit/attachments/<attachment-guid>?fileName=<ten-file>"   --org https://dev.azure.com/<org>
```

`az boards` co xac thuc rieng nen chay duoc ngay ca khi `az account get-access-token`
bi MFA chan. Luu y: `--relation-type` chi nhan **ten hien thi** `"Attached File"`,
KHONG nhan reference name `AttachedFile` — mat ba lan thu moi ra.
Lay `<attachment-guid>` bang cach doc `relations` cua work item dang giu file do.

---

## 14. "Default view" khác nhau giữa các version — KHÔNG phải lỗi model, và KHÔNG tự sửa được qua trình duyệt

Gặp khi so v0 vs v1/v2: report giống hệt nhau về DAX/data, nhưng "Reset to default"
(nút filter-pane mà script dùng để reset trước mỗi state) lại đưa mỗi version về một
bộ filter/breakdown-mode KHÁC NHAU (vd: v0 mặc định `行選択=タイプ`, v1/v2 mặc định
`行選択=店舗`). Kéo theo hàng loạt ô "khác về số liệu" ở MỌI state (load/filter1/filter2)
vì hai bên xuất phát từ ngữ cảnh filter khác nhau ngay từ đầu — không liên quan gì đến
việc tối ưu model.

**Cách phân biệt với lỗi thật:** report này dùng nhóm nút "Bookmark Navigator" (nhiều
bookmark, mỗi nút = 1 bookmark đổi cả visibility/sort/filter, không phải slicer đơn
thuần). Diff nguyên văn `report.json`, `bookmarks.json`, `pages.json`, và **từng
visual.json** giữa file nguồn đã deploy của v0 và v1 — nếu **giống hệt tuyệt đối**
(thường là vậy) thì khác biệt **không nằm trong file định nghĩa đã deploy**, mà là
**state lưu phía server của Fabric Service riêng cho từng report item** — độc lập
với nội dung file.

**Ba cách đã thử để "sửa" state đó, tất cả đều KHÔNG persist:**
1. Bấm nút bookmark ở View mode (bình thường) → chỉ đổi tạm trong phiên xem, biến mất
   ngay khi bấm "Reset to default" hoặc mở lại report.
2. Bấm "選択解除"/Clear Selection + bấm bookmark mong muốn → tưởng đã fix (verify ngay
   sau đó khớp), nhưng lần chụp tiếp theo (script tự gọi `resetDefault()` trước mỗi
   state) lại **revert về đúng state cũ** — chứng minh state "mặc định" thật sự được
   Fabric phục hồi từ đâu đó không đổi được qua click thường.
3. Vào **Edit mode**, bấm bookmark đúng, bấm **Save** (thật sự thấy toast "saved") →
   reload lại vẫn sai. Không tìm thấy "Set as Default" qua right-click nút bookmark
   hay qua menu "View" trong Fabric web editor.

**Kết luận: đây không phải việc script/agent tự sửa được qua trình duyệt hay API.**
Muốn sửa default view của 1 report cần **Power BI Desktop** (pane Bookmarks đầy đủ,
có chức năng "Set as Default", rồi Publish lại) — nằm ngoài phạm vi mọi thao tác agent
có thể tự động hoá qua Playwright/CDP hay REST API hiện có.

**Khi báo cáo:** ghi rõ đây là khác biệt về **default bookmark/view state giữa các
report item đã publish**, không phải lỗi DAX/model/optimization — và việc sửa cần bàn
giao cho người có Power BI Desktop, không phải việc agent tự làm tiếp được.

**Cập nhật:** có 1 cách khác không cần Desktop — **xóa rồi tạo lại report item** từ
đúng file PBIR hiện tại của nó (`delete_item` + `create_item`, xem
`verify/recreate_v0_report.py` / `recreate_v1_report.py` làm ví dụ). Đã kiểm chứng: item
mới luôn rơi về default "gốc theo file", tức state mà các bản đã publish gần đây nhất
đang có (không nhất thiết là state ban đầu-ban đầu). Dùng khi chỉ cần MỘT bản khớp theo
bản còn lại, không cần custom default riêng. Nhược điểm: xóa thật, không recycle bin,
đổi report ID (phải cập nhật `inventory.json` và mọi chỗ trỏ tới ID cũ); và bị Claude
Code's tool permission tự chặn `delete_item` (destructive-op classifier) → phải chuẩn bị
script rồi để **user tự chạy** trong terminal của họ, agent không tự chạy được lệnh xóa.

## 15. Bookmark có thể ép được TRONG PHIÊN CHỤP (không cần persist) — nhưng một panel không tài nào tái hiện được ngoài pipeline thật

Tiếp nối mục 14: mục đó kết luận "không tự sửa được qua browser" là đúng cho việc
**LƯU VĨNH VIỄN** default view trên server Fabric. Nhưng cho mục đích của skill này
(mỗi lần chụp đều tự `resetDefault()` rồi chụp ngay), **không cần persist** — chỉ cần
click lại đúng bookmark đó SAU MỖI LẦN reset, ngay trong phiên đang chụp. Cách này
**có tác dụng thật và đã verify bằng dữ liệu** (không chỉ suy đoán): thêm trường
`"bookmarks": [...]` vào mục page tương ứng trong `filters.json`, `capture.js` sẽ click
lại đúng các nhãn đó ngay sau mỗi `resetDefault()` (cả ở `load` lẫn trước mỗi
`filter1`/`filter2`). Đã xác nhận qua ảnh + số liệu ngày thật: R1|P1 (nút "タイプ") và
R1|P2 (nút "直近3か月" + "レート展開") — sau khi ép, ngày tháng hiển thị của v0/v1 khớp
tuyệt đối, trong khi trước đó lệch hẳn (v0 "26/08/12〜26/09/23" vs v1 "26/09/11〜26/09/23").

**Bẫy đã gặp khi viết cơ chế xác minh "nút đã được chọn chưa":** những nút này KHÔNG
phải slicer (`.slicer-dropdown-menu`) mà là shape gắn action "Bookmark", text nằm
trong `.ui-role-button-text`. Lúc đầu dùng `element.classList.contains('selected')`
để biết nút nào đang active — **sai hoàn toàn**: dump DOM thật cho thấy **MỌI** phần
tử `.ui-role-button-text` (chọn hay không) đều có class `selected` giống hệt nhau,
class này vô nghĩa với mục đích này. Tín hiệu THẬT nằm ở **màu fill của SVG
path/rect bên trong** — nút CHƯA chọn (trong một nhóm loại trừ lẫn nhau) luôn là màu
xám trung tính `rgb(179,179,179)`; nút ĐANG chọn có màu khác hẳn (vd xanh sáng
`rgb(80,156,250)`). Đối chiếu "có phải xám trung tính không" (thay vì khớp đúng 1 mã
màu) để chịu được sai khác nhỏ giữa theme/report.

**Một panel không tài nào ép được — đã xác nhận là hạn chế thật, không phải chưa
thử đủ:** R1|P3 có 1 panel liệt kê ~28 nút (`■列選択区分`/`■行選択区分`), trong đó có
nút "品質" cần ép để trang thái nhất quán. Nút này **chắc chắn tồn tại và render được**
trong lần chụp thật của pipeline (xác nhận bằng cách crop + phóng to 3 lần đúng ảnh
PNG đã chụp) — nhưng **không bao giờ xuất hiện trong DOM** khi tự mở tab kiểm tra
riêng, dù đã thử đủ 7 hướng: chờ tới 45 giây, phóng full màn hình giống hệt
`measureView()`, mở tuần tự P1 rồi mới sang P3 trong cùng 1 tab (mô phỏng đúng thứ tự
pipeline thật), bấm `resetDefault()`, mở/đóng một slicer dropdown thật, tự gọi
`.displayArea.screenshot()` (cơ chế `shoot()` thật dùng), và kiểm tra
`scrollHeight`/`scrollWidth` (bằng `clientHeight`/`clientWidth` — không phải do cuộn).
Đã bỏ "品質" khỏi `bookmarks` của R1|P3 trong `filters.json` (giữ lại "直近10日", nút
này ép được bình thường) để khỏi lãng phí thời gian chờ vô ích mỗi lần chạy. Kết quả:
pham vi ngay của P3 vẫn có thể lệch giữa v0/v1 do nhóm nút `列選択区分` — ghi nhận là
hạn chế đã biết (cùng bản chất "default view/bookmark" của mục 14), không phải lỗi model.

**Gặp lại lần 2, xác nhận đây là một LOẠI hiện tượng, không phải ca đơn lẻ:** R1|P1
có danh sách "値選択" (chọn nhiều số liệu hiển thị cùng lúc) — v0 bật thêm 2 mục
("機械遊技業収入(千)", "収入_手数料抜(千)") mà v1 không bật. Thử ép y hệt cách trên
("機械遊技業収入(千)" vào `bookmarks`) → **cùng thất bại theo đúng kiểu cũ**: tồn tại
thật trong ảnh chụp pipeline thật, nhưng `document.createTreeWalker` tìm text node
chứa đúng chữ đó trên toàn bộ `document.body` của một tab mở riêng để kiểm tra thì
**ra rỗng tuyệt đối** — không phải sai chọn class/selector, mà đúng là nội dung đó
không hề có mặt trong DOM khi tự mở tab riêng. Đã bỏ 2 nhãn này khỏi `bookmarks` của
R1|P1 (giữ "タイプ", vẫn ép được bình thường). **Quy luật rút ra:** panel/danh sách
càng nhiều mục (ở đây ~15-28 mục) càng có khả năng rơi vào loại này; panel ít mục
(≤3-5, như "期間"/"列選択"/"行選択区分" loại nhỏ) luôn ép được. Nghi ngờ hợp lý (chưa
verify được) là các panel nhiều mục dùng cơ chế render/virtualization khác, chỉ kích
hoạt trong ngữ cảnh đủ dài của pipeline thật (nhiều lane, nhiều report đã mở trước đó
trong cùng phiên) mà một tab đơn lẻ mở riêng để test không tái tạo được — ghi "chưa
xác định" đúng theo mục 0 nguyên tắc 3, không suy diễn thêm.

**Cập nhật quan trọng — Bách tự tay xác nhận (không qua script):** mở trực tiếp cả 2 tab
Fabric (v0 và v1-P1), **KHÔNG bấm "Reset to default"**, chỉ nhìn đúng trạng thái đang có.
Kết quả: `機械遊技業収入(千)` = 225 và `収入_手数料抜(千)` = 225 — **giống hệt nhau ở cả
hai bên**, dù `行選択区分` đang khác nhau (v0 = タイプ, v1 = 店舗 — chỉ là 2 cách nhóm
khác nhau của CÙNG một dữ liệu, không phải thiếu số liệu). Vậy số liệu thật sự khớp,
điều tôi từng thấy "thiếu" chỉ là do sau khi ép reset+click, script không set được đúng
state để 2 dòng đó HIỆN RA — không phải data thật sự khác.

**Bài học phương pháp, áp dụng từ giờ:** với các trang có bookmark/panel dạng này, đừng
lấy `resetDefault()` làm điểm xuất phát chung rồi ép click lại từng cái — chính
`resetDefault()` đưa mỗi bản về default RIÊNG của nó (đã biết từ mục 14), và một số
panel (như đã gặp) không set lại được sau đó bằng click tự động. Cách chắc chắn hơn:
**không reset, tự tay (hoặc bằng script) set thẳng đúng giá trị cần so trên cả hai
bên**, so sánh đúng con số đang hiện — không quan trọng 2 bên có đang ở cùng
"trạng thái mặc định" hay không, miễn 2 bên cùng hiện đúng phép so cần kiểm.

## 16. `NOT_SIGNED_IN` giả — do quên set `FRC_PROBE_WORKSPACE` trong terminal session mới

Chrome đã đăng nhập Fabric thật (kiểm tra bằng mắt: vào được workspace, thấy danh sách
report bình thường) nhưng `run.py` vẫn báo:

```
LUU_Y: trinh duyet dang o Fabric nhung danh sach workspace chua dung xong sau 45 giay.
NOT_SIGNED_IN: the Fabric session is not authenticated.
```

Nguyên nhân: `driver.js` kiểm tra đăng nhập bằng cách mở 1 workspace ID cố định làm
"probe" (đọc `FRC_PROBE_WORKSPACE`, fallback về 1 ID mặc định thuộc **project khác**).
Biến môi trường **không tự nhớ giữa các session/terminal khác nhau** — mở terminal mới,
hoặc Chrome mới, hoặc agent bị compact/restart giữa chừng đều làm mất biến này. Khi đó
probe 404 vào workspace không tồn tại/không có quyền → trang không bao giờ render danh
sách item → script kết luận nhầm là chưa đăng nhập.

**Luôn set trước mỗi lần chạy trong 1 session mới** (không set 1 lần rồi quên):

```powershell
$env:FRC_PROBE_WORKSPACE = "<id một workspace bất kỳ CỦA PROJECT NÀY>"
```
```bash
export FRC_PROBE_WORKSPACE=<id một workspace bất kỳ CỦA PROJECT NÀY>
```

Cách chẩn đoán nhanh khi gặp lỗi này: `echo $FRC_PROBE_WORKSPACE` (hay `$env:FRC_PROBE_WORKSPACE`)
trước khi nghi ngờ Chrome/đăng nhập — nếu rỗng, đó là nguyên nhân, không phải Chrome.

## 17. Kiểm bằng DOM-state có thể báo "giống hệt" trong khi ảnh chụp cho thấy khác rõ ràng — LUÔN mở ảnh trước, không tin DOM một mình

Gặp khi verify tay (Bước 5) 3 ô `VALUE` diff còn lại của `R1|P3` (`稼働玉利データ`, trang "プロ")
sau x10 scale-up. Một script kiểm tra tự động dump toàn bộ `.ui-role-button-text` (màu fill) và
trạng thái list-slicer (checked/unchecked) giữa v0 và v1 — **so khớp 23 control, báo 0 khác biệt
tuyệt đối**. Theo đúng kết quả đó thì phải kết luận "chưa xác định nguyên nhân" (đã từng viết vào
báo cáo đúng như vậy).

**Sai hoàn toàn.** Mở trực tiếp 2 ảnh đã chụp sẵn
(`shots/annot/load/full__R1__P3__v1__{v0,v1}.png`) bằng tool đọc ảnh (không phải qua DOM) thì thấy
NGAY LẬP TỨC, rõ ràng bằng mắt: dropdown `土日祝` khác (`休日` vs `All`), dropdown `LT` khác (`All`
vs `LT`), và nút chọn trong panel `列選択区分` khác (`土日祝` vs `日別`) — đúng 3 control DOM-check
đã bỏ sót hoàn toàn, không phải vì chọn sai màu ngưỡng mà vì **không hề kiểm tra 3 control này** dù
tưởng đã bao quát hết "mọi control nhìn thấy được" trên trang.

**Bài học, áp dụng bắt buộc từ giờ — thứ tự làm Bước 5 phải đảo lại:**
1. **Mở ảnh chụp thật trước tiên** (`shots/annot/.../full__<report>__<page>__<version>__{v0,vX}.png`
   qua tool đọc ảnh), nhìn trực tiếp toàn bộ vùng có khoanh đỏ VÀ vùng lân cận — không chỉ tin vào
   vùng đã khoanh sẵn, vì DOM-check hoặc thuật toán khoanh vùng có thể không biết một control nào
   đó tồn tại để mà khoanh.
2. **Chỉ sau khi đã nhìn ảnh và xác định được (hoặc loại trừ được) sự khác biệt bằng mắt**, mới viết
   script DOM/click để *thao tác* (ép filter, bấm nút) — không bao giờ dùng DOM-dump làm **bước xác
   minh đầu tiên** để kết luận "giống/khác", vì DOM có thể thiếu, chọn nhầm selector, hoặc bỏ sót
   control mà không hề báo lỗi.
3. Khi bấm control để ép trạng thái khớp nhau: dùng Playwright `.locator(...).click()` thật (đúng
   như mục 15), tuyệt đối không dùng `element.click()` qua `page.evaluate()` — đã thử 2 lần, click
   "thành công" theo log nhưng KHÔNG có tác dụng gì trên UI (không trigger được pointer-event handler
   thật của Power BI/React).
4. Sau khi ép đúng bằng tay và số liệu khớp, viết luôn phần chứng minh này vào báo cáo — đừng để
   "chưa xác định" đứng yên nếu có thể tự tay verify.

**Quy tắc chung rút ra: luôn nghi ngờ kết quả "giống hệt" từ một phép kiểm gián tiếp (DOM/text/
màu sắc) khi vẫn có ảnh chụp thật sẵn có — ảnh chụp là bằng chứng gốc, DOM-state chỉ là một cách
diễn giải có thể sai.**

## 18. Filter kiểu "ngày tương đối" (`直近月`) cho kết quả khác nhau giữa các version chỉ vì refresh lệch mốc thời gian — không phải bug model

Gặp khi so trực tiếp 3 ảnh chụp cùng page/cùng filter (`計画グループ別詳細_S`, máy
`Ｌ東京喰種ＣＴ`) giữa `PS設定データ_s` v2 / v2.1 / v2.5: v2 và v2.1 hiện đủ dữ liệu, v2.5 (vừa
được Full Refresh trước đó) hiện bảng trống — dù measure đã sửa đúng và trả giá trị thật qua DAX
trực tiếp.

**Nguyên nhân thật**: filter `月選択=直近月` ("tháng gần nhất") tự tính dựa trên ngày lớn nhất
*hiện có trong bảng* tại thời điểm truy vấn — không phải ngày cố định. Máy test giả lập
`Ｌ東京喰種ＣＴ` có dữ liệu dummy chốt cứng ở `2026-08-26` (giống hệt ở cả v2/v2.1/v2.5, xác nhận
qua `MIN`/`MAX` DAX). v2/v2.1 chưa refresh lại lâu nên "ngày hiện tại" của bảng calendar vẫn còn
nằm trong khoảng có dữ liệu của máy đó; v2.5 vừa bị Full Refresh (do chính quá trình fix bug ở
mục trên) nên "ngày hiện tại" nhảy tới ngày refresh thật (hôm đó), vượt qua mốc 8/26 của máy này
→ `直近月` trỏ sang tháng không còn dữ liệu cho riêng cái máy test đó → bảng trống.

**Cách xác minh nhanh, không cần UI**: DAX `EVALUATE ROW("TableMaxDate", MAX(...[営業日]),
"MachineMaxDate", CALCULATE(MAX(...[営業日]), FILTER(..., [機種名称]="<máy>")))` chạy trên từng
version — nếu `MachineMaxDate` giống hệt nhau giữa các version nhưng `TableMaxDate` (mốc "hôm nay"
hiệu dụng của mỗi version) khác nhau rõ rệt, đây chính là nguyên nhân, không phải lỗi dữ liệu hay
lỗi model.

**Kết luận / cách xử lý**: đây là giới hạn của dữ liệu test giả lập (máy test không có dữ liệu
liên tục đến "hôm nay"), không phải bug cần sửa trong model — chỉ cần chạy lại refresh (incremental
hoặc full) đồng thời cho tất cả version đang so sánh để chúng cùng chung một mốc "ngày hiện tại",
thì kết quả sẽ lại khớp nhau. Không nên "fix" bằng cách ép ngày filter cố định — việc đó chỉ che
triệu chứng, đúng tinh thần mục 3 của file này (không ép khoảng ngày để giấu lệch mốc refresh).
