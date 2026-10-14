import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
CACHE_DIR = HERE / "cache"
MODEL = "claude-sonnet-5-5"
READING_RANGE = (-40.0, 30.0)

PROMPT = """Use the Read tool to open the image file at: {path}

The photo shows a perforated AWD water gauge tube (pani pipe) in a rice field, with a printed cm scale.
The 0 mark is the soil surface. Positive numbers are above the soil, negative numbers are below.
Find where the water surface sits on the scale and read it in cm, to one decimal place.

Reply with ONLY one JSON object, no prose and no code fence:
{{"reading_cm": <number>, "confidence": <number 0..1>, "reason": "<one or two short sentences: which marks you used>"}}
If the scale or the water line cannot be seen, use "reading_cm": null and a low confidence."""


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_capture_time(path):
    with Image.open(path) as img:
        exif = img.getexif()
        stamp = exif.get_ifd(0x8769).get(0x9003) or exif.get(0x0132)
    if not stamp:
        return None
    try:
        return datetime.strptime(str(stamp).strip("\x00 "), "%Y:%m:%d %H:%M:%S").isoformat()
    except ValueError:
        return None


def extract_json(text):
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        raise ValueError("no JSON object in model output")
    return json.loads(match.group(0))


def validate(payload):
    reading = payload.get("reading_cm")
    confidence = float(payload.get("confidence", 0))
    reason = str(payload.get("reason", "")).strip()
    if reading is not None:
        reading = float(reading)
        if not READING_RANGE[0] <= reading <= READING_RANGE[1]:
            raise ValueError(f"reading {reading} outside plausible range")
    if not 0 <= confidence <= 1:
        raise ValueError("confidence outside 0..1")
    return {"reading_cm": reading, "confidence": confidence, "reason": reason}


def claude_executable():
    return shutil.which("claude") or shutil.which("claude.cmd") or "claude"


def ask_claude(image_path, timeout=180):
    cmd = [claude_executable(), "-p", "--model", MODEL, "--allowedTools", "Read", "--output-format", "json"]
    proc = subprocess.run(cmd, input=PROMPT.format(path=image_path.as_posix()), capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI exit {proc.returncode}: {proc.stderr[-300:]}")
    envelope = json.loads(proc.stdout)
    if envelope.get("is_error"):
        raise RuntimeError(f"claude CLI error: {envelope.get('result')}")
    return envelope.get("result", "")


def read_with_llm(image_path, attempts=2):
    errors = []
    for _ in range(attempts):
        try:
            return validate(extract_json(ask_claude(image_path))), errors
        except (ValueError, RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
            errors.append(str(exc))
    return None, errors


def cache_path(digest):
    return CACHE_DIR / f"{digest}.json"


def read_gauge_photo(image_path, replay=False):
    image_path = Path(image_path).resolve()
    digest = file_sha256(image_path)
    captured_at = read_capture_time(image_path)
    cached = cache_path(digest)
    if cached.exists():
        record = json.loads(cached.read_text(encoding="utf-8"))
        return {**record["result"], "captured_at": captured_at, "source": "cache", "llm_seconds": record.get("llm_seconds")}
    if replay:
        return {"reading_cm": None, "confidence": 0.0, "reason": "replay mode: no cached reading for this image", "captured_at": captured_at, "source": "replay-miss", "llm_seconds": None}
    started = time.perf_counter()
    result, errors = read_with_llm(image_path)
    elapsed = round(time.perf_counter() - started, 2)
    if result is None:
        return {"reading_cm": None, "confidence": 0.0, "reason": "LLM failed: " + " | ".join(errors)[-300:], "captured_at": captured_at, "source": "error", "llm_seconds": elapsed}
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps({"file": image_path.name, "model": MODEL, "llm_seconds": elapsed, "retries": len(errors), "result": result}, indent=2, ensure_ascii=False), encoding="utf-8")
    return {**result, "captured_at": captured_at, "source": "llm", "llm_seconds": elapsed}


def main():
    parser = argparse.ArgumentParser(description="Read an AWD gauge photo with Claude vision")
    parser.add_argument("image")
    parser.add_argument("--replay", action="store_true", help="use cache only, never call the model")
    sys.stdout.reconfigure(encoding="utf-8")
    args = parser.parse_args()
    print(json.dumps(read_gauge_photo(args.image, replay=args.replay), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
