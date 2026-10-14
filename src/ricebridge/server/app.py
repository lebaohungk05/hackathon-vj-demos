import argparse
import base64
import copy
import hashlib
import json
import mimetypes
import sys
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import i18n
import translate
import vision_hook
import weather_source
from engine import EVENTS, FIELD_IDS, SENDERS, DemoError, Demo
from i18n import tr
from llm import CALL_TIMEOUT_S, cli_version

WEB_DIR = Path(__file__).resolve().parents[1] / "web"
MEDIA_DIRS = (vision_hook.TESTSET_DIR, vision_hook.UPLOAD_DIR)
MAX_BODY_BYTES = 12 * 1024 * 1024
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
IMAGE_MAGIC = {b"\xff\xd8\xff": ".jpg", b"\x89PNG": ".png"}
JOB_WAIT_S = 0.6
RESET_WAIT_S = 20


def message_of(exc):
    return getattr(exc, "t", None) or i18n.lit(str(exc))


class Busy(RuntimeError):
    def __init__(self, job):
        super().__init__(job["label"])
        self.job = job


def log_error(context):
    sys.stderr.write(f"ERROR in {context}\n{traceback.format_exc()}\n")
    sys.stderr.flush()


class Runtime:
    def __init__(self, demo, cli):
        self.demo = demo
        self.cli = cli
        self.mutate = threading.RLock()
        self.slot = threading.Lock()
        self.job = None
        self.side = {}
        self.version = 0
        self.published = "{}"
        self.forecast = None
        self.store = translate.Store()
        self.missing = {}
        self.translating = False
        demo.progress_hook = self.on_progress
        with self.mutate:
            self.publish()

    def publish(self):
        # Translation is a presentation concern; never mutate source evidence or
        # change cache keys in the running engine through shared nested objects.
        snap = copy.deepcopy(self.demo.snapshot())
        missing = {}
        translate.fill(snap, self.store, missing)
        self.missing = missing
        self.version += 1
        snap["version"] = self.version
        self.published = json.dumps(snap, ensure_ascii=False, default=str)

    def maybe_translate(self):
        if self.translating or not self.missing or self.demo.client.mode not in ("auto", "live") or not self.demo.client.binary:
            return
        self.translating = True
        items = dict(self.missing)
        self.spawn_side("translate", tr("job.translate"), self.translate_worker, items)

    def translate_worker(self, items):
        try:
            translate.translate_all(self.demo.client, self.store, items, log=lambda m: sys.stderr.write(f"[translate] {m}\n"), workers=2)
        finally:
            self.translating = False

    def on_progress(self, text):
        job = self.job
        if job and job["status"] == "running" and job["thread"] is threading.current_thread():
            text_t = text if isinstance(text, dict) else i18n.lit(text)
            job["stage"] = text_t["en"]
            job["stage_t"] = text_t
            job["stages"].append({"text": text_t["en"], "at": round(time.time() - job["started"], 1)})

    def job_view(self, job):
        if not job:
            return None
        end = job.get("finished") or time.time()
        return {"id": job["id"], "kind": job["kind"], "label": job["label"], "label_t": job["label_t"], "stage": job["stage"],
                "stage_t": job.get("stage_t") or job["label_t"], "status": job["status"],
                "elapsed_s": round(end - job["started"], 1), "error": job["error"], "error_t": job.get("error_t"), "stages": job["stages"][-6:]}

    def live(self):
        now = time.time()
        return {"job": self.job_view(self.job),
                "side_jobs": [{"id": k, "kind": v["kind"], "label": v["label"]["en"], "label_t": v["label"], "elapsed_s": round(now - v["started"], 1)}
                              for k, v in list(self.side.items())],
                "llm_running": self.demo.client.status(), "vision_running": vision_hook.running_vision(),
                "server": {"cli": self.cli, "mode": self.demo.client.mode, "timeout_s": CALL_TIMEOUT_S}}

    def state_json(self, since=None):
        live = json.dumps(self.live(), ensure_ascii=False, default=str)
        busy = (self.job and self.job["status"] == "running") or self.side
        if since is not None and since == self.version and not busy:
            return '{"unchanged":true,"version":' + str(self.version) + ',"live":' + live + "}"
        return '{"live":' + live + "," + self.published[1:]

    def start_job(self, kind, label_t, fn):
        with self.slot:
            if self.job and self.job["status"] == "running":
                raise Busy(self.job)
            job = {"id": uuid.uuid4().hex[:8], "kind": kind, "label": label_t["en"], "label_t": label_t, "stage": label_t["en"], "status": "running", "error": None,
                   "started": time.time(), "finished": None, "done": threading.Event(), "stages": [], "thread": None}
            thread = threading.Thread(target=self.run_job, args=(job, fn), daemon=True)
            job["thread"] = thread
            self.job = job
        thread.start()
        job["done"].wait(JOB_WAIT_S)
        return job

    def run_job(self, job, fn):
        try:
            with self.mutate:
                try:
                    fn()
                finally:
                    self.publish()
            job["status"] = "done"
        except DemoError as exc:
            job["status"], job["error"], job["error_t"] = "error", str(exc), message_of(exc)
        except Exception as exc:
            log_error(f"job {job['kind']}")
            message = tr("err.internal_job", kind=type(exc).__name__)
            job["status"], job["error"], job["error_t"] = "error", message["en"], message
        finally:
            job["finished"] = time.time()
            job["done"].set()
            self.spawn_briefs()
            self.maybe_translate()

    def spawn_briefs(self):
        with self.mutate:
            jobs = self.demo.take_deferred()
        for item in jobs:
            self.spawn_side("brief", tr("job.brief", id=item["plan"]["id"]), self.brief_worker, item)

    def spawn_side(self, kind, label, target, item):
        key = uuid.uuid4().hex[:8]
        self.side[key] = {"kind": kind, "label": label, "started": time.time()}

        def runner():
            try:
                target(item)
            except Exception:
                log_error(f"side job {kind}")
            finally:
                with self.mutate:
                    self.publish()
                self.side.pop(key, None)
                if kind != "translate":
                    self.maybe_translate()
        threading.Thread(target=runner, daemon=True).start()

    def brief_worker(self, item):
        if item["epoch"] != self.demo.epoch:
            return
        brief = self.demo.interpreter.plan_brief(item["payload"])
        entry = self.demo.client.last
        with self.mutate:
            if item["epoch"] == self.demo.epoch:
                self.demo.apply_brief(item["plan"], brief, item["trace"], item["focus"], entry)

    def whatif_brief_worker(self, item):
        out, payload = item
        brief = self.demo.interpreter.plan_brief(payload)
        entry = self.demo.client.last
        with self.mutate:
            if self.demo.whatif is out:
                headline_t = brief.get("headline_t") if brief.get("engine") == "llm" else dict(out["plan"]["summary_t"])
                out["brief"] = {"headline_en": brief["headline_en"], "headline_vi": brief["headline_vi"], "explain_en": brief.get("explain_en", ""),
                                "headline_t": headline_t, "explain_t": brief.get("explain_t") or i18n.lit(""),
                                "engine": brief.get("engine"), "model": brief.get("model"), "ms": brief.get("ms", 0), "source": brief.get("source"),
                                "fallback_reason": brief.get("fallback_reason"), "fallback_t": brief.get("fallback_t")}
                if entry and entry.get("task") == "plan_brief":
                    out["trace"].append(entry)

    def cancel(self):
        n = self.demo.client.cancel_all()
        vision_hook.cancel_vision()
        return n

    def reset(self):
        self.cancel()
        deadline = time.time() + RESET_WAIT_S
        while not self.mutate.acquire(timeout=0.5):
            self.cancel()
            if time.time() > deadline:
                raise DemoError(tr("err.reset_wait"))
        try:
            self.demo.reset()
            self.publish()
        finally:
            self.mutate.release()
        with self.slot:
            if self.job and self.job["status"] == "running":
                self.job["status"] = "cancelled"
        self.spawn_briefs()


