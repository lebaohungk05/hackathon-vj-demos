import html
import random

FLOWS = {
    "A": {
        "title": "Tra cứu tình trạng hồ sơ",
        "steps": [
            {"heading": "Bước 1: Nhập thông tin tra cứu",
             "fields": [("ma_ho_so", ["Mã hồ sơ", "Số biên nhận hồ sơ"]), ("cccd", ["Số CCCD", "Số căn cước công dân"])],
             "button": "Tra cứu"},
            {"heading": "Bước 2: Kết quả tra cứu", "fields": [], "table": True, "button": "Kết thúc"},
        ],
    },
    "B": {
        "title": "Đăng ký cấp Phiếu lý lịch tư pháp",
        "steps": [
            {"heading": "Bước 1: Thông tin người yêu cầu",
             "fields": [("ho_ten", ["Họ và tên", "Họ tên đầy đủ"]), ("ngay_sinh", ["Ngày sinh", "Ngày, tháng, năm sinh"]),
                        ("cccd", ["Số CCCD", "Số định danh cá nhân"])],
             "button": "Tiếp tục"},
            {"heading": "Bước 2: Thông tin liên hệ",
             "fields": [("dien_thoai", ["Số điện thoại", "Điện thoại liên hệ"]), ("email", ["Email", "Thư điện tử"]),
                        ("dia_chi", ["Địa chỉ cư trú", "Nơi cư trú hiện tại"])],
             "button": "Tiếp tục"},
            {"heading": "Bước 3: Mục đích yêu cầu",
             "fields": [("muc_dich", ["Mục đích sử dụng phiếu", "Mục đích yêu cầu"]), ("so_ban", ["Số lượng bản", "Số bản cần cấp"])],
             "button": "Tiếp tục"},
            {"heading": "Bước 4: Xác nhận trước khi nộp",
             "fields": [("cam_doan", ["Tôi cam đoan thông tin trên là đúng sự thật"])], "table": True,
             "button": "Nộp hồ sơ"},
        ],
    },
    "C": {
        "title": "Đặt lịch hẹn nộp hồ sơ trực tiếp",
        "steps": [
            {"heading": "Bước 1: Chọn nơi và thời gian",
             "fields": [("co_quan", ["Cơ quan tiếp nhận", "Nơi tiếp nhận hồ sơ"]), ("ngay_hen", ["Ngày hẹn", "Ngày muốn đến"]),
                        ("khung_gio", ["Khung giờ", "Giờ hẹn"])],
             "button": "Tiếp tục"},
            {"heading": "Bước 2: Thông tin người đặt lịch",
             "fields": [("ho_ten", ["Họ và tên", "Họ tên người đặt"]), ("dien_thoai", ["Số điện thoại", "Điện thoại liên hệ"])],
             "button": "Tiếp tục"},
            {"heading": "Bước 3: Xác nhận lịch hẹn", "fields": [], "table": True, "button": "Đặt lịch"},
        ],
    },
}

CHECKBOX_KEYS = {"cam_doan"}

DEFECTS = {
    "missing_label_req": {"sc": "3.3.2", "blocking": True, "fixable": True, "needs": "req_text"},
    "nondesc_label_req": {"sc": "2.4.6", "blocking": True, "fixable": True, "needs": "req_text"},
    "kbd_trap": {"sc": "2.1.1", "blocking": True, "fixable": True, "needs": "req_text"},
    "div_button": {"sc": "2.1.1", "blocking": True, "fixable": True, "needs": "button"},
    "img_button_noalt": {"sc": "1.1.1", "blocking": True, "fixable": True, "needs": "button"},
    "captcha": {"sc": "1.1.1", "blocking": True, "fixable": False, "needs": "form"},
    "missing_label_opt": {"sc": "3.3.2", "blocking": False, "fixable": True, "needs": "form"},
    "logo_noalt": {"sc": "1.1.1", "blocking": False, "fixable": True, "needs": "any"},
    "fake_heading": {"sc": "1.3.1", "blocking": False, "fixable": True, "needs": "heading"},
    "table_no_th": {"sc": "1.3.1", "blocking": False, "fixable": True, "needs": "table"},
    "mouse_only_extra": {"sc": "2.1.1", "blocking": False, "fixable": True, "needs": "any"},
    "vague_link": {"sc": "2.4.4", "blocking": False, "fixable": True, "needs": "any"},
    "nondesc_heading": {"sc": "2.4.6", "blocking": False, "fixable": True, "needs": "heading"},
}

