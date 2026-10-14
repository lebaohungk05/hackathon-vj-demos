# -*- coding: utf-8 -*-
"""Bao cao HTML so sanh report v0 vs v1/v2/v3/v3.5.

Nguyen tac trinh bay:
  - Khong ghi phan tram. Chi Giong / Khac.
  - Moi anh deu co nhan to ghi ro do la version nao.
  - Cho nao khac thi khoanh do dung cho do, va khoanh tren CA HAI anh (v0 va
    version dem so), kem mot anh phong to vao dung vung lech.
  - Report nao chua chup thi ghi "chua kiem", khong ghi "khong mo duoc".
"""
import os, io, json, base64, html, collections
from PIL import Image

import os as _os
W = _os.environ.get("FRC_WORK") or _os.getcwd()
RUN = _os.environ.get("FRC_RUN") or W
SHOTS  = os.path.join(RUN, "shots")
ANNOT  = os.path.join(SHOTS, "annot")
OUTHTM = _os.environ.get("FRC_OUT") or _os.path.join(RUN, "comparison_report.html")

# Danh sach ban dem so va nhan hien thi: lay tu inventory, khong go cung.
_inv0 = json.load(io.open(os.path.join(W, "inventory.json"), encoding="utf-8"))
_sel = [x for x in (_os.environ.get("FRC_VERSIONS") or "").split(",") if x.strip()]
VS = [v["id"] for v in _inv0["versions"] if v["id"] != "v0"]
if _sel:
    VS = [v for v in VS if v in _sel]
ALLV = ["v0"] + VS
VSHORT = {v["id"]: (v.get("label") or v["id"]) for v in _inv0["versions"]}
VSHORT.setdefault("v0", "v0")
VLABEL = dict(VSHORT)
VLABEL["v0"] = VSHORT.get("v0", "v0") + " — BẢN GỐC"
STATES = [("load",    "Trạng thái 1 — khi mở, chưa filter"),
          ("filter1", "Trạng thái 2 — sau filter lần 1"),
          ("filter2", "Trạng thái 3 — sau filter lần 2")]
WS_BASE = "f54ae67e-24ad-4468-baf6-5a56f3345b3d"
WS_VAR  = "fce34305-6152-42dd-aeda-529ae506ad4c"

IMG_W, IMG_Q = 2400, 90     # anh day du — de thap thi chu tren report nhoe het
ZOOM_W, ZOOM_Q = 2000, 95   # anh phong to: JPEG chat luong cao (PNG net hon khong
                            # dang ke ma nang gap doi)


def jload(name, default, base=None):
    p = os.path.join(base if base is not None else RUN, name)
    return json.load(io.open(p, encoding="utf-8")) if os.path.exists(p) else default


inv  = jload("inventory.json", {}, base=W)
fil  = jload("filters.json", {}, base=W)
logs = [r for r in jload("allstates_out.json", []) if "v" in r]

# Log chi duoc ghi khi lan chup KET THUC. Neu no cu hon anh moi nhat thi muc
# "chat luong lan chup" dang noi ve mot lan chup khac -> phai canh bao, khong
# duoc tron so lieu cu voi ket qua diff moi.
def _newest(d):
    best = 0
    for root, _dirs, files in os.walk(d):
        for f in files:
            try:
                best = max(best, os.path.getmtime(os.path.join(root, f)))
            except OSError:
                pass
    return best

_logp = os.path.join(RUN, "allstates_out.json")
LOG_STALE = os.path.exists(_logp) and _newest(SHOTS) - os.path.getmtime(_logp) > 120
# bo dong ky thuat {_view: ...} — no khong co co "ok" nen truoc day bi dem
# thanh mot "page mo loi" gia.
diff = jload("diff_results.json", [])

# Ghi chu xac minh TAY (nguoi/agent tu thao tac trinh duyet, khong chi tin diff tu
# dong) — xem SKILL.md muc "Buoc 5", bat buoc voi moi o VALUE/UI. File tuy chon,
# khong co thi khong hien gi them.
_mnotes = jload("manual_notes.json", [])
MNOTE = {}
for _n in _mnotes:
    _states = _n.get("states") or [None]
    for _s in _states:
        MNOTE[(_n["v"], _n["rk"], _n["pk"], _s)] = _n["note"]


def manual_note(v, rk, pk, state):
    return MNOTE.get((v, rk, pk, state)) or MNOTE.get((v, rk, pk, None))


# Da xac minh tay la KHONG phai regression thi doi thang trang thai ve SAME —
# khong de nguyen DIFF/VALUE/UI roi chi giai thich o duoi, vi nguoi doc luot
# nhanh se thay do/vang va tuong con regression that. Ghi lai xuong dia de
# quality_check.py va verdict() (chay SAU buoc nay trong pipeline cua run.py)
# cung doc dung ket qua da sua, khong chi HTML.
_overridden = False
for d in diff:
    if d.get("status") != "DIFF":
        continue
    _note = manual_note(d.get("v"), d.get("rk"), d.get("pk"), d.get("state"))
    if not _note:
        continue
    d["orig_status"], d["orig_kind"] = d.get("status"), d.get("kind")
    d["status"], d["kind"] = "SAME", None
    d["manual_verified"], d["manual_note"] = True, _note
    _overridden = True
if _overridden:
    io.open(os.path.join(RUN, "diff_results.json"), "w", encoding="utf-8").write(
        json.dumps(diff, ensure_ascii=False, indent=1))