def resolve_image(name):
    name = unquote(str(name or ""))
    if name.startswith("upload:"):
        base, rel = vision_hook.UPLOAD_DIR, name[len("upload:"):]
    else:
        base, rel = vision_hook.TESTSET_DIR, name
    target = (base / rel).resolve()
    if base.resolve() not in target.parents or not target.is_file():
        raise DemoError(tr("err.unknown_photo"))
    return target


class Handler(BaseHTTPRequestHandler):
    runtime = None

    def log_message(self, fmt, *args):
        pass

    def send_body(self, body, content_type, status=200, extra=None):
        data = body.encode("utf-8") if isinstance(body, str) else body
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def send_json(self, payload, status=200):
        body = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, default=str)
        self.send_body(body, "application/json; charset=utf-8", status)

    def fail(self, status, error, message, **extra):
        message_t = message if isinstance(message, dict) else i18n.lit(message)
        self.send_json({"ok": False, "error": error, "message": message_t["en"], "message_t": message_t, **extra}, status)

    def do_GET(self):
        try:
            self.route_get()
        except DemoError as exc:
            self.fail(400, "bad_request", message_of(exc))
        except Exception:
            log_error(f"GET {self.path}")
            self.fail(500, "internal", tr("err.internal"))

    def do_POST(self):
        try:
            self.route_post()
        except Busy as exc:
            rt = self.runtime
            view = rt.job_view(exc.job)
            self.fail(409, "busy", tr("err.busy", label=view["label_t"], s=f"{view['elapsed_s']:.0f}"), job=view)
        except DemoError as exc:
            self.fail(400, "bad_request", message_of(exc))
        except Exception:
            log_error(f"POST {self.path}")
            self.fail(500, "internal", tr("err.internal"))

    def route_get(self):
        url = urlparse(self.path)
        path, query = url.path, parse_qs(url.query)
        rt = self.runtime
        if path == "/api/state":
            since = query.get("since", [None])[0]
            return self.send_json(rt.state_json(int(since) if since and since.isdigit() else None))
        if path == "/api/health":
            return self.send_json({"ok": True, "mode": rt.demo.client.mode, "cli": rt.cli, "version": rt.version})
        if path == "/api/testset":
            return self.send_json({"ok": True, "images": vision_hook.testset(), "note": "SYNTHETIC images from vision/make_testset.py"})
        if path == "/api/evidence.csv":
            with rt.mutate:
                csv = rt.demo.evidence_csv()
            return self.send_body("\ufeff" + csv, "text/csv; charset=utf-8",
                                  extra={"Content-Disposition": "attachment; filename=ricebridge_evidence_log.csv"})
        if path == "/api/evidence.json":
            with rt.mutate:
                payload = json.dumps(rt.demo.evidence_json(), ensure_ascii=False, indent=1, default=str)
            return self.send_body(payload, "application/json; charset=utf-8",
                                  extra={"Content-Disposition": "attachment; filename=ricebridge_evidence_log.json"})
        if path == "/api/verify":
            with rt.mutate:
                result = rt.demo.verify_chain(tamper=query.get("tamper", ["0"])[0] == "1")
            return self.send_json({"ok": True, **result})
        if path == "/api/forecast":
            if rt.forecast is None or time.time() - rt.forecast[0] > 600:
                rt.forecast = (time.time(), weather_source.forecast(timeout=4))
            return self.send_json(rt.forecast[1])
        if path.startswith("/media/"):
            target = resolve_image(path[len("/media/"):])
            return self.send_static(target)
        rel = "index.html" if path == "/" else unquote(path).lstrip("/")
        target = (WEB_DIR / rel).resolve()
        if WEB_DIR.resolve() not in target.parents or not target.is_file():
            return self.fail(404, "not_found", tr("err.not_found_page", path=path))
        return self.send_static(target)

    def send_static(self, target):
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if target.suffix == ".woff2":
            content_type = "font/woff2"
        if content_type.startswith("text/") or content_type.endswith("javascript"):
            content_type += "; charset=utf-8"
        self.send_body(target.read_bytes(), content_type)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError as exc:
            raise DemoError(tr("err.bad_json")) from exc
        if length < 0:
            raise DemoError(tr("err.bad_json"))
        if length > MAX_BODY_BYTES:
            raise DemoError(tr("err.too_large"))
        raw = self.rfile.read(length) if length else b""
        if not raw.strip():
            return {}
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise DemoError(tr("err.bad_json")) from exc
        if not isinstance(body, dict):
            raise DemoError(tr("err.not_object"))
        return body

    def job_reply(self, job):
        view = self.runtime.job_view(job)
        if job["status"] == "error":
            return self.send_json({"ok": False, "error": "failed", "message": job["error"], "message_t": job.get("error_t"), "job": view}, 200)
        return self.send_json({"ok": True, "pending": job["status"] == "running", "job": view}, 202 if job["status"] == "running" else 200)

    def route_post(self):
        path = urlparse(self.path).path
        body = self.read_json()
        rt, demo = self.runtime, self.runtime.demo
        if path == "/api/reset":
            rt.reset()
            return self.send_json({"ok": True, "version": rt.version})
        if path == "/api/cancel":
            n = rt.cancel()
            message = tr("err.cancelled")
            return self.send_json({"ok": True, "cancelled": n, "message": message["en"], "message_t": message})
        if path == "/api/next":
            if demo.step + 1 >= len(EVENTS):
                return self.fail(400, "end", tr("err.end"))
            return self.job_reply(rt.start_job("next", tr("job.next"), demo.next_event))
        if path == "/api/goto":
            step = body.get("step", -1)
            if isinstance(step, bool) or not isinstance(step, int):
                raise DemoError(tr("err.step_int"))
            return self.job_reply(rt.start_job("goto", tr("job.goto", n=step + 1), lambda: demo.goto(step)))
        if path == "/api/message":
            sender, text = body.get("sender"), body.get("text")
            if not isinstance(text, str) or not text.strip():
                raise DemoError(tr("err.type_message"))
            if sender not in SENDERS:
                raise DemoError(tr("err.unknown_sender"))
            return self.job_reply(rt.start_job("message", tr("job.message", who=i18n.person(sender)), lambda: demo.post_message(sender, text)))
        if path == "/api/decision":
            decision = body.get("decision")
            if decision not in ("approve", "reject"):
                raise DemoError(tr("err.decision"))

            def decide():
                if (("plan_id" in body and (not demo.plan or body["plan_id"] != demo.plan["id"]))
                        or ("epoch" in body and body["epoch"] != demo.epoch)):
                    raise DemoError(tr("err.stale_plan"))
                if not demo.decide(decision, body.get("note", "")):
                    raise DemoError(tr("err.no_plan"))
            return self.job_reply(rt.start_job("decision", tr("job.decision"), decide))
        if path == "/api/whatif":
            return self.job_reply(self.start_whatif(body))
        if path == "/api/whatif/clear":
            def clear():
                demo.whatif = None
            return self.job_reply(rt.start_job("whatif_clear", tr("job.whatif_clear"), clear))
        if path == "/api/upload":
            return self.send_json(self.save_upload(body))
        return self.fail(404, "not_found", tr("err.not_found_action", path=path))

    def start_whatif(self, body):
        rt, demo = self.runtime, self.runtime.demo
        kind = body.get("kind")
        params = body.get("params") or {}
        if kind not in ("rain", "flowering", "pump", "photo") or not isinstance(params, dict):
            raise DemoError(tr("err.unknown_whatif"))
        if demo.plan is None:
            raise DemoError(tr("err.press_next"))
        image = None
        if kind == "photo":
            if params.get("fid") not in FIELD_IDS:
                raise DemoError(tr("err.choose_field"))
            image = resolve_image(params.get("image"))
            params["image_label"] = image.name if image.parent == vision_hook.TESTSET_DIR.resolve() else "uploaded photo"

        def run():
            vision = None
            if image is not None:
                demo.progress(tr("p.vision"))
                vision = vision_hook.read_gauge_photo(image, replay=demo.vision_replay)
                vision["image"] = params.get("image")
            demo.progress(tr("p.sandbox"))
            out, payload = demo.what_if(kind, params, vision)
            rt.spawn_side("whatif_brief", tr("job.whatif_brief"), rt.whatif_brief_worker, (out, payload))
        return rt.start_job("whatif", tr("wi.kind." + kind), run)

    def save_upload(self, body):
        data = body.get("data")
        if not isinstance(data, str) or not data:
            raise DemoError(tr("err.no_photo_data"))
        if "," in data[:100]:
            data = data.split(",", 1)[1]
        try:
            raw = base64.b64decode(data, validate=True)
        except (ValueError, TypeError) as exc:
            raise DemoError(tr("err.bad_base64")) from exc
        if len(raw) > MAX_UPLOAD_BYTES:
            raise DemoError(tr("err.photo_size"))
        ext = next((e for magic, e in IMAGE_MAGIC.items() if raw.startswith(magic)), None)
        if ext is None:
            raise DemoError(tr("err.photo_type"))
        vision_hook.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        name = hashlib.sha256(raw).hexdigest()[:16] + ext
        (vision_hook.UPLOAD_DIR / name).write_bytes(raw)
        return {"ok": True, "image": f"upload:{name}", "bytes": len(raw)}


