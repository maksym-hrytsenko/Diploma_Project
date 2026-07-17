# Привіт

Це проєкт Максима Гриценка — дипломна робота на тему **"Проєктування
мультимодальної системи керування комп'ютером за допомогою жестів і
голосу"**. Щоб спробувати систему:

1. **Встанови її** — інструкції нижче, у розділі [Setup](#setup) (проєкт
   вже тут, у цьому репозиторії — окремо нічого шукати не треба).
2. **Прочитай, що вона вміє** — повний опис кожної голосової команди,
   жесту, режиму та середовища в
   [`docs/SYSTEM_FUNCTIONS.md`](docs/SYSTEM_FUNCTIONS.md) (або короткий
   список у [`docs/FUNCTIONS_LIST.txt`](docs/FUNCTIONS_LIST.txt), якщо
   треба просто швидко глянути, що куди веде). Той самий опис відкривається
   і прямо в застосунку кнопкою "Functions description".
3. **Запусти застосунок і одразу увімкни Try Mode** — перемикач одразу
   біля перегляду з камери. Це безпечний режим: жодна дія не виконується
   на реальному комп'ютері (жоден клік, жодна клавіша, жоден запуск
   застосунку) — можна просто подивитись на себе, спробувати жести й
   голосові команди, побачити, як система їх розпізнає, і зрозуміти, як
   усе працює, перш ніж довірити їй керування чимось реальним. Детальніше
   — розділ [Try Mode](#try-mode) нижче.

При першому запуску застосунок сам покаже коротке привітальне вікно з
цими самими трьома кроками — цей README для того, хто ще навіть не
встановив і не запускав.

---

# Multimodal Computer Control System

Master's thesis project: **"Design of a Multimodal System for Computer
Control Using Gestures and Voice."**

A macOS desktop application that combines hand gestures (MediaPipe),
offline voice commands (Vosk, with optional semantic/LLM fallback) and
keyboard shortcuts into a single event-driven control pipeline, letting a
user open apps, navigate presentations, scroll, move the cursor and
control calls/media without touching the mouse or keyboard.

## Architecture

The system follows a strict, one-directional event pipeline — every
module communicates only through a shared `EventBus`, never by calling
another module directly:

```
Input (keyboard / microphone / camera)
        -> Processing (recognizers: keyboard, speech, gesture, face)
        -> IntentModel / CommandInterpreter
        -> MultimodalFusion
        -> SignalMapper (the only module that decides an action)
        -> ActionExecutor
        -> OSController
```

Two independent, orthogonal pieces of state ride on top of this pipeline:
**mode** (Presentation / Flip / Cursor / Call / Quick Circle — what the
same gesture currently means) and **Try Mode** (an on/off flag that can be
active alongside any mode, and makes `ActionExecutor` skip every real OS
side effect — see [Try Mode](#try-mode) below).

See [`src/CLAUDE.md`](src/CLAUDE.md) for module-level responsibilities and
[`docs/SYSTEM_FUNCTIONS.md`](docs/SYSTEM_FUNCTIONS.md) for the full
behavior reference (every voice command, gesture, mode and environment).
[`docs/FUNCTIONS_LIST.txt`](docs/FUNCTIONS_LIST.txt) is a short
plain-text quick-lookup list.

## Project structure

A reviewer's map of the repository — what to open depending on what you're
looking for:

```
.
├── README.md                 you are here
├── requirements.txt          Python dependencies (runtime)
├── pytest.ini                pytest configuration
├── .python-version           pinned Python version (3.10)
│
├── src/                      the application itself
│   ├── main.py                entry point — wires every module to EventBus
│   ├── CLAUDE.md               module-level architecture reference
│   ├── config/                  system.json / mapping.json / fusion.json + loader
│   ├── core/                     EventBus, StateManager
│   ├── input/                    keyboard / microphone / camera capture (raw only)
│   ├── processing/                recognizers: keyboard, speech, gesture, face
│   ├── interpretation/            IntentModel, CommandInterpreter (voice -> command)
│   ├── fusion/                    MultimodalFusion, SignalMapper (decision-making)
│   ├── execution/                 ActionExecutor, OSController (real OS effects)
│   ├── ui/                        MainWindow, dialogs, overlays (PyQt6)
│   └── utils/                     logger, permissions, app_state
│
├── tests/                    automated + manual tests (see Testing below)
├── docs/                     behavior reference, function list, thesis
├── models/                   Vosk / MediaPipe model files (not source code)
├── benchmarks/                standalone CPU/RAM profiling tool
├── packaging/                 PyInstaller build -> .app / .dmg
└── logs/                      runtime logs (generated, gitignored)
```

`__pycache__/`, `.pytest_cache/` and `.DS_Store` you may see in your
editor's file tree are Python/pytest/macOS Finder caches — all gitignored,
nobody reviewing this on GitHub ever sees them; safe to ignore.

## Requirements

- macOS (the app talks directly to AppKit/Quartz/MediaRemote — it does
  not run on Windows or Linux)
- Python 3.10 (see [`.python-version`](.python-version))
- A working webcam and microphone
- Accessibility permission granted to the terminal/process running the
  app (System Settings -> Privacy & Security -> Accessibility) — without
  it, synthetic cursor/click/scroll/hotkey events silently do nothing

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

The Vosk speech model (`models/vosk-model-small-en-us-0.15`) and the
MediaPipe `.task` files under `models/` must be present before starting
the app — see `src/config/system.json` for the configured paths.

## Running

```bash
source venv/bin/activate
python src/main.py
```

The first time the app ever runs, it shows a short welcome screen before
the main window — a plain-language introduction and a nudge toward Try
Mode. It only shows once; the same information is always available later
via the main window's "Functions description" button.

**Known first-run quirk:** on a fresh install, the camera preview
sometimes stays blank even though the Camera toggle shows "Active" (the
camera really is capturing — this is a macOS permission-prompt timing
issue, not a crash). If the preview doesn't show your video within a few
seconds of launch, just flip the Camera toggle off and back on once — the
picture appears immediately after.

Optional debug flags:

- `--debug-gesture` — overlays the camera feed with the tracked hand,
  anchor point and current zone
- `--debug-face` — overlays live head pose and blendshape scores against
  their thresholds
- `--debug-voice` — prints partial/final speech recognition results

### Try Mode

A switch right next to the camera preview (also reachable by saying "jack
try mode", or pressing `ctrl+shift+t`). While it's on, `ActionExecutor`
skips every real OS side effect — no key presses, no clicks, no cursor
movement, no app/URL launches — while everything else (mode switching,
gesture/voice/keyboard recognition, the camera preview's live
"Detected: ..." caption) keeps working exactly as normal. It's independent
of the four regular modes — it stays on while you switch between
Presentation/Flip/Cursor/Call, so you can see how each one behaves before
trusting it with real control. Saying "exit mode" or pressing `Esc` turns
it off too, on top of leaving whichever mode is active. See
`docs/SYSTEM_FUNCTIONS.md` §2.6 for the full reference.

## Testing

Two kinds, both under `tests/`:

- **Automated** (`pytest tests/test_pipeline.py`) — drives the real
  `CommandInterpreter -> MultimodalFusion -> SignalMapper -> ActionExecutor`
  pipeline against `config/mapping.json` and `config/fusion.json`, with
  `OSController` mocked out, plus a unit-level check of the voice
  pipeline's utterance-segmentation logic — no camera, microphone or
  keyboard hardware needed:

  ```bash
  source venv/bin/activate
  pytest
  ```

- **Manual** ([`tests/MANUAL_TEST_SCENARIOS.md`](tests/MANUAL_TEST_SCENARIOS.md))
  — everything that genuinely needs a real camera, microphone, or macOS
  desktop to verify (gesture/face/voice recognition accuracy, real OS
  side effects, UI behavior, stress/timing edge cases), organized as a
  checklist by type.

## Benchmarking

`benchmarks/resource_monitor.py` is a standalone tool (not part of the
shipped app) that launches the app, samples CPU/RAM usage of it and every
worker process it spawns at a fixed interval, and writes the results to a
CSV file:

```bash
python benchmarks/resource_monitor.py --duration 120
```

Run `python benchmarks/resource_monitor.py --help` for all options.

## Logs

Runtime logs are written to both the console and `logs/app.log`
(rotating, kept out of version control) via `src/utils/logger.py`.
