import os
import re
import shutil
import threading
import time
from pathlib import Path

from procedures import PROCEDURES

ROOT = Path(__file__).resolve().parent
PORTAL = ROOT / "portal"
ORIGINAL = PORTAL / "original"
FIXED = PORTAL / "fixed"
CLEAN = PORTAL / "clean"

KINDS = {
    "unnamed_field": {"label": "Remove a field label", "sc": "3.3.2", "short": "No label",
                      "what": "The visible caption stays, but it is no longer linked to the field, so a screen reader says only “edit box”."},
    "code_label": {"label": "Code instead of a label", "sc": "2.4.6", "short": "Code name",
                   "what": "The field is announced by an internal code (fld_…_01) instead of its caption."},
    "keyboard_trap": {"label": "Keyboard trap", "sc": "2.1.1", "short": "Tab trap",
                      "what": "A formatter script swallows the Tab key, so keyboard users cannot leave the field."},
    "mouse_only": {"label": "Mouse-only button", "sc": "2.1.1", "short": "Mouse only",
                   "what": "The Continue button becomes a clickable <div>: not focusable, Enter and Space do nothing."},
    "captcha": {"label": "Image CAPTCHA", "sc": "1.1.1", "short": "CAPTCHA",
                "what": "An image CAPTCHA with no audio or text alternative is added before the buttons."},
}

CURATED = {
    "vn": {"unnamed_field": ["email", "hoten", "cccd"], "code_label": ["ngaysinh", "sdt", "diachi"],
           "keyboard_trap": ["cccd", "email", "sdt"], "mouse_only": ["next2", "next1", "next3"], "captcha": ["step3", "step2", "step4"]},
    "jp": {"unnamed_field": ["jusho", "shimei", "denwa"], "code_label": ["denwa", "seinengappi", "yubin"],
           "keyboard_trap": ["seinengappi", "shimei", "yubin"], "mouse_only": ["next1", "next2"], "captcha": ["step2", "step1", "step3"]},
}

CAPTCHA_LABEL = {"vn": "Nhập mã xác nhận", "jp": "画像認証の文字を入力"}
LABEL_RE = r'<label for="{id}"(?: class="lbl")?>(.*?)</label>(\s*)<input id="{id}"'


def write_atomic(path, data):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    for _ in range(40):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.05)
    os.replace(tmp, path)


def build_clean():
    shutil.rmtree(CLEAN, ignore_errors=True)
    shutil.copytree(ORIGINAL, CLEAN)
    for key in PROCEDURES:
        for f in (FIXED / key).glob("*.html"):
            shutil.copy(f, CLEAN / key / f.name)
    step4 = CLEAN / "vn" / "step4.html"
    html = step4.read_text(encoding="utf-8")
    html = re.sub(r'<div class="field"><img id="captcha-img"[^>]*></div>\n', "", html)
    html = re.sub(r'<div class="field"><label for="captcha">[^<]*</label><input id="captcha" type="text"></div>\n', "", html)
    step4.write_text(html, encoding="utf-8")
    shutil.copy(ORIGINAL / "vn" / "captcha.svg", CLEAN / "jp" / "captcha.svg")


def _strip(text):
    return re.sub(r"<[^>]+>", "", text).replace("*", "").strip()


def targets(key, folder=CLEAN):
    proc = PROCEDURES[key]
    fields, buttons, steps = [], [], []
    for n, file in enumerate(proc.steps, 1):
        html = (folder / key / file).read_text(encoding="utf-8")
        steps.append({"id": f"step{n}", "step": n, "file": file, "name": proc.step_names[n - 1]})
        for m in re.finditer(r'<label for="(\w+)"(?: class="lbl")?>(.*?)</label>\s*<input id="\1" type="(text|email|tel)"', html):
            fields.append({"id": m.group(1), "step": n, "file": file, "name": _strip(m.group(2))})
        if n < len(proc.steps):
            m = re.search(r'<button[^>]*\bid="(next\d)"[^>]*>(.*?)</button>', html)
            if m:
                buttons.append({"id": m.group(1), "step": n, "file": file, "name": _strip(m.group(2))})
    pool = {"unnamed_field": fields, "code_label": fields, "keyboard_trap": fields, "mouse_only": buttons, "captcha": steps}
    out = {}
    for kind, items in pool.items():
        by_id = {i["id"]: i for i in items}
        out[kind] = sorted((by_id[i] for i in CURATED[key][kind] if i in by_id), key=lambda t: (t["step"], t["id"]))
    return out


