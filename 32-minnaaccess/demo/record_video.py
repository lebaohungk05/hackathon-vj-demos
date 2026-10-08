import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

import run_demo

ROOT = Path(__file__).resolve().parent
VIDEO = ROOT / "video"
SIZE = {"width": 1920, "height": 1080}


def record_agent(slow):
    raw = VIDEO / "_raw_agent"
    shutil.rmtree(raw, ignore_errors=True)
    run_demo.main(["--replay", "--auto-approve", "--headless", "--slow", str(slow), "--video-dir", str(raw)])
    names = []
    for key, clip in run_demo.VIDEO_PATHS.items():
        out = VIDEO / f"agent_run_{key}.webm"
        shutil.move(str(clip), out)
        names.append(out)
    shutil.rmtree(raw, ignore_errors=True)
    return names


def record_dashboard(seconds):
    raw = VIDEO / "_raw_dash"
    shutil.rmtree(raw, ignore_errors=True)
    import server as srv
    server, _ = srv.create(8766, fallback=True)
    port = server.server_address[1]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport=SIZE, record_video_dir=str(raw), record_video_size=SIZE)
        page = ctx.new_page()
        page.goto(f"http://127.0.0.1:{port}/dashboard.html?present&auto={seconds}")
        page.wait_for_function("window.appReady === true")
        n = page.evaluate("scenes.length")
        page.wait_for_function("window.autoDone === true", timeout=int((n + 2) * seconds * 1000))
        page.wait_for_timeout(int(seconds * 1000))
        ctx.close()
        browser.close()
    server.shutdown()
    out = VIDEO / "dashboard_walkthrough.webm"
    shutil.move(str(next(raw.glob("*.webm"))), out)
    shutil.rmtree(raw, ignore_errors=True)
    return out, n


def to_mp4(parts, out):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("ffmpeg not found: WebM files only")
        return None
    inputs, filters = [], []
    for i, part in enumerate(parts):
        inputs += ["-i", str(part)]
        filters.append(f"[{i}:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x0d1a2e,setsar=1,fps=25[v{i}]")
    graph = ";".join(filters) + ";" + "".join(f"[v{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=0[out]"
    cmd = [ffmpeg, "-y", "-loglevel", "error", *inputs, "-filter_complex", graph, "-map", "[out]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium", str(out)]
    subprocess.run(cmd, check=True)
    return out


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Record the stage backup video (replay mode, offline)")
    ap.add_argument("--slow", type=int, default=120, help="slow-motion delay per browser action in the agent clip (ms)")
    ap.add_argument("--scene-seconds", type=float, default=7)
    ap.add_argument("--dashboard-only", action="store_true", help="keep out/ and the agent clips, re-record only the dashboard walkthrough")
    args = ap.parse_args(argv)
    VIDEO.mkdir(exist_ok=True)
    agent = sorted(VIDEO.glob("agent_run_*.webm"), key=lambda f: 0 if f.stem.endswith("vn") else 1) if args.dashboard_only else record_agent(args.slow)
    dash, n = record_dashboard(args.scene_seconds)
    full = to_mp4([*agent, dash], VIDEO / "minnaaccess_demo_full.mp4")
    walk = to_mp4([dash], VIDEO / "dashboard_walkthrough.mp4")
    for f in [*agent, dash, full, walk]:
        if f:
            print(f"{f}  {f.stat().st_size / 1e6:.1f} MB")
    print(f"dashboard scenes: {n} x {args.scene_seconds} s")


if __name__ == "__main__":
    main()
