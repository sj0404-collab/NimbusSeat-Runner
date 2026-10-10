# NimbusSeat Desktop Client (Windows / Linux)

Лаунчер в духе GeForce NOW: находит NimbusSeat-хост в LAN, показывает статус и
обратный отсчёт 6-часовой сессии, запускает Moonlight одной кнопкой.

## Требования
- Python 3.10+ (с tkinter; на Debian/Ubuntu: `sudo apt install python3-tk`)
- [Moonlight](https://moonlight-stream.org) (моonlight-qt), спарен с хостом Duo

## Запуск
```
python nimbusseat_client.py
```
Первый раз выполните паринг Moonlight с хостом (PIN подтверждается в веб-интерфейсе Duo).

## Облачная вкладка: цели (targets)

Вкладка **Облако** не привязана к одному репозиторию. «Цель» — это набор
`repo + token + workflow + входы запуска + откуда читать живую сессию`. Из
списка целей выбирается активная, поэтому одним клиентом можно смотреть и на
`NimbusSeat-Runner`, и на хаб `zen-panel`, и на любой форк/зеркало.

Две цели идут «из коробки»:

| Цель | repo | workflow | сессия |
|---|---|---|---|
| NimbusSeat | `…/NimbusSeat-Runner` | `remote-seat.yml` | `live` / `session.json` |
| zen-panel hub | `…/zen-panel` | `hub.yml` | `session-state` / `live/session-hub-linux.json` |

Кнопка **⚙** открывает редактор целей: название, repo, токен, workflow, ветка
и файл сессии, `inputs` в JSON и **«Гейт хаба ?zt=»**. Токен хранится в
`nimbus_cloud.json` рядом с клиентом (старый формат `{repo, token}`
автоматически превращается в одну цель).

Адрес берётся из `mobile` → `url` → `novncUrl` → `novnc` → `web` →
`desktop` → `hubUrl`, поэтому хаб zen-panel открывается своей мобильной
страницей `/m` — экран + OPus-звук (`/ws/audio`) + виртуальная мышь + zoom,
чего голый `vnc.html` не даёт.

Перед открытием адрес дополняется: голый `vnc.html` — `?autoconnect=1&resize=scale`
(иначе тёмная табличка «Connect» и стол 1:1), хаб с заполненным «Гейтом» —
`?zt=<гейт>`, тот же гейт уходит джобе как input `token`. Без гейта хаб
поднимается с выключенными дверями, и `/m` открывается и без `?zt=`.
