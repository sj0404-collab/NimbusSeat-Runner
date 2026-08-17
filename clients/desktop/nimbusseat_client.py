#!/usr/bin/env python3
"""NimbusSeat desktop client for Windows and Linux.

GeForce NOW / Steam Remote Play style launcher:
  * discovers the NimbusSeat host on the LAN via UDP broadcast,
  * shows host status and the 6-hour session countdown,
  * starts the session on the host and launches Moonlight in one click.

Dependencies: Python 3.10+ standard library only (tkinter + urllib).
Moonlight must be installed (https://moonlight-stream.org).
"""
from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.request
from tkinter import messagebox, ttk

DISCOVERY_PORT = 48121
MAGIC = b"NIMBUSSEAT/1"


def discover(timeout: float = 3.0) -> tuple[str, dict] | None:
    """Send a probe and wait for the host's reply. Returns (ip, info)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)
    try:
        sock.sendto(MAGIC, ("255.255.255.255", DISCOVERY_PORT))
        end = time.time() + timeout
        while time.time() < end:
            try:
                data, addr = sock.recvfrom(1024)
            except socket.timeout:
                break
            try:
                info = json.loads(data.decode())
            except ValueError:
                continue
            if info.get("magic") == "NIMBUSSEAT/1":
                return addr[0], info
    finally:
        sock.close()
    return None


def api(host_ip: str, port: int, path: str, method: str = "GET") -> dict:
    req = urllib.request.Request(
        f"http://{host_ip}:{port}/api/v1/{path}", method=method
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode())


def find_moonlight() -> list[str] | None:
    """Locate the Moonlight executable on Windows or Linux."""
    for name in ("moonlight", "moonlight-qt"):
        path = shutil.which(name)
        if path:
            return [path]
    if sys.platform == "win32":
        import os

        for base in (
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("LocalAppData", ""),
        ):
            candidate = os.path.join(base, "Moonlight Game Streaming", "Moonlight.exe")
            if os.path.isfile(candidate):
                return [candidate]
    if shutil.which("flatpak"):
        return ["flatpak", "run", "com.moonlight_stream.Moonlight"]
    return None


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("NimbusSeat")
        self.geometry("420x260")
        self.resizable(False, False)
        self.host_ip: str | None = None
        self.api_port = 48120

        pad = {"padx": 16, "pady": 6}
        self.lbl_host = ttk.Label(self, text="Поиск хоста в локальной сети…", font=("", 12, "bold"))
        self.lbl_host.pack(**pad)
        self.lbl_state = ttk.Label(self, text="—")
        self.lbl_state.pack(**pad)
        self.lbl_timer = ttk.Label(self, text="", font=("", 20, "bold"))
        self.lbl_timer.pack(**pad)

        row = ttk.Frame(self)
        row.pack(**pad)
        self.btn_play = ttk.Button(row, text="▶ Играть", command=self.play, state=tk.DISABLED)
        self.btn_play.grid(row=0, column=0, padx=6)
        self.btn_stop = ttk.Button(row, text="⏹ Завершить", command=self.stop, state=tk.DISABLED)
        self.btn_stop.grid(row=0, column=1, padx=6)
        ttk.Button(row, text="⟳ Обновить", command=self.rescan).grid(row=0, column=2, padx=6)

        threading.Thread(target=self._poll_loop, daemon=True).start()
        self.rescan()

    def rescan(self) -> None:
        def worker() -> None:
            found = discover()
            if found:
                self.host_ip, info = found
                self.api_port = info.get("api_port", 48120)
                self.lbl_host.config(text=f"{info.get('name')} — {self.host_ip}")
            else:
                self.lbl_host.config(text="Хост не найден. Он включён и в той же сети?")

        threading.Thread(target=worker, daemon=True).start()

    def _poll_loop(self) -> None:
        while True:
            if self.host_ip:
                try:
                    st = api(self.host_ip, self.api_port, "status")
                    self._render(st)
                except Exception:
                    self.lbl_state.config(text="Нет связи с хостом")
            time.sleep(2)

    def _render(self, st: dict) -> None:
        state = st.get("state", "?")
        names = {
            "idle": "Свободен — можно играть",
            "active": "Идёт сессия",
            "grace": "Время вышло! Стрим завершается",
            "cooldown": "Перерыв между сессиями",
        }
        self.lbl_state.config(text=names.get(state, state))
        left = int(st.get("seconds_left", 0))
        if state == "active":
            h, rem = divmod(left, 3600)
            m, s = divmod(rem, 60)
            self.lbl_timer.config(text=f"{h}:{m:02d}:{s:02d}")
        else:
            self.lbl_timer.config(text="")
        self.btn_play.config(state=tk.NORMAL if state == "idle" else tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL if state == "active" else tk.DISABLED)

    def play(self) -> None:
        if not self.host_ip:
            return
        try:
            resp = api(self.host_ip, self.api_port, "session/start", "POST")
        except Exception as exc:
            messagebox.showerror("NimbusSeat", f"Не удалось начать сессию: {exc}")
            return
        if not resp.get("ok"):
            messagebox.showwarning("NimbusSeat", resp.get("message", "Хост занят"))
            return
        moonlight = find_moonlight()
        if not moonlight:
            messagebox.showinfo(
                "NimbusSeat",
                "Сессия начата, но Moonlight не найден.\n"
                "Установите его: https://moonlight-stream.org",
            )
            return
        subprocess.Popen([*moonlight, "stream", self.host_ip, "Desktop"])

    def stop(self) -> None:
        if self.host_ip and messagebox.askyesno("NimbusSeat", "Завершить сессию?"):
            try:
                api(self.host_ip, self.api_port, "session/stop", "POST")
            except Exception as exc:
                messagebox.showerror("NimbusSeat", str(exc))


if __name__ == "__main__":
    App().mainloop()
