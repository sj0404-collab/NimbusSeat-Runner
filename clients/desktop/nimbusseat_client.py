#!/usr/bin/env python3
"""NimbusSeat desktop client (Windows / Linux) — Local + Cloud.

Две вкладки:
  * Local  — LAN-хост (Duo/Moonlight): автопоиск, 6-часовой таймер, Play.
  * Cloud  — облачное место на GitHub-раннере: список целей (targets), запуск
             workflow, подключение к живому экрану в браузере.

«Цель» — это репо + workflow + куда положить сессию + входы запуска. Цели
хранятся в nimbus_cloud.json и переключаются прямо в UI, поэтому один клиент
может смотреть и на NimbusSeat-Runner, и на экран zen-panel, и на любой форк,
не будучи жёстко привязанным к одному репозиторию. Логика целей и форматов
сессии живёт в nimbus_targets.py (без tkinter, покрыта юнит-тестами).

Только стандартная библиотека (tkinter + urllib).
"""
from __future__ import annotations

import json
import socket
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk

import nimbus_targets as nt

DISCOVERY_PORT = 48121
MAGIC = b"NIMBUSSEAT/1"
CONF = Path(__file__).with_name("nimbus_cloud.json")


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
    """Config + GitHub actions for every target, whichever repo it points at."""

    def __init__(self):
        self.config = nt.load_config(CONF)

    # -- config --------------------------------------------------------
    @property
    def token(self):
        return self.config.get("token", "")

    @property
    def targets(self):
        return self.config.get("targets", [])

    def target(self):
        return nt.find_target(self.config, self.config.get("active"))

    def names(self):
        return [t.get("name", t.get("repo", "?")) for t in self.targets]

    def set_active(self, name):
        self.config["active"] = name
        self.save()

    def save(self):
        nt.save_config(CONF, self.config)

    # -- GitHub --------------------------------------------------------
    def _gh(self):
        return nt.GitHub(self.token)

    def start(self, overrides=None):
        target = self.target()
        if not target:
            return False
        return self._gh().dispatch(target, overrides=overrides)

    def stop(self):
        target = self.target()
        if not target:
            return 0
        return self._gh().cancel(target)

    def session(self):
        target = self.target()
        if not target:
            return None
        return self._gh().read_session(target)

    def open_url(self, session):
        """Address to open for the active target, decorated (noVNC autoconnect
        + fit, hub gate as ?zt=)."""
        target = self.target() or {}
        url = (session or {}).get("url") or (session or {}).get("novnc")
        return nt.novnc_url(url, target.get("gate", ""))

    def session_source(self):
        target = self.target() or {}
        session = target.get("session") or {}
        return f"{target.get('repo', '?')} · {target.get('workflow', '?')} · " \
               f"{session.get('branch', '?')}/{session.get('path', '?')}"


