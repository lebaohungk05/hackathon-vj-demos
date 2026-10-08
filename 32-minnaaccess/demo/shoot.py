import argparse
import shutil
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
SHOTS = ROOT / "shots" / "scenes"
SMALL_KEYS = ["vn-blocked-hoten", "jp-fix-honseki", "vn-axe"]
OVERFLOW_JS = """() => {
  const bad = [];
  const out = el => { const r = el.getBoundingClientRect(); return r.width > 0 && (r.right > innerWidth + 1 || r.bottom > innerHeight + 1); };
  document.querySelectorAll('header *, .rail *, footer *, .shead h2, .card, .fi, .proc, .chip').forEach(el => { if (out(el)) bad.push(el.className || el.tagName); });
  document.querySelectorAll('.proc, .chip, .st .lb b').forEach(el => { if (el.getBoundingClientRect().height > parseFloat(getComputedStyle(document.documentElement).fontSize) * 2.6) bad.push('wrap:' + el.textContent.trim().slice(0, 30)); });
  const img = document.getElementById('frame');
  const left = document.querySelector('.left');
  if (left && getComputedStyle(left).display !== 'none' && !img.hidden && !(img.complete && img.naturalWidth)) bad.push('broken frame image');
  if (document.documentElement.scrollWidth > innerWidth || document.documentElement.scrollHeight > innerHeight) bad.push('page scrolls');
  return bad;
}"""


def shoot(page, url, keys, folder, only=None):
    page.goto(url)
    page.wait_for_function("window.appReady === true")
    page.wait_for_timeout(600)
    all_keys = page.evaluate("scenes.map(s => s.key)")
    problems = 0
    for n, key in enumerate(all_keys, 1):
        if keys and key not in keys:
            continue
        if only and key not in only:
            continue
        page.evaluate("k => go(scenes.findIndex(s => s.key === k))", key)
        page.wait_for_function("(() => { const i = document.getElementById('frame'); return document.querySelector('main').classList.contains('wide') || i.hidden || (i.complete && i.naturalWidth > 0) || document.querySelector('#screen iframe.fallback'); })")
        page.wait_for_timeout(2600)
        bad = page.evaluate(OVERFLOW_JS)
        problems += bool(bad)
        out = folder / f"{n:02d}_{key}.png"
        page.screenshot(path=str(out))
        print(f"{out.relative_to(ROOT)}{'  PROBLEM: ' + ', '.join(map(str, bad[:6])) if bad else ''}")
    return problems


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="1920x1080 screenshots of every dashboard scene, plus a few at 1366x768 in shots/small")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--file", action="store_true", help="open the dashboard from disk (file://) instead of a local http server")
    args = ap.parse_args(argv)
    if not args.only:
        shutil.rmtree(SHOTS, ignore_errors=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    (SHOTS / "small").mkdir(parents=True, exist_ok=True)
    server = None
    if args.file:
        url = (ROOT / "dashboard.html").as_uri() + "?present"
    else:
        import server as srv
        server, _ = srv.create(8796, fallback=True)
        url = f"http://127.0.0.1:{server.server_address[1]}/dashboard.html?present"
    problems = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        problems += shoot(page, url, None, SHOTS, args.only)
        small = browser.new_page(viewport={"width": 1366, "height": 768})
        problems += shoot(small, url, SMALL_KEYS, SHOTS / "small", args.only)
        browser.close()
    if server:
        server.shutdown()
    print("all scenes clean" if not problems else f"{problems} scene(s) with layout problems")


if __name__ == "__main__":
    main()
