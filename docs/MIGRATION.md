# План выживания: если GitHub-аккаунт закроется

Вся система **не привязана к конкретному аккаунту**. Привязка — только два
параметра: `owner/repo` и токен. Они задаются в клиентах и CLI.

## Что сделать заранее (сейчас)

1. Скачайте себе:
   - APK из Releases;
   - папку `nimbus-signing/` (keystore + пароль) — она нужна для обновлений APK;
   - архив репозитория: Code → Download ZIP (или `git clone`).
2. Запомните: секреты Actions (`KEYSTORE_B64`, `KEYSTORE_PASSWORD`, `KEY_ALIAS`)
   не копируются автоматически — их надо будет внести заново.

## Переезд на новый аккаунт (5 минут)

1. Регистрируете новый GitHub-аккаунт → создаёте Personal Access Token
   (Actions: RW, Contents: RW, Administration: RW для создания репо).
2. Одной командой переносите всё:
   ```
   python3 tools/nimbusctl.py --repo OLD_OWNER/NimbusSeat-Runner --token OLD_TOKEN \
       migrate NEW_OWNER/NimbusSeat-Runner --new-token NEW_TOKEN
   ```
   Если старый аккаунт уже недоступен — просто пушите локальную копию:
   ```
   cd NimbusSeat-Runner && git remote set-url origin https://github.com/NEW_OWNER/NimbusSeat-Runner
   git push --mirror
   ```
3. Вносите секреты подписи заново: Settings → Secrets → Actions:
   `KEYSTORE_B64` = base64 файла nimbus.keystore, `KEYSTORE_PASSWORD`, `KEY_ALIAS`.
4. Обновляете конфиг в клиентах:
   - CLI: `export NIMBUS_REPO=NEW_OWNER/NimbusSeat-Runner NIMBUS_TOKEN=...`
   - APK: экран «Облако» → ⚙ → repo + токен (+ workflow/сессия; сохраняется на устройстве);
   - Desktop: `nimbus_cloud.json` рядом с клиентом.

## Любой репо/раннер, не только свой

Начиная с обобщённых клиентов «облако» — это не один жёстко зашитый репозиторий,
а список **целей**, каждая из которых описывает `repo + workflow + входы + где
лежит живая сессия`. Поэтому один клиент может подключаться и к своему
NimbusSeat-Runner, и, например, к экрану `zen-panel`.

Формат `nimbus_cloud.json` (desktop):

```json
{
  "token": "ghp_…",
  "active": "zen-panel screen",
  "targets": [
    { "name": "NimbusSeat", "repo": "OWNER/NimbusSeat-Runner",
      "workflow": "remote-seat.yml",
      "inputs": {"minutes": "340", "resolution": "1280x720", "fps": "30"},
      "session": {"branch": "live", "path": "session.json"} },
    { "name": "zen-panel screen", "repo": "OWNER/zen-panel",
      "workflow": "hub.yml",
      "inputs": {"os": "linux", "label": "panel"},
      "session": {"branch": "session-state", "path": "live/session-vnc.json"} }
  ]
}
```

Старый формат `{"repo": "...", "token": "..."}` читается по-прежнему и
превращается в одну цель. Адрес берётся из `url`/`novncUrl`/`novnc`/`web`;
если поля `state` нет (как у VNC-слота zen-panel) — сессия считается live при
наличии адреса.

## Автономное управление раннером

```
python3 tools/nimbusctl.py start --minutes 340 --res 1920x1080 --fps 60
python3 tools/nimbusctl.py status
python3 tools/nimbusctl.py url
python3 tools/nimbusctl.py stop
```
То же самое умеют APK (кнопки Запустить/Остановить в облачной вкладке)
и desktop-клиент.
