import argparse
import importlib.util
import re
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from netutil import DEFAULT_PORT, HOST, minna_server_on, port_free  # noqa: E402

OK, WARN, FAIL = "ok", "warn", "fail"


def check(label, status, detail):
    mark = {OK: "[ ok ]", WARN: "[warn]", FAIL: "[FAIL]"}[status]
    print(f"  {mark} {label}: {detail}")
    return status


def missing_frames():
    text = (ROOT / "out" / "run_data.js").read_text(encoding="utf-8")
    shots = sorted(set(re.findall(r'"shot": "([^"]+)"', text)))
    return [s for s in shots if not (ROOT / s).exists()]


def prerequisites():
    print("MinnaAccess demo: checking prerequisites")
    results = []
    results.append(check("Python", OK if sys.version_info >= (3, 10) else FAIL, sys.version.split()[0] + ("" if sys.version_info >= (3, 10) else " (need 3.10+)")))
    has_pw = importlib.util.find_spec("playwright") is not None
    results.append(check("Playwright", OK if has_pw else FAIL, "installed" if has_pw else "missing: pip install playwright"))
    if has_pw:
        from server import chromium_ok
        ok = chromium_ok()
        results.append(check("Chromium", OK if ok else FAIL, "installed" if ok else "missing: python -m playwright install chromium (live run disabled)"))
    from llm import find_claude
    exe = find_claude()
    results.append(check("Claude CLI", OK if exe else WARN, exe if exe else "not found: live LLM calls disabled, cached replies still work"))
    axe = ROOT.parent / "sim" / "vendor" / "axe.min.js"
    results.append(check("axe-core", OK if axe.exists() else FAIL, "found" if axe.exists() else f"missing {axe}"))
    run_data = ROOT / "out" / "run_data.js"
    if run_data.exists():
        miss = missing_frames()
        results.append(check("Recorded replay", OK if not miss else WARN, "out/run_data.js + frames" if not miss else f"{len(miss)} frame(s) missing, re-run: python run_demo.py --replay --auto-approve --headless"))
    else:
        results.append(check("Recorded replay", FAIL, "out/run_data.js missing: python run_demo.py --replay --auto-approve --headless"))
    cache = len(list((ROOT / "cache").glob("*.json")))
    results.append(check("LLM cache", OK if cache else WARN, f"{cache} cached answers (offline replay)"))
    fonts = (ROOT / "fonts" / "fonts.css").exists()
    results.append(check("Fonts", OK if fonts else WARN, "bundled (works offline)" if fonts else "missing, system fonts used"))
    return results


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    ap = argparse.ArgumentParser(description="Start the MinnaAccess demo: one local server, replay presenter + live agent runs")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--live", action="store_true", help="open the Live run tab first")
    ap.add_argument("--scene", default="", help="open the replay at this scene, e.g. jp-listen")
    ap.add_argument("--auto", type=float, default=0, help="replay autoplay, one scene every N seconds")
    ap.add_argument("--kiosk", action="store_true", help="full-screen Chromium window")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--check", action="store_true", help="only check prerequisites")
    args = ap.parse_args(argv)
    results = prerequisites()
    if args.check:
        sys.exit(1 if FAIL in results else 0)
    port = args.port
    if not port_free(port):
        existing = minna_server_on(port)
        if existing:
            print(f"\nA MinnaAccess server is already running on port {port}. Stop it (Ctrl+C in its window) or use --port.")
            url = f"http://{HOST}:{port}/dashboard.html"
            print(f"It is reachable at {url}")
            if not args.no_browser:
                webbrowser.open(url + ("#live" if args.live else "?present"))
            return
        alt = next((p for p in range(port + 1, port + 20) if port_free(p)), 0)
        print(f"\nPort {port} is used by another program; using port {alt or 'auto'} instead.")
        port = alt
    import server as srv
    httpd, runner = srv.create(port, fallback=True)
    port = httpd.server_address[1]
    query = "?present" + (f"&auto={args.auto}" if args.auto else "")
    hash_ = "#live" if args.live else (f"#{args.scene}" if args.scene else "")
    url = f"http://{HOST}:{port}/dashboard.html{query}{hash_}"
    print(f"\nMinnaAccess demo running: {url}")
    print(f"  Replay (stage backup): http://{HOST}:{port}/dashboard.html?present")
    print(f"  Live run + Try it yourself: http://{HOST}:{port}/dashboard.html#live")
    print("  Keys: Right/Left or PageDown/PageUp = scene, Space = autoplay, 1-4 chapters, L = Live/Replay, A/R = approve/reject. Ctrl+C to stop.")
    print("  Only the local mock portal is reachable from the agent; forms are never submitted.")
    try:
        if args.kiosk and not args.no_browser:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False, args=["--start-fullscreen", "--kiosk"])
                page = browser.new_page(no_viewport=True)
                page.goto(url)
                page.bring_to_front()
                page.wait_for_event("close", timeout=0)
                browser.close()
        else:
            if not args.no_browser:
                webbrowser.open(url)
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping…")
    finally:
        runner.stop()
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    main()
