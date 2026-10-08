import functools
import json
import shutil
import sys
import threading
import time
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import barriers
from agent import (AXE, VIEWPORT, Recorder, Run, Workspace, build_proc_data, compare, make_guard, quiet, run_axe)
from engine import LLMEngine
from llm import HAIKU, SONNET, Cancelled, ClaudeCLI, find_claude
from netutil import DEFAULT_PORT, HOST, QuietHandler, serve
from procedures import PROCEDURES
from translate import LiveTranslator

ROOT = Path(__file__).resolve().parent
PORTAL = ROOT / "portal"
SANDBOX = PORTAL / "sandbox"
SANDBOX_STAGING = PORTAL / "sandbox_staging"
CACHE = ROOT / "cache"
RUNS = ROOT / "runs"
LIVE_RUNS = RUNS / "live"
LIVE_CACHE = RUNS / "llm_cache"
VERSION = "2026-10-06"
MAX_BODY = 64 * 1024
MODE_TEXT = {"live": "live Claude calls", "auto": "cache first, live Claude call when missing", "replay": "cached replies (offline)"}


def chromium_ok():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            return Path(p.chromium.executable_path).exists()
    except Exception:
        return False


def health_info(chromium=None):
    run_data = ROOT / "out" / "run_data.js"
    return {
        "app": "minnaaccess", "version": VERSION,
        "claude_cli": bool(find_claude()), "claude_path": find_claude() or "",
        "chromium": chromium, "axe": AXE.exists(), "replay_data": run_data.exists(),
        "rule_baseline": (ROOT / "out_rule" / "run_data.js").exists(),
        "cache_entries": len(list(CACHE.glob("*.json"))) + len(list(LIVE_CACHE.glob("*.json"))) if LIVE_CACHE.exists() else len(list(CACHE.glob("*.json"))),
        "fonts": (ROOT / "fonts" / "fonts.css").exists(),
    }


def restore_sandbox():
    for key in PROCEDURES:
        barriers.prepare(SANDBOX, key, "original")
    shutil.rmtree(SANDBOX_STAGING, ignore_errors=True)


