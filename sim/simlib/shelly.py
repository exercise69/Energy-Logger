"""Shelly Plus Plug S model plus the simulator's control panel.

One small threaded HTTP server on port 8081:

    /rpc/<method>     what the device talks to (Shelly Gen2 RPC over HTTP GET)
    /                 control panel for a human
    /sim/state        JSON state for the tests
    /sim/api?action=  switches for the tests and the panel

The fields follow the Shelly Gen2 docs: sys.unixtime is UTC and null while
the Shelly has no time; sys.utc_offset is in *seconds*.
"""

import json
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlsplit

_real_time = time.time          # captured before the shims patch time.time


class Shelly:
    def __init__(self, load_w=60.0, has_time=False):
        self.lock = threading.Lock()
        self.output = True
        self.energy_wh = 1234.5
        self.load_w = load_w
        self.has_time = has_time
        self.time_offset = 0.0          # Sys.SetTime: offset to real UTC
        self._last = time.monotonic()

    def _step(self):
        now = time.monotonic()
        self.energy_wh += self.power() * (now - self._last) / 3600.0
        self._last = now

    def power(self):
        if not self.output:
            return 0.0
        return round(self.load_w * random.uniform(0.95, 1.05), 1)

    def rpc(self, method, params):
        with self.lock:
            self._step()
            if method == "Shelly.GetStatus":
                p = self.power()
                return {
                    "switch:0": {
                        "id": 0, "output": self.output, "apower": p,
                        "voltage": 231.4, "current": round(p / 231.4, 3),
                        "aenergy": {"total": round(self.energy_wh, 3)},
                        "temperature": {"tC": 31.2, "tF": 88.2},
                    },
                    "sys": {
                        "unixtime": (int(_real_time() + self.time_offset)
                                     if self.has_time else None),
                        "utc_offset": 7200,
                        "time": None,
                    },
                }
            if method == "Switch.Toggle":
                was_on = self.output
                self.output = not self.output
                return {"was_on": was_on}
            if method == "Sys.SetTime":
                self.time_offset = float(params.get("unixtime", _real_time())) - _real_time()
                self.has_time = True
                return None
        raise KeyError(method)


_PANEL = """<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Energy-Logger Simulator</title>
<style>body{font-family:system-ui;background:#222;color:#eee;padding:16px;max-width:760px;margin:auto}
button{margin:4px;padding:8px 14px;background:#00d1ff;border:0;border-radius:4px;font-weight:bold}
pre{background:#111;padding:10px;overflow:auto;font-size:.8rem}</style></head><body>
<h1>Energy-Logger Simulator</h1>
<p><a style="color:#00d1ff" href="http://127.0.0.1:{ui_port}/" target="_blank">Geräteoberfläche öffnen</a></p>
<div>
<button onclick="a('shelly_offline&v=1')">Shelly antwortet nicht</button>
<button onclick="a('shelly_offline&v=0')">Shelly antwortet</button>
<button onclick="a('wifi_off&v=1')">Shelly-WLAN aus</button>
<button onclick="a('wifi_off&v=0')">Shelly-WLAN an</button>
<button onclick="a('sd_remove')">SD-Karte ziehen</button>
<button onclick="a('sd_insert')">SD-Karte stecken</button>
<button onclick="a('sd_fail_after_write&n=3')">3 Schreibfehler nach dem Schreiben</button>
<button onclick="a('shelly_time&v=1')">Shelly hat Zeit</button>
<button onclick="a('load&w=2000')">Last 2000 W</button>
<button onclick="a('load&w=60')">Last 60 W</button>
</div>
<h2>Zustand</h2><pre id="s"></pre>
<script>
async function a(q){await fetch('/sim/api?action='+q);s()}
async function s(){const r=await fetch('/sim/state');document.getElementById('s').textContent=JSON.stringify(await r.json(),null,1)}
s();setInterval(s,2000);
</script></body></html>"""


def start(state, port, ui_port):
    shelly = state["shelly"]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            split = urlsplit(self.path)
            params = dict(parse_qsl(split.query))
            if split.path.startswith("/rpc/"):
                try:
                    result = shelly.rpc(split.path[5:], params)
                except KeyError:
                    return self._send(404, json.dumps({"code": 404, "message": "No handler"}))
                return self._send(200, json.dumps(result))
            if split.path == "/sim/state":
                return self._send(200, json.dumps(state["describe"]()))
            if split.path == "/sim/api":
                try:
                    state["action"](params.get("action"), params)
                except Exception as e:
                    return self._send(400, json.dumps({"ok": False, "error": str(e)}))
                return self._send(200, json.dumps({"ok": True}))
            if split.path == "/":
                return self._send(200, _PANEL.replace("{ui_port}", str(ui_port)),
                                  "text/html; charset=utf-8")
            self._send(404, "{}")

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