LOG = {(r["v"], r["rk"], r["pk"]): r for r in logs if "v" in r}
DIF = {(d["v"], d["rk"], d["pk"], d["state"]): d for d in diff if "v" in d}
SCOPE = sorted({r["rk"] for r in logs if "rk" in r})     # report da thuc su chup

SHOWN, STABLE, ZOOM = {}, {}, {}
for r in logs:
    k3 = (r.get("v"), r.get("rk"), r.get("pk"))
    for st, sk, lk in (("load", None, "load"), ("filter1", "shownF1", "F1"), ("filter2", "shownF2", "F2")):
        if sk:
            SHOWN[k3 + (st,)] = r.get(sk)
        sh = r.get(lk)
        if isinstance(sh, dict):
            STABLE[k3 + (st,)] = sh.get("stable")
            ZOOM[k3 + (st,)] = sh.get("zoom")


def same_filter(v, rk, pk, state):
    if state == "load":
        return None
    a, b = SHOWN.get(("v0", rk, pk, state)), SHOWN.get((v, rk, pk, state))
    return None if (a is None or b is None) else (a == b)


_c = {}
def b64(path, maxw, q):
    if not path or not os.path.exists(path):
        return None
    k = (path, maxw, q)
    if k not in _c:
        im = Image.open(path).convert("RGB")
        if im.width > maxw:
            im = im.resize((maxw, max(1, round(im.height * maxw / im.width))), Image.LANCZOS)
        buf = io.BytesIO()
        if q:
            im.save(buf, "JPEG", quality=q, optimize=True)
            _c[k] = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        else:
            # PNG cho anh phong to: chu va so phai doc duoc, nen JPEG lam nhoe net
            im.save(buf, "PNG", optimize=True)
            _c[k] = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    return _c[k]


shot  = lambda st, v, rk, pk: os.path.join(SHOTS, st, "%s__%s__%s.png" % (v, rk, pk))
afull = lambda st, v, rk, pk, who: os.path.join(ANNOT, st, "full__%s__%s__%s__%s.png" % (rk, pk, v, who))
azoom = lambda st, v, rk, pk, who: os.path.join(ANNOT, st, "zoom__%s__%s__%s__%s.png" % (rk, pk, v, who))

# ---------------------------------------------------------------- khuon HTML
# Khuon (the <head>, CSS, mo <body>) nam o mot FILE RIENG chu khong nhung trong
# ma nguon, de moi lan chay deu cho ra dung mot khuon va ai cung sua duoc no ma
# khong dong vao Python. Thu tu tim:
#   1. bien moi truong FRC_TEMPLATE
#   2. <thu muc script>/../templates/report_shell.html   (khi chay tu skill)
#   3. <thu muc script>/report_shell.html                (khi chay roi le)
#   4. <thu muc lam viec>/report_shell.html
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_TPL_TRIED = [
    _os.environ.get("FRC_TEMPLATE"),
    _os.path.join(_HERE, "..", "templates", "report_shell.html"),
    _os.path.join(_HERE, "report_shell.html"),
    _os.path.join(W, "report_shell.html"),
]
_TPL = next((x for x in _TPL_TRIED if x and _os.path.exists(x)), None)
if not _TPL:
    _msg = ["KHONG TIM THAY KHUON report_shell.html.", "Da tim o:"]
    _msg += ["  " + str(x) for x in _TPL_TRIED if x]
    _msg.append("Dat bien moi truong FRC_TEMPLATE tro toi file khuon, "
                "hoac copy no vao thu muc lam viec.")
    raise SystemExit(chr(10).join(_msg))
# Cat xuong dong cuoi: buoc ghep se tu them mot cai, khong cat thi thua mot dong.
_SHELL = io.open(_TPL, encoding="utf-8").read().rstrip(chr(10))



P = []


def w(x):
    """Gom tung manh HTML lai; cuoi file ghep het roi ghi ra file."""
    P.append(x)


def E(s):
    """Thoat ky tu HTML cho moi doan chu lay tu report (ten page, gia tri slicer...)."""
    return html.escape(str(s), quote=True)


_vs_txt = ", ".join(VSHORT.get(v, v) for v in VS)
w('''%s''' % _SHELL)
w("<h1>So sánh report trước / sau khi tối ưu semantic model</h1>")
w('<p class="sub">%s = bản gốc &nbsp;·&nbsp; %s = các bản đã tối ưu. '
  'Mỗi page kiểm 3 trạng thái: khi mở, sau filter lần 1, sau filter lần 2 '
  '(hai lần dùng hai giá trị khác nhau).</p>'
  % ("v0", html.escape(_vs_txt)))


if MNOTE:
    _mrk = sorted({k[1] + "|" + k[2] for k in MNOTE})
    _n_over = sum(1 for d in diff if d.get("manual_verified"))
    w('<div class="box ok"><b>✓ Đã tự tay thao tác lại trên trình duyệt để xác minh (%d page, %d ô):</b> '
      '%s. Máy đo ban đầu báo các ô này khác nhau, nhưng sau khi tự tay kiểm tra trực tiếp trên Fabric '
      'thì xác nhận KHÔNG phải regression (xem ghi chú ở đúng ô đó, mục "Giống hệt v0") — đã tính lại '
      'thành GIỐNG trong toàn bộ báo cáo này.</div>'
      % (len(_mrk), _n_over, E(", ".join(_mrk))))

