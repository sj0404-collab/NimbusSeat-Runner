# NimbusSeat Android Client

Клиент в духе GeForce NOW: находит NimbusSeat-хост в Wi-Fi сети, показывает
статус и обратный отсчёт 6-часовой сессии, запускает Moonlight для стрима.

## Сборка
Откройте папку `clients/android` в Android Studio (Hedgehog+) и соберите APK,
либо из консоли:
```
./gradlew assembleDebug
```

## Требования
- Android 8.0+ (API 26)
- Приложение [Moonlight](https://play.google.com/store/apps/details?id=com.limelight)
- Телефон/планшет в той же Wi-Fi сети, что и хост

Первый запуск: спарьте Moonlight с хостом (PIN подтверждается в веб-интерфейсе Duo),
дальше кнопка «Играть» делает всё сама.
