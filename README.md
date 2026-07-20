# Multimodal Computer Control System

Master's thesis project: **"Design of a Multimodal System for Computer
Control Using Gestures and Voice."**

A macOS desktop application that combines hand gestures (MediaPipe),
offline voice commands (Vosk, with optional semantic/LLM fallback) and
keyboard shortcuts into a single event-driven control pipeline, letting a
user open apps, navigate presentations, scroll, move the cursor and
control calls/media without touching the mouse or keyboard.

## ⚠️ Must read

1. **You received the pre-built app separately from this git
   repository.** Or you can build it yourself following the instructions
   below.

2. **After the first launch you'll see three permission prompts**
   (Camera, Microphone, Accessibility). Watch out: **the third one
   sometimes hides behind the app's own window** — don't forget to find
   and confirm it, or the app won't be able to perform any real actions.

3. **From there, just follow the instructions you're given** — the app
   walks you through the first steps itself on its welcome screen.

4. **To actually use the app, you first need to spend a little time
   learning how it works.** That's exactly what **Try Mode** is for: you
   see how the app perceives you and reacts to commands, but no action
   ever reaches the real computer. I'd recommend trying everything
   yourself:
   - **Switching modes by hand:** show a closed fist to the camera, then
     open it — the action circle (**Quick Circle**) appears.
   - **To learn swipes,** try **Flip** mode in Try Mode — it uses the
     same set of motions and reacts to quick hand movements.
   - **To close the action circle,** slowly close your hand into a fist
     and move it out of frame — that avoids false triggers.

This app is an attempt at a ready-made solution in this space — nothing
quite like it exists yet, so it closes out a whole list of problems and
use cases. One note: to try the app-opening functions, those apps need
to actually be installed on your computer — trying to open one that
isn't there simply won't work.

**Enjoy!**

---

*Read on if you're curious.*

## Quick start