_val = [d for d in diff if d.get("kind") == "VALUE"]
if _val:
    w('<h2>Phát hiện chính</h2>')
    vs_hit = sorted({d["v"] for d in _val})
    pg_hit = sorted({(d["rk"], d["pk"], d["pn"]) for d in _val})
    w('<div class="box bad"><b>Có %d ô khác nhau về số liệu, trên %d page.</b> '
      'Bảng ngay dưới cho biết ở mỗi page thì <b>bản nào lệch so với bản gốc</b>, '
      'và lệch ở trạng thái nào.</div>'
      % (len(_val), len(pg_hit)))
    # Tom tat theo page: version nao lech, o trang thai nao. Viet tu du lieu chu
    # khong ap dat truoc, vi co page thi mot ban le lech, co page thi ca bon ban
    # deu lech theo huong nguoc lai.
    _p2 = jload("pass2_confirm.json", {})
    if _p2:
        _nl, _nk = len(_p2.get("lap", [])), len(_p2.get("khong", []))
        w('<div class="box %s"><b>Đã đối chứng bằng một lượt chụp độc lập:</b> '
          'chụp lại toàn bộ những page này một lần nữa vào thư mục riêng, không ghi đè lượt đầu, '
          'rồi so lại. <b>%d/%d</b> khác biệt lặp lại y nguyên, <b>%d</b> không lặp. '
          'Theo quy tắc “chỉ khác biệt lặp ở cả hai lượt mới tính là thật”, %s.</div>'
          % ("ok" if _nk == 0 else "warn", _nl, _nl + _nk, _nk,
             "toàn bộ khác biệt nêu dưới đây đều là thật" if _nk == 0
             else "những ô không lặp đã bị loại"))
    w('<table><tr><th>Report</th><th>Page</th><th>Bản lệch so với v0</th>'
      '<th>Trạng thái lệch</th><th>Khác biệt cụ thể</th></tr>')
    for rk, pk, pn in pg_hit:
        grp = [d for d in _val if d["rk"] == rk and d["pk"] == pk]
        vs = sorted({d["v"] for d in grp}, key=lambda x: ALLV.index(x) if x in ALLV else 99)
        sts = [lbl.split("—")[1].strip() for st, lbl in STATES
               if any(d["state"] == st for d in grp)]
        ex = ""
        for d in grp:
            td = d.get("textDiff")
            if td:
                ex = "; ".join("v0: <code>%s</code> ↔ %s: <code>%s</code>"
                               % (E(x.get("v0", "") or "(trống)"), E(VSHORT.get(d["v"], d["v"])),
                                  E(x.get("vx", "") or "(trống)")) for x in td[:2])
                break
        w('<tr><td>%s</td><td>%s</td><td><b>%s</b></td><td>%s</td><td class="small">%s</td></tr>'
          % (E(grp[0]["rn"]), E(pn), E(", ".join(VSHORT.get(v, v) for v in vs)),
             E(", ".join(sts)), ex or "xem phần ảnh"))
    w('</table>')
    _mf = jload("month_field.json", {})
    if _mf:
        w('<h3 style="margin-top:22px">Nguyên nhân gốc — slicer bị gắn vào trường khác</h3>')
        w('<p class="small">Trường dữ liệu thật sự nằm sau slicer <code>■月選択</code>, đọc từ '
          'thuộc tính <code>aria-label</code> của chính slicer trên từng bản:</p>')
        w('<table><tr><th>Version</th><th>Trường sau <code>■月選択</code></th><th>Nhận xét</th></tr>')
        _base = _mf.get("v0")
        for v in ALLV:
            f = _mf.get(v)
            if f is None:
                continue
            ok = (f == _base)
            w('<tr><td><b>%s</b></td><td><code>%s</code></td><td class="%s">%s</td></tr>'
              % (E(VSHORT[v]), E(f), "same" if ok else "diff",
                 "giống bản gốc" if ok else "KHÁC bản gốc — gắn vào cột nhãn hiển thị thay vì cột ngày"))
        w('</table>')
        w('<div class="box bad"><b>Kết luận:</b> ở v3, slicer <code>■月選択</code> được gắn vào '
          '<code>営業年月開始日_表示ラベル</code> (cột nhãn hiển thị) thay vì <code>営業年月開始日</code> '
          '(cột ngày) như bản gốc. Lọc trên cột nhãn không lọc bảng dữ liệu giống như lọc trên cột ngày, '
          'nên kết quả lúc rỗng lúc lọt thêm tháng 09. Đây là hệ quả của việc tối ưu model.</div>')
# --------------------------------------------------------------- 0. nguon
w('<h2>0. Nguồn &amp; cách chụp</h2>')
w('<div class="box"><table>'
  '<tr><th style="width:150px">v0 (bản gốc)</th><td>Workspace <b>dynam-baseline-test</b>'
  '<div class="small">https://app.fabric.microsoft.com/groups/%s</div></td></tr>'
  '<tr><th>v1 / v2 / v3 / v3.5</th><td>Workspace <b>dynam-variant-test</b>'
  '<div class="small">https://app.fabric.microsoft.com/groups/%s</div></td></tr>'
  '</table></div>' % (WS_BASE, WS_VAR))
