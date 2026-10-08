import json
import socket
import threading
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
DEFAULT_PORT = 8765


class ExclusiveServer(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class QuietHandler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".js": "text/javascript; charset=utf-8",
                      ".css": "text/css; charset=utf-8", ".html": "text/html; charset=utf-8",
                      ".svg": "image/svg+xml", ".json": "application/json; charset=utf-8", ".csv": "text/csv; charset=utf-8"}

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args):
        pass

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            self.close_connection = True


def port_free(port, host=HOST):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        s.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def minna_server_on(port, host=HOST, timeout=1.5):
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/api/health", timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
            return data if data.get("app") == "minnaaccess" else None
    except Exception:
        return None


def serve(handler, port, host=HOST, fallback=True):
    candidates = [port] + ([0] if fallback else [])
    last = None
    for p in candidates:
        try:
            server = ExclusiveServer((host, p), handler)
        except OSError as exc:
            last = exc
            continue
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server
    raise OSError(f"port {port} on {host} is already in use ({last})")
