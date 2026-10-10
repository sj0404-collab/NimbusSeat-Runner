# NimbusSeat All-in-One Android APK

Один APK, который содержит **всё**: лаунчер NimbusSeat (поиск хоста в LAN,
6-часовой таймер, старт сессии) **плюс встроенный open-source Moonlight**
([moonlight-android](https://github.com/moonlight-stream/moonlight-android),
GPL-3.0). Ничего не нужно скачивать из Play Market.

## Как собирается

GitHub Actions (workflow `Android All-in-One APK`):
1. клонирует moonlight-android v12.1 с сабмодулями (стриминговое ядро C);
2. накладывает наш код из `overlay/` (лаунчер + discovery + REST-клиент);
3. `patch_moonlight.py` меняет applicationId на `app.nimbusseat.client`
   (по просьбе автора Moonlight не выпускать чужие сборки под `com.limelight`),
   метку приложения на NimbusSeat и делает наш экран стартовым;
4. собирает `assembleNonRootRelease` и подписывает **release-ключом**
   (keystore хранится в GitHub Secrets).

## Облачный экран: любая цель

Экран «Облако» не зашит на один репозиторий. В ⚙ задаются `repo`, `token`,
`workflow`, ветка и файл сессии, и `inputs` запуска в JSON — то есть один APK
может подключаться и к NimbusSeat-Runner, и к экрану `zen-panel`, и к форку.
Два пресета (NimbusSeat / zen-panel экран) переключают цель одним тапом.
Понимаются оба формата сессии (`session.json` на `live`, `live/session-*.json`
на `session-state`); адрес берётся из `url`/`novncUrl`/`novnc`/`web`.

Подключение — через **предпросмотр**: «🔗 Предпросмотр» встраивает экран прямо
в WebView (короткий бокс; тап по нему разворачивает на весь экран, «Назад» —
свернуть), «⛶ На весь экран» открывает сразу развёрнутым, «↗ Ссылка в браузере»
отдаёт адрес системе. Экран показывается, как только в сессии есть адрес, —
даже если `state` не записан; пустой токен больше не мешает читать публичные
репозитории (заголовок `Authorization` не шлётся, если токена нет). Голый
`vnc.html` от noVNC дополняется `?autoconnect=1&resize=scale` — иначе видна
тёмная табличка «Connect» и рабочий стол 1:1 (на телефоне выглядит как чёрный
экран).

## Лицензия

Итоговый APK — производная работа от moonlight-android → распространяется по
**GPL-3.0**. Исходники изменений — в этой папке.