def options():
    return {key: {"kinds": [{"id": k, **v} for k, v in KINDS.items()], "targets": targets(key),
                  "defaults": {k: v[0] for k, v in CURATED[key].items()}} for key in PROCEDURES}


def _inject_unnamed(html, eid, code=False):
    pattern = re.compile(LABEL_RE.format(id=re.escape(eid)), re.S)
    m = pattern.search(html)
    if not m:
        raise ValueError(f"no <label for={eid}> found")
    attr = f' aria-label="fld_{eid}_01"' if code else ""
    return pattern.sub(lambda m: f'<div class="lbl">{m.group(1)}</div>{m.group(2)}<input id="{eid}"{attr}', html, count=1)


def _inject_trap(html, eid):
    if f'id="{eid}"' not in html:
        raise ValueError(f"#{eid} not found")
    script = (f"<script id=\"input-format\">\ndocument.getElementById('{eid}').addEventListener('keydown', function (e) {{\n"
              f"  if (e.key === 'Tab') {{ e.preventDefault(); this.value = this.value.trim(); }}\n}});\n</script>\n")
    return html.replace('<p class="foot">', script + '<p class="foot">', 1)


def _inject_mouse_only(html, eid):
    pattern = re.compile(rf'<button[^>]*\bid="{re.escape(eid)}"[^>]*>(.*?)</button>', re.S)
    m = pattern.search(html)
    if not m:
        raise ValueError(f"button #{eid} not found")
    onclick = re.search(r'onclick="([^"]*)"', m.group(0)).group(1)
    return pattern.sub(lambda m: f'<div class="btn" id="{eid}" onclick="{onclick}">{m.group(1)}</div>', html, count=1)


def _inject_captcha(html, key):
    block = (f'<div class="field"><img id="captcha-img" src="captcha.svg" alt="CAPTCHA" width="180" height="60"></div>\n'
             f'<div class="field"><label for="captcha">{CAPTCHA_LABEL[key]}</label><input id="captcha" type="text"></div>\n')
    if 'id="captcha-img"' in html:
        return html
    return html.replace('<div class="actions">', block + '<div class="actions">', 1)


def inject(folder, key, kind, target):
    if kind not in KINDS:
        raise ValueError(f"unknown barrier kind {kind}")
    found = {t["id"]: t for t in targets(key, CLEAN)[kind]}
    if target not in found:
        raise ValueError(f"unknown target {target} for {kind}")
    t = found[target]
    path = Path(folder) / key / t["file"]
    html = path.read_text(encoding="utf-8")
    if kind == "unnamed_field":
        html, element = _inject_unnamed(html, target), target
    elif kind == "code_label":
        html, element = _inject_unnamed(html, target, code=True), target
    elif kind == "keyboard_trap":
        html, element = _inject_trap(html, target), target
    elif kind == "mouse_only":
        html, element = _inject_mouse_only(html, target), target
    else:
        html, element = _inject_captcha(html, key), "captcha-img"
    write_atomic(path, html)
    return {"kind": kind, "label": KINDS[kind]["label"], "sc": KINDS[kind]["sc"], "what": KINDS[kind]["what"],
            "element": element, "step": t["step"], "file": t["file"], "target": target, "target_name": t["name"]}


PREPARE_LOCK = threading.Lock()


def prepare(dest, key, form, kind=None, target=None):
    dest = Path(dest)
    source = ORIGINAL if form == "original" else CLEAN
    with PREPARE_LOCK:
        target_dir = dest / key
        target_dir.mkdir(parents=True, exist_ok=True)
        wanted = {f.name for f in (source / key).iterdir()}
        for f in target_dir.iterdir():
            if f.name not in wanted and not f.name.endswith(".tmp"):
                shutil.rmtree(f) if f.is_dir() else f.unlink()
        for f in (source / key).iterdir():
            data = f.read_bytes()
            out = target_dir / f.name
            if not out.exists() or out.read_bytes() != data:
                write_atomic(out, data)
        if form == "inject":
            return inject(dest, key, kind, target)
    return None


if __name__ == "__main__":
    build_clean()
    import json
    print(json.dumps(options(), ensure_ascii=False, indent=1)[:3000])
