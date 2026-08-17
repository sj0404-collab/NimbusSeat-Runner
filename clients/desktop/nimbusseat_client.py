#!/usr/bin/env python3
"""NimbusSeat desktop client (Windows / Linux) — Local + Cloud.

Две вкладки:
  * Local  — LAN-хост (Duo/Moonlight): автопоиск, 6-часовой таймер, Play.
  * Cloud  — облачное место на GitHub-раннере: запустить/остановить раннер,
             открыть сессию в браузере. Repo и токен настраиваются и хранятся
             в nimbus_cloud.json рядом с клиентом — при закрытии аккаунта
             GitHub достаточно указать новое зеркало (docs/MIGRATION.md).

Только стандартная библиотека (tkinter + urllib).
"""
from __future__ import annotations

import base64
import json
import shutil
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

DISCOVERY_PORT = 48121
MAGIC = b"NIMBUSSEAT/1"
CONF = Path(__file__).with_name("nimbus_cloud.json")
GH = "https://api.github.com"
WORKFLOW = "remote-seat.yml"


# ----------------------------- LAN part -----------------------------------

def discover(timeout: float = 3.0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)
    try:
        sock.sendto(MAGIC, ("255.255.255.255", DISCOVERY_PORT))
        data, addr = sock.recvfrom(1024)
        info = json.loads(data.decode())
        if info.get("magic") == "NIMBUSSEAT/1":
            return addr[0], info
    except OSError:
        pass
    finally:
        sock.close()
    return None


def api(host_ip, port, path, method="GET"):
    req = urllib.request.Request(f"http://{host_ip}:{port}/api/v1/{path}", method=method)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode())


def find_moonlight():
    for name in ("moonlight", "moonlight-qt"):
        p = shutil.which(name)
        if p:
            return [p]
    if sys.platform == "win32":
        import os
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("LocalAppData", "")):
            c = Path(base) / "Moonlight Game Streaming" / "Moonlight.exe"
            if c.is_file():
                return [str(c)]
    if shutil.which("flatpak"):
        return ["flatpak", "run", "com.moonlight_stream.Moonlight"]
    return None


# ----------------------------- Cloud part ---------------------------------

