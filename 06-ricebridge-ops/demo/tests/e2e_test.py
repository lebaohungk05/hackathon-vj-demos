import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "out"
VIEWPORTS = [(1920, 1080), (1536, 864), (1366, 768), (1280, 720)]
SAMPLES = [
    ("nước ba phân", {"recorded"}),
    ("khô nứt chân chim", {"clarify", "not_reading"}),
    ("lấp xấp mắt cá", {"clarify", "not_reading"}),
    ("thửa 4 âm năm phân", {"held"}),
    ("prompt injection", {"refused"}),
]
FREE_TEXT = [
    ("Hộ thửa 6", "thửa 6 nước bốn phân rưỡi", {"recorded", "clarify", "held"}),
    ("Hộ thửa 1", "asdf qwer zxcv", {"not_reading", "clarify"}),
    ("Hộ thửa 1", "🌾💧 thửa 1 ổn không?", {"not_reading", "clarify"}),
    ("Hộ thửa 2", "田んぼ2の水位は3センチです", {"recorded", "clarify", "not_reading", "held"}),
    ("Hộ thửa 5", "x" * 420, {"not_reading", "clarify"}),
]
LAYOUT_CHECK = """() => { const out = []; const W = innerWidth, H = innerHeight;
  if (document.documentElement.scrollWidth > W + 1) out.push('horizontal page scroll ' + document.documentElement.scrollWidth + '>' + W);
  if (document.documentElement.scrollHeight > H + 1) out.push('vertical page scroll ' + document.documentElement.scrollHeight + '>' + H);
  document.querySelectorAll('header button, .st, .card, .tile, .chat, .fi, .dbtn, .live, #send, #text, #sender, .lbtn, .runbtn').forEach(el => {
    if (el.closest('[hidden]')) return; const r = el.getBoundingClientRect(); if (!r.width) return;
    if (r.right > W + 1 || r.bottom > H + 1 || r.left < -1 || r.top < -1) out.push('outside viewport: ' + (el.id || el.className) + ' @' + Math.round(r.right) + 'x' + Math.round(r.bottom)); });
  document.querySelectorAll('.focal, .plan, .tracecard, .fieldscard, .wicard, .stage, .side, .chatcol, .view > .col, .card').forEach(el => {
    if (el.closest('[hidden]')) return; if (el.scrollHeight > el.clientHeight + 2) { const box = el.getBoundingClientRect(); let worst = null;
      el.querySelectorAll('*').forEach(d => { const r = d.getBoundingClientRect(); if (r.height && r.bottom > box.bottom + 1 && (!worst || r.bottom > worst[1])) worst = [d.className || d.tagName, Math.round(r.bottom - box.bottom), (d.innerText || '').slice(0, 30)]; });
      out.push('clipped content: ' + (el.id || el.className) + ' ' + el.scrollHeight + '>' + el.clientHeight + ' by ' + JSON.stringify(worst)); } });
  return out; }"""

MIXED_CHECK = r"""(lang) => {
  const VI = /[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]/i;
  const CJK = /[぀-ヿ㐀-鿿＀-￯]/;
  const EN_WORDS = /\b(the|and|of|with|from|is|are|this|that|will|should|before|after|when|only|into|has|have|was|were|which|not|your|for|by|to)\b/gi;
  const out = [];
  const seen = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const text = node.nodeValue.replace(/\s+/g, ' ').trim();
    if (!text) continue;
    const el = node.parentElement;
    if (!el || el.closest('[data-src], script, style, [hidden], option')) continue;
    if (!el.getClientRects().length) continue;
    let bad = false;
    if (lang === 'en') bad = VI.test(text) || CJK.test(text);
    else if (lang === 'ja') bad = VI.test(text) || (text.match(EN_WORDS) || []).length >= 2;
    else bad = CJK.test(text) || (text.match(EN_WORDS) || []).length >= 2;
    if (bad && !seen.has(text)) { seen.add(text); out.push((el.id || el.className || el.tagName) + ': ' + text.slice(0, 90)); }
  }
  return out;
}"""


class Check:
    def __init__(self):
        self.passed = 0
        self.failures = []

    def ok(self, cond, label):
        if cond:
            self.passed += 1
        else:
            self.failures.append(label)
            print("  FAIL", label, flush=True)


