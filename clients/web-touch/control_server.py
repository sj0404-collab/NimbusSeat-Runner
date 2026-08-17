#!/usr/bin/env python3
"""NimbusSeat control server.

GET /ping?key=                 -> latency probe
GET /status?key=               -> current display mode
GET /resize?w=&h=&fps=&key=    -> restart desktop in new mode
GET /app?name=&action=&key=    -> manage apps on the seat
       name: stk | chromium      action: stop | start | restart
"""
import json
import os
import subprocess
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

KEY = os.environ.get("CTL_KEY", "")
SCRIPT = os.environ.get("DESKTOP_SCRIPT", "/tmp/desktop.sh")
MODE_FILE = "/tmp/current_mode"


def mode():
    try:
        return open(MODE_FILE).read().strip()
    except OSError:
        return "1280x720@30"


def res():
    return mode().split("@")[0].split("x")


APPS = {
    "stk": {
        "stop": ["pkill", "-f", "supertuxkart"],
        "start": lambda: subprocess.Popen(
            ["supertuxkart", f"--screensize={res()[0]}x{res()[1]}", "--fullscreen"],
            env={**os.environ, "DISPLAY": ":99", "LIBGL_ALWAYS_SOFTWARE": "1",
                 "GALLIUM_DRIVER": "llvmpipe"},
            stdout=open("/tmp/stk.log", "ab"), stderr=subprocess.STDOUT),
    },
    "chromium": {
        "stop": ["pkill", "-f", "chrome-profile"],
        "start": lambda: subprocess.Popen(
            ["chromium-browser", "--no-sandbox", "--disable-gpu",
             f"--window-size={res()[0]},{res()[1]}", "--start-maximized",
             "--user-data-dir=/tmp/chrome-profile", "https://play.geforcenow.com"],
            env={**os.environ, "DISPLAY": ":99", "LIBGL_ALWAYS_SOFTWARE": "1"},
            stdout=open("/tmp/chrome.log", "ab"), stderr=subprocess.STDOUT),
    },
}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):  # noqa: N802
        pass

    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if KEY and q.get("key", [""])[0] != KEY:
            return self._send(403, {"error": "bad key"})
        if u.path == "/ping":
            return self._send(200, {"pong": True})
        if u.path == "/status":
            return self._send(200, {"mode": mode()})
        if u.path == "/resize":
            try:
                w = int(q["w"][0]); h = int(q["h"][0]); fps = int(q["fps"][0])
                assert 320 <= w <= 3840 and 240 <= h <= 2160 and 5 <= fps <= 120
            except (KeyError, ValueError, AssertionError):
                return self._send(400, {"error": "bad params"})
            subprocess.Popen(["bash", SCRIPT, str(w), str(h), str(fps)])
            return self._send(200, {"ok": True, "mode": f"{w}x{h}@{fps}"})
        if u.path == "/app":
            name = q.get("name", [""])[0]
            action = q.get("action", [""])[0]
            if name not in APPS or action not in ("stop", "start", "restart"):
                return self._send(400, {"error": "bad app/action"})
            app = APPS[name]
            if action in ("stop", "restart"):
                subprocess.run(app["stop"], check=False)
            if action in ("start", "restart"):
                import time as _t; _t.sleep(1)
                app["start"]()
            return self._send(200, {"ok": True, "app": name, "action": action})
        return self._send(404, {"error": "not found"})


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 6082), H).serve_forever()
