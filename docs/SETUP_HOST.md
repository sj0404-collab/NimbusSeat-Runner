# Настройка хоста (Windows 11)

Пошаговая инструкция превращения ПК в NimbusSeat-хост со вторым игровым местом.

## 1. Требования

- Windows 11 (Pro рекомендуется), дискретная видеокарта с HW-энкодером
  (NVENC / AMF / QuickSync), 16+ ГБ RAM.
- Гигабитная LAN или Wi-Fi 5/6 для клиентов.
- Python 3.11+ (`winget install Python.Python.3.12`).

## 2. Duo (мультисессионный форк Apollo/Sunshine)

1. Скачайте и установите Duo — форк Apollo с поддержкой нескольких
   одновременных сессий: https://github.com/ClassicOldSong/Apollo (ветка/релизы Duo).
2. Вместе с Duo ставится **Virtual Display Driver** — он создаёт виртуальный
   монитор для гостевой сессии. Убедитесь, что в настройках Duo включено
   `Virtual Display` для стрим-профиля гостя.
3. Откройте веб-интерфейс `https://localhost:47990`, задайте логин/пароль.
4. Создайте приложение `Desktop` (обычно уже есть) — его запускают клиенты.

## 3. ASTER V7 (multiseat)

1. Установите ASTER V7: https://www.ibik.ru/ (платный, есть триал).
2. В панели ASTER настройте **Место 2**:
   - Дисплей: виртуальный монитор Duo (Virtual Display).
   - Аудио: отдельное виртуальное аудиоустройство (например, Steam Streaming
     Speakers или VB-Cable) — звук гостя не попадёт в колонки хозяина.
   - Ввод: не назначайте физические клавиатуру/мышь — ввод придёт от Moonlight.
3. Включите ASTER и перезагрузитесь. Проверьте, что Место 1 (ваш монитор)
   работает как раньше.

> ASTER гарантирует, что у гостевой сессии свой рабочий стол, свой звук и свой
> ввод — хозяин ПК может параллельно работать или играть на Месте 1.

## 4. NimbusSeat host-manager

```powershell
git clone https://github.com/sj0404-collab/NimbusSeat-Runner
cd NimbusSeat-Runner\host
pip install -r requirements.txt
copy config.example.json config.json
notepad config.json   # проверьте пути к Duo/ASTER и подсети LAN
```

Firewall (разово, от администратора):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_firewall_lan_only.ps1
```

Запуск вручную:

```powershell
python -m nimbusseat_host run
```

Или как служба Windows (нужен NSSM: `winget install NSSM.NSSM`):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_service.ps1
```

## 5. Проверка

- `http://<IP хоста>:48120/api/v1/info` из LAN — должен вернуть JSON.
- Тот же URL с не-LAN адреса — 403.
- Клиент (Android или desktop) должен найти хост автоматически.

## 6. Как работает 6-часовой таймер

1. Клиент нажимает «Играть» → `POST /api/v1/session/start` → таймер 360 минут.
2. За 30/10/5 минут до конца гость получает предупреждение на экран (через
   ASTER-уведомление).
3. По истечении — минутный grace-период, затем manager перезапускает службу Duo,
   стрим обрывается, начинается 15-минутный перерыв (cooldown).
4. Лимит и все интервалы настраиваются в `config.json`.