def http(base, path, body=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"}, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def wait_server(base):
    for _ in range(120):
        try:
            if http(base, "/api/health")[1].get("ok"):
                return
        except OSError:
            pass
        time.sleep(0.5)
    raise RuntimeError("server did not start")


def idle(page, timeout=180_000):
    page.wait_for_function("() => window.__rb && window.__rb.state() && !window.__rb.busy()", timeout=timeout)
    page.wait_for_timeout(250)


def state(page, expr):
    return page.evaluate(f"() => {{ const S = window.__rb.state(); return {expr}; }}")


def layout(page, c, vp, scene):
    page.evaluate("() => Promise.all(document.getAnimations().filter(a => a.effect && a.effect.getComputedTiming().iterations !== Infinity).map(a => a.finished.catch(() => null)))")
    issues = page.evaluate(LAYOUT_CHECK)
    c.ok(not issues, f"{vp} {scene}: layout {issues}")
    lang = page.evaluate("() => window.__rb.lang()")
    mixed = page.evaluate(MIXED_CHECK, lang)
    c.ok(not mixed, f"{vp} {scene} [{lang}]: mixed-language text {mixed[:4]}")


def set_lang(page, lang):
    page.click(f"#langseg button[data-lang='{lang}']")
    page.wait_for_function(f"() => window.__rb.lang() === '{lang}' && document.documentElement.lang === '{lang}'")
    page.wait_for_timeout(250)


LANG_MARKERS = {
    "ja": {"htx": "このステップの処理ログ", "carbon": "区画マップ", "approve": "承認"},
    "vi": {"htx": "Agent đang làm gì?", "carbon": "Bản đồ thửa", "approve": "Duyệt"},
    "en": {"htx": "Agent trace", "carbon": "Parcel map", "approve": "Approve"},
}


def language_pass(page, c, name, lang, shots):
    tag = f"{name} {lang}"
    set_lang(page, lang)
    page.keyboard.press("Escape")
    page.click("#reset")
    idle(page)
    if page.is_visible("#view-carbon"):
        page.keyboard.press("c")
    layout(page, c, tag, "intro")
    for i in range(6):
        page.keyboard.press("ArrowRight")
        idle(page)
        c.ok(state(page, "S.step") == i, f"{tag} step {i + 1} reached")
        layout(page, c, tag, f"step {i + 1}")
        if shots:
            page.screenshot(path=str(shots / f"{name}_{lang}_step{i + 1}.png"))
    c.ok(LANG_MARKERS[lang]["htx"].lower() in page.inner_text("#trace").lower(), f"{tag} farmer view labels in {lang}")
    c.ok(page.inner_text("#approve").startswith(LANG_MARKERS[lang]["approve"]), f"{tag} approve button in {lang}")
    page.click("#approve")
    idle(page)
    c.ok(state(page, "S.plan.status") == "approved", f"{tag} approve")
    layout(page, c, tag, "approved")
    if lang != "vi":
        c.ok(page.locator("#messages .msg.agent .et").count() > 0, f"{tag} agent messages show a {lang} translation line")
        c.ok(page.locator("#messages .msg.agent .sent").count() > 0, f"{tag} agent messages marked as sent in Vietnamese")
    else:
        c.ok(page.locator("#messages .et").count() == 0, f"{tag} no translation lines in Vietnamese mode")
    for sample, expected in (("thửa 4 âm năm phân", {"held"}), ("nước ba phân", {"recorded"}), ("prompt injection", {"refused"})):
        page.click(f".sample[data-tag='{sample}']")
        page.press("#text", "Enter")
        idle(page)
        kind = state(page, "S.current.result.verdict && S.current.result.verdict.kind")
        c.ok(kind in expected, f"{tag} live '{sample}' -> {kind}")
        layout(page, c, tag, f"live {sample}")
        if shots and sample == "thửa 4 âm năm phân":
            page.screenshot(path=str(shots / f"{name}_{lang}_live.png"))
    page.keyboard.press("Escape")
    page.keyboard.press("w")
    page.wait_for_selector("#whatif:not([hidden])")
    for tab, setup in [("rain", lambda: page.click("[data-mm='40']")), ("flowering", lambda: page.click("[data-fid='F2']")),
                       ("photo", lambda: page.click("[data-img='gauge_23.jpg']"))]:
        page.click(f".witab[data-tab='{tab}']")
        setup()
        page.click("#wi-run")
        idle(page, 240_000)
        c.ok(state(page, "S.whatif && S.whatif.kind") == tab, f"{tag} what-if {tab}")
        layout(page, c, tag, f"what-if {tab}")
        if shots and tab == "flowering":
            page.screenshot(path=str(shots / f"{name}_{lang}_whatif.png"))
    page.keyboard.press("Escape")
    page.keyboard.press("c")
    page.wait_for_timeout(400)
    c.ok(LANG_MARKERS[lang]["carbon"].lower() in page.inner_text("#view-carbon").lower(), f"{tag} carbon labels in {lang}")
    page.click("#verify")
    page.wait_for_selector("#verify-result.ok")
    layout(page, c, tag, "carbon verified")
    page.click("#tamper")
    page.wait_for_selector("#verify-result.bad")
    layout(page, c, tag, "carbon tamper")
    if shots:
        page.screenshot(path=str(shots / f"{name}_{lang}_carbon.png"))
    page.keyboard.press("c")
    page.wait_for_timeout(300)


def language_controls(page, c, name):
    set_lang(page, "en")
    order = []
    for _ in range(3):
        page.keyboard.press("j")
        page.wait_for_timeout(150)
        order.append(page.evaluate("() => window.__rb.lang()"))
    c.ok(order == ["ja", "vi", "en"], f"{name} key J cycles EN → JA → VI → EN ({order})")
    set_lang(page, "vi")
    page.reload()
    idle(page)
    c.ok(page.evaluate("() => window.__rb.lang()") == "vi", f"{name} language remembered after reload")
    c.ok(page.locator("#langseg button.on").inner_text() == "VI", f"{name} segmented control shows the active language")
    base = page.url.split("?")[0]
    page.goto(base + "?view=htx&lang=ja")
    idle(page)
    c.ok(page.evaluate("() => window.__rb.lang()") == "ja", f"{name} ?lang=ja selects Japanese")
    set_lang(page, "en")


def api_robustness(base, c):
    print("API robustness")
    for path, body, raw, code in [("/api/goto", {"step": "abc"}, None, 400), ("/api/next", None, b"{nope", 400), ("/api/nope", {}, None, 404),
                                  ("/api/message", {"sender": None, "text": None}, None, 400), ("/api/message", {"sender": "hacker", "text": "thửa 2 nước 2 phân"}, None, 400),
                                  ("/api/decision", {"decision": "maybe"}, None, 400), ("/api/whatif", {"kind": "nope"}, None, 400),
                                  ("/api/upload", {"data": "bm90IGFuIGltYWdl"}, None, 400)]:
        status, reply = http(base, path, body, raw)
        c.ok(status == code and reply.get("ok") is False and reply.get("message"), f"api {path} {body or raw} -> {status} {reply}")
    status, reply = http(base, "/media/..%2F..%2Fbackend%2Fserver.py")
    c.ok(status in (400, 404) and reply.get("ok") is False, f"media traversal blocked ({status})")


def run_viewport(browser, base, vp, c, mode, shots, full):
    W, H = vp
    name = f"{W}x{H}"
    print(f"Viewport {name}", flush=True)
    ctx = browser.new_context(viewport={"width": W, "height": H}, accept_downloads=True)
    page = ctx.new_page()
    problems = []
    page.on("console", lambda m: problems.append(f"console.{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
    page.on("requestfailed", lambda r: None if ("ERR_ABORTED" in str(r.failure) and "/api/state" in r.url) else problems.append(f"requestfailed {r.url} {r.failure}"))
    page.on("response", lambda r: problems.append(f"HTTP {r.status} {r.url}") if r.status >= 400 else None)
    page.goto(base + "/?view=htx&lang=en")
    idle(page)
    page.click("#reset")
    idle(page)
    c.ok(state(page, "S.step") == -1, f"{name} reset to intro")
    layout(page, c, name, "intro")
    page.dblclick("#next")
    idle(page)
    step = state(page, "S.step")
    c.ok(step in (0, 1), f"{name} double-click Next advanced at most twice (step {step})")
    page.click("#reset")
    idle(page)
    kinds = ["sensor", "rain", "photo", "resolved", "assisted", "pump"]
    for i in range(6):
        page.keyboard.press("ArrowRight")
        idle(page)
        c.ok(state(page, "S.step") == i, f"{name} step {i + 1} reached")
        c.ok(state(page, "S.current.result.focal && S.current.result.focal.kind") == kinds[i], f"{name} step {i + 1} focal {kinds[i]}")
        c.ok(page.locator("#focal .tile").count() > 0, f"{name} step {i + 1} focal element visible")
        layout(page, c, name, f"step {i + 1}")
        if shots:
            page.screenshot(path=str(shots / f"{name}_step{i + 1}.png"))
    c.ok(state(page, "S.plan.summary").startswith("Pump run Fri 06 Mar: open F6, then F4"), f"{name} hero plan F6 then F4 on Fri 06 Mar")
    page.keyboard.press("ArrowLeft")
    idle(page)
    c.ok(state(page, "S.step") == 4, f"{name} back one step")
    page.keyboard.press("ArrowRight")
    idle(page)
    page.click("#approve")
    idle(page)
    c.ok(state(page, "S.plan.status") == "approved", f"{name} approve via button")
    c.ok(state(page, "S.complete_fields") == 4, f"{name} 4/6 parcels complete")
    layout(page, c, name, "approved")
    page.keyboard.press("c")
    page.wait_for_timeout(400)
    layout(page, c, name, "carbon")
    page.click("#verify")
    page.wait_for_selector("#verify-result.ok")
    c.ok("verified" in page.inner_text("#verify-result").lower(), f"{name} hash chain verified")
    page.click("#tamper")
    page.wait_for_selector("#verify-result.bad")
    c.ok("tampering" in page.inner_text("#verify-result").lower(), f"{name} tampering detected")
    page.keyboard.press("j")
    page.wait_for_timeout(300)
    c.ok("区画マップ" in page.inner_text("#view-carbon"), f"{name} Japanese carbon labels")
    layout(page, c, name, "carbon ja")
    if shots:
        page.screenshot(path=str(shots / f"{name}_carbon_ja.png"))
    page.keyboard.press("c")
    page.wait_for_timeout(300)
    c.ok("詳細" in page.inner_text("#detailToggle"), f"{name} Japanese labels on the farmer view")
    set_lang(page, "en")
    page.keyboard.press("c")
    page.wait_for_timeout(300)
    if full:
        with page.expect_download() as info:
            page.click("#export")
        csv = Path(info.value.path()).read_text(encoding="utf-8-sig")
        c.ok(csv.startswith("seq,time,field") and csv.count("\n") > 50, f"{name} CSV export")
        with page.expect_download() as info:
            page.click("#exportjson")
        exported = json.loads(Path(info.value.path()).read_text(encoding="utf-8"))
        c.ok(exported["verification"]["ok"] and len(exported["records"]) > 50, f"{name} JSON export verifies")
    page.keyboard.press("c")
    page.wait_for_timeout(300)

    for tag, expected in SAMPLES:
        page.click(f".sample[data-tag='{tag}']")
        page.press("#text", "Enter")
        idle(page)
        kind = state(page, "S.current.result.verdict && S.current.result.verdict.kind")
        c.ok(kind in expected, f"{name} sample '{tag}' -> {kind} (expected {expected})")
        layout(page, c, name, f"sample {tag}")
        if shots and tag in ("nước ba phân", "thửa 4 âm năm phân", "prompt injection"):
            page.screenshot(path=str(shots / f"{name}_live_{tag.replace(' ', '_')}.png"))
    c.ok(not state(page, "S.log.some(e => e.value_cm === 50 || e.value_cm === 10 && e.field === 'F2' && e.status === 'accepted')"), f"{name} injection never recorded")

    texts = FREE_TEXT if full else FREE_TEXT[:1]
    for sender, text, expected in texts:
        before = state(page, "S.chat.length")
        page.select_option("#sender", sender)
        page.fill("#text", text)
        page.press("#text", "Enter")
        idle(page, 240_000)
        kind = state(page, "S.current.result.verdict && S.current.result.verdict.kind")
        c.ok(kind in expected and state(page, "S.chat.length") > before, f"{name} free text {text[:24]!r} -> {kind}")
    page.fill("#text", "   ")
    page.press("#text", "Enter")
    page.wait_for_timeout(300)
    c.ok(page.is_visible("#toast"), f"{name} empty message shows a hint, not a request")

    before = state(page, "S.chat.length")
    page.select_option("#sender", "Hộ thửa 2")
    page.fill("#text", "Thửa 2 nước ba phân rồi nghen")
    page.press("#text", "Enter")
    page.fill("#text", "Ruộng tui khô nứt chân chim rồi")
    page.press("#text", "Enter")
    idle(page, 240_000)
    page.wait_for_timeout(600)
    idle(page, 240_000)
    texts_now = state(page, "S.chat.map(m => m.vi)")
    c.ok("Ruộng tui khô nứt chân chim rồi" in texts_now and "Thửa 2 nước ba phân rồi nghen" in texts_now[before:], f"{name} second message queued and sent after the first")
    if state(page, "S.plan.status") == "proposed":
        page.click("#reject")
        idle(page)
        c.ok(state(page, "S.plan.status") == "rejected", f"{name} reject via button")
        c.ok(page.locator(".stamp.rejected").count() == 1, f"{name} rejected stamp shown")
    else:
        page.select_option("#sender", "Hộ thửa 6")
        page.fill("#text", "Thửa 6 nước hai phân")
        page.press("#text", "Enter")
        idle(page)
        page.click("#reject")
        idle(page)
        c.ok(state(page, "S.plan.status") == "rejected", f"{name} reject via button")

    page.keyboard.press("Escape")
    page.keyboard.press("w")
    page.wait_for_selector("#whatif:not([hidden])")
    for tab, setup in [("rain", lambda: page.click("[data-mm='40']")), ("flowering", lambda: page.click("[data-fid='F2']")),
                       ("pump", lambda: page.click("[data-date]:not([title])")), ("photo", lambda: page.click("[data-img='gauge_23.jpg']"))]:
        page.click(f".witab[data-tab='{tab}']")
        setup()
        if tab == "photo":
            page.uncheck("#wi-exif")
        page.click("#wi-run")
        idle(page, 240_000)
        w = state(page, "S.whatif && {label: S.whatif.label, kind: S.whatif.kind, brief: !S.whatif.brief.pending}")
        c.ok(bool(w) and w["kind"] == tab and w["brief"], f"{name} what-if {tab}: {w}")
        layout(page, c, name, f"what-if {tab}")
        if shots and tab in ("flowering", "photo"):
            page.screenshot(path=str(shots / f"{name}_whatif_{tab}.png"))
    c.ok(state(page, "S.whatif.verdict && S.whatif.verdict.kind") == "recorded", f"{name} what-if photo accepted with upload time")
    if full:
        page.check("#wi-exif")
        page.click("#wi-run")
        idle(page)
        c.ok(state(page, "S.whatif.flags.some(f => f.code === 'STALE_PHOTO')"), f"{name} what-if photo with EXIF flagged STALE_PHOTO")
        page.set_input_files("#wi-upload", str(ROOT / "vision" / "testset" / "gauge_05.jpg"))
        page.wait_for_selector(".pill.info:has-text('your upload')")
        page.click("#wi-run")
        idle(page, 240_000)
        c.ok(state(page, "S.whatif && S.whatif.kind") == "photo", f"{name} uploaded photo what-if ran")
    log_len = state(page, "S.log.length")
    page.keyboard.press("Escape")
    c.ok(page.is_hidden("#whatif"), f"{name} what-if closes with Esc")
    c.ok(state(page, "S.log.length") == log_len, f"{name} what-if wrote nothing to the log")

    page.keyboard.press("3")
    idle(page)
    c.ok(state(page, "S.step") == 2, f"{name} jump to step 3 with key 3")
    page.keyboard.press("r")
    idle(page)
    c.ok(state(page, "S.step") == -1 and state(page, "S.chat.length") == 0, f"{name} reset mid-way clears the run")
    page.keyboard.press("ArrowRight")
    idle(page)
    page.keyboard.press("ArrowRight")
    idle(page)
    page.reload()
    idle(page)
    c.ok(state(page, "S.step") == 1, f"{name} reload keeps the server state")
    c.ok(page.locator("#messages .msg").count() > 0, f"{name} chat rebuilt after reload")
    layout(page, c, name, "after reload")
    language_controls(page, c, name)
    for lang in ("ja", "vi"):
        language_pass(page, c, name, lang, shots)
    c.ok(not problems, f"{name} console errors / failed requests: {problems[:6]}")
    ctx.close()


def live_llm_check(browser, base, c):
    print("Live LLM call with progress", flush=True)
    ctx = browser.new_context(viewport={"width": 1536, "height": 864})
    page = ctx.new_page()
    problems = []
    page.on("pageerror", lambda e: problems.append(str(e)))
    page.on("console", lambda m: problems.append(m.text) if m.type == "error" else None)
    page.goto(base)
    idle(page)
    page.click("#reset")
    idle(page)
    for _ in range(6):
        page.keyboard.press("ArrowRight")
        idle(page)
    page.select_option("#sender", "Hộ thửa 6")
    page.fill("#text", f"Thửa 6 nước hai phân rưỡi nha, kiểm tra lúc {time.strftime('%H:%M:%S')}")
    page.press("#text", "Enter")
    page.wait_for_selector("#progress:not([hidden]) #secs", timeout=10_000)
    page.wait_for_timeout(2500)
    secs = page.inner_text("#secs")
    c.ok(secs.endswith(" s") and float(secs.split()[0]) > 1.0, f"progress shows elapsed seconds ({secs})")
    c.ok(page.evaluate("() => document.querySelector('#rail') !== null") and page.is_enabled(".tab[data-view=carbon]"), "UI responsive during the LLM call")
    started = time.time()
    status = http(base, "/api/state")[0]
    c.ok(status == 200 and time.time() - started < 1.0, f"state endpoint answers during the LLM call ({time.time() - started:.2f} s)")
    idle(page, 240_000)
    c.ok(state(page, "S.current.result.parse.engine") in ("llm", "rules"), "live message processed")
    c.ok(not problems, f"live LLM console errors {problems}")
    ctx.close()


def main():
    parser = argparse.ArgumentParser(description="RiceBridge Ops end-to-end test")
    parser.add_argument("--mode", default="replay", choices=["replay", "auto", "rules", "live"])
    parser.add_argument("--port", type=int, default=8811)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--shots", action="store_true", help="save screenshots to tests/out")
    parser.add_argument("--with-llm", action="store_true", help="also send one new sentence through the real Claude CLI (needs --mode auto)")
    parser.add_argument("--viewports", default="all", help="all or e.g. 1536x864")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    log_path = OUT / f"server_{args.mode}.log"
    base = f"http://127.0.0.1:{args.port}"
    log = open(log_path, "w", encoding="utf-8")
    server = subprocess.Popen([sys.executable, str(ROOT / "backend" / "server.py"), "--port", str(args.port), f"--{args.mode}"],
                              cwd=ROOT / "backend", stdout=log, stderr=subprocess.STDOUT)
    c = Check()
    started = time.time()
    try:
        wait_server(base)
        api_robustness(base, c)
        vps = VIEWPORTS if args.viewports == "all" else [tuple(int(x) for x in v.split("x")) for v in args.viewports.split(",")]
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not args.headed)
            for i, vp in enumerate(vps):
                run_viewport(browser, base, vp, c, args.mode, OUT if args.shots else None, full=i == 0 or len(vps) == 1)
            if args.with_llm:
                live_llm_check(browser, base, c)
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)
        log.close()
    text = log_path.read_text(encoding="utf-8")
    c.ok("Traceback" not in text and "ERROR" not in text, f"server log has no tracebacks ({log_path.name})")
    print(f"\n{c.passed} checks passed, {len(c.failures)} failed · mode {args.mode} · {time.time() - started:.0f} s")
    for f in c.failures:
        print("  -", f)
    return 1 if c.failures else 0


if __name__ == "__main__":
    sys.exit(main())
