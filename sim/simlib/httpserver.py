"""Stand-in for adafruit_httpserver on CPython (taken from the SolarLoader).

Built like the original: one non-blocking socket, served via poll(). So the
web server runs inside the same asyncio task as on the device, and the web
UI steals time from the other tasks just like in the field.

TLS is left out on purpose: the simulator speaks plain HTTP.
"""

import errno
import os
import socket
import traceback
from urllib.parse import parse_qsl, unquote_plus, urlsplit

from . import fs

PORT = 8080
MAX_PER_POLL = 12

_REASON = {200: "OK", 400: "Bad Request", 403: "Forbidden", 404: "Not Found",
           500: "Internal Server Error", 503: "Service Unavailable"}

_MIME = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8", ".json": "application/json",
    ".png": "image/png", ".txt": "text/plain; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
}


class ServerStoppedError(Exception):
    pass


class Params:
    """Dict-like like QueryParams in the original."""

    def __init__(self, pairs=()):
        self._d = {}
        for k, v in pairs:
            self._d.setdefault(k, v)

    def __contains__(self, k):
        return k in self._d

    def __getitem__(self, k):
        return self._d[k]

    def get(self, k, default=None):
        return self._d.get(k, default)


class Request:
    def __init__(self, method, path, query, headers, body):
        self.method = method
        self.path = path
        self.headers = headers
        self.body = body
        self.query_params = Params(parse_qsl(query, keep_blank_values=True))
        if "application/x-www-form-urlencoded" in headers.get("content-type", ""):
            self.form_data = Params(parse_qsl(body.decode("utf-8", "replace"),
                                              keep_blank_values=True))
        else:
            self.form_data = Params()


class Response:
    def __init__(self, request, body="", content_type="text/plain", status=200,
                 headers=None):
        self.request = request
        self.body = body
        self.content_type = content_type
        self.status = getattr(status, "code", status)
        self.headers = headers or {}

    def render(self):
        data = self.body
        if isinstance(data, str):
            data = data.encode("utf-8")
        elif data is None:
            data = b""
        return self.status, self.content_type, dict(self.headers), data


class FileResponse(Response):
    def __init__(self, request, filename="index.html", root_path="/", status=200,
                 content_type=None, headers=None):
        path = root_path.rstrip("/") + "/" + filename.lstrip("/")
        try:
            real = fs.dev(path)
            with open(real, "rb") as f:
                data = f.read()
            code = status
        except OSError:
            real, data, code = path, b"Not Found", 404
        ext = os.path.splitext(real)[1].lower()
        super().__init__(request, data,
                         content_type or _MIME.get(ext, "application/octet-stream"),
                         code, headers)


class ChunkedResponse(Response):
    """As in the original (4.8.x): body is a generator *function* that the
    library calls itself. Here everything is collected and sent at once."""

    def __init__(self, request, body, status=200, content_type="text/plain",
                 headers=None):
        parts = [p.encode("utf-8") if isinstance(p, str) else p for p in body()]
        super().__init__(request, b"".join(parts), content_type, status, headers)


class Server:
    def __init__(self, pool=None, root_path=None, https=False,
                 certfile=None, keyfile=None, debug=False):
        self.root_path = root_path
        self._routes = []
        self._sock = None

    def route(self, path, methods=None, **kw):
        allowed = methods or ["GET"]
        if isinstance(allowed, str):
            allowed = [allowed]

        def deco(fn):
            self._routes.append((path, [m.upper() for m in allowed], fn))
            return fn

        return deco

    def start(self, host="0.0.0.0", port=80):
        if self._sock is not None:
            return
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._sock.bind(("127.0.0.1", PORT))
        except OSError as e:
            raise SystemExit(f"\n[SIM] port {PORT} is busy ({e}).\n"
                             f"      Simulator still running?  pkill -f sim/run_sim.py\n")
        self._sock.listen(8)
        self._sock.setblocking(False)
        print(f"[SIM] web UI: http://127.0.0.1:{PORT}/")

    def stop(self):
        pass        # keep the socket; start() is idempotent

    def poll(self):
        if self._sock is None:
            raise ServerStoppedError()
        for _ in range(MAX_PER_POLL):
            try:
                conn, _addr = self._sock.accept()
            except (BlockingIOError, InterruptedError):
                return
            except OSError as e:
                if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    return
                return
            try:
                conn.setblocking(True)
                conn.settimeout(2.0)
                self._handle(conn)
            except Exception:
                pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    def _handle(self, conn):
        raw = b""
        while b"\r\n\r\n" not in raw:
            chunk = conn.recv(4096)
            if not chunk:
                return
            raw += chunk
        head, _, body = raw.partition(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        try:
            method, target, _ver = lines[0].split(" ", 2)
        except ValueError:
            return
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        want = int(headers.get("content-length", 0) or 0)
        while len(body) < want:
            chunk = conn.recv(min(65536, want - len(body)))
            if not chunk:
                break
            body += chunk

        split = urlsplit(target)
        request = Request(method.upper(), unquote_plus(split.path), split.query,
                          headers, body)
        status, ctype, extra, data = self._dispatch(request)
        out = [f"HTTP/1.1 {status} {_REASON.get(status, 'OK')}",
               f"Content-Type: {ctype}", f"Content-Length: {len(data)}",
               "Connection: close"]
        out += [f"{k}: {v}" for k, v in extra.items()]
        conn.sendall(("\r\n".join(out) + "\r\n\r\n").encode("latin-1") + data)

    def _dispatch(self, request):
        for path, methods, fn in self._routes:
            if path == request.path and request.method in methods:
                try:
                    result = fn(request)
                except Exception:
                    traceback.print_exc()
                    return 500, "text/plain", {}, b"handler error"
                if isinstance(result, Response):
                    return result.render()
                return 200, "text/plain", {}, str(result).encode("utf-8")
        if request.method == "GET" and self.root_path:
            return self._static(request.path)
        return 404, "text/plain", {}, b"Not Found"

    def _static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        try:
            real = fs.dev(self.root_path.rstrip("/") + path)
            base = os.path.realpath(fs.dev(self.root_path))
        except OSError:
            return 404, "text/plain", {}, b"Not Found"
        if not os.path.realpath(real).startswith(base):
            return 403, "text/plain", {}, b"Forbidden"
        try:
            with open(real, "rb") as f:
                data = f.read()
        except OSError:
            return 404, "text/plain", {}, b"Not Found"
        ext = os.path.splitext(real)[1].lower()
        return 200, _MIME.get(ext, "application/octet-stream"), {}, data
