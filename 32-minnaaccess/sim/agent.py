import json
import re

GOAL = {
    "ma_ho_so": "HS-2026-000123", "cccd": "001090012345", "ho_ten": "Nguyễn Văn An", "ngay_sinh": "15/04/1990",
    "dien_thoai": "0912345678", "email": "an.nguyen@example.vn", "dia_chi": "12 Lê Lợi, Hoàn Kiếm, Hà Nội",
    "muc_dich": "Bổ sung hồ sơ xin việc", "so_ban": "1", "co_quan": "Sở Tư pháp Hà Nội", "ngay_hen": "20/10/2026",
    "khung_gio": "08:00 - 09:00", "ghi_chu": "không",
}

KEYWORDS = {
    "ma_ho_so": ["mã hồ sơ", "biên nhận"], "cccd": ["cccd", "căn cước", "định danh"],
    "ho_ten": ["họ và tên", "họ tên"], "ngay_sinh": ["ngày sinh", "năm sinh"],
    "dien_thoai": ["điện thoại"], "email": ["email", "thư điện tử"], "dia_chi": ["cư trú", "địa chỉ"],
    "muc_dich": ["mục đích"], "so_ban": ["số lượng bản", "số bản"], "co_quan": ["cơ quan", "nơi tiếp nhận"],
    "ngay_hen": ["ngày hẹn", "ngày muốn đến"], "khung_gio": ["khung giờ", "giờ hẹn"], "ghi_chu": ["ghi chú"],
    "cam_doan": ["cam đoan"],
}

CONTINUE_NAMES = {"tiếp tục", "tra cứu", "nộp hồ sơ", "đặt lịch", "kết thúc"}
CAPTCHA_WORDS = ["mã xác nhận", "captcha", "mã bảo vệ"]
DONE_RE = re.compile(r"hoàn tất|thành công", re.I)
ERROR_RE = re.compile(r"vui lòng", re.I)
FOCUS_RE = re.compile(r'^- (\w+)(?: "((?:[^"\\]|\\.)*)")?(.*)$')


def match_key(name):
    low = (name or "").lower()
    for key, words in KEYWORDS.items():
        if any(w in low for w in words):
            return key
    return None


def body_snapshot(page):
    return page.locator("body").aria_snapshot()


def focused(page):
    loc = page.locator("*:focus")
    if loc.count() == 0:
        return None, "", ""
    snap = loc.first.aria_snapshot(timeout=2000).splitlines()[0].strip()
    m = FOCUS_RE.match(snap)
    if not m:
        return "other", "", snap
    return m.group(1), (m.group(2) or "").replace('\\"', '"'), m.group(3)


def diagnose_unreached(snapshot, trapped):
    if trapped:
        return ["2.1.1"]
    suspects = []
    if re.search(r"^\s*- button(\s*\[.*\])?:?\s*$", snapshot, re.M) or re.search(r"^\s*- button:?\s*\n\s+- img\s*$", snapshot, re.M):
        suspects.append("1.1.1")
    for line in snapshot.splitlines():
        low = line.lower()
        if "button" not in low and any(n in low for n in CONTINUE_NAMES):
            suspects.append("2.1.1")
            break
    return suspects or ["unknown"]


def attempt_step(page, max_tabs=25):
    unfilled, trapped, prev, stuck = [], False, None, 0
    for _ in range(max_tabs):
        page.keyboard.press("Tab")
        role, name, state = focused(page)
        sig = (role, name)
        stuck = stuck + 1 if sig == prev and role else 0
        prev = sig
        if stuck >= 2:
            trapped = True
            return {"pressed": False, "trapped": True, "unfilled": unfilled, "stuck_on": {"role": role, "name": name}}
        if role == "textbox":
            key = match_key(name)
            if key and key in GOAL:
                page.keyboard.press("Control+A")
                page.keyboard.type(GOAL[key])
            elif {"role": role, "name": name} not in unfilled:
                unfilled.append({"role": role, "name": name})
        elif role == "checkbox":
            key = match_key(name)
            if key and "checked" not in state:
                page.keyboard.press("Space")
            elif not key and {"role": role, "name": name} not in unfilled:
                unfilled.append({"role": role, "name": name})
        elif role == "button" and name.lower() in CONTINUE_NAMES:
            page.keyboard.press("Enter")
            page.wait_for_timeout(30)
            return {"pressed": True, "trapped": False, "unfilled": unfilled}
    return {"pressed": False, "trapped": trapped, "unfilled": unfilled}