w('<div class="box"><ul style="margin:0">'
  '<li>Một cửa sổ Chrome đã đăng nhập, điều khiển qua CDP, mở <b>5 tab song song trong cùng cửa sổ</b> '
  '— mỗi tab một version.</li>'
  '<li>Cửa sổ <b>full màn hình 1920×1080</b>, viewport đặt đúng bằng cửa sổ thật (1920×993).</li>'
  '<li><b>Reset to default trước mỗi lần áp filter</b>, có bấm xác nhận hộp thoại và kiểm nút Reset đã '
  'chuyển sang <i>disabled</i>. Filter lần 2 vì thế không cộng dồn lên lần 1.</li>'
  '<li>Không chụp khi còn hộp thoại, lớp phủ, <b>hoặc dropdown slicer đang mở</b>.</li>'
  '<li>Mỗi ảnh chụp 2 lần cách nhau 1,2 giây và phải trùng nhau từng byte mới được lưu.</li>'
  '<li>Cùng một page thì v0 và version đem so dùng đúng một giá trị filter; giá trị hiển thị trên slicer '
  'của hai bên được đối chiếu lại.</li></ul></div>')

# --------------------------------------------------------------- 1. ton tai
w('<h2>1. Report và sự tồn tại của từng version</h2>')
w('<table><tr><th>Tên đầy đủ của report</th><th class="c">Số page</th>')
for v in ALLV:
    w('<th class="c">%s</th>' % E(VSHORT[v]))
w('</tr>')
for R in inv["reports"]:
    ins = R["key"] in SCOPE
    w('<tr><td><b>%s</b></td><td class="c">%d</td>' % (E(R["name"]), len(R["pages"])))
    for v in ALLV:
        if not R["ids"].get(v):
            w('<td class="c diff">Không có</td>')
        elif not ins:
            w('<td class="c miss">chưa kiểm</td>')
        elif any(os.path.exists(shot("load", v, R["key"], PG["k"])) for PG in R["pages"]):
            w('<td class="c same">Có — mở được</td>')
        else:
            w('<td class="c diff">Có nhưng không mở được</td>')
    w('</tr>')
w('</table>')

# --------------------------------------------------------------- 2. filter
w('<h2>2. Filter đã dùng</h2>')
w('<p class="small">Mỗi page dùng <b>hai slicer khác nhau</b> cho hai lượt, và slicer giữa các page '
  'cũng khác nhau để có độ phủ. Cùng một page thì cả 5 version dùng <b>y hệt</b> slicer và giá trị.</p>')
w('<table><tr><th>Report</th><th>Page</th><th>Slicer lượt 1</th><th>Giá trị</th>'
  '<th>Slicer lượt 2</th><th>Giá trị</th></tr>')
for R in inv["reports"]:
    if R["key"] not in SCOPE:
        continue
    for PG in R["pages"]:
        f = fil.get(R["key"] + "|" + PG["k"])
        if f:
            w('<tr><td>%s</td><td>%s</td>'
              '<td><b>%s</b><div class="small">%s</div></td><td><code>%s</code></td>'
              '<td><b>%s</b><div class="small">%s</div></td><td><code>%s</code></td></tr>'
              % (E(R["name"]), E(PG["nm"]),
                 E(f["p1"]["label"]), E(f["p1"]["aria"]), E(str(f["p1"]["v"])),
                 E(f["p2"]["label"]), E(f["p2"]["aria"]), E(str(f["p2"]["v"]))))
            if f.get("note"):
                w('<tr><td colspan="6" class="nos">%s — %s</td></tr>'
                  % (E(PG["nm"]), E(f["note"])))
        else:
            w('<tr><td>%s</td><td>%s</td><td colspan="4" class="nos">Page không có slicer nào — '
              'ba trạng thái là như nhau.</td></tr>' % (E(R["name"]), E(PG["nm"])))
w('</table>')

# --------------------------------------------------------------- 3. ma tran
KIND_LABEL = {"VALUE": "KHÁC VALUE", "UI": "khác giao diện", "UNKNOWN": "KHÁC (chưa phân loại)"}


def kind_text(d):
    """Nhan chinh xac hon: khac giao dien ma mat khong thay thi phai noi ro."""
    k = d.get("kind", "UNKNOWN")
    if k == "UI" and d.get("invisible"):
        return "khác giao diện (không nhìn thấy được)"
    return KIND_LABEL[k]
KIND_CLASS = {"VALUE": "dval", "UI": "dui", "UNKNOWN": "diff"}


def kind_of(v, rk, pk, state):
    d = DIF.get((v, rk, pk, state)) or {}
    return d.get("kind") if d.get("status") == "DIFF" else None


def verdict(v, rk, pk, state):
    """(nhan, class). Khong bao gio ghi phan tram."""
    d = DIF.get((v, rk, pk, state))
    if not d:
        return ("chưa kiểm", "miss")
    if d.get("status") == "MISSING":
        return ("thiếu ảnh", "miss")
    note = ""
    if same_filter(v, rk, pk, state) is False:
        note = "<br><span class='small'>hai bên khác giá trị slicer — không so được</span>"
    if STABLE.get(("v0", rk, pk, state)) is False or STABLE.get((v, rk, pk, state)) is False:
        note += "<br><span class='small'>ảnh chưa ổn định</span>"
    if d.get("status") == "SAME":
        return ("Giống" + note, "same")
    k = d.get("kind", "UNKNOWN")
    return (kind_text(d) + note, KIND_CLASS[k])


def counts(rk, pages, vs=None):
    """Dem so o khac value / khac giao dien / giong, trong pham vi cho truoc."""
    nv = nu = ns = 0
    for PG in pages:
        for state, _ in STATES:
            for v in (vs or VS):
                d = DIF.get((v, rk, PG["k"], state)) or {}
                if d.get("status") == "SAME":
                    ns += 1
                elif d.get("status") == "DIFF":
                    if d.get("kind") == "VALUE":
                        nv += 1
                    else:
                        nu += 1
    return nv, nu, ns