def build_server(port, llm_mode, refresh_weather=False, host="127.0.0.1"):
    demo = Demo(refresh_weather=refresh_weather, llm_mode=llm_mode)
    cli = {"found": bool(demo.client.binary), "version": cli_version() if demo.client.binary and llm_mode != "rules" else None}
    Handler.runtime = Runtime(demo, cli)
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server, demo, cli


def main():
    parser = argparse.ArgumentParser(description="RiceBridge Ops live demo server")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--refresh-weather", action="store_true", help="re-download Open-Meteo data instead of using the cache")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_const", dest="llm", const="live", help="always call the Claude CLI and refresh the cache")
    mode.add_argument("--replay", action="store_const", dest="llm", const="replay", help="offline stage mode: cached LLM replies only, rule fallback on a miss")
    mode.add_argument("--rules", action="store_const", dest="llm", const="rules", help="no LLM at all, deterministic rules only")
    mode.add_argument("--auto", action="store_const", dest="llm", const="auto", help="default: cached reply if present, otherwise call the Claude CLI")
    parser.set_defaults(llm="auto")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    server, demo, cli = build_server(args.port, args.llm, args.refresh_weather)
    print(f"RiceBridge Ops demo on http://127.0.0.1:{args.port}  (LLM mode: {args.llm}; Claude CLI: {cli['version'] or 'not found'}; weather cache: {demo.weather_meta['cache_file']})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
