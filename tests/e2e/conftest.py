import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def base_url(request):
    port = free_port()
    log = (ROOT / ".cache").joinpath(f"{Path(request.module.__file__).stem}-server.log")
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as out:
        proc = subprocess.Popen([sys.executable, "-m", "ricebridge.server.app", "--port", str(port), "--replay"],
                                cwd=ROOT, stdout=out, stderr=subprocess.STDOUT)
        url = f"http://127.0.0.1:{port}"
        try:
            for _ in range(60):
                try:
                    with urllib.request.urlopen(url + "/api/health", timeout=1) as r:
                        if json.loads(r.read()).get("ok"):
                            break
                except OSError:
                    time.sleep(0.5)
            else:
                pytest.fail(f"server did not start; see {log}")
            yield url
        finally:
            proc.terminate()
            proc.wait(timeout=10)