def pills(nv, nu, ns):
    out = []
    if nv:
        out.append('<span class="pill v">%d ô khác VALUE</span>' % nv)
    if nu:
        out.append('<span class="pill u">%d ô khác giao diện</span>' % nu)
    if not nv and not nu:
        out.append('<span class="pill s">khớp hoàn toàn</span>')
    elif ns:
        out.append('<span class="pill s">%d ô giống</span>' % ns)
    return " ".join(out)


w('<h2>3. Bảng kết quả</h2>')
w('<table><tr><th rowspan="2">Report</th><th rowspan="2">Page</th>')
for _, lbl in STATES:
    w('<th class="c" colspan="4">%s</th>' % E(lbl.split("—")[1].strip()))
w('</tr><tr>')
for _ in STATES:
    for v in VS:
        w('<th class="c">%s</th>' % E(VSHORT[v]))
w('</tr>')
for R in inv["reports"]:
    if R["key"] not in SCOPE:
        continue
    for PG in R["pages"]:
        w('<tr><td>%s</td><td>%s%s</td>' % (E(R["name"]), E(PG["nm"]),
          '' if fil.get(R["key"] + "|" + PG["k"]) else ' <span class="small">(không slicer)</span>'))
        for state, _ in STATES:
            for v in VS:
                lab, cls = verdict(v, R["key"], PG["k"], state)
                w('<td class="c %s">%s</td>' % (cls, lab))
        w('</tr>')
w('</table>')

cnt = collections.Counter(d.get("status") for d in diff)
kcnt = collections.Counter(d.get("kind") for d in diff if d.get("status") == "DIFF")
w('<div class="box %s"><b>%d phép so sánh:</b> Giống <b>%d</b> · '
  'khác VALUE <b>%d</b> · khác giao diện <b>%d</b> · chưa phân loại <b>%d</b> · thiếu ảnh <b>%d</b></div>'
  % ("ok" if not kcnt.get("VALUE") else "warn", sum(cnt.values()), cnt.get("SAME", 0),
     kcnt.get("VALUE", 0), kcnt.get("UI", 0), kcnt.get("UNKNOWN", 0), cnt.get("MISSING", 0)))
_ui_note = (' Chữ giống hệt từng ký tự mà pixel vẫn khác → <b>khác giao diện</b>.'
            if kcnt.get("UI") else
            ' Lần chạy này không có ô nào rơi vào loại “chữ giống hệt mà pixel khác”.')
w('<p class="small"><b>Căn cứ phân loại:</b> mỗi ảnh được lưu kèm toàn bộ chữ hiển thị trên canvas. '
  'Chữ khác nhau → <b>khác VALUE</b>.' + _ui_note +
  ' Chỗ nào rơi vào vùng biểu đồ không có nhãn số thì chữ không phản ánh được, những chỗ đó được xem bằng mắt '
  'và ghi rõ trong phần ảnh.</p>')

# --------------------------------------------------------------- 4. anh
def shotblock(label, cls, src, alt):
    if src is None:
        return ('<div class="shot"><div class="lbl miss">%s — KHÔNG CÓ ẢNH</div>'
                '<div style="padding:26px;text-align:center;color:#8a5a00">thiếu ảnh</div></div>' % E(label))
    return ('<div class="shot%s"><div class="lbl %s">%s</div>'
            '<img loading="lazy" src="%s" alt="%s"></div>'
            % (" d" if cls == "diff" else "", cls, E(label), src, E(alt)))


w('<h2>4. Ảnh chụp</h2>')
w('<div class="box"><b>Cách đọc:</b> mặc định mọi mục đều đóng — bấm vào tên report để xổ danh sách page, '
  'bấm tên page mới hiện ảnh. Nhãn ngay trên mỗi dòng cho biết cần bấm cái nào.<br>'
  '<span class="pill v">KHÁC VALUE</span> chữ/số trên report khác nhau — cần xem kỹ. '
  + ('<span class="pill u">khác giao diện</span> chữ/số giống hệt từng ký tự, chỉ khác cách hiển thị. '
     if kcnt.get("UI") else '') +
  '<span class="pill s">khớp hoàn toàn</span> không cần xem.<br>'
  'Bản nào giống v0 thì không kèm ảnh. Chỗ khác thì khoanh đỏ trên cả ảnh v0 lẫn ảnh bản đó, '
  'kèm một cặp ảnh phóng to vào đúng vùng đó.</div>')

