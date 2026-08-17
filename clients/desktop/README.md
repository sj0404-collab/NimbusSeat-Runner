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