# ----------------------------- UI -----------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NimbusSeat")
        self.geometry("500x420")
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
        self.c_state.pack(pady=8)
        self.c_info = ttk.Label(f, text="")
        self.c_info.pack()

        pick = ttk.Frame(f)
        pick.pack(pady=6)
        ttk.Label(pick, text="Цель:").grid(row=0, column=0)
        self.v_target = tk.StringVar()
        names = self.cloud.names()
        self.c_target = ttk.Combobox(pick, textvariable=self.v_target, width=26,
                                     state="readonly", values=names)
        if self.cloud.config.get("active") in names:
            self.c_target.set(self.cloud.config["active"])
        elif names:
            self.c_target.set(names[0])
        self.c_target.grid(row=0, column=1, padx=4)
        self.c_target.bind("<<ComboboxSelected>>", lambda _e: self.c_pick())
        ttk.Button(pick, text="⚙", width=3, command=self.c_conf).grid(row=0, column=2, padx=4)

        self.c_src = ttk.Label(f, text="", foreground="#777")
        self.c_src.pack()

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
        ttk.Label(f, foreground="#777",
                  text="Цели и токен хранятся локально (nimbus_cloud.json).\n"
                       "Один клиент может смотреть на любой репо/раннер —\n"
                       "переключайте цель в списке выше.",
                  justify=tk.CENTER).pack(pady=6)
        self.c_sync_source()
        threading.Thread(target=self.c_poll, daemon=True).start()

    def c_sync_source(self):
        self.c_src.config(text=self.cloud.session_source())

    def c_pick(self):
        self.cloud.set_active(self.v_target.get())
        self.c_sync_source()
        self.c_poll_once()

    def c_conf(self):
        TargetsDialog(self, self.cloud)
        names = self.cloud.names()
        self.c_target.configure(values=names)
        if self.cloud.config.get("active") not in names and names:
            self.cloud.set_active(names[0])
        self.v_target.set(self.cloud.config.get("active", names[0] if names else ""))
        self.c_sync_source()

    def c_ready(self):
        if not self.cloud.token or not self.cloud.target():
            if not TargetsDialog(self, self.cloud).ok:
                return False
            names = self.cloud.names()
            self.c_target.configure(values=names)
            self.c_sync_source()
        return bool(self.cloud.token and self.cloud.target())

    def c_start(self):
        if not self.c_ready():
            return
        res, fps = self.v_res.get(), self.v_fps.get()
        def w():
            ok = self.cloud.start(overrides={"resolution": res, "fps": fps})
            self.c_state.config(text="Раннер: запускается (1-3 мин)…" if ok else "Ошибка dispatch")
        threading.Thread(target=w, daemon=True).start()

    def c_open(self):
        if not self.c_ready():
            return
        def w():
            s = self.cloud.session()
            url = self.cloud.open_url(s)
            if s and s.get("live") and url:
                webbrowser.open(url)
            else:
                messagebox.showinfo("NimbusSeat", "Сессия ещё не live — подождите или запустите раннер")
        threading.Thread(target=w, daemon=True).start()

    def c_stop(self):
        if not self.c_ready():
            return
        threading.Thread(target=lambda: self.c_stop_done(self.cloud.stop()), daemon=True).start()

    def c_stop_done(self, n):
        self.c_state.config(text=f"Раннер: остановлено runs: {n}")

    def c_poll_once(self):
        def w():
            if self.cloud.token and self.cloud.target():
                s = self.cloud.session()
                self.after(0, lambda: self._render_cloud(s))
        threading.Thread(target=w, daemon=True).start()

    def c_poll(self):
        while True:
            self.c_poll_once()
            time.sleep(15)

    def _render_cloud(self, s):
        if s and s.get("live"):
            self.c_state.config(text="Раннер: 🟢 LIVE")
            detail = " ".join(x for x in [
                s.get("kind"),
                (f"{s['resolution']} @ {s['fps']}fps" if s.get("resolution") else ""),
                (f"до {s['ends_at_utc']}" if s.get("ends_at_utc") else ""),
            ] if x)
            self.c_info.config(text=detail)
        else:
            self.c_state.config(text="Раннер: ⚪ выключен")
            self.c_info.config(text="")


