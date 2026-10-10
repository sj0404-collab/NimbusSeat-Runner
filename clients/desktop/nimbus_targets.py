#!/usr/bin/env python3
"""Targets and session-schema helpers for the NimbusSeat clients.

A "target" is one remote seat: a GitHub repo, the workflow that launches it,
the dispatch inputs, and where its live session descriptor lives. Keeping that
as data - instead of a hardcoded repo/workflow/branch - is what lets one client
hang off ANY repo and runner: its own NimbusSeat-Runner, a `zen-panel` screen,
a fork, a mirror.

Only the standard library is used, and nothing here imports tkinter, so the
module can be unit-tested on a headless runner and reused by CLI tools.

Two session layouts are understood, without any per-repo wiring:

  * NimbusSeat   -> branch ``live``            file ``session.json``
                    {state: live|offline, url: <nimbus.html?...>}
  * zen-panel    -> branch ``session-state``   file ``live/session-vnc.json``
                    {kind: Linux-VNC, url: <.../vnc.html>, novncUrl: ...}

Anything that carries a browser URL is accepted; the state falls back to
"live when a URL is present" so a publisher that never writes ``state`` (like
zen-panel's VNC slot) still shows up.
"""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from pathlib import Path

GH = "https://api.github.com"

NIMBUS_WORKFLOW = "remote-seat.yml"

# Keys a session descriptor may use for the address the client should open, in
# preference order. Both "novncUrl" (zen-panel) and "novnc" (NimbusSeat) are
# covered, plus a plain "url"/"web"/"desktop" from any future publisher.
URL_KEYS = ("url", "novncUrl", "novnc", "web", "desktop", "hubUrl")

# Two built-in targets so a fresh install can pick either without typing
# anything. Only repo/token are tied to an account; editing the name/token in
# the UI (or MIGRATION.md) moves the whole thing to a new mirror.
DEFAULT_TARGETS = [
    {
        "name": "NimbusSeat",
        "repo": "sj0404-collab/NimbusSeat-Runner",
        "workflow": NIMBUS_WORKFLOW,
        "inputs": {"minutes": "340", "resolution": "1280x720", "fps": "30"},
        "session": {"branch": "live", "path": "session.json"},
    },
    {
        "name": "zen-panel screen",
        "repo": "sj0404-collab/zen-panel",
        "workflow": "hub.yml",
        "inputs": {"os": "linux", "label": "panel"},
        "session": {"branch": "session-state", "path": "live/session-vnc.json"},
    },
]


def extract_url(data) -> str | None:
    """First http(s) address a session descriptor advertises, or None."""
    if not isinstance(data, dict):
        return None
    for key in URL_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    return None


def normalize_session(data) -> dict:
    """Flatten any supported session descriptor into one stable shape.

    ``live`` is the only field callers must trust; the rest are best-effort.
    A descriptor with an explicit non-"live" state (e.g. zen-panel's "ended")
    is never treated as live even if a stale URL is still present.
    """
    if not isinstance(data, dict):
        return {"live": False, "state": "offline", "url": None, "raw": {}}
    url = extract_url(data)
    state = data.get("state")
    if not state:
        state = "live" if url else "offline"
    return {
        "live": state == "live" and bool(url),
        "state": str(state),
        "url": url,
        "novnc": data.get("novncUrl") or data.get("novnc") or data.get("web") or url,
        "kind": data.get("kind") or data.get("type") or "",
        "label": data.get("label") or "",
        "resolution": data.get("resolution") or "",
        "fps": data.get("fps"),
        "ends_at_utc": data.get("ends_at_utc") or data.get("endsAtUtc") or "",
        "password": data.get("password") or "",
        "raw": data,
    }


def _normalize_target(target: dict) -> dict:
    target = dict(target or {})
    target.setdefault("name", target.get("repo", "seat"))
    target.setdefault("repo", "")
    target.setdefault("workflow", NIMBUS_WORKFLOW)
    target.setdefault("token", "")
    inputs = target.get("inputs")
    target["inputs"] = dict(inputs) if isinstance(inputs, dict) else {}
    session = target.get("session")
    if not isinstance(session, dict):
        session = {}
    session.setdefault("branch", "live")
    session.setdefault("path", "session.json")
    target["session"] = session
    return target


