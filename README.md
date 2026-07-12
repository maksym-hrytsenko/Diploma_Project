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

See [`src/CLAUDE.md`](src/CLAUDE.md) for module-level responsibilities and
[`docs/SYSTEM_FUNCTIONS.md`](docs/SYSTEM_FUNCTIONS.md) for the full
behavior reference (every voice command, gesture, mode and environment).
[`docs/FUNCTIONS_LIST.txt`](docs/FUNCTIONS_LIST.txt) is a short
plain-text quick-lookup list.

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

Optional debug flags:

- `--debug-gesture` — overlays the camera feed with the tracked hand,
  anchor point and current zone
- `--debug-face` — overlays live head pose and blendshape scores against
  their thresholds
- `--debug-voice` — prints partial/final speech recognition results

## Testing

The regression suite drives the real
`CommandInterpreter -> MultimodalFusion -> SignalMapper -> ActionExecutor`
pipeline against `config/mapping.json` and `config/fusion.json`, with
`OSController` mocked out — no camera, microphone or keyboard hardware
needed:

```bash
source venv/bin/activate
pytest
```

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
