#!/usr/bin/env python3
"""NimbusSeat control server: change server resolution/FPS at runtime.

GET /ping?key=...              -> pong (latency probe)
GET /status?key=...            -> current mode
GET /resize?w=&h=&fps=&key=... -> restart desktop stack in the new mode
"""
import json
import os
import subprocess
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

KEY = os.environ.get("CTL_KEY", "")
SCRIPT = os.environ.get("DESKTOP_SCRIPT", "/tmp/desktop.sh")
MODE_FILE = "/tmp/current_mode"


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
            mode = "unknown"
            if os.path.exists(MODE_FILE):
                mode = open(MODE_FILE).read().strip()
            return self._send(200, {"mode": mode})
        if u.path == "/resize":
            try:
                w = int(q["w"][0]); h = int(q["h"][0]); fps = int(q["fps"][0])
                assert 320 <= w <= 3840 and 240 <= h <= 2160 and 5 <= fps <= 120
            except (KeyError, ValueError, AssertionError):
                return self._send(400, {"error": "bad params"})
            subprocess.Popen(["bash", SCRIPT, str(w), str(h), str(fps)])
            return self._send(200, {"ok": True, "mode": f"{w}x{h}@{fps}"})
        return self._send(404, {"error": "not found"})


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 6082), H).serve_forever()