class LiveRunner:
    def __init__(self, port):
        self.port = port
        self.lock = threading.RLock()
        self.decided = threading.Event()
        self.thread = None
        self.chromium = None
        self._reset_state()
        self.prepared = None

    def _reset_state(self):
        self.status = "idle"
        self.run_id = None
        self.config = None
        self.events = []
        self.pending = None
        self.decision = None
        self.result = None
        self.error = None
        self.llm_busy = None
        self.cancel_flag = False
        self.client = None
        self.started = None
        self.finished = None

    def emit(self, kind, text="", **extra):
        with self.lock:
            ev = {"n": len(self.events), "kind": kind, "text": text, "t": round(time.time(), 2), **extra}
            self.events.append(ev)
            return ev

    def state(self, since=0):
        with self.lock:
            return {
                "status": self.status, "run_id": self.run_id, "config": self.config, "prepared": self.prepared,
                "events": self.events[since:], "next": len(self.events), "pending": self.pending,
                "result": self.result, "error": self.error, "llm_busy": self.llm_busy,
                "elapsed": round((self.finished or time.time()) - self.started, 1) if self.started else 0,
            }

    def busy(self):
        return self.thread is not None and self.thread.is_alive()

    def prepare(self, cfg):
        with self.lock:
            if self.busy():
                raise RuntimeError("A run is in progress. Stop or reset it first.")
            return self._prepare(cfg)

    def _prepare(self, cfg):
        key = cfg["procedure"]
        injected = barriers.prepare(SANDBOX, key, cfg["form"], cfg.get("barrier"), cfg.get("target"))
        shutil.rmtree(SANDBOX_STAGING / key, ignore_errors=True)
        self.prepared = {"procedure": key, "form": cfg["form"], "injected": injected, "at": time.time()}
        return self.prepared

    def start(self, cfg):
        with self.lock:
            if self.busy():
                raise RuntimeError("A run is already in progress. Stop or reset it first.")
            self._reset_state()
            self.prepare(cfg)
            self.run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
            self.config = cfg
            self.status = "starting"
            self.started = time.time()
            self.decided.clear()
            self.thread = threading.Thread(target=self._run, args=(cfg, self.run_id), daemon=True)
            self.thread.start()
        return self.run_id

    def stop(self):
        with self.lock:
            self.cancel_flag = True
            client = self.client
            self.decided.set()
        if client:
            client.cancel()

    def reset(self):
        self.stop()
        if self.thread is not None:
            self.thread.join(timeout=15)
        with self.lock:
            if self.busy():
                raise RuntimeError("The previous run is still shutting down. Try Reset again in a few seconds.")
            self._reset_state()
            restore_sandbox()
            self.prepared = {"procedure": None, "form": "original", "injected": None, "at": time.time()}

    def decide(self, approved, run_id=None, seq=None):
        with self.lock:
            if (self.pending is None or self.decision is not None or self.cancel_flag
                    or (run_id and run_id != self.run_id)
                    or (seq is not None and seq != self.pending["seq"])):
                return False
            self.decision = (bool(approved), "presenter (web UI button)")
            self.decided.set()
            return True

    def _approve(self, pending):
        with self.lock:
            self.pending = {**pending, "run_id": self.run_id, "seq": len(self.events)}
            self.decision = None
            self.status = "waiting"
            self.decided.clear()
        while not self.decided.wait(0.25):
            if self.cancel_flag:
                break
        with self.lock:
            decision, self.pending = self.decision, None
            if self.cancel_flag or decision is None:
                raise Cancelled()
            self.status = "running"
        return decision

    def _on_call(self, phase, purpose="", model="", ok=None, ms=0, error=""):
        with self.lock:
            if phase == "start":
                self.llm_busy = {"purpose": purpose, "model": model, "since": time.time()}
                self.emit("llm_start", f"Calling {model} ({purpose})", purpose=purpose, model=model)
            else:
                self.llm_busy = None
                self.emit("llm_end", f"{model} answered in {ms / 1000:.1f} s" if ok else f"{model} failed: {error[:160]}",
                          purpose=purpose, model=model, ok=ok, ms=ms, error=error[:300])

    def _record(self, ev):
        if ev["kind"] == "tree":
            return
        self.emit("agent", ev["text"], ev=ev)

    def _run(self, cfg, run_id):
        out_dir = LIVE_RUNS / run_id
        key = cfg["procedure"]
        proc = PROCEDURES[key]
        log_lines = []
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(SANDBOX / key, out_dir / "start" / key)
            mode = cfg.get("llm") if cfg.get("llm") in ("live", "auto") else "replay"
            if mode in ("live", "auto") and not find_claude():
                self.emit("warning", "Claude CLI not found on this machine: using cached LLM answers, then the rule engine.")
                mode = "replay"
            with self.lock:
                self.config = {**cfg, "llm_effective": mode}
            LIVE_CACHE.mkdir(parents=True, exist_ok=True)
            if mode == "auto":
                client = ClaudeCLI("auto", CACHE, timeout=int(cfg.get("timeout", 120)), read_dirs=[LIVE_CACHE], on_call=self._on_call)
            elif mode == "live":
                client = ClaudeCLI("live", LIVE_CACHE, timeout=int(cfg.get("timeout", 90)), read_dirs=[CACHE], on_call=self._on_call)
            else:
                client = ClaudeCLI("replay", CACHE, read_dirs=[LIVE_CACHE], on_call=self._on_call)
            with self.lock:
                self.client = client
                if self.cancel_flag:
                    raise Cancelled()
            injected = self.prepared and self.prepared.get("injected")
            what = f" with a planted barrier ({injected['label']}, WCAG {injected['sc']})" if injected else (
                " (original mock with the planted barriers)" if cfg["form"] == "original" else " (clean form)")
            self.emit("info", f"Starting Chromium for {proc.title}{what}. LLM answers: {MODE_TEXT[mode]}.")
            ws = Workspace(base=f"http://{HOST}:{self.port}", walk_dir=SANDBOX, walk_url="portal/sandbox",
                           staging_dir=SANDBOX_STAGING, staging_url="portal/sandbox_staging")
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    ctx = browser.new_context(locale=proc.lang, viewport=VIEWPORT)
                    ctx.route("**/*", make_guard(HOST))
                    page = ctx.new_page()
                    engine = LLMEngine(client, proc, HAIKU, SONNET)
                    rec = Recorder(proc, ws, listener=self._record)
                    with self.lock:
                        self.status = "running"
                    run = Run(ctx, page, proc, engine, rec, self._approve, lambda: None, ws, log=log_lines.append,
                              cancelled=lambda: self.cancel_flag, pace=float(cfg.get("pace", 0)))
                    final = run.run()
                    submitted = page.evaluate("() => document.body.dataset.submitted || 'no'")
                    axe = None
                    if run.barriers:
                        self.emit("info", "Running axe-core 4.10.2 on the same starting pages for comparison.")
                        axe_start = run_axe(page, ws, proc, f"runs/live/{run_id}/start")
                        rows, extra = compare(proc, run.barriers, axe_start)
                        axe = {"comparison": rows, "axe_only": extra}
                    ctx.close()
                finally:
                    browser.close()
            data = build_proc_data(proc, run, rec, final, submitted, axe)
            data["events"] = [e for e in data["events"] if e["kind"] != "tree"]
            summary = {
                "final": final, "submitted": submitted, "attempts": data["rounds"],
                "found": len(run.barriers), "fixed": sum(b["status"] == "fixed" for b in run.barriers),
                "handoff": sum(b["status"] == "handoff" for b in run.barriers),
                "rejected": sum(b["status"] == "rejected" for b in run.barriers),
                "barriers": run.barriers, "advisories": run.advisories, "audit": data["audit"], "axe": axe,
                "llm_calls": client.summary(), "llm_mode": mode, "folder": f"runs/live/{run_id}",
                "reached": data["reached_confirmation"],
            }
            record = {"run_id": run_id, "config": self.config, "prepared": self.prepared, "procedure": data, "summary": summary,
                      "generated": datetime.now().isoformat(timespec="seconds")}
            (out_dir / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
            with self.lock:
                self.result = summary
                self.status = "done"
                self.finished = time.time()
            self.emit("done", f"Run finished: {final}", summary=summary)
        except Cancelled:
            with self.lock:
                self.status = "stopped"
                self.finished = time.time()
            self.emit("stopped", "Run stopped by the presenter. Nothing was submitted.")
        except Exception as exc:
            detail = traceback.format_exc()
            try:
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "error.txt").write_text(detail, encoding="utf-8")
            except OSError:
                pass
            print(detail, file=sys.stderr)
            message = friendly_error(exc)
            with self.lock:
                self.status = "error"
                self.error = message
                self.finished = time.time()
            self.emit("error", message)
        finally:
            with self.lock:
                self.llm_busy = None
                self.pending = None
            try:
                (out_dir / "agent_log.txt").write_text("\n".join(log_lines), encoding="utf-8")
            except OSError:
                pass