BLOCKING_RULE = (
    "Lỗi là BLOCKING khi người chỉ dùng bàn phím + trình đọc màn hình không thể hoàn thành bước chứa lỗi: "
    "trường BẮT BUỘC không có tên truy cập được hoặc tên không mô tả; nút tiếp tục không có tên hoặc không thao tác được "
    "bằng bàn phím; bẫy bàn phím; CAPTCHA ảnh không có phương án thay thế. Mọi lỗi còn lại (trường tuỳ chọn, ảnh trang trí, "
    "heading/bảng sai cấu trúc, link mơ hồ, chức năng phụ chỉ dùng chuột) là NON-BLOCKING."
)

IMG_SVG = ("data:image/svg+xml;utf8," + "<svg xmlns='http://www.w3.org/2000/svg' width='120' height='32'>"
           "<rect width='120' height='32' fill='%23b00'/><text x='10' y='21' fill='white'>{}</text></svg>")


def svg(text):
    return IMG_SVG.format(text.replace(" ", "%20"))


def eligible(defect, step):
    need = DEFECTS[defect]["needs"]
    has_req_text = any(k not in CHECKBOX_KEYS for k, _ in step["fields"])
    if need == "req_text":
        return has_req_text
    if need == "form":
        return bool(step["fields"])
    if need == "table":
        return step.get("table", False)
    return True


def sample_defects(flow_key, rng, count):
    steps = FLOWS[flow_key]["steps"]
    chosen, used = [], set()
    attempts = 0
    while len(chosen) < count and attempts < 200:
        attempts += 1
        d = rng.choice(list(DEFECTS))
        s = rng.randrange(len(steps))
        if not eligible(d, steps[s]):
            continue
        slot = (s, DEFECTS[d]["needs"] if DEFECTS[d]["needs"] in ("button", "heading", "table") else d)
        if slot in used:
            continue
        target = None
        if DEFECTS[d]["needs"] == "req_text":
            free = [k for k, _ in steps[s]["fields"] if k not in CHECKBOX_KEYS and (s, "field", k) not in used]
            if not free:
                continue
            target = rng.choice(free)
            used.add((s, "field", target))
        used.add(slot)
        meta = DEFECTS[d]
        chosen.append({"id": f"d{len(chosen)}", "type": d, "step": s + 1, "sc": meta["sc"],
                       "blocking": meta["blocking"], "fixable": meta["fixable"], "target": target,
                       "detect_key": "captcha" if d == "captcha" else meta["sc"]})
    return chosen


def esc(t):
    return html.escape(t, quote=True)


def render_field(key, label, fid, defect):
    attr = f'data-defect="{defect["id"]}"' if defect else ""
    if key in CHECKBOX_KEYS:
        return (f'<div class="f" {attr}><input type="checkbox" id="{fid}" data-req="1">'
                f'<label for="{fid}">{esc(label)}</label></div>')
    kind = defect["type"] if defect else None
    if kind == "missing_label_req":
        return f'<div class="f" {attr}><span>{esc(label)}</span><input id="{fid}" data-req="1"></div>'
    if kind == "nondesc_label_req":
        return (f'<div class="f" {attr}><label for="{fid}">Thông tin {fid[-1]}</label><input id="{fid}" data-req="1">'
                f'<small>{esc(label)}</small></div>')
    if kind == "kbd_trap":
        return (f'<div class="f"><label for="{fid}">{esc(label)}</label><input id="{fid}" data-req="1" {attr} '
                f'onkeydown="if(event.key===\'Tab\'){{event.preventDefault();}}"></div>')
    return f'<div class="f"><label for="{fid}">{esc(label)}</label><input id="{fid}" data-req="1"></div>'