class Cloud:
    def __init__(self):
        self.repo, self.token = "", ""
        self.load()

    def load(self):
        if CONF.is_file():
            d = json.loads(CONF.read_text())
            self.repo, self.token = d.get("repo", ""), d.get("token", "")

    def save(self):
        CONF.write_text(json.dumps({"repo": self.repo, "token": self.token}))

    def gh(self, method, path, body=None):
        req = urllib.request.Request(
            GH + path, method=method,
            data=json.dumps(body).encode() if body else None,
            headers={"Authorization": f"token {self.token}",
                     "Accept": "application/vnd.github+json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                raw = r.read()
                return r.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            return e.code, {}
        except OSError:
            return 0, {}

    def start(self, minutes=340, res="1280x720", fps=30):
        code, _ = self.gh("POST", f"/repos/{self.repo}/actions/workflows/{WORKFLOW}/dispatches",
                          {"ref": "main", "inputs": {"minutes": str(minutes),
                                                     "resolution": res, "fps": str(fps)}})
        return code == 204

    def stop(self):
        code, d = self.gh("GET", f"/repos/{self.repo}/actions/runs?per_page=10")
        n = 0
        for r in d.get("workflow_runs", []):
            if r["name"].startswith("Remote Seat") and r["status"] in ("queued", "in_progress"):
                self.gh("POST", f"/repos/{self.repo}/actions/runs/{r['id']}/cancel", {})
                n += 1
        return n

    def session(self):
        code, d = self.gh("GET", f"/repos/{self.repo}/contents/session.json?ref=live")
        if code == 200 and "content" in d:
            try:
                return json.loads(base64.b64decode(d["content"]))
            except ValueError:
                pass
        return None


# ----------------------------- UI -----------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NimbusSeat")
        self.geometry("470x360")
        self.cloud = Cloud()
        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True)
        self.local_tab(nb)
        self.cloud_tab(nb)

    # ---- Local -------------------------------------------------------
    def local_tab(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="🏠 Локально (LAN)")
        self.host_ip, self.api_port = None, 48120
        self.l_host = ttk.Label(f, text="Поиск хоста…", font=("", 12, "bold"))
        self.l_host.pack(pady=10)
        self.l_state = ttk.Label(f, text="—")
        self.l_state.pack()
        self.l_timer = ttk.Label(f, text="", font=("", 20, "bold"))
        self.l_timer.pack(pady=8)
        row = ttk.Frame(f)
        row.pack(pady=10)
        self.b_play = ttk.Button(row, text="▶ Играть", command=self.play, state=tk.DISABLED)
        self.b_play.grid(row=0, column=0, padx=5)
        self.b_stop = ttk.Button(row, text="⏹ Стоп", command=self.stop, state=tk.DISABLED)
        self.b_stop.grid(row=0, column=1, padx=5)
        ttk.Button(row, text="⟳", command=self.rescan).grid(row=0, column=2, padx=5)
        threading.Thread(target=self.poll_local, daemon=True).start()
        self.rescan()

    def rescan(self):
        def w():
            found = discover()
            if found:
                self.host_ip, info = found
                self.api_port = info.get("api_port", 48120)
                self.l_host.config(text=f"{info.get('name')} — {self.host_ip}")
            else:
                self.l_host.config(text="LAN-хост не найден")
        threading.Thread(target=w, daemon=True).start()

    def poll_local(self):
        while True:
            if self.host_ip:
                try:
                    st = api(self.host_ip, self.api_port, "status")
                    self.render(st)
                except OSError:
                    self.l_state.config(text="нет связи")
            time.sleep(2)

    def render(self, st):
        names = {"idle": "Свободен", "active": "Идёт сессия",
                 "grace": "Время вышло!", "cooldown": "Перерыв"}
        s = st.get("state", "?")
        self.l_state.config(text=names.get(s, s))
        left = int(st.get("seconds_left", 0))
        self.l_timer.config(text=f"{left//3600}:{left%3600//60:02d}:{left%60:02d}" if s == "active" else "")
        self.b_play.config(state=tk.NORMAL if s == "idle" else tk.DISABLED)
        self.b_stop.config(state=tk.NORMAL if s == "active" else tk.DISABLED)

    def play(self):
        if not self.host_ip:
            return
        try:
            resp = api(self.host_ip, self.api_port, "session/start", "POST")
        except OSError as e:
            return messagebox.showerror("NimbusSeat", str(e))
        if not resp.get("ok"):
            return messagebox.showwarning("NimbusSeat", resp.get("message", "Занято"))
        ml = find_moonlight()
        if ml:
            subprocess.Popen([*ml, "stream", self.host_ip, "Desktop"])
        else:
            messagebox.showinfo("NimbusSeat", "Moonlight не найден: moonlight-stream.org")

    def stop(self):
        if self.host_ip and messagebox.askyesno("NimbusSeat", "Завершить сессию?"):
            try:
                api(self.host_ip, self.api_port, "session/stop", "POST")
            except OSError:
                pass

    # ---- Cloud -------------------------------------------------------
    def cloud_tab(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="☁ Облако (раннер)")
        self.c_state = ttk.Label(f, text="Раннер: …", font=("", 12, "bold"))
        self.c_state.pack(pady=10)
        self.c_info = ttk.Label(f, text="")
        self.c_info.pack()

        conf = ttk.Frame(f)
        conf.pack(pady=6)
        ttk.Label(conf, text="Разрешение:").grid(row=0, column=0)
        self.v_res = tk.StringVar(value="1280x720")
        ttk.Combobox(conf, textvariable=self.v_res, width=10, state="readonly",
                     values=["960x540", "1280x720", "1600x900", "1920x1080"]).grid(row=0, column=1, padx=4)
        ttk.Label(conf, text="FPS:").grid(row=0, column=2)
        self.v_fps = tk.StringVar(value="30")
        ttk.Combobox(conf, textvariable=self.v_fps, width=5, state="readonly",
                     values=["15", "30", "60"]).grid(row=0, column=3, padx=4)

        row = ttk.Frame(f)
        row.pack(pady=10)
        ttk.Button(row, text="▶ Запустить раннер", command=self.c_start).grid(row=0, column=0, padx=4)
        ttk.Button(row, text="🔗 Открыть сессию", command=self.c_open).grid(row=0, column=1, padx=4)
        ttk.Button(row, text="⏹ Остановить", command=self.c_stop).grid(row=0, column=2, padx=4)
        ttk.Button(f, text="⚙ Repo / токен", command=self.c_conf).pack(pady=4)
        ttk.Label(f, foreground="#777",
                  text="Repo и токен хранятся локально (nimbus_cloud.json).\n"
                       "Если аккаунт закроют — укажите новое зеркало (docs/MIGRATION.md).",
                  justify=tk.CENTER).pack(pady=6)
        threading.Thread(target=self.c_poll, daemon=True).start()

    def c_conf(self):
        repo = simpledialog.askstring("Облако", "owner/repo:", initialvalue=self.cloud.repo or
                                      "sj0404-collab/NimbusSeat-Runner", parent=self)
        if repo is None:
            return
        token = simpledialog.askstring("Облако", "GitHub token:", show="*", parent=self)
        if token is None:
            return
        self.cloud.repo, self.cloud.token = repo.strip(), token.strip()
        self.cloud.save()

    def c_ready(self):
        if not self.cloud.repo or not self.cloud.token:
            self.c_conf()
        return bool(self.cloud.repo and self.cloud.token)

    def c_start(self):
        if not self.c_ready():
            return
        def w():
            ok = self.cloud.start(res=self.v_res.get(), fps=int(self.v_fps.get()))
            self.c_state.config(text="Раннер: запускается (1-3 мин)…" if ok else "Ошибка dispatch")
        threading.Thread(target=w, daemon=True).start()

    def c_open(self):
        if not self.c_ready():
            return
        def w():
            s = self.cloud.session()
            if s and s.get("state") == "live":
                webbrowser.open(s["url"])
            else:
                messagebox.showinfo("NimbusSeat", "Сессия ещё не live — подождите или запустите раннер")
        threading.Thread(target=w, daemon=True).start()

    def c_stop(self):
        if not self.c_ready():
            return
        threading.Thread(target=lambda: self.c_stop_done(self.cloud.stop()), daemon=True).start()

    def c_stop_done(self, n):
        self.c_state.config(text=f"Раннер: остановлено runs: {n}")

    def c_poll(self):
        while True:
            if self.cloud.repo and self.cloud.token:
                s = self.cloud.session()
                if s and s.get("state") == "live":
                    self.c_state.config(text="Раннер: 🟢 LIVE")
                    self.c_info.config(text=f"{s.get('resolution')} @ {s.get('fps')}fps, до {s.get('ends_at_utc')}")
                else:
                    self.c_state.config(text="Раннер: ⚪ выключен")
                    self.c_info.config(text="")
            time.sleep(15)


if __name__ == "__main__":
    App().mainloop()