class TargetsDialog(tk.Toplevel):
    """Add / edit / delete targets, so one client can point at any repo."""

    def __init__(self, master, cloud: Cloud):
        super().__init__(master)
        self.cloud = cloud
        self.ok = False
        self.title("Цели Cloud (репо / workflow / сессия)")
        self.transient(master)
        self.grab_set()

        self.v_name = tk.StringVar()
        self.v_repo = tk.StringVar()
        self.v_token = tk.StringVar(value=cloud.token)
        self.v_workflow = tk.StringVar()
        self.v_branch = tk.StringVar()
        self.v_path = tk.StringVar()
        self.v_inputs = tk.StringVar()
        self.v_gate = tk.StringVar()

        self.pick = ttk.Combobox(self, width=30, state="readonly",
                                 values=cloud.names())
        self.pick.grid(row=0, column=0, columnspan=2, padx=8, pady=8)
        self.pick.bind("<<ComboboxSelected>>", lambda _e: self.load())
        if cloud.names():
            self.pick.set(cloud.config.get("active", cloud.names()[0]))

        rows = [("Название", self.v_name), ("repo (owner/name)", self.v_repo),
                ("GitHub token", self.v_token), ("workflow (файл в .github)", self.v_workflow),
                ("Ветка сессии", self.v_branch), ("Файл сессии", self.v_path),
                ("inputs (JSON)", self.v_inputs), ("Гейт хаба (?zt=)", self.v_gate)]
        for i, (label, var) in enumerate(rows, start=1):
            ttk.Label(self, text=label).grid(row=i, column=0, sticky="e", padx=6, pady=2)
            show = "*" if var is self.v_token else ""
            e = ttk.Entry(self, textvariable=var, width=34, show=show)
            e.grid(row=i, column=1, padx=6, pady=2)
        self.v_token.set(cloud.token)

        bar = ttk.Frame(self)
        bar.grid(row=len(rows) + 1, column=0, columnspan=2, pady=8)
        ttk.Button(bar, text="Сохранить", command=self.save).grid(row=0, column=0, padx=3)
        ttk.Button(bar, text="＋ Новая", command=self.new).grid(row=0, column=1, padx=3)
        ttk.Button(bar, text="Удалить", command=self.delete).grid(row=0, column=2, padx=3)
        ttk.Button(bar, text="Готово", command=self.close).grid(row=0, column=3, padx=3)

        if cloud.names():
            self.load()
        self.wait_window(self)

    def _target(self):
        return nt.find_target(self.cloud.config, self.pick.get())

    def load(self):
        t = self._target() or {}
        session = t.get("session") or {}
        self.v_name.set(t.get("name", ""))
        self.v_repo.set(t.get("repo", ""))
        self.v_workflow.set(t.get("workflow", nt.NIMBUS_WORKFLOW))
        self.v_branch.set(session.get("branch", "live"))
        self.v_path.set(session.get("path", "session.json"))
        self.v_gate.set(t.get("gate", ""))
        self.v_inputs.set(json.dumps(t.get("inputs") or {}, ensure_ascii=False))

    def save(self):
        try:
            inputs = json.loads(self.v_inputs.get() or "{}")
            assert isinstance(inputs, dict)
        except (ValueError, AssertionError):
            return messagebox.showerror("NimbusSeat", "inputs — должен быть JSON-объект", parent=self)
        target = {
            "name": self.v_name.get().strip() or self.v_repo.get().strip(),
            "repo": self.v_repo.get().strip(),
            "token": "",
            "workflow": self.v_workflow.get().strip() or nt.NIMBUS_WORKFLOW,
            "gate": self.v_gate.get().strip(),
            "inputs": inputs,
            "session": {"branch": self.v_branch.get().strip() or "live",
                        "path": self.v_path.get().strip() or "session.json"},
        }
        self.cloud.config["token"] = self.v_token.get().strip()
        targets = [t for t in self.cloud.targets if t.get("name") != target["name"]
                   and t.get("name") != self.pick.get()]
        targets.append(target)
        self.cloud.config["targets"] = targets
        self.cloud.config["active"] = target["name"]
        self.cloud.save()
        self.ok = True
        self.pick.configure(values=self.cloud.names())
        self.pick.set(target["name"])
        messagebox.showinfo("NimbusSeat", "Сохранено", parent=self)

    def new(self):
        self.pick.set("")
        for var in (self.v_name, self.v_repo, self.v_workflow, self.v_branch,
                    self.v_path, self.v_inputs, self.v_gate):
            var.set("")
        self.v_workflow.set(nt.NIMBUS_WORKFLOW)
        self.v_branch.set("live")
        self.v_path.set("session.json")
        self.v_inputs.set("{}")

    def delete(self):
        name = self.pick.get()
        self.cloud.config["targets"] = [t for t in self.cloud.targets if t.get("name") != name]
        if self.cloud.config.get("active") == name:
            names = self.cloud.names()
            self.cloud.config["active"] = names[0] if names else ""
        self.cloud.save()
        self.pick.configure(values=self.cloud.names())
        if self.cloud.names():
            self.pick.set(self.cloud.names()[0])
            self.load()

    def close(self):
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
