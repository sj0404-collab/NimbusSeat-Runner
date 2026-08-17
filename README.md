# NimbusSeat-Runner

**Второе игровое место из одного ПК на Windows 11** — в духе GeForce NOW / Steam Remote Play, но у вас дома и только в LAN.

NimbusSeat-Runner — это host-manager, который превращает один мощный компьютер с Windows 11 в
два независимых игровых места:

- физическое место (монитор, клавиатура, мышь, звук хозяина ПК), и
- **отдельная игровая сессия**, транслируемая по локальной сети на Android, Windows или Linux
  клиент через **Duo** (мультисессионный форк Apollo/Sunshine) и протокол **Moonlight**.

Изоляция мест обеспечивается **ASTER V7** (multiseat) + виртуальным дисплеем Duo:
у каждой сессии — **свой экран, свой звук и свой ввод**, они не мешают друг другу.

Поверх этого host-manager добавляет то, чего нет ни в Duo, ни в ASTER:

| Возможность | Описание |
|---|---|
| ⏱ 6-часовой таймер | Каждая гостевая сессия ограничена 6 часами (настраивается). Предупреждения за 30/10/5 минут, по истечении — корректное завершение стрима. |
| 🌐 LAN-only доступ | Firewall-правила и проверка подсети: подключиться можно только из локальной сети. Никакого WAN/UPnP. |
| 📡 Автообнаружение | Клиенты находят хост по UDP-broadcast — как список серверов в GeForce NOW. |
| 🖥 Независимый экран | Виртуальный дисплей Duo (Virtual Display Driver) — гостевая сессия не дублирует и не занимает монитор хозяина. |
| 🔊 Независимый звук | Отдельное виртуальное аудиоустройство на сессию; звук гостя не играет из колонок хозяина. |
| ⌨️ Независимый ввод | Ввод Moonlight-клиента инжектится только в гостевую сессию (ASTER-место №2). |
| 📱 Клиенты | Android-клиент и десктопный клиент (Windows/Linux): обнаружение хоста, статус, обратный отсчёт таймера, запуск Moonlight в один клик. |

## Архитектура

```
                ┌──────────────────────── Windows 11 Host ────────────────────────┐
                │                                                                 │
   Seat 1      │  ASTER V7 (multiseat)                                            │
   (хозяин)  ──┼─►  Место 1: физич. монитор + клава/мышь + аудио хозяина          │
                │   Место 2: виртуальный дисплей Duo + вирт. аудио + вирт. ввод   │
                │                        ▲                                        │
                │                        │ захват/инжект                          │
                │   Duo (форк Apollo/Sunshine) ── стрим H.264/HEVC/AV1 ─────┐     │
                │                        ▲                                 │     │
                │   NimbusSeat Host-Manager (этот репозиторий)              │     │
                │    • 6h session timer  • LAN guard  • discovery beacon    │     │
                │    • REST API :48120   • управление Duo и ASTER           │     │
                └────────────────────────────────────────────────────────── │ ────┘
                                                                            │ LAN only
                          ┌─────────────────────────┬──────────────────────┘
                          ▼                         ▼
                 Android-клиент             Desktop-клиент (Win/Linux)
                 (NimbusSeat App            (NimbusSeat Launcher
                  + Moonlight)               + Moonlight)
```

## Состав репозитория

```
host/                     Host-manager для Windows 11 (Python 3.11+)
  nimbusseat_host/        Пакет: таймер, API, discovery, Duo/ASTER контроллеры
  scripts/                PowerShell: firewall LAN-only, установка службы (NSSM)
  config.example.json     Пример конфигурации
clients/
  desktop/                Клиент для Windows/Linux (Python + Tkinter, один файл)
  android/                Android-клиент (Kotlin), запускает Moonlight по intent
docs/                     Пошаговая настройка: хост, ASTER, Duo, клиенты, FAQ
```

## Быстрый старт (хост)

1. Установите [Duo](https://github.com/ClassicOldSong/Apollo) (мультисессионный форк Apollo) и
   Virtual Display Driver, [ASTER V7](https://www.ibik.ru/), Python 3.11+.
2. `cd host && pip install -r requirements.txt`
3. `copy config.example.json config.json` и отредактируйте пути/подсеть.
4. Разовая настройка: `powershell -ExecutionPolicy Bypass -File scripts\setup_firewall_lan_only.ps1`
5. Запуск: `python -m nimbusseat_host run`
   (или как служба: `scripts\install_service.ps1`).

Подробности — в [docs/SETUP_HOST.md](docs/SETUP_HOST.md).

## Быстрый старт (клиент)

- **Windows/Linux:** установите Moonlight, затем `python clients/desktop/nimbusseat_client.py` —
  хост найдётся сам, кнопка **Play** запустит стрим.
- **Android:** установите Moonlight из Play Market, соберите/установите `clients/android`,
  откройте приложение — хост найдётся сам.

## Лицензия

MIT. Duo/Apollo/Sunshine, Moonlight и ASTER V7 — продукты их авторов со своими лицензиями
(ASTER V7 — платный, требуется своя лицензия).
