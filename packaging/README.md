# Пакування у macOS-застосунок

Збирає `GestureVoiceControl.app` (PyInstaller, `--onedir`) і `GestureVoiceControl.dmg`
(drag-to-Applications) з поточного стану гілки `packaging/macos-app`.

## Вимоги

- macOS на Apple Silicon (arm64) — `mlx`, від якого залежить розпізнавання
  мови, збирається лише під arm64.
- macOS 26 (Tahoe) або новіша — реальна нижня межа задається пакетом `mlx`
  (`mlx-0.32.0`/`mlx_metal-0.32.0` мають тег `macosx_26_0_arm64`), а не
  рештою залежностей.
- Активоване й наповнене `venv/` з `requirements.txt` (те саме оточення,
  яким запускається `python src/main.py`).
- Git-гілка `packaging/*` з чистим робочим деревом (`build.sh` перевіряє
  обидві умови і зупиняється, якщо щось не так).

## Збірка

```bash
source venv/bin/activate
bash packaging/build.sh
```

Результат: `packaging/output/GestureVoiceControl.dmg`.

`packaging/build/` і `packaging/dist/` — проміжні артефакти PyInstaller,
у `.gitignore`, перестворюються щоразу.

## Перевірка після збірки

1. Змонтувати `.dmg`, перетягнути `.app` у `/Applications`.
2. Скинути дозволи перед кожним тестовим запуском:
   ```bash
   tccutil reset Camera com.mgricenko.gvcontrol
   tccutil reset Microphone com.mgricenko.gvcontrol
   tccutil reset Accessibility com.mgricenko.gvcontrol
   tccutil reset ListenEvent com.mgricenko.gvcontrol
   ```
3. Запустити `.app` **подвійним кліком у Finder** (не через `open` з
   довіреного термінала) — лише так перевіряється і реальний `cwd`
   (не корінь репозиторію), і чисті системні запити дозволів.
4. Очікувана послідовність: спершу попередження/запит Accessibility
   (`src/utils/permissions.py`, до старту камери/мікрофона), далі системний
   запит Camera при першому кадрі з `cv2.VideoCapture`, потім запит
   Microphone при відкритті `sounddevice`-потоку.
5. Надати Accessibility → перевірити, що синтетичні кліки/скрол
   (`pyautogui`/Quartz) реально відбуваються.
6. Промовити голосову команду і показати жест — обидва мають дійти до
   `OSController`. Це підтверджує, що `models/` (vosk, mediapipe-задачі)
   правильно потрапили в бандл і `resolve_model_path()` резолвить шляхи
   в замороженому режимі так само, як у dev-режимі.
7. Якщо застосунок падає одразу після запуску або мовчки не відкриває
   камеру/мікрофон — перевірити `Console.app` або:
   ```bash
   log show --predicate 'process == "GestureVoiceControl"' --last 5m
   ```
   на предмет `dlopen`/`ImportError`. Найризикованіші місця — власний
   `.dylib` mediapipe (Tasks C API) і Metal-бібліотека mlx
   (`mlx.metallib`/`libmlx.dylib`): `collect_all()` у `main.spec` зазвичай
   їх ловить, але не гарантовано. Якщо чогось бракує — додати точковий
   запис у `datas` в `packaging/main.spec` і перезібрати.

## Обмеження поточної збірки

- **Іконка** (`packaging/assets/AppIcon.icns`) — тимчасова, згенерована з
  `src/ui/images/quick_circle.png`. Замінити на власний дизайн за потреби
  (`iconutil -c icns packaging/assets/AppIcon.iconset`).
- **Підпис — лише ad-hoc**, для локального використання на цьому Маку.
  Свідомо без `--options runtime`: hardened runtime + ad-hoc — ненадійна
  комбінація для PyInstaller-бандла з окремо підписаними `.dylib` від
  torch/mlx/mediapipe (AMFI може відхилити їх при library validation),
  а сенсу в hardened runtime без нотаризації однаково нема.
- **Без нотаризації** — потрібен платний Apple Developer ID. Кроки для
  переходу на Developer ID + нотаризацію задокументовані в кінці
  `packaging/build.sh` (закоментовані).
- Розмір `.dmg` реалістично 1.5–3 ГБ через torch/mediapipe/mlx.
