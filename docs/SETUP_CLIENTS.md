# Настройка клиентов

## Windows / Linux

1. Установите Moonlight: https://moonlight-stream.org
   - Windows: `winget install MoonlightGameStreamingProject.Moonlight`
   - Linux: `flatpak install com.moonlight_stream.Moonlight`
2. Запустите `python clients/desktop/nimbusseat_client.py`
   (нужен Python 3.10+ с tkinter).
3. Первый раз выполните паринг Moonlight с хостом: Moonlight покажет PIN,
   подтвердите его в веб-интерфейсе Duo (`https://<хост>:47990` → PIN).
4. Дальше кнопка **▶ Играть** сама начнёт сессию и откроет стрим.

## Android

1. Установите Moonlight из Google Play (`com.limelight`).
2. Соберите и установите NimbusSeat-клиент из `clients/android`
   (Android Studio → assembleDebug), либо возьмите APK из релизов.
3. Откройте приложение — хост найдётся сам, паринг Moonlight как выше.

## Советы по качеству

- 1080p60: ~20 Мбит/с; 1440p120: 40–80 Мбит/с. По Wi-Fi используйте 5 ГГц.
- Включите в Moonlight HEVC или AV1, если клиент поддерживает.
- Геймпад подключайте к клиенту — ввод пробрасывается в гостевую сессию.
