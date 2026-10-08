import argparse
import functools
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

import agent
from agent import Recorder, Run, Workspace, build_proc_data, color, compare, make_guard, run_axe, write_jis_csv
from engine import LLMEngine, RuleBasedEngine
from llm import HAIKU, SONNET, ClaudeCLI
from netutil import DEFAULT_PORT, HOST, QuietHandler, serve
from procedures import PROCEDURES

ROOT = Path(__file__).resolve().parent
PORTAL = ROOT / "portal"
ORIGINAL = PORTAL / "original"
LIVE = PORTAL / "live"
STAGING = PORTAL / "staging"
FIXED = PORTAL / "fixed"
CACHE = ROOT / "cache"
METRICS = ROOT.parent / "sim" / "out" / "test" / "metrics.json"
VIDEO_PATHS = {}


def make_approver(mode):
    def approve(pending):
        if mode == "auto":
            print(color("    [--approve auto] patch approved for recording", "dim"))
            return True, "developer (auto-approve, recording mode)"
        answer = input(color("    Approve this patch? [y/N] ", "yellow")).strip().lower()
        return answer in ("y", "yes"), "developer (CLI prompt)"
    return approve


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="MinnaAccess recorded run on local mock portals (Vietnam + Japan). For the web UI use: python start_demo.py")
    ap.add_argument("--engine", choices=["llm", "rule"], default="llm")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--replay", action="store_true", help="answer every LLM call from demo/cache only (offline, deterministic)")
    mode.add_argument("--live", action="store_true", help="call the claude CLI for every decision (cached answer only if the call fails)")
    ap.add_argument("--approve", choices=["cli", "auto"], default="cli")
    ap.add_argument("--auto-approve", action="store_true", help="same as --approve auto")
    ap.add_argument("--only", choices=list(PROCEDURES), action="append")
    ap.add_argument("--model", default=HAIKU)
    ap.add_argument("--patch-model", default=SONNET)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--slow", type=int, default=60)
    ap.add_argument("--video-dir")
    ap.add_argument("--out", help="output folder (default out/, or out_rule/ with --engine rule)")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help="local port for the mock portal; a free port is used if it is taken")
    args = ap.parse_args(argv)
    approve_mode = "auto" if args.auto_approve else args.approve
    llm_mode = "replay" if args.replay else "live" if args.live else "auto"

    out = Path(args.out).resolve() if args.out else ROOT / ("out_rule" if args.engine == "rule" else "out")
    frames = out / "frames"
    try:
        frames_url = out.relative_to(ROOT).as_posix() + "/frames"
    except ValueError:
        frames_url = "frames"
    for d in (LIVE, STAGING, FIXED, out):
        shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(ORIGINAL, LIVE)
    frames.mkdir(parents=True)
    server = serve(functools.partial(QuietHandler, directory=str(ROOT)), args.port)
    port = server.server_address[1]
    if port != args.port:
        print(color(f"Port {args.port} is busy (is start_demo.py running?). The mock portal is served on port {port} for this run.", "yellow"))
    ws = Workspace(base=f"http://{HOST}:{port}", walk_dir=LIVE, walk_url="portal/live", staging_dir=STAGING,
                   staging_url="portal/staging", frames_dir=frames, frames_url=frames_url)
    client = ClaudeCLI(llm_mode, CACHE)
    if llm_mode != "replay" and args.engine == "llm" and not client.available:
        print(color("claude CLI not found: every LLM decision falls back to the cache, then to the rule engine.", "yellow"))
    procs = [PROCEDURES[k] for k in (args.only or list(PROCEDURES))]
    started = time.time()
    results = {}
    engine_name = "rule-based (deterministic)" if args.engine == "rule" else f"LLM: {args.model} (decisions) + {args.patch_model} (patches), rule fallback"

    def assemble(final_parts=None):
        return {
            "generated": datetime.now().isoformat(timespec="seconds"),
            "engine": engine_name, "engine_kind": args.engine, "llm_mode": llm_mode, "approve_mode": approve_mode,
            "models": {"decisions": args.model, "patches": args.patch_model} if args.engine == "llm" else None,
            "procedures": [results[k]() if callable(results[k]) else results[k] for k in results],
            "llm_calls": client.summary(),
            "sim_metrics": json.loads(METRICS.read_text(encoding="utf-8")) if METRICS.exists() else None,
            "runtime_seconds": round(time.time() - started, 1),
            "complete": bool(final_parts),
        }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=args.headless, slow_mo=args.slow)
            opts = {"viewport": agent.VIEWPORT, "device_scale_factor": 1.5}
            if args.video_dir:
                opts["record_video_dir"] = args.video_dir
                opts["record_video_size"] = dict(agent.VIEWPORT)
            for proc in procs:
                ctx = browser.new_context(locale=proc.lang, **opts)
                ctx.route("**/*", make_guard(HOST))
                page = ctx.new_page()
                engine = RuleBasedEngine(proc) if args.engine == "rule" else LLMEngine(client, proc, args.model, args.patch_model)
                rec = Recorder(proc, ws)
                run = Run(ctx, page, proc, engine, rec, make_approver(approve_mode), lambda: None, ws)
                results[proc.key] = functools.partial(build_proc_data, proc, run, rec)
                final = run.run()
                submitted = page.evaluate("() => document.body.dataset.submitted || 'no'")
                print(color(f"\n=== [{proc.key.upper()}] axe-core 4.10.2 on the same pages ===", "cyan"))
                axe_original = run_axe(page, ws, proc, "portal/original")
                axe_fixed = run_axe(page, ws, proc, "portal/live")
                ctx.close()
                if args.video_dir and page.video:
                    VIDEO_PATHS[proc.key] = Path(page.video.path())
                cmp_rows, axe_extra = compare(proc, run.barriers, axe_original)
                for r in cmp_rows:
                    print(f"  step {r['step']} WCAG {r['sc']:6} #{r['element']:10} agent=YES  axe={'YES ' + ','.join(r['axe_rules']) if r['axe'] else 'no'}")
                for x in axe_extra:
                    print(f"  step {x['step']} axe-only: {x['rule']} ({x['impact']}) {x['target']}")
                axe = {"original": axe_original, "fixed": axe_fixed, "comparison": cmp_rows, "axe_only": axe_extra,
                       "fixed_violations": sum(len(v) for v in axe_fixed.values())}
                results[proc.key] = build_proc_data(proc, run, rec, final, submitted, axe)
                write_jis_csv(proc, results[proc.key]["audit"], out / f"jis_shiken_kekka_{proc.key}.csv")
                shutil.copytree(LIVE / proc.key, FIXED / proc.key)
                print(color(f"[{proc.key.upper()}] final: {final}; attempts={results[proc.key]['rounds']}; submitted={submitted}; "
                            f"barriers={len(run.barriers)}; patches applied={len(run.patches)}", "green"))
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    shutil.rmtree(STAGING, ignore_errors=True)
    data = assemble(True)
    (out / "run.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "run_data.js").write_text(("window.RULE_BASELINE = " if args.engine == "rule" else "window.RUN = ") + json.dumps(data, ensure_ascii=False) + ";", encoding="utf-8")
    calls = data["llm_calls"]
    if calls:
        print(color("\n=== LLM calls ===", "cyan"))
        for c in calls:
            print(f"  {c['purpose']:16} {c['model']:28} {c['source']:11} ok={c['ok']!s:5} {c['ms']:6} ms tries={c['tries']} {c['error'][:60]}")
    print(color(f"\nDone in {data['runtime_seconds']} s. Output: {out}. Web UI: python start_demo.py", "green"))


if __name__ == "__main__":
    main()