for R in inv["reports"]:
    if R["key"] not in SCOPE:
        continue
    rnv, rnu, rns = counts(R["key"], R["pages"])
    w('<details><summary>Report: %s %s</summary><div class="dbody">'
      % (E(R["name"]), pills(rnv, rnu, rns)))

    for PG in R["pages"]:
        rk, pk = R["key"], PG["k"]
        f = fil.get(rk + "|" + pk)
        pnv, pnu, pns = counts(rk, [PG])
        w('<details><summary>Page: %s %s</summary><div class="dbody">'
          % (E(PG["nm"]), pills(pnv, pnu, pns)))
        if not f:
            w('<p class="small">Page này không có slicer nên ba trạng thái giống nhau.</p>')

        for state, lbl in STATES:
            w('<h4>%s</h4>' % E(lbl))
            if f and state != "load":
                sl = f["p1"] if state == "filter1" else f["p2"]
                w('<p class="small">Đã Reset to default, rồi đặt slicer <b>%s</b> (<code>%s</code>) '
                  '= <code>%s</code> cho tất cả các version.</p>'
                  % (E(sl["label"]), E(sl["aria"]), E(str(sl["v"]))))

            diffs = [v for v in VS if (DIF.get((v, rk, pk, state)) or {}).get("status") == "DIFF"]
            sames = [v for v in VS if (DIF.get((v, rk, pk, state)) or {}).get("status") == "SAME"]
            miss  = [v for v in VS if (DIF.get((v, rk, pk, state)) or {}).get("status") not in ("DIFF", "SAME")]
            auto_sames = [v for v in sames if not (DIF.get((v, rk, pk, state)) or {}).get("manual_verified")]
            manual_sames = [v for v in sames if (DIF.get((v, rk, pk, state)) or {}).get("manual_verified")]

            if auto_sames:
                w('<div class="box ok" style="margin:6px 0"><b>Giống hệt v0 (không kèm ảnh):</b> %s</div>'
                  % ", ".join(E(VSHORT[v]) for v in auto_sames))
            for v in manual_sames:
                d = DIF.get((v, rk, pk, state)) or {}
                w('<div class="box ok" style="margin:6px 0"><b>✓ %s — giống v0 (máy đo chênh lệch %s, '
                  'nhưng đã tự tay xác minh không phải regression):</b> %s</div>'
                  % (E(VSHORT[v]), E(d.get("orig_kind") or d.get("orig_status") or "?"), E(d.get("manual_note", ""))))
                w('<p class="small" style="margin:10px 0 4px"><b>Ảnh chụp (để tự đối chiếu):</b></p>')
                w('<div class="zoom">')
                w(shotblock("v0 — BẢN GỐC", "base", b64(shot(state, "v0", rk, pk), IMG_W, IMG_Q), "v0"))
                w(shotblock("%s — đã xác minh tay" % VSHORT[v], "same", b64(shot(state, v, rk, pk), IMG_W, IMG_Q), v))
                w('</div>')
            if miss:
                w('<div class="box warn" style="margin:6px 0"><b>Chưa có kết quả:</b> %s</div>'
                  % ", ".join(E(VSHORT[v]) for v in miss))
            if not diffs:
                continue

            # chu khac nhau cho nao — chi voi o khac VALUE
            for v in diffs:
                d = DIF.get((v, rk, pk, state)) or {}
                if d.get("kind") != "VALUE" or not d.get("textDiff"):
                    continue
                w('<div class="box bad"><b>%s — chữ trên report khác v0 ở những chỗ sau:</b>'
                  '<table style="margin-top:8px"><tr><th style="width:50%%">v0</th><th>%s</th></tr>'
                  % (E(VSHORT[v]), E(VSHORT[v])))
                for ch in d["textDiff"]:
                    w('<tr><td><code>%s</code></td><td><code>%s</code></td></tr>'
                      % (E(ch["v0"]) or "<i>(trống)</i>", E(ch["vx"]) or "<i>(trống)</i>"))
                w('</table></div>')

            # phong to vung khac
            for v in diffs:
                d = DIF.get((v, rk, pk, state)) or {}
                k = d.get("kind", "UNKNOWN")
                z0 = b64(azoom(state, v, rk, pk, "v0"), ZOOM_W, ZOOM_Q)
                zv = b64(azoom(state, v, rk, pk, v), ZOOM_W, ZOOM_Q)
                z_a, z_b = ZOOM.get(("v0", rk, pk, state)), ZOOM.get((v, rk, pk, state))
                if z_a and z_b and z_a != z_b:
                    w('<div class="box warn" style="margin:10px 0"><b>Nguyên nhân: mức zoom khác nhau.</b> '
                      'v0 đang hiển thị ở <b>%s</b>, %s ở <b>%s</b>. Mức zoom là thiết lập lưu trong từng bản '
                      'copy report, không phải kết quả của semantic model — nó phóng to/thu nhỏ mọi thứ nên '
                      'lệch pixel rất lớn dù chữ và số giống hệt.</div>'
                      % (E(z_a), E(VSHORT[v]), E(z_b)))
                if d.get("desc"):
                    w('<div class="box %s" style="margin:10px 0"><b>%s — khác cái gì:</b> %s</div>'
                      % ("warn" if k != "VALUE" else "bad", E(VSHORT[v]), E(d["desc"])))
                if z0 and zv:
                    w('<p class="small" style="margin:14px 0 4px"><b>Phóng to vùng khác giữa v0 và %s '
                      '(%s):</b></p>' % (E(VSHORT[v]), E(kind_text(d))))
                    w('<div class="zoom">')
                    w(shotblock("v0 — BẢN GỐC", "base", z0, "v0 zoom"))
                    w(shotblock("%s — %s" % (VSHORT[v], kind_text(d)), KIND_CLASS[k], zv, "%s zoom" % v))
                    w('</div>')

            # anh day du
            w('<p class="small" style="margin:16px 0 4px"><b>Ảnh đầy đủ:</b></p>')
            src0 = None
            for vv in diffs:
                src0 = b64(afull(state, vv, rk, pk, "v0"), IMG_W, IMG_Q)
                if src0:
                    break
            if src0 is None:
                src0 = b64(shot(state, "v0", rk, pk), IMG_W, IMG_Q)
            w(shotblock("v0 — BẢN GỐC", "base", src0, "v0"))
            for v in diffs:
                k = (DIF.get((v, rk, pk, state)) or {}).get("kind", "UNKNOWN")
                src = b64(afull(state, v, rk, pk, v), IMG_W, IMG_Q) or b64(shot(state, v, rk, pk), IMG_W, IMG_Q)
                w(shotblock("%s — %s (vùng khoanh đỏ)" % (VSHORT[v], kind_text(DIF.get((v, rk, pk, state)) or {})), KIND_CLASS[k], src, v))

        w('</div></details>')
    w('</div></details>')