def render(flow_key, seed, defects):
    rng = random.Random(seed)
    flow = FLOWS[flow_key]
    by_step = {}
    for d in defects:
        by_step.setdefault(d["step"], {})[d["type"]] = d
    sections = []
    for i, step in enumerate(flow["steps"], start=1):
        ds = by_step.get(i, {})
        fields = list(step["fields"])
        rng.shuffle(fields)
        parts = []
        if "fake_heading" in ds:
            parts.append(f'<div class="h2" data-defect="{ds["fake_heading"]["id"]}">{esc(step["heading"])}</div>')
        elif "nondesc_heading" in ds:
            parts.append(f'<h2 data-defect="{ds["nondesc_heading"]["id"]}">Thông tin</h2>')
        else:
            parts.append(f'<h2>{esc(step["heading"])}</h2>')
        if "logo_noalt" in ds:
            parts.append(f'<img src="{svg("Cong DVC")}" data-defect="{ds["logo_noalt"]["id"]}">')
        for n, (key, syns) in enumerate(fields, start=1):
            label = rng.choice(syns)
            fdef = next((d for d in ds.values() if d["target"] == key), None)
            parts.append(render_field(key, label, f"s{i}f{n}", fdef))
        if "missing_label_opt" in ds:
            parts.append(f'<div class="f" data-defect="{ds["missing_label_opt"]["id"]}"><span>Ghi chú (không bắt buộc)</span>'
                         f'<input id="s{i}note"></div>')
        if "captcha" in ds:
            code = "".join(rng.choice("0123456789") for _ in range(4))
            parts.append(f'<div class="f" data-defect="{ds["captcha"]["id"]}"><img src="{svg(code)}">'
                         f'<label for="s{i}cap">Nhập mã xác nhận trong ảnh</label><input id="s{i}cap" data-req="1" data-code="{code}"></div>')
        if step.get("table"):
            if "table_no_th" in ds:
                parts.append(f'<table data-defect="{ds["table_no_th"]["id"]}"><tr><td><b>Thông tin</b></td><td><b>Giá trị</b></td></tr>'
                             '<tr><td>Trạng thái</td><td>Đang xử lý</td></tr></table>')
            else:
                parts.append('<table><caption>Tóm tắt hồ sơ</caption><tr><th scope="col">Thông tin</th><th scope="col">Giá trị</th></tr>'
                             '<tr><td>Trạng thái</td><td>Đang xử lý</td></tr></table>')
        if "vague_link" in ds:
            parts.append(f'<p><a href="#huong-dan" data-defect="{ds["vague_link"]["id"]}">Xem thêm</a></p>')
        else:
            parts.append('<p><a href="#huong-dan">Xem hướng dẫn thực hiện thủ tục</a></p>')
        if "mouse_only_extra" in ds:
            parts.append(f'<div class="btn" data-defect="{ds["mouse_only_extra"]["id"]}" onclick="void 0">Chọn trên bản đồ</div>')
        parts.append(f'<div role="alert" id="err{i}"></div>')
        if "div_button" in ds:
            parts.append(f'<div class="btn" data-defect="{ds["div_button"]["id"]}" onclick="next({i})">{esc(step["button"])}</div>')
        elif "img_button_noalt" in ds:
            parts.append(f'<button type="button" data-defect="{ds["img_button_noalt"]["id"]}" onclick="next({i})">'
                         f'<img src="{svg(step["button"])}"></button>')
        else:
            parts.append(f'<button type="button" onclick="next({i})">{esc(step["button"])}</button>')
        hidden = "" if i == 1 else " hidden"
        sections.append(f'<section id="step{i}" data-step="{i}" tabindex="-1"{hidden}>' + "\n".join(parts) + "</section>")
    return PAGE.format(title=esc(flow["title"]), body="\n".join(sections))


PAGE = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><title>{title} - Cổng dịch vụ công (mô phỏng)</title>
<style>body{{font-family:sans-serif;max-width:640px;margin:auto}} .f{{margin:8px 0}} .btn{{display:inline-block;background:#b00;color:#fff;padding:6px 12px;cursor:pointer}} .h2{{font-size:1.4em;font-weight:bold}}</style>
</head><body>
<header><h1>{title}</h1></header>
<main>
{body}
<section id="done" tabindex="-1" hidden><h2>Hoàn tất: hồ sơ đã được ghi nhận thành công</h2></section>
</main>
<script>
function next(k){{
  const s=document.getElementById('step'+k);
  const miss=[...s.querySelectorAll('[data-req]')].filter(e=>e.type==='checkbox'?!e.checked:(e.dataset.code?e.value.trim()!==e.dataset.code:!e.value.trim()));
  if(miss.length){{document.getElementById('err'+k).textContent='Vui lòng điền đầy đủ thông tin bắt buộc ('+miss.length+' trường)';return;}}
  s.hidden=true;
  const n=document.getElementById('step'+(k+1))||document.getElementById('done');
  n.hidden=false; n.focus();
}}
const m=location.hash.match(/audit=(\\d+)/);
if(m){{document.querySelectorAll('section').forEach(s=>s.hidden=(s.id!=='step'+m[1]));}}
</script>
</body></html>"""
