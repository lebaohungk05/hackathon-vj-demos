import argparse
import filecmp
import hashlib
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

DEMO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEMO))
import server as srv  # noqa: E402

VIEWPORTS = [(1920, 1080), (1536, 864), (1366, 768), (1280, 720)]
LANGS = ["en", "ja", "vi"]
SHOTS = DEMO / "shots"
LAYOUT_JS = """() => {
  const bad = [];
  const vw = innerWidth, vh = innerHeight;
  const vis = el => { const s = getComputedStyle(el); return s.display !== 'none' && s.visibility !== 'hidden' && el.getClientRects().length; };
  if (document.documentElement.scrollWidth > vw + 1) bad.push('page scrolls horizontally');
  if (document.documentElement.scrollHeight > vh + 1) bad.push('page scrolls vertically');
  document.querySelectorAll('header, .rail, main, footer, .right > *, .left > *, .card, .fi, .stat, .modes, .langs, .chip, .proc').forEach(el => {
    if (!vis(el)) return;
    const r = el.getBoundingClientRect();
    if (r.right > vw + 1 || r.bottom > vh + 1) bad.push('outside viewport: ' + (el.id || el.className));
  });
  const right = document.querySelector('.right');
  if (right && vis(right)) { const rr = right.getBoundingClientRect(); [...right.children].forEach(c => { if (vis(c) && c.getBoundingClientRect().bottom > rr.bottom + 2) bad.push('right column overflow: ' + c.className); }); }
  const panel = document.getElementById('panel');
  if (panel && vis(panel) && panel.scrollHeight > panel.clientHeight + 3) bad.push('panel clipped ' + panel.scrollHeight + '>' + panel.clientHeight);
  document.querySelectorAll('.card').forEach(c => { if (vis(c) && getComputedStyle(c).overflow !== 'visible' && c.scrollHeight > c.clientHeight + 3 && !c.classList.contains('shrink')) bad.push('card clipped: ' + c.className + ' ' + c.scrollHeight + '>' + c.clientHeight); });
  document.querySelectorAll('.proc, .chip, .st .lb b, .chap, .pill, th, .cell, .kicker, .modes button, .langs button, .seg button, .runbtn, .ghost').forEach(el => {
    if (vis(el) && el.getClientRects().length > 1) bad.push('wrapped: ' + el.textContent.trim().slice(0, 30));
  });
  document.querySelectorAll('.hdr-right').forEach(el => { if (el.scrollWidth > el.clientWidth + 1) bad.push('header chips cut'); });
  const img = document.getElementById('frame');
  const left = document.querySelector('.left');
  if (left && vis(left) && img && !img.hidden && !(img.complete && img.naturalWidth)) bad.push('broken frame');
  if (panel && vis(panel) && panel.innerText.trim().length < 5) bad.push('blank panel');
  return bad;
}"""
MIXED_JS = r"""lang => {
  const cjk = /[　-〿぀-ヿ㐀-鿿豈-﫿＀-￯]/;
  const vn = /[̀-ͯĂăĐđĨĩŨũƠơƯưẠ-ỹÀ-ÃÈ-ÊÌÍÒ-ÕÙÚÝà-ãè-êìíò-õùúý]/;
  const en = /\b(the|and|of|is|are|with|from|by|for|not|this|that|was|into|only|never|then)\b/i;
  const bad = [];
  const shown = el => { for (let e = el; e && e !== document.body; e = e.parentElement) { const s = getComputedStyle(e); if (s.display === 'none' || s.visibility === 'hidden' || e.hidden) return false; } return true; };
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = walker.nextNode())) {
    const text = n.nodeValue;
    if (!text.trim()) continue;
    const el = n.parentElement;
    if (!el || el.closest('[data-src], script, style, iframe, noscript') || !shown(el)) continue;
    const hit = lang === 'en' ? (text.match(cjk) || text.match(vn)) : lang === 'ja' ? (text.match(vn) || text.match(en)) : (text.match(cjk) || text.match(en));
    if (hit) bad.push(text.trim().slice(0, 60) + ' [' + hit[0] + '] in ' + (el.id || el.className || el.tagName));
  }
  return bad;
}"""


