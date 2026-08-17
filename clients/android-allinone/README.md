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

## Лицензия

Итоговый APK — производная работа от moonlight-android → распространяется по
**GPL-3.0**. Исходники изменений — в этой папке.