def friendly_error(exc):
    text = str(exc)
    if "Executable doesn't exist" in text or "playwright install" in text:
        return "Chromium for Playwright is not installed. Run: python -m playwright install chromium"
    if "axe" in text and "No such file" in text:
        return "axe-core file missing (../sim/vendor/axe.min.js)."
    return f"The agent stopped with an internal error ({type(exc).__name__}). Details are in runs/live/…/error.txt. The replay mode still works."


class ApiHandler(QuietHandler):
    runner: LiveRunner = None
    translator: LiveTranslator = None

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            self.close_connection = True

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 <= length <= MAX_BODY:
            raise ValueError("Request body is too large or has an invalid length.")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw or b"{}")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError("Request body must be valid JSON.") from exc
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object.")
        return data

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/health":
            return self._json(health_info(self.runner.chromium))
        if url.path == "/api/live/options":
            return self._json({"procedures": {k: {"key": k, "title": p.title, "country": p.country, "lang": p.lang, "steps": p.steps,
                                                  "step_names": p.step_names, "goal": p.goal, "standard": p.standard}
                                              for k, p in PROCEDURES.items()},
                               "barriers": barriers.options(), "health": health_info(self.runner.chromium)})
        if url.path == "/api/live/state":
            since = parse_qs(url.query).get("since", ["0"])[0]
            return self._json(self.runner.state(int(since) if since.isdigit() else 0))
        if url.path.startswith("/api/"):
            return self._json({"error": "unknown endpoint"}, 404)
        return super().do_GET()

    def do_POST(self):
        url = urlparse(self.path)
        try:
            body = self._body()
            if url.path == "/api/live/prepare":
                if self.runner.busy():
                    return self._json({"error": "A run is in progress. Stop or reset it first."}, 409)
                return self._json({"prepared": self.runner.prepare(validate_config(body))})
            if url.path == "/api/live/start":
                run_id = self.runner.start(validate_config(body))
                return self._json({"run_id": run_id})
            if url.path == "/api/live/decision":
                if not isinstance(body.get("approved"), bool):
                    raise ValueError("approved must be true or false")
                ok = self.runner.decide(body["approved"], body.get("run_id"), body.get("seq"))
                return self._json({"accepted": ok}, 200 if ok else 409)
            if url.path == "/api/live/stop":
                self.runner.stop()
                return self._json({"stopping": True})
            if url.path == "/api/translate":
                items = body.get("items") if isinstance(body.get("items"), list) else []
                found, pending = self.translator.lookup([i for i in items[:60] if isinstance(i, dict)], body.get("lang"))
                return self._json({"translations": found, "pending": pending})
            if url.path == "/api/live/reset":
                self.runner.reset()
                return self._json({"reset": True, "state": self.runner.state()})
        except ValueError as exc:
            return self._json({"error": str(exc)}, 400)
        except RuntimeError as exc:
            return self._json({"error": str(exc)}, 409)
        except Exception as exc:
            traceback.print_exc()
            return self._json({"error": f"server error: {type(exc).__name__}: {exc}"[:300]}, 500)
        return self._json({"error": "unknown endpoint"}, 404)