class Problems:
    def __init__(self):
        self.items = []
        self.checks = 0

    def check(self, ok, msg):
        self.checks += 1
        if not ok:
            self.items.append(msg)
            print("  FAIL", msg, flush=True)
        return ok


def watch(page, log, tag):
    page.on("console", lambda m: log.append(f"[{tag}] console.{m.type}: {m.text[:200]}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: log.append(f"[{tag}] pageerror: {str(e)[:200]}"))
    page.on("requestfailed", lambda r: log.append(f"[{tag}] requestfailed: {r.url[:150]} {r.failure}"))
    page.on("response", lambda r: log.append(f"[{tag}] HTTP {r.status}: {r.url[:150]}") if r.status >= 400 else None)


def layout(page, pr, where):
    page.wait_for_timeout(250)
    bad = page.evaluate(LAYOUT_JS)
    pr.check(not bad, f"layout {where}: {bad[:5]}")


def mixed(page, pr, lang, where):
    bad = page.evaluate(MIXED_JS, lang)
    pr.check(not bad, f"one language only ({lang}) {where}: {bad[:4]}")


def i18n_complete(page, pr, lang, where, requests=True):
    missing = page.evaluate("[...window.i18nMissing]")
    pr.check(not missing, f"UI strings translated ({lang}) {where}: {missing[:5]}")
    if requests:
        asked = page.evaluate("[...window.i18nRequested]")
        pr.check(not asked, f"no on-demand translation needed ({lang}) {where}: {asked[:4]}")


def wait_live_idle(page):
    page.wait_for_function("window.appReady && document.querySelector('[data-act=run]')", timeout=20000)


def replay_suite(page, base, pr, w, h, shots, lang="en"):
    page.goto(base + f"dashboard.html?present&lang={lang}")
    page.wait_for_function("window.appReady === true", timeout=20000)
    pr.check(page.evaluate("window.uiLang") == lang, f"?lang={lang} opens the page in {lang}")
    n = page.evaluate("scenes.length")
    pr.check(n >= 30, f"replay has {n} scenes")
    for i in range(n):
        key = page.evaluate("window.sceneKey")
        page.wait_for_timeout(900 if (w, h) == (1920, 1080) else 450)
        layout(page, pr, f"{w}x{h} {lang} replay #{key}")
        mixed(page, pr, lang, f"{w}x{h} replay #{key}")
        if shots and (w, h) == (1920, 1080):
            page.wait_for_timeout(1500)
            page.screenshot(path=str(SHOTS / f"replay_{lang}_{i + 1:02d}_{key}.png"))
        if i < n - 1:
            page.keyboard.press("ArrowRight")
            page.wait_for_function("k => window.sceneKey !== k", arg=key, timeout=5000)
    i18n_complete(page, pr, lang, f"{w}x{h} replay")
    if lang != "en" or (w, h) != (1536, 864):
        return
    pr.check(page.evaluate("cur") == n - 1, "ArrowRight reaches the last scene")
    page.keyboard.press("Home")
    pr.check(page.evaluate("cur") == 0, "Home goes to scene 1")
    for k, want in (("2", "jp-listen"), ("3", "vn-axe"), ("4", "engine"), ("1", "vn-listen")):
        page.keyboard.press(k)
        pr.check(page.evaluate("window.sceneKey") == want, f"key {k} -> {want}")
    page.keyboard.press("PageDown")
    pr.check(page.evaluate("cur") == 1, "PageDown advances")
    page.keyboard.press("PageUp")
    page.click("#procs button:nth-child(2)")
    pr.check(page.evaluate("window.sceneKey") == "jp-listen", "JP pill jumps to Japan")
    page.click("#ticks button[data-i='5']")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    pr.check(page.evaluate("cur") == 6, "Enter after a tick click does not jump back")
    page.goto(base + "dashboard.html?present&lang=en#jp-read-honseki")
    page.wait_for_function("window.appReady === true")
    pr.check(page.evaluate("window.sceneKey") == "jp-read-honseki", "direct hash opens the scene")
    page.evaluate("location.hash = '#does-not-exist'")
    page.wait_for_timeout(300)
    pr.check(page.evaluate("location.hash") == "#jp-read-honseki", "unknown hash is corrected")
    page.reload()
    page.wait_for_function("window.appReady === true")
    pr.check(page.evaluate("window.sceneKey") == "jp-read-honseki", "reload keeps the scene")
    page.keyboard.press(" ")
    pr.check(page.evaluate("playing") is True, "Space starts autoplay")
    page.keyboard.press(" ")
    page.set_viewport_size({"width": 1100, "height": 620})
    page.wait_for_timeout(500)
    layout(page, pr, f"resized 1100x620 from {w}x{h}")
    page.set_viewport_size({"width": w, "height": h})
    page.wait_for_timeout(500)
    layout(page, pr, f"resized back {w}x{h}")
    lang_switch_suite(page, base, pr)


def lang_switch_suite(page, base, pr):
    page.goto(base + "dashboard.html?present#vn-fix-hoten")
    page.wait_for_function("window.appReady === true")
    page.evaluate("localStorage.removeItem('minna-lang')")
    page.goto(base + "dashboard.html?present#vn-fix-hoten")
    page.wait_for_function("window.appReady === true")
    pr.check(page.evaluate("window.uiLang") == "vi", "default language is VI")
    pr.check(page.evaluate("document.querySelector('#langs [aria-pressed=true]').dataset.lang") == "vi", "VI button pressed by default")
    page.click("#langs button[data-lang=ja]")
    page.wait_for_timeout(300)
    pr.check(page.evaluate("window.uiLang") == "ja" and page.evaluate("document.documentElement.lang") == "ja", "click JA switches the page to Japanese")
    pr.check("lang=ja" in page.url and page.evaluate("window.sceneKey") == "vn-fix-hoten", "switch keeps the scene and writes ?lang=ja")
    mixed(page, pr, "ja", "after clicking JA")
    page.keyboard.press("g")
    page.wait_for_timeout(300)
    pr.check(page.evaluate("window.uiLang") == "vi", "G cycles JA -> VI")
    mixed(page, pr, "vi", "after G")
    page.keyboard.press("G")
    page.wait_for_timeout(300)
    pr.check(page.evaluate("window.uiLang") == "en", "G cycles VI -> EN")
    page.keyboard.press("g")
    page.wait_for_timeout(200)
    page.goto(base + "dashboard.html?present#vn-audit")
    page.wait_for_function("window.appReady === true")
    pr.check(page.evaluate("window.uiLang") == "ja", "language remembered in localStorage")
    pr.check("試験結果" in page.inner_text("#panel"), "JA audit uses the JIS term 試験結果")
    page.goto(base + "dashboard.html?present&lang=en#vn-audit")
    page.wait_for_function("window.appReady === true")
    text = page.inner_text("#app")
    pr.check(text.count("試験結果") == 1 and "TEST RESULTS (試験結果)" in text.upper(), "EN audit shows test results (試験結果) once")
    page.goto(base + "dashboard.html?present&lang=en#jp-audit")
    page.wait_for_function("window.appReady === true")
    pr.check(page.inner_text("#app").count("試験結果") == 1, "EN JIS table shows 試験結果 once")
    page.goto(base + "dashboard.html?present&lang=en#vn-blocked-hoten")
    page.wait_for_function("window.appReady === true")
    page.wait_for_timeout(2500)
    pr.check(page.evaluate("document.getElementById('said').dataset.src") == "vi" and page.inner_text("#gloss").strip() != "",
             "EN: screen-reader quote marked as Vietnamese source with an English gloss")
    page.goto(base + "dashboard.html?present&lang=vi#vn-blocked-hoten")
    page.wait_for_function("window.appReady === true")
    page.wait_for_timeout(2500)
    pr.check(page.inner_text("#gloss").strip() == "", "VI: no gloss under a Vietnamese quote")
    page.evaluate("localStorage.removeItem('minna-lang')")


def run_live(page, pr, decisions, tag, shots=None, timeout=240, lang="en"):
    page.click("[data-act=run]")
    t0 = time.time()
    shot_pending = shot_running = False
    while time.time() - t0 < timeout:
        state = page.evaluate("({s: window.liveStatus, pend: !!document.querySelector('[data-act=approve]:not([disabled])'), res: !!document.querySelector('.result')})")
        if state["res"]:
            break
        if not shot_running and page.evaluate("L.events.some(e => e.kind === 'hear')"):
            shot_running = True
            if shots:
                page.wait_for_timeout(300)
                page.screenshot(path=str(SHOTS / f"{shots}_1_running.png"))
            layout(page, pr, f"{tag} running")
            mixed(page, pr, lang, f"{tag} running")
        if state["pend"]:
            pr.check(page.evaluate("document.querySelector('#screen iframe.livef') !== null"), f"{tag}: live iframe present")
            pr.check(page.evaluate("!!document.querySelector('#screen iframe.livef').contentDocument.querySelector('.ma-hl')"), f"{tag}: focused element highlighted in the iframe")
            layout(page, pr, f"{tag} approval card")
            mixed(page, pr, lang, f"{tag} approval card")
            if shots and not shot_pending:
                shot_pending = True
                page.screenshot(path=str(SHOTS / f"{shots}_2_decision.png"))
            approve = decisions.pop(0) if decisions else True
            page.click("[data-act=approve]" if approve else "[data-act=reject]")
            page.wait_for_function("!document.querySelector('[data-act=approve]:not([disabled])')", timeout=10000)
        page.wait_for_timeout(150)
    ok = pr.check(page.evaluate("!!document.querySelector('.result')"), f"{tag}: result card shown")
    page.wait_for_timeout(400)
    layout(page, pr, f"{tag} result")
    mixed(page, pr, lang, f"{tag} result")
    i18n_complete(page, pr, lang, tag)
    if shots:
        page.screenshot(path=str(SHOTS / f"{shots}_3_result.png"))
    return page.evaluate("L.result") if ok else None


def live_suite(page, base, pr, shots, lang="en"):
    page.goto(base + f"dashboard.html?speed=40&lang={lang}#live")
    wait_live_idle(page)
    layout(page, pr, f"live setup {lang}")
    mixed(page, pr, lang, "live setup")
    if shots:
        page.screenshot(path=str(SHOTS / f"live_{lang}_0_setup.png"))
    res = run_live(page, pr, [True, True, True], f"live VN approve {lang}", f"live_{lang}_vn" if shots else None, lang=lang)
    if res:
        pr.check(res["fixed"] == 3 and res["handoff"] == 1 and res["submitted"] == "no", f"VN approve result fixed=3 handoff=1: {res['fixed']} {res['handoff']}")
        pr.check(res["axe"] and sum(r["axe"] for r in res["axe"]["comparison"]) == 1, "axe-core found 1 of 4 on the same start pages")
    page.click("[data-act=setup]")
    page.click("#procs [data-proc=jp]")
    page.wait_for_timeout(500)
    mixed(page, pr, lang, "live setup JP")
    res = run_live(page, pr, [False], f"live JP reject {lang}", f"live_{lang}_jp_reject" if shots else None, lang=lang)
    if res:
        pr.check(res["final"] == "rejected" and res["rejected"] == 1 and res["fixed"] == 0, f"JP reject result: {res['final']}")
    sandbox = DEMO / "portal" / "sandbox" / "jp" / "step1.html"
    original = DEMO / "portal" / "original" / "jp" / "step1.html"
    pr.check(filecmp.cmp(sandbox, original, shallow=False), "rejected patch was not written to the portal")


def inject_suite(page, base, pr, shots, lang="en"):
    page.goto(base + f"dashboard.html?speed=40&lang={lang}#live")
    wait_live_idle(page)
    page.click("#procs [data-proc=vn]")
    page.click("[data-set=form][data-v=inject]")
    page.click("[data-set=barrier][data-v=keyboard_trap]")
    page.select_option("#targetSel", "email")
    page.wait_for_function("document.querySelector('#screen iframe.livef') && document.querySelector('#screen iframe.livef').contentDocument && document.querySelector('#screen iframe.livef').contentDocument.querySelector('#email.ma-plant') && document.getElementById('url').textContent.includes('step2.html') && L.cfg.target === 'email'", timeout=10000)
    page.wait_for_timeout(600)
    pr.check(True, "planted barrier highlighted in the preview")
    injected = False
    for _ in range(40):
        html = (DEMO / "portal" / "sandbox" / "vn" / "step2.html").read_text(encoding="utf-8")
        injected = "getElementById('email').addEventListener('keydown'" in html
        if injected:
            break
        page.wait_for_timeout(100)
    pr.check(injected, "keyboard trap injected into the sandbox copy")
    layout(page, pr, f"inject setup {lang}")
    mixed(page, pr, lang, "inject setup")
    if shots:
        page.screenshot(path=str(SHOTS / f"try_{lang}_0_planted.png"))
    res = run_live(page, pr, [True], f"inject keyboard trap {lang}", f"try_{lang}_trap" if shots else None, lang=lang)
    if res:
        found = [b for b in res["barriers"]]
        pr.check(len(found) == 1 and found[0]["element_id"] == "email" and found[0]["kind"] == "keyboard_trap" and found[0]["status"] == "fixed",
                 f"agent found and fixed the planted trap: {[(b['element_id'], b['kind'], b['status']) for b in found]}")
        pr.check(res["axe"] and not res["axe"]["comparison"][0]["axe"], "axe-core misses the planted keyboard trap")
    page.click("[data-act=setup]")
    page.click("[data-set=barrier][data-v=captcha]")
    page.wait_for_timeout(600)
    res = run_live(page, pr, [], f"inject captcha {lang}", lang=lang)
    if res:
        pr.check(res["final"] == "handoff" and res["handoff"] == 1, "planted CAPTCHA is handed to a human")
    page.click("[data-act=reset]")
    page.wait_for_function("document.querySelector('[data-act=run]') && !document.querySelector('.result')", timeout=20000)
    page.wait_for_timeout(500)
    same = all(filecmp.cmp(DEMO / "portal" / "sandbox" / k / f.name, f, shallow=False) for k in ("vn", "jp") for f in (DEMO / "portal" / "original" / k).iterdir())
    pr.check(same, "Reset restores the original mock portal")
    pr.check(page.evaluate("L.cfg.form") == "original", "Reset returns the setup to the original mock")


def live_layouts(page, base, pr, langs):
    for lang in langs:
        for w, h in VIEWPORTS:
            page.set_viewport_size({"width": w, "height": h})
            page.goto(base + f"dashboard.html?lang={lang}#live")
            wait_live_idle(page)
            layout(page, pr, f"{w}x{h} {lang} live setup")
            mixed(page, pr, lang, f"{w}x{h} live setup")
            page.click("[data-set=form][data-v=inject]")
            page.wait_for_timeout(500)
            for kind in ("unnamed_field", "code_label", "keyboard_trap", "mouse_only", "captcha"):
                page.click(f"[data-set=barrier][data-v={kind}]")
                page.wait_for_timeout(300)
                layout(page, pr, f"{w}x{h} {lang} try-it {kind}")
                mixed(page, pr, lang, f"{w}x{h} try-it {kind}")
            for proc in ("jp", "vn"):
                page.click(f"#procs [data-proc={proc}]")
                page.wait_for_timeout(300)
                mixed(page, pr, lang, f"{w}x{h} try-it {proc}")
            page.click("[data-set=form][data-v=original]")
            page.wait_for_timeout(300)
            i18n_complete(page, pr, lang, f"{w}x{h} live setup")


def digest(folder):
    h = hashlib.sha256()
    for f in sorted(folder.rglob("*")):
        if f.is_file():
            h.update(f.relative_to(folder).as_posix().encode())
            h.update(f.read_bytes())
    return h.hexdigest()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="End-to-end test of the MinnaAccess demo (replay + live + try-it + reset, 4 viewports, EN/JA/VI)")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--port", type=int, default=8799)
    ap.add_argument("--shots", action="store_true", help="also write screenshots to shots/")
    ap.add_argument("--quick", action="store_true", help="replay at 1536x864 only")
    ap.add_argument("--langs", default=",".join(LANGS), help="comma-separated UI languages to test (default en,ja,vi)")
    ap.add_argument("--only", choices=["replay", "live", "inject", "layouts"], help="run one part only")
    args = ap.parse_args()
    langs = [x for x in args.langs.split(",") if x in LANGS]
    part = lambda name: args.only in (None, name)
    out_before = digest(DEMO / "out")
    httpd, runner = srv.create(args.port, fallback=True)
    base = f"http://127.0.0.1:{httpd.server_address[1]}/"
    pr, log = Problems(), []
    started = time.time()
    if args.shots:
        SHOTS.mkdir(exist_ok=True)
        for f in SHOTS.glob("*.png"):
            f.unlink()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        if part("replay"):
            for lang in langs:
                for w, h in ([(1536, 864)] if args.quick else VIEWPORTS):
                    print(f"replay {lang} {w}x{h}", flush=True)
                    ctx = browser.new_context(viewport={"width": w, "height": h})
                    page = ctx.new_page()
                    watch(page, log, f"replay {lang} {w}x{h}")
                    replay_suite(page, base, pr, w, h, args.shots, lang)
                    ctx.close()
            print("replay from file://", flush=True)
            for lang in langs:
                ctx = browser.new_context(viewport={"width": 1366, "height": 768})
                page = ctx.new_page()
                watch(page, log, f"file {lang}")
                page.goto((DEMO / "dashboard.html").as_uri() + f"?present&lang={lang}#vn-fix-hoten")
                page.wait_for_function("window.appReady === true")
                layout(page, pr, f"file:// replay {lang}")
                mixed(page, pr, lang, "file:// replay")
                i18n_complete(page, pr, lang, "file:// replay")
                page.keyboard.press("l")
                page.wait_for_timeout(300)
                mixed(page, pr, lang, "file:// live tab")
                if lang == "en":
                    pr.check("needs the local server" in page.inner_text("#panel").lower(), "file:// live tab explains how to start the server")
                ctx.close()
        if part("live"):
            for w, h, lang in [(1536, 864, "en"), (1280, 720, "ja"), (1366, 768, "vi")]:
                if lang not in langs:
                    continue
                print(f"live {lang} {w}x{h}", flush=True)
                ctx = browser.new_context(viewport={"width": w, "height": h})
                page = ctx.new_page()
                watch(page, log, f"live {lang} {w}x{h}")
                live_suite(page, base, pr, args.shots, lang)
                ctx.close()
        if part("inject"):
            for lang, (w, h) in zip(langs, [(1366, 768), (1920, 1080), (1280, 720)]):
                print(f"try it yourself + reset {lang} {w}x{h}", flush=True)
                ctx = browser.new_context(viewport={"width": w, "height": h})
                page = ctx.new_page()
                watch(page, log, f"inject {lang}")
                inject_suite(page, base, pr, args.shots, lang)
                ctx.close()
        if part("layouts"):
            print("live setup layouts", flush=True)
            ctx = browser.new_context(viewport={"width": 1366, "height": 768})
            page = ctx.new_page()
            watch(page, log, "live layouts")
            live_layouts(page, base, pr, langs)
            ctx.close()
        browser.close()
    httpd.shutdown()
    httpd.server_close()
    pr.check(digest(DEMO / "out") == out_before, "recorded replay data in out/ unchanged by live runs")
    pr.check(not log, f"zero console errors/warnings and failed requests ({len(log)})")
    for line in log[:30]:
        print("  ", line)
    print(f"\n{pr.checks - len(pr.items)}/{pr.checks} checks passed in {time.time() - started:.0f} s")
    sys.exit(1 if pr.items else 0)


if __name__ == "__main__":
    main()
