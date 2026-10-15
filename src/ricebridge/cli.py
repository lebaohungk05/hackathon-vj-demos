import argparse
import json
import socket
import sys
import threading
import urllib.request
import webbrowser

from .paths import LOG_PATH, RUNTIME_DIR


class Tee:
    def __init__(self, stream, path):
        self.stream = stream
        self.file = open(path, "a", encoding="utf-8")
        self.lock = threading.Lock()

    def write(self, text):
        with self.lock:
            self.stream.write(text)
            self.file.write(text)
            self.file.flush()
        return len(text)

    def flush(self):
        self.stream.flush()
        self.file.flush()


def port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def existing_demo(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as r:
            return json.loads(r.read()).get("ok")
    except (OSError, ValueError):
        return False


def check(label, ok, detail):
    print(f"  [{'OK' if ok else '!!'}] {label}: {detail}")
    return ok


def preflight(mode):
    print("RiceBridge Ops · pre-flight")
    ok = check("Python", sys.version_info >= (3, 10), sys.version.split()[0])
    try:
        from . import engine  # noqa: F401
        check("Simulation package ricebridge.sim", True, "water balance, crop stages, pump capacity loaded")
    except Exception as exc:
        check("Simulation package ricebridge.sim", False, f"{exc}")
        return False, None
    from . import weather_source
    from .llm.client import CACHE_DIR, cli_version, find_cli
    from .paths import I18N_DIR, VISION_CACHE_DIR
    check("Weather cache", weather_source.CACHE_PATH.exists(), weather_source.CACHE_PATH.name)
    llm_cache = len(list(CACHE_DIR.glob("*.json")))
    vision_cache = len(list(VISION_CACHE_DIR.glob("*.json")))
    check("LLM reply cache", llm_cache > 0, f"{llm_cache} cached replies (scenario + 5 sample messages answer instantly, offline)")
    check("Vision cache", vision_cache > 0, f"{vision_cache} cached gauge readings (28 synthetic test images)")
    tx_path = I18N_DIR / "translations.json"
    tx_count = len(json.loads(tx_path.read_text(encoding="utf-8"))) if tx_path.exists() else 0
    check("Translation cache", tx_count > 0, f"{tx_count} JA/VI/EN translations of cached LLM text (offline)")
    version = cli_version() if find_cli() else None
    if mode == "auto" and not version:
        check("Claude CLI", False, "not found or not logged in → switching to --replay (cache + rules, fully offline)")
        mode = "replay"
    else:
        check("Claude CLI", bool(version) or mode in ("replay", "rules"), version or f"not needed in --{mode}")
    try:
        import playwright  # noqa: F401
        check("Playwright (tests, video)", True, "installed")
    except ImportError:
        check("Playwright (tests, video)", True, "not installed; only needed for tests/e2e/run_e2e.py and scripts/capture.py")
    return ok, mode


def main():
    parser = argparse.ArgumentParser(description="Start the RiceBridge Ops demo with one command")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--mode", choices=["auto", "replay", "live", "rules"], default="auto",
                        help="auto = cache first, Claude CLI on a miss (default); replay = offline stage mode")
    parser.add_argument("--stage", action="store_true", help="same as --mode replay: no network at all")
    parser.add_argument("--open", action="store_true", help="open the browser")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    mode = "replay" if args.stage else args.mode
    ok, mode = preflight(mode)
    if not ok:
        print("Pre-flight failed. Fix the item marked !! and run again.")
        return 1
    url = f"http://127.0.0.1:{args.port}"
    if port_in_use(args.port):
        if existing_demo(args.port):
            print(f"\nA RiceBridge demo is already running on {url} . Open it, or stop it first (Ctrl+C in its window).")
            return 0
        print(f"\nPort {args.port} is used by another program. Try: python -m ricebridge --port 8777")
        return 1
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    sys.stderr = Tee(sys.stderr, LOG_PATH)
    from .server.app import build_server
    server, demo, cli = build_server(args.port, mode)
    print(f"\n  RiceBridge Ops is running:  {url}")
    print(f"  LLM mode: {mode} · Claude CLI: {cli['version'] or 'not used'} · log: {LOG_PATH.name}")
    print("  Stage keys: → next · ← back · C carbon · J language EN/JA/VI · E story or engineering view · M message · W what-if · R reset · F11 full screen")
    print("  Stop with Ctrl+C.\n", flush=True)
    if args.open:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
