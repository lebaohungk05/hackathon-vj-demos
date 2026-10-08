import argparse
import json
import sys
import time
import urllib.request

import server as srv


def call(base, path, body=None):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"http": e.code, **json.loads(e.read())}


def drive(base, cfg, limit=900):
    call(base, "/api/live/start", cfg)
    since, t0 = 0, time.time()
    while time.time() - t0 < limit:
        s = call(base, f"/api/live/state?since={since}")
        since = s["next"]
        if s["pending"]:
            call(base, "/api/live/decision", {"approved": True, "run_id": s["run_id"]})
        if s["status"] in ("done", "stopped", "error"):
            return s
        time.sleep(0.4)
    call(base, "/api/live/stop", {})
    return {"status": "timeout"}


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Fill cache/ with LLM answers for every Try-it-yourself scenario (cache first, claude CLI when missing)")
    ap.add_argument("--port", type=int, default=8797)
    ap.add_argument("--only", choices=["vn", "jp"])
    args = ap.parse_args(argv)
    httpd, runner = srv.create(args.port, fallback=True)
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    opts = call(base, "/api/live/options")["barriers"]
    scenarios = [{"procedure": "vn", "form": "original"}, {"procedure": "jp", "form": "original"},
                 {"procedure": "vn", "form": "clean"}, {"procedure": "jp", "form": "clean"}]
    for key in ("vn", "jp"):
        for kind, targets in opts[key]["targets"].items():
            scenarios += [{"procedure": key, "form": "inject", "barrier": kind, "target": t["id"]} for t in targets]
    scenarios = [s for s in scenarios if not args.only or s["procedure"] == args.only]
    for i, cfg in enumerate(scenarios, 1):
        t0 = time.time()
        s = drive(base, {**cfg, "llm": "auto"})
        res = s.get("result") or {}
        calls = res.get("llm_calls", [])
        fresh = sum(c["source"] == "live" for c in calls)
        fails = sum(not c["ok"] for c in calls)
        print(f"[{i}/{len(scenarios)}] {cfg.get('procedure')} {cfg.get('form')} {cfg.get('barrier', '')} {cfg.get('target', '')}: "
              f"{s['status']} final={res.get('final')} found={res.get('found')} fixed={res.get('fixed')} "
              f"llm fresh={fresh} failed={fails} {time.time() - t0:.0f}s {s.get('error') or ''}", flush=True)
    call(base, "/api/live/reset", {})
    httpd.shutdown()


if __name__ == "__main__":
    main()