1. **Install it** — see [Setup](#setup) below; the project is already
   right here in this repository, nothing else to fetch separately.
2. **Read what it can do** — the full reference for every voice command,
   gesture, mode and environment lives in
   [`project/docs/SYSTEM_FUNCTIONS.md`](project/docs/SYSTEM_FUNCTIONS.md)
   (or the short quick-lookup list in
   [`project/docs/FUNCTIONS_LIST.txt`](project/docs/FUNCTIONS_LIST.txt)).
   The same reference also opens directly inside the app via its
   "Functions description" button.
3. **Run the app and turn on Try Mode right away** — the toggle sits next
   to the camera preview. It's a safe mode: no action ever reaches the
   real computer (no clicks, no key presses, no app launches), so you can
   watch yourself, try gestures and voice commands, and see how the
   system recognizes them before trusting it with real control. See
   [Try Mode](#try-mode) below for details.

The app's own first-run welcome screen walks through these same three
steps; this README is for anyone who hasn't installed or launched it yet.

## Limitations

- **macOS only** — the app talks directly to AppKit/Quartz/MediaRemote,
  it does not run on Windows or Linux.
- **The pre-built `.app`/`.dmg` requires Apple Silicon (arm64)** — the
  `mlx` dependency (LLM voice fallback) only ships arm64 wheels. Running
  from source has the same practical requirement, since `mlx` is in
  `requirements.txt`. See
  [`project/packaging/BUILD.md`](project/packaging/BUILD.md).
- **Requires a working webcam, microphone, and Accessibility permission**
  granted to the process running the app — without Accessibility,
  synthetic cursor/click/scroll/hotkey events silently do nothing (no
  error, no crash).
- **Known first-run quirk:** the camera preview can stay blank on a fresh
  install even though the Camera toggle shows "Active" — a macOS
  permission-prompt timing issue, not a crash. Flipping the Camera
  toggle off and back on fixes it immediately.
- **Voice recognition is hybrid and probabilistic**, not deterministic —
  exact/semantic/LLM tiers each have their own accuracy tradeoffs, and
  under real testing conditions some short commands spoken in quick
  succession were found to be silently dropped from the log rather than
  reported as "not understood" (a logging/observability gap, not a lost
  command). See
  [`project/tests/voice_pipeline_fixes_log.md`](project/tests/voice_pipeline_fixes_log.md)
  for the full record of what was found and fixed during real testing,
  including what's still open.
- **First run needs internet access.** Only the exact-match tier's model
  (Vosk) ships inside this repository (`models/`). The semantic tier
  (`all-MiniLM-L6-v2`) and the LLM fallback tier
  (`mlx-community/Llama-3.2-3B-Instruct-4bit`) are downloaded
  automatically from Hugging Face the first time they're needed, then
  cached locally — after that first download, everything runs fully
  offline.

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

See [`project/docs/ARCHITECTURE.md`](project/docs/ARCHITECTURE.md) for
module-level responsibilities and
[`project/docs/SYSTEM_FUNCTIONS.md`](project/docs/SYSTEM_FUNCTIONS.md)
for the full behavior reference (every voice command, gesture, mode and
environment).
[`project/docs/FUNCTIONS_LIST.txt`](project/docs/FUNCTIONS_LIST.txt) is a
short plain-text quick-lookup list.

## Repository layout

```
.
├── README.md              you are here
├── build.sh                shortcut -> project/packaging/build.sh
└── project/                the application and everything it needs
    ├── requirements.txt      Python dependencies (runtime)
    ├── pytest.ini             pytest configuration
    ├── .python-version        pinned Python version (3.10)
    │
    ├── src/                   the application itself
    │   ├── main.py              entry point — wires every module to EventBus
    │   ├── config/                system.json / mapping.json / fusion.json + loader
    │   ├── core/                   EventBus, StateManager
    │   ├── input/                   keyboard / microphone / camera capture (raw only)
    │   ├── processing/               recognizers: keyboard, speech, gesture, face
    │   ├── interpretation/           IntentModel, CommandInterpreter (voice -> command)
    │   ├── fusion/                    MultimodalFusion, SignalMapper (decision-making)
    │   ├── execution/                  ActionExecutor, OSController (real OS effects)
    │   ├── ui/                         MainWindow, dialogs, overlays (PyQt6)
    │   └── utils/                       logger, permissions, app_state
    │
    ├── tests/                 automated + manual tests (see Testing below)
    │   └── benchmarks/          standalone CPU/RAM profiling tool
    ├── docs/                  architecture, behavior reference, function list
    ├── models/                Vosk / MediaPipe model files (not source code)
    └── packaging/             PyInstaller build -> .app / .dmg
```

`__pycache__/`, `.pytest_cache/`, `.DS_Store` and `venv/` you may see in
your editor's file tree are Python/pytest/macOS Finder/virtualenv
artifacts — all gitignored, nobody reviewing this on GitHub ever sees
them; safe to ignore.

## Requirements

- macOS on Apple Silicon (arm64) — see [Limitations](#limitations)
- Python 3.10 (see [`project/.python-version`](project/.python-version))
- A working webcam and microphone
- Accessibility permission granted to the terminal/process running the
  app (System Settings -> Privacy & Security -> Accessibility)

## Setup

```bash
cd project
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

The Vosk speech model (`models/vosk-model-small-en-us-0.15`) and the
MediaPipe `.task` files under `models/` must be present before starting
the app — see `src/config/system.json` for the configured paths. Both
already ship inside this repository.

### Prebuilt app

Building the application from source (above) is the way to run it today.
A pre-built `GestureVoiceControl.dmg` is not committed to this
repository — it's ~600 MB, well past what a normal git push accepts — so
it isn't tracked in git. `bash build.sh` (from the repository root, see
[Repository layout](#repository-layout)) produces it locally; a signed
copy may also be published separately as a GitHub Release for direct
download. See
[`project/packaging/BUILD.md`](project/packaging/BUILD.md) for the full
build/install procedure and its own requirements.

## Running

```bash
cd project
source venv/bin/activate
python src/main.py
```

The first time the app ever runs, it shows a short welcome screen before
the main window — a plain-language introduction and a nudge toward Try
Mode. It only shows once; the same information is always available later
via the main window's "Functions description" button.

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
`project/docs/SYSTEM_FUNCTIONS.md` §2.6 for the full reference.

## Testing

Two kinds, both under `project/tests/`:

- **Automated** (`pytest tests/test_pipeline.py`) — drives the real
  `CommandInterpreter -> MultimodalFusion -> SignalMapper -> ActionExecutor`
  pipeline against `config/mapping.json` and `config/fusion.json`, with
  `OSController` mocked out, plus a unit-level check of the voice
  pipeline's utterance-segmentation logic — no camera, microphone or
  keyboard hardware needed:

  ```bash
  cd project
  source venv/bin/activate
  pytest
  ```

- **Manual** ([`project/tests/MANUAL_TEST_SCENARIOS.md`](project/tests/MANUAL_TEST_SCENARIOS.md))
  — everything that genuinely needs a real camera, microphone, or macOS
  desktop to verify (gesture/face/voice recognition accuracy, real OS
  side effects, UI behavior, stress/timing edge cases), organized as a
  checklist by type.

## Benchmarking

`project/tests/benchmarks/resource_monitor.py` is a standalone tool (not
part of the shipped app) that launches the app, samples CPU/RAM usage of
it and every worker process it spawns at a fixed interval, and writes the
results to a CSV file:

```bash
cd project
python tests/benchmarks/resource_monitor.py --duration 120
```

Run `python tests/benchmarks/resource_monitor.py --help` for all options.

## Logs

Runtime logs are written to both the console and `project/logs/app.log`
(rotating, kept out of version control) via `src/utils/logger.py`.