def migrate_config(raw) -> dict:
    """Upgrade every config shape to {"token", "targets": [...], "active"}.

    Accepts the legacy {"repo", "token"} single-seat file, the current
    {"targets": [...], "active", "token"} file, and an empty/missing file
    (falls back to the built-in targets).
    """
    raw = raw if isinstance(raw, dict) else {}
    token = raw.get("token", "") or ""

    if isinstance(raw.get("targets"), list) and raw["targets"]:
        targets = [_normalize_target(t) for t in raw["targets"]]
    elif raw.get("repo"):
        legacy = dict(DEFAULT_TARGETS[0])
        legacy["repo"] = raw["repo"]
        if raw.get("workflow"):
            legacy["workflow"] = raw["workflow"]
        if isinstance(raw.get("session"), dict):
            legacy["session"] = raw["session"]
        targets = [_normalize_target(legacy)]
    else:
        targets = [_normalize_target(dict(t)) for t in DEFAULT_TARGETS]

    names = [t["name"] for t in targets]
    active = raw.get("active")
    if active not in names:
        active = names[0] if names else ""
    return {"token": token, "targets": targets, "active": active}


def load_config(path: Path | str) -> dict:
    path = Path(path)
    if path.is_file():
        try:
            return migrate_config(json.loads(path.read_text()))
        except (ValueError, OSError):
            pass
    return migrate_config({})


def save_config(path: Path | str, config: dict) -> None:
    Path(path).write_text(json.dumps(config, ensure_ascii=False, indent=2))


def find_target(config: dict, name: str | None = None) -> dict | None:
    targets = config.get("targets") or []
    if not targets:
        return None
    wanted = name or config.get("active")
    for target in targets:
        if target.get("name") == wanted:
            return target
    return targets[0]


class GitHub:
    """Tiny GitHub Actions/contents client for one token (stdlib only)."""

    def __init__(self, token: str):
        self.token = token or ""

    def _req(self, method: str, path: str, body: dict | None = None):
        # Public repos must read fine with no token: GitHub answers 401 to a
        # bare `Authorization: token ` header, so only send it when present.
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        req = urllib.request.Request(
            GH + path,
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read()
                return resp.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            return exc.code, {}
        except OSError:
            return 0, {}

    def read_session(self, target: dict) -> dict | None:
        session = target.get("session") or {}
        branch = session.get("branch", "live")
        path = session.get("path", "session.json")
        code, data = self._req(
            "GET", f"/repos/{target['repo']}/contents/{path}?ref={branch}"
        )
        if code != 200 or "content" not in data:
            return None
        try:
            payload = json.loads(base64.b64decode(data["content"]))
        except (ValueError, KeyError):
            return None
        return normalize_session(payload)

    def dispatch(self, target: dict, ref: str = "main",
                 overrides: dict | None = None) -> bool:
        inputs = dict(target.get("inputs") or {})
        if overrides:
            for key, value in overrides.items():
                if key in inputs:
                    inputs[key] = value
        code, _ = self._req(
            "POST",
            f"/repos/{target['repo']}/actions/workflows/{target['workflow']}"
            f"/dispatches",
            {"ref": ref, "inputs": inputs},
        )
        return code == 204

    def cancel(self, target: dict) -> int:
        """Cancel active runs of the target's workflow; returns how many."""
        workflow = target.get("workflow", "")
        code, data = self._req(
            "GET", f"/repos/{target['repo']}/actions/runs?per_page=20"
        )
        if code != 200:
            return 0
        cancelled = 0
        for run in data.get("workflow_runs", []):
            if run.get("status") not in ("queued", "in_progress"):
                continue
            run_path = run.get("path", "")
            if workflow and not run_path.endswith("/" + workflow):
                continue
            self._req(
                "POST", f"/repos/{target['repo']}/actions/runs/{run['id']}/cancel"
            )
            cancelled += 1
        return cancelled