def validate_config(body):
    key = body.get("procedure")
    if key not in PROCEDURES:
        raise ValueError("procedure must be vn or jp")
    form = body.get("form", "original")
    if form not in ("original", "clean", "inject"):
        raise ValueError("form must be original, clean or inject")
    cfg = {"procedure": key, "form": form, "llm": body.get("llm") if body.get("llm") in ("live", "auto") else "cached",
           "pace": max(0.0, min(float(body.get("pace", 0) or 0), 1.0))}
    if form == "inject":
        opts = barriers.options()[key]
        kind = body.get("barrier") or "unnamed_field"
        if kind not in barriers.KINDS:
            raise ValueError("unknown barrier")
        target = body.get("target") or opts["defaults"][kind]
        if target not in {t["id"] for t in opts["targets"][kind]}:
            raise ValueError("unknown target for this barrier")
        cfg.update(barrier=kind, target=target)
    return cfg


def create(port=DEFAULT_PORT, fallback=False):
    restore_sandbox()
    RUNS.mkdir(exist_ok=True)
    runner = LiveRunner(port)
    handler = type("Handler", (ApiHandler,), {"runner": runner, "translator": LiveTranslator()})
    server = serve(functools.partial(handler, directory=str(ROOT)), port, fallback=fallback)
    runner.port = server.server_address[1]
    threading.Thread(target=lambda: setattr(runner, "chromium", chromium_ok()), daemon=True).start()
    return server, runner
