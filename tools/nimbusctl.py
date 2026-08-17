#!/usr/bin/env python3
"""nimbusctl — автономное управление NimbusSeat-раннером с ЛЮБОГО GitHub-аккаунта.

Не привязан к конкретному аккаунту: репозиторий и токен задаются параметрами
или переменными окружения NIMBUS_REPO / NIMBUS_TOKEN. Если исходный аккаунт
закроется — форкните/зальёте зеркало репозитория в новый аккаунт, создадите
новый токен, и всё продолжит работать (см. docs/MIGRATION.md).

Команды:
  python3 nimbusctl.py start [--minutes 340] [--res 1280x720] [--fps 30]
  python3 nimbusctl.py stop
  python3 nimbusctl.py status
  python3 nimbusctl.py url          # ссылка текущей сессии
  python3 nimbusctl.py migrate NEW_OWNER/NEW_REPO --new-token TOKEN
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.request

API = "https://api.github.com"
WORKFLOW = "remote-seat.yml"


def req(method, url, token, data=None):
    r = urllib.request.Request(url, method=method,
        headers={"Authorization": f"token {token}",
                 "Accept": "application/vnd.github+json"})
    body = json.dumps(data).encode() if data is not None else None
    try:
        with urllib.request.urlopen(
                urllib.request.Request(r.full_url, data=body, method=method,
                                       headers=r.headers), timeout=30) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def get_conf(args):
    repo = args.repo or os.environ.get("NIMBUS_REPO")
    token = args.token or os.environ.get("NIMBUS_TOKEN")
    if not repo or not token:
        sys.exit("Задайте --repo owner/name и --token (или NIMBUS_REPO / NIMBUS_TOKEN)")
    return repo, token


def cmd_start(args):
    repo, token = get_conf(args)
    code, _ = req("POST", f"{API}/repos/{repo}/actions/workflows/{WORKFLOW}/dispatches",
                  token, {"ref": args.ref, "inputs": {
                      "minutes": str(args.minutes),
                      "resolution": args.res, "fps": str(args.fps)}})
    if code != 204:
        sys.exit(f"dispatch failed: HTTP {code}")
    print("Запуск принят. Жду ссылку (1-3 мин)…")
    old = session_json(repo, token)
    old_url = old.get("url") if old else None
    for _ in range(60):
        time.sleep(10)
        s = session_json(repo, token)
        if s and s.get("state") == "live" and s.get("url") != old_url:
            print("ГОТОВО:\n " + s["url"])
            return
        print(".", end="", flush=True)
    sys.exit("\nТаймаут — проверьте вкладку Actions в репозитории")


def active_runs(repo, token):
    code, d = req("GET", f"{API}/repos/{repo}/actions/runs?per_page=10", token)
    if code != 200:
        sys.exit(f"HTTP {code}: {d.get('message')}")
    return [r for r in d.get("workflow_runs", [])
            if r["name"].startswith("Remote Seat") and r["status"] in ("queued", "in_progress")]


def cmd_stop(args):
    repo, token = get_conf(args)
    runs = active_runs(repo, token)
    if not runs:
        print("Активных сессий нет")
        return
    for r in runs:
        code, _ = req("POST", f"{API}/repos/{repo}/actions/runs/{r['id']}/cancel", token)
        print(f"cancel run {r['id']}: HTTP {code}")


def session_json(repo, token):
    code, d = req("GET", f"{API}/repos/{repo}/contents/session.json?ref=live", token)
    if code != 200 or "content" not in d:
        return None
    try:
        return json.loads(base64.b64decode(d["content"]))
    except ValueError:
        return None


def cmd_status(args):
    repo, token = get_conf(args)
    runs = active_runs(repo, token)
    s = session_json(repo, token)
    print(f"Раннер: {'АКТИВЕН (' + str(len(runs)) + ' run)' if runs else 'выключен'}")
    if s:
        print(f"Сессия: {s.get('state')}")
        if s.get("state") == "live":
            print(f"  URL: {s.get('url')}")
            print(f"  Режим: {s.get('resolution')} @ {s.get('fps')} fps, до {s.get('ends_at_utc')}")


def cmd_url(args):
    repo, token = get_conf(args)
    s = session_json(repo, token)
    if s and s.get("state") == "live":
        print(s["url"])
    else:
        sys.exit("Сессия не запущена (nimbusctl start)")


def cmd_migrate(args):
    """Скопировать репозиторий в новый аккаунт: mirror push."""
    repo, token = get_conf(args)
    new_repo, new_token = args.new_repo, args.new_token
    owner_new = new_repo.split("/")[0]
    # 1. создать пустой репозиторий у нового владельца
    code, d = req("POST", f"{API}/user/repos", new_token,
                  {"name": new_repo.split("/")[1], "private": False})
    print(f"create {new_repo}: HTTP {code} {d.get('message') or ''}")
    # 2. зеркальный перенос через git (требуется установленный git)
    import subprocess, tempfile
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "clone", "--mirror",
                        f"https://x-access-token:{token}@github.com/{repo}.git", tmp + "/m"],
                       check=True)
        subprocess.run(["git", "push", "--mirror",
                        f"https://x-access-token:{new_token}@github.com/{new_repo}.git"],
                       cwd=tmp + "/m", check=True)
    print(f"Готово. Дальше: NIMBUS_REPO={new_repo} NIMBUS_TOKEN=<новый токен>")
    print("Не забудьте перенести секреты (KEYSTORE_B64 и др.) — см. docs/MIGRATION.md")


def main():
    p = argparse.ArgumentParser(prog="nimbusctl")
    p.add_argument("--repo", help="owner/name (или env NIMBUS_REPO)")
    p.add_argument("--token", help="GitHub token (или env NIMBUS_TOKEN)")
    p.add_argument("--ref", default="main")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start"); s.add_argument("--minutes", type=int, default=340)
    s.add_argument("--res", default="1280x720"); s.add_argument("--fps", type=int, default=30)
    sub.add_parser("stop"); sub.add_parser("status"); sub.add_parser("url")
    m = sub.add_parser("migrate"); m.add_argument("new_repo"); m.add_argument("--new-token", required=True)
    args = p.parse_args()
    {"start": cmd_start, "stop": cmd_stop, "status": cmd_status,
     "url": cmd_url, "migrate": cmd_migrate}[args.cmd](args)


if __name__ == "__main__":
    main()
