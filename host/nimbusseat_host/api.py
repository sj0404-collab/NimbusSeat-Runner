"""LAN-only REST API used by NimbusSeat clients (Android / desktop)."""
from __future__ import annotations

import logging
import time

from flask import Flask, jsonify, request

from .config import AppConfig
from .lan_guard import LanGuard
from .manager import HostManager

log = logging.getLogger("nimbusseat.api")


def create_app(manager: HostManager, config: AppConfig) -> Flask:
    app = Flask("nimbusseat")
    guard = LanGuard(config.network.lan_subnets)

    @app.before_request
    def lan_only():  # type: ignore[unused-variable]
        ip = request.remote_addr or ""
        if not guard.is_allowed(ip):
            return jsonify({"error": "LAN-only: access denied"}), 403
        return None

    @app.get("/api/v1/info")
    def info():
        return jsonify(
            {
                "name": config.host_name,
                "version": "0.1.0",
                "max_session_minutes": config.session.max_duration_minutes,
                "duo_web_ui": config.duo.web_ui,
                "moonlight_ports": config.duo.stream_ports,
                "server_time": time.time(),
            }
        )

    @app.get("/api/v1/status")
    def status():
        return jsonify(manager.status())

    @app.post("/api/v1/session/start")
    def start():
        ok, message = manager.start_session(request.remote_addr or "?")
        code = 200 if ok else 409
        return jsonify({"ok": ok, "message": message, **manager.status()}), code

    @app.post("/api/v1/session/stop")
    def stop():
        manager.stop_session(reason=f"client {request.remote_addr}")
        return jsonify({"ok": True, **manager.status()})

    @app.get("/api/v1/health")
    def health():
        return jsonify({"ok": True})

    return app
