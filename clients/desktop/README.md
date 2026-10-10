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
`NimbusSeat-Runner`, и на экран `zen-panel`, и на любой форк/зеркало.

Две цели идут «из коробки»:

| Цель | repo | workflow | сессия |
|---|---|---|---|
| NimbusSeat | `…/NimbusSeat-Runner` | `remote-seat.yml` | `live` / `session.json` |
| zen-panel screen | `…/zen-panel` | `hub.yml` | `session-state` / `live/session-vnc.json` |

Кнопка **⚙** открывает редактор целей: название, repo, токен, workflow, ветка
и файл сессии, `inputs` в JSON. Токен хранится в `nimbus_cloud.json` рядом с
клиентом (старый формат `{repo, token}` автоматически превращается в одну
цель). Понимаются оба формата сессии — NimbusSeat (`url`/`state`) и
zen-panel (`url`/`novncUrl`, без `state` → считается live, если есть адрес).
