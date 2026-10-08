import hashlib
import json
import shutil
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-5-5"


def find_claude():
    found = shutil.which("claude")
    if found:
        exe = Path(found).parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        if exe.exists():
            return str(exe)
    return found


class Cancelled(Exception):
    pass


class InfraError(RuntimeError):
    pass


@dataclass
class CallRecord:
    purpose: str
    model: str
    source: str
    ok: bool
    ms: int
    tries: int
    key: str
    error: str = ""
    at: str = ""


class ClaudeCLI:
    def __init__(self, mode, cache_dir, timeout=180, read_dirs=None, on_call=None):
        self.mode = mode
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.read_dirs = [self.cache_dir] + [Path(d) for d in (read_dirs or []) if Path(d) != self.cache_dir]
        self.timeout = timeout
        self.exe = find_claude()
        self.calls = []
        self.on_call = on_call or (lambda *a, **k: None)
        self._proc = None
        self._lock = threading.Lock()
        self.cancelled = False

    @property
    def available(self):
        return bool(self.exe)

    def cancel(self):
        self.cancelled = True
        with self._lock:
            proc = self._proc
        if proc and proc.poll() is None:
            proc.kill()

    def _key(self, model, system, prompt, schema):
        blob = json.dumps([model, system, prompt, schema], ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]

    def _invoke(self, model, system, prompt, schema):
        if not self.exe:
            raise InfraError("claude CLI not found on PATH")
        cmd = [self.exe, "-p", "--model", model, "--output-format", "json", "--tools", "",
               "--system-prompt", system, "--json-schema", json.dumps(schema)]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", cwd=str(self.cache_dir), creationflags=flags)
        except OSError as exc:
            raise InfraError(f"cannot start claude CLI: {exc}") from exc
        with self._lock:
            self._proc = proc
        try:
            out, err = proc.communicate(prompt, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise InfraError(f"claude CLI did not answer within {self.timeout} s")
        finally:
            with self._lock:
                self._proc = None
        if self.cancelled:
            raise Cancelled()
        if proc.returncode != 0:
            raise InfraError(f"claude exited {proc.returncode}: {(err or out)[-300:]}")
        envelope = json.loads(out)
        if envelope.get("is_error"):
            raise InfraError(str(envelope.get("result"))[:300])
        obj = envelope.get("structured_output")
        if obj is None:
            text = (envelope.get("result") or "").strip().strip("`")
            text = text[text.find("{"): text.rfind("}") + 1]
            obj = json.loads(text)
        return obj

    def _cached(self, key, validate):
        for folder in self.read_dirs:
            path = folder / f"{key}.json"
            if path.exists():
                try:
                    cached = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if validate(cached["output"]) is None:
                    return cached
        return None

    def _from_cache(self, purpose, model, key, cached, note=""):
        rec = CallRecord(purpose, model, "cache", True, cached.get("ms", 0), cached.get("tries", 1), key,
                         note, at=cached.get("created", ""))
        self.calls.append(rec)
        return cached["output"], rec

    def ask(self, purpose, model, system, prompt, schema, validate=None):
        key = self._key(model, system, prompt, schema)
        validate = validate or (lambda o: None)
        cached = self._cached(key, validate)
        if self.mode != "live" and cached:
            return self._from_cache(purpose, model, key, cached)
        if self.mode == "replay":
            rec = CallRecord(purpose, model, "replay-miss", False, 0, 0, key, "no cached answer for this prompt in replay mode")
            self.calls.append(rec)
            return None, rec
        started, tries, error, current = time.time(), 0, "", prompt
        self.on_call("start", purpose=purpose, model=model)
        for tries in (1, 2):
            if self.cancelled:
                raise Cancelled()
            infra = False
            try:
                obj = self._invoke(model, system, current, schema)
                error = validate(obj) or ""
            except Cancelled:
                raise
            except InfraError as exc:
                obj, error, infra = None, str(exc)[:400], True
            except Exception as exc:
                obj, error = None, f"{type(exc).__name__}: {exc}"[:400]
            if obj is not None and not error:
                ms = int((time.time() - started) * 1000)
                created = datetime.now().isoformat(timespec="seconds")
                path = self.cache_dir / f"{key}.json"
                if not path.exists():
                    path.write_text(json.dumps({"purpose": purpose, "model": model, "ms": ms, "tries": tries, "created": created,
                                                "prompt": prompt, "output": obj}, ensure_ascii=False, indent=1), encoding="utf-8")
                rec = CallRecord(purpose, model, "live", True, ms, tries, key, at=created)
                self.calls.append(rec)
                self.on_call("end", purpose=purpose, model=model, ok=True, ms=ms)
                return obj, rec
            if infra:
                break
            current = (prompt + "\n\nYour previous answer was rejected by the validator: " + error +
                       "\nReturn a corrected JSON object that follows the schema exactly.")
        ms = int((time.time() - started) * 1000)
        self.on_call("end", purpose=purpose, model=model, ok=False, ms=ms, error=error)
        if cached:
            return self._from_cache(purpose, model, key, cached, f"live call failed, cached answer used: {error[:120]}")
        rec = CallRecord(purpose, model, "live", False, ms, tries, key, error)
        self.calls.append(rec)
        return None, rec

    def summary(self):
        return [asdict(c) for c in self.calls]