def suspects_from_unfilled(unfilled):
    out = []
    for u in unfilled:
        low = u["name"].lower()
        if any(w in low for w in CAPTCHA_WORDS):
            out.append("captcha")
        elif not u["name"]:
            out.append("3.3.2")
        else:
            out.append("2.4.6")
    return out


def run_journey(page, url, patches, max_steps=8):
    page.goto(url)
    for p in patches:
        page.evaluate(p["js"])
    step = 1
    while step <= max_steps:
        before = body_snapshot(page)
        if DONE_RE.search(before):
            return {"completed": True, "steps_passed": step - 1, "breakpoint": None}
        res = attempt_step(page)
        if res["pressed"]:
            after = body_snapshot(page)
            if DONE_RE.search(after):
                return {"completed": True, "steps_passed": step, "breakpoint": None}
            if after != before and not ERROR_RE.search(after):
                step += 1
                continue
            suspects = suspects_from_unfilled(res["unfilled"]) or ["unknown"]
        else:
            suspects = diagnose_unreached(before, res["trapped"])
            suspects += [s for s in suspects_from_unfilled(res["unfilled"]) if s == "captcha"]
        return {"completed": False, "steps_passed": step - 1,
                "breakpoint": {"step": step, "suspects": sorted(set(suspects)), "unfilled": res["unfilled"],
                               "stuck_on": res.get("stuck_on")}}
    return {"completed": False, "steps_passed": step - 1, "breakpoint": {"step": step, "suspects": ["unknown"], "unfilled": []}}


PATCH_JS = {
    "3.3.2": """(k)=>{document.querySelectorAll('#step'+k+' input:not([type=checkbox])').forEach(e=>{
        if(!e.labels.length&&!e.getAttribute('aria-label')){const t=e.previousElementSibling;
        if(t&&t.textContent.trim())e.setAttribute('aria-label',t.textContent.trim());}});}""",
    "2.4.6": """([k,names])=>{document.querySelectorAll('#step'+k+' input').forEach(e=>{
        const lab=e.labels.length?e.labels[0].textContent.trim():'';const h=e.nextElementSibling;
        if(names.includes(lab)&&h&&h.tagName==='SMALL')e.setAttribute('aria-label',lab+' - '+h.textContent.trim());});}""",
    "1.1.1": """(k)=>{document.querySelectorAll('#step'+k+' button').forEach(b=>{
        if(!b.textContent.trim()&&!b.getAttribute('aria-label')&&![...b.querySelectorAll('img')].some(i=>i.alt))
        b.setAttribute('aria-label',(b.getAttribute('onclick')||'').startsWith('next(')?'Tiếp tục':'Nút');});}""",
    "2.1.1": """(k)=>{const s=document.getElementById('step'+k);
        s.querySelectorAll('[onkeydown]').forEach(e=>{e.removeAttribute('onkeydown');e.onkeydown=null;});
        s.querySelectorAll('[onclick]').forEach(e=>{if(['BUTTON','A','INPUT'].includes(e.tagName)||e.hasAttribute('tabindex'))return;
        e.tabIndex=0;e.setAttribute('role','button');
        e.addEventListener('keydown',ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();e.click();}});});}""",
}


def make_patches(breakpoint):
    k = breakpoint["step"]
    out = []
    for sc in breakpoint["suspects"]:
        if sc == "2.4.6":
            names = [u["name"] for u in breakpoint["unfilled"] if u["name"]]
            body = PATCH_JS[sc]
            out.append({"sc": sc, "step": k, "js": "(" + body + ")(" + json.dumps([k, names], ensure_ascii=False) + ")"})
        elif sc in PATCH_JS:
            out.append({"sc": sc, "step": k, "js": "(" + PATCH_JS[sc] + f")({k})"})
    return out


def run_with_repair(page, url, max_rounds=6):
    patches, rounds, handoff = [], [], False
    for _ in range(max_rounds):
        r = run_journey(page, url, patches)
        rounds.append(r)
        bp = r["breakpoint"]
        if r["completed"] or bp is None:
            break
        if "captcha" in bp["suspects"]:
            handoff = True
            break
        new = [p for p in make_patches(bp) if (p["sc"], p["step"]) not in {(q["sc"], q["step"]) for q in patches}]
        if not new:
            break
        patches += new
    return {"rounds": rounds, "patches": [{"sc": p["sc"], "step": p["step"]} for p in patches],
            "handoff": handoff, "completed_after": rounds[-1]["completed"]}
