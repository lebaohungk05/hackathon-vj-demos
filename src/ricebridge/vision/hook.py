import hashlib
import importlib.util
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

VISION_DIR = Path(__file__).resolve().parents[1] / "vision"
READER_PATH = VISION_DIR / "gauge_reader.py"
CONSISTENCY_PATH = VISION_DIR / "consistency.py"
TESTSET_DIR = VISION_DIR / "testset"
UPLOAD_DIR = VISION_DIR / "uploads"
GROUND_TRUTH = TESTSET_DIR / "ground_truth.json"
SYNTHETIC_NOTE = "synthetic test images"
BLOCKING_FLAGS = {"UNREADABLE_PHOTO", "STALE_PHOTO", "PHOTO_SUSPECT", "SOURCES_DISAGREE"}
MODULES = {}
LOAD_LOCK = threading.Lock()


def load_module(name, path):
    with LOAD_LOCK:
        if name in MODULES:
            return MODULES[name]
        if not path.exists():
            return None
        if str(VISION_DIR) not in sys.path:
            sys.path.insert(0, str(VISION_DIR))
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        MODULES[name] = module
        return module


CANCEL = {"epoch": 0, "at": 0.0, "procs": set()}
CANCEL_WINDOW_S = 3.0


def cancel_vision():
    CANCEL["epoch"] += 1
    CANCEL["at"] = time.time()
    for proc in list(CANCEL["procs"]):
        if proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass


def running_vision():
    return len(CANCEL["procs"])


def cancellable_ask(reader):
    def ask_claude(image_path, timeout=90):
        if time.time() - CANCEL["at"] < CANCEL_WINDOW_S:
            raise RuntimeError("vision call skipped by presenter")
        epoch = CANCEL["epoch"]
        cmd = [reader.claude_executable(), "-p", "--model", reader.MODEL, "--allowedTools", "Read", "--output-format", "json",
               "--strict-mcp-config", "--no-session-persistence", "--disable-slash-commands"]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        CANCEL["procs"].add(proc)
        try:
            out, err = proc.communicate(reader.PROMPT.format(path=Path(image_path).as_posix()), timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise RuntimeError(f"vision call timed out after {timeout} s")
        finally:
            CANCEL["procs"].discard(proc)
        if CANCEL["epoch"] != epoch:
            raise RuntimeError("vision call skipped by presenter")
        if proc.returncode != 0:
            raise RuntimeError(f"claude CLI exit {proc.returncode}: {(err or '')[-300:]}")
        envelope = json.loads(out)
        if envelope.get("is_error"):
            raise RuntimeError(f"claude CLI error: {envelope.get('result')}")
        return envelope.get("result", "")
    return ask_claude


def empty(reason, image_path=None):
    return {"reading_cm": None, "confidence": 0.0, "reason": reason, "engine": "none", "captured_at": None, "flags": [],
            "sha256": file_digest(image_path) if image_path and Path(image_path).exists() else None}


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_consistency(reading_cm, captured_at, context, confidence):
    try:
        consistency = load_module("consistency", CONSISTENCY_PATH)
    except Exception:
        consistency = None
    if consistency is None:
        return {"photo_usable": reading_cm is not None, "flags": []}
    return consistency.check_photo(reading_cm, captured_at, context.get("sensor_cm"), context.get("water_balance_cm"),
                                   context.get("latest_rain_at"), context.get("submitted_at"), confidence)


def read_gauge_photo(image_path, replay=False, context=None):
    if image_path is None or not Path(image_path).exists():
        return empty("no image file for this event")
    try:
        reader = load_module("gauge_reader", READER_PATH)
    except Exception as exc:
        return empty(f"vision module failed to load: {exc}", image_path)
    if reader is None or not callable(getattr(reader, "read_gauge_photo", None)):
        return empty("vision module not installed", image_path)
    if callable(getattr(reader, "ask_claude", None)) and hasattr(reader, "PROMPT") and not getattr(reader, "cancellable", False):
        reader.ask_claude = cancellable_ask(reader)
        reader.cancellable = True
    try:
        out = reader.read_gauge_photo(str(image_path), replay=replay)
    except Exception as exc:
        return empty(f"vision module error: {exc}", image_path)
    value = out.get("reading_cm")
    result = {"reading_cm": None if value is None else float(value), "confidence": float(out.get("confidence") or 0.0),
              "reason": str(out.get("reason", "")), "captured_at": out.get("captured_at"), "source": out.get("source"),
              "llm_seconds": out.get("llm_seconds"), "model": getattr(reader, "MODEL", "vision model"),
              "engine": "vision" if value is not None else "none", "flags": [], "photo_usable": None,
              "sha256": file_digest(image_path)}
    if context is not None:
        check = check_consistency(result["reading_cm"], result["captured_at"], context, result["confidence"])
        result.update(flags=check["flags"], photo_usable=check["photo_usable"])
    return result


def testset():
    try:
        truth = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))["images"]
    except (OSError, ValueError, KeyError):
        truth = [{"file": p.name} for p in sorted(TESTSET_DIR.glob("*.jpg"))]
    return [{"file": t["file"], "truth_cm": t.get("truth_cm"), "captured_at": t.get("captured_at"), "hero": bool(t.get("hero")),
             "synthetic": True} for t in truth if (TESTSET_DIR / t["file"]).exists()]