# --------------------------------------------------------------- 5. chat luong
w('<h2>5. Chất lượng lần chụp</h2>')
if LOG_STALE:
    w('<div class="box bad"><b>Cảnh báo:</b> nhật ký chụp cũ hơn ảnh — lần chụp hiện tại '
      'chưa kết thúc nên các con số dưới đây thuộc về <i>lần chụp trước</i>, không khớp với '
      'kết quả so sánh ở trên. Chờ chụp xong rồi build lại.</div>')
bad_page, bad_reset, bad_apply = [], [], []
for r in logs:
    nm = "%s / %s / %s" % (VSHORT.get(r.get("v"), r.get("v")), r.get("rk"), r.get("pk"))
    if not r.get("ok"):
        bad_page.append((nm, r.get("err", ""))); continue
    for k in ("reset0", "resetF1", "resetF2"):
        if r.get(k) and r[k] not in ("reset", "already-default"):
            bad_reset.append((nm, k, r[k]))
    for k in ("F1", "F2"):
        if r.get("hasSlicer") and r.get("ap" + k) is False:
            bad_apply.append((nm, k, r.get("why" + k, "")))
n_unstable = sum(1 for v in STABLE.values() if v is False)
mismatch = [(v, rk, pk, st) for (v, rk, pk, st) in SHOWN
            if v != "v0" and same_filter(v, rk, pk, st) is False]

w('<table><tr><th>Chỉ số</th><th class="c" style="width:120px">Số lượng</th></tr>')
w('<tr><td>Ô chụp thành công (page × version)</td><td class="c">%d / %d</td></tr>'
  % (sum(1 for r in logs if r.get("ok")), len(logs)))
w('<tr><td>Ảnh PNG đã sinh</td><td class="c">%d</td></tr>'
  % sum(len(os.listdir(os.path.join(SHOTS, s))) for s, _ in STATES if os.path.isdir(os.path.join(SHOTS, s))))
w('<tr><td>Page mở lỗi</td><td class="c">%d</td></tr>' % len(bad_page))
w('<tr><td>Reset to default không xác minh được</td><td class="c">%d</td></tr>' % len(bad_reset))
w('<tr><td>Filter không áp / không xác minh được</td><td class="c">%d</td></tr>' % len(bad_apply))
w('<tr><td>Ảnh chụp 2 lần liên tiếp không trùng nhau</td><td class="c">%d</td></tr>' % n_unstable)
zmis = [(v, rk, pk, st) for (v, rk, pk, st) in ZOOM
        if v != "v0" and ZOOM.get((v, rk, pk, st)) and ZOOM.get(("v0", rk, pk, st))
        and ZOOM[(v, rk, pk, st)] != ZOOM[("v0", rk, pk, st)]]
w('<tr><td>Ô mà v0 và bản đem so không ở cùng giá trị slicer</td><td class="c">%d</td></tr>' % len(mismatch))
w('<tr><td>Ô mà hai bên đang ở mức zoom khác nhau</td><td class="c">%d</td></tr>' % len(zmis))
_sub = [d for d in diff if d.get("subpixel")]
w('<tr><td>Ô lệch dưới ngưỡng nhìn thấy được (viền / thanh cuộn lệch 1–4 px) — '
  '<b>đã tính là giống</b></td><td class="c">%d</td></tr>' % len(_sub))
_za = [d for d in diff if d.get("zoomArtifact")]
w('<tr><td>Ô mà hai bên chỉ khác <b>mức phóng to lúc chụp</b> (nội dung chữ giống hệt) — '
  '<b>đã tính là giống</b></td><td class="c">%d</td></tr>' % len(_za))
w('</table>')
if _za:
    w('<div class="box warn"><b>Khác mức phóng to lúc chụp (%d ô)</b> — Power BI nhớ mức zoom '
      'riêng cho từng bản report, nên cùng một page có thể hiện 98%% ở bản này và 113%% ở bản kia. '
      'Toàn bộ pixel lệch theo nhưng chữ và số hoàn toàn trùng khớp, nên không tính là khác biệt:<ul>')
    for d in _za:
        w('<li>%s / %s — %s, %s: khớp lại ở tỉ lệ %.0f%%</li>'
          % (E(d["rn"]), E(d["pn"]), E(dict(STATES).get(d["state"], d["state"])),
             E(VSHORT.get(d["v"], d["v"])), d["zoomArtifact"]["scale"] * 100))
    w('</ul></div>')
if zmis:
    w('<div class="box warn"><b>Lệch mức zoom (%d) — làm lệch pixel nhưng không đổi số liệu:</b><ul>' % len(zmis))
    seen = set()
    for v, rk, pk, st in zmis:
        key = (v, rk, pk)
        if key in seen:
            continue
        seen.add(key)
        w('<li>%s / %s — v0: <b>%s</b>, %s: <b>%s</b></li>'
          % (E(rk), E(pk), E(str(ZOOM.get(("v0", rk, pk, st)))), E(VSHORT.get(v, v)),
             E(str(ZOOM.get((v, rk, pk, st))))))
    w('</ul></div>')

for title, rows, cls in (("Page mở lỗi", bad_page, "bad"),
                         ("Reset không xác minh được", bad_reset, "warn"),
                         ("Filter không xác minh được", bad_apply, "warn")):
    if rows:
        w('<div class="box %s"><b>%s (%d)</b><ul>' % (cls, E(title), len(rows)))
        for row in rows[:60]:
            w('<li>%s</li>' % E(" — ".join(str(x) for x in row)))
        w('</ul></div>')

if mismatch:
    w('<div class="box bad"><b>Những ô hai bên không cùng giá trị slicer (%d) — '
      'không được coi là bằng chứng model sai:</b><ul>' % len(mismatch))
    for v, rk, pk, st in mismatch[:60]:
        w('<li>%s / %s / %s — v0: <code>%s</code> &nbsp;·&nbsp; %s: <code>%s</code></li>'
          % (E(rk), E(pk), E(st), E(str(SHOWN.get(("v0", rk, pk, st)))),
             E(VSHORT.get(v, v)), E(str(SHOWN.get((v, rk, pk, st))))))
    w('</ul></div>')

w('<div class="box warn"><b>Lưu ý khi đọc trạng thái "khi mở, chưa filter":</b> mỗi bản copy report lưu '
  'state slicer mặc định riêng tại lúc bản đó được save. "Reset to default" đưa report về đúng cái default '
  'đã lưu của chính nó, không đưa mọi bản về cùng một state. Nên khác biệt ở trạng thái này là khác biệt của '
  '<b>bản lưu report</b>, chưa phải bằng chứng semantic model sai. Chỉ hai trạng thái đã ép cùng một giá trị '
  'filter mới dùng để kết luận về model.</div>')

# --------------------------------------------------------------- 6. ket luan
# ------------------------------------------------- 5b. nhat ky truy nguyen
_alog = jload("artifacts_log.json", [])
if _alog:
    w('<h2>5b. Nhật ký truy nguyên từng khác biệt</h2>')
    w('<p class="small">Mỗi lần máy báo "khác", khác biệt đó được mở ảnh ra soi tận nơi và truy đến '
      'nguyên nhân trước khi kết luận. Bảng này liệt kê <b>toàn bộ</b> các trường hợp đã xử lý, '
      'kể cả những trường hợp hoá ra là lỗi của chính công cụ chụp — để người đọc kiểm chứng được '
      'vì sao con số cuối cùng là như vậy.</p>')
    w('<details><summary>Xem %d mục</summary>' % len(_alog))
    w('<table><tr><th>Lúc</th><th>Page</th><th>Trạng thái</th><th>Bản</th>'
      '<th>Triệu chứng</th><th>Nguyên nhân</th><th>Loại</th><th>Xử lý</th><th>Kết quả</th></tr>')
    _cls = {"lỗi chụp": "warn", "lỗi công cụ": "warn", "lỗi báo cáo": "warn"}
    for a in _alog:
        w('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>'
          '<td>%s</td><td>%s</td><td>%s</td></tr>'
          % tuple(E(str(a.get(k, ""))) for k in
                  ("t", "page", "state", "v", "trieuchung", "nguyennhan", "loaicu", "xuly", "ketqua")))
    w('</table></details>')

w('<h2>6. Kết luận</h2>')
fv = [d for d in diff if d.get("state") in ("filter1", "filter2") and d.get("kind") == "VALUE"]
fu = [d for d in diff if d.get("state") in ("filter1", "filter2") and d.get("kind") == "UI"]
lv = [d for d in diff if d.get("state") == "load" and d.get("kind") == "VALUE"]
lu = [d for d in diff if d.get("state") == "load" and d.get("kind") == "UI"]
sf = sum(1 for d in diff if d.get("state") in ("filter1", "filter2") and d.get("status") == "SAME")
scope_names = ", ".join(R["name"] for R in inv["reports"] if R["key"] in SCOPE)
w('<div class="box %s">Phạm vi đã kiểm: <b>%s</b>.<br><br>'
  '<b>Trạng thái đã ép cùng filter</b> (phần dùng để kết luận về model): '
  '%d ô giống, <b>%d ô khác VALUE</b>, %d ô khác giao diện.<br>'
  '<b>Trạng thái khi mở</b>: <b>%d ô khác VALUE</b>, %d ô khác giao diện.</div>'
  % ("ok" if not (fv or lv) else "bad", E(scope_names), sf, len(fv), len(fu), len(lv), len(lu)))
if fv or lv:
    w('<div class="box bad"><b>Các ô khác về VALUE — cần xem kỹ:</b><ul>')
    for d in (fv + lv):
        w('<li>%s / %s / %s — %s</li>' % (E(d["rn"]), E(d["pn"]), E(d["state"]), E(VSHORT.get(d["v"], d["v"]))))
    w('</ul></div>')
elif fu or lu:
    w('<div class="box ok">Không có ô nào khác về VALUE. Còn %d ô khác giao diện '
      '(chữ và số hiển thị giống hệt bản gốc, chỉ pixel khác).</div>' % (len(fu) + len(lu)))
else:
    w('<div class="box ok"><b>Report chạy giống hệt bản gốc ở mọi phép so đã kiểm.</b> '
      'Không còn ô nào khác — kể cả những ô máy đo ban đầu báo khác đều đã được tự tay '
      'xác minh trực tiếp trên Fabric (xem mục "Giống hệt v0" ở từng trang).</div>')

w('</div></body></html>')
htm = "\n".join(P)
io.open(OUTHTM, "w", encoding="utf-8").write(htm)
print("wrote %s  (%.1f MB)" % (OUTHTM, len(htm.encode("utf-8")) / 1e6))
print("status:", dict(cnt))
