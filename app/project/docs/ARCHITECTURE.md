# Architecture

Module-level reference for the multimodal computer control system. See
[`SYSTEM_FUNCTIONS.md`](SYSTEM_FUNCTIONS.md) for *behavior* (what each
command/gesture/mode does); this document describes *structure* (which
module is responsible for what, and how they're wired together).

## Core architecture

The system follows a strict event pipeline:

```
KeyboardInput
MicrophoneInput
CameraInput
        │
        ▼
KeyboardProcessor
SpeechRecognizer
GestureRecognizer
        │
        ▼
IntentModel
        │
        ▼
CommandInterpreter
        │
        ▼
normalized_signal
        │
        ▼
MultimodalFusion
        │
        ▼
SignalMapper
        │
        ▼
command_event
        │
        ▼
ActionExecutor
        │
        ▼
OSController
```

Every module has a single responsibility. Modules communicate only
through `EventBus` — no module calls another module directly.

## EventBus rules

Modules only ever call `subscribe()`, `unsubscribe()` and `publish()` on
the shared `EventBus`. There are no direct dependencies between modules.

## Module responsibilities

### Input

- `KeyboardInput` — reads the keyboard.
- `MicrophoneInput` — captures microphone audio.
- `CameraInput` — captures camera frames.

None of these perform recognition.

### Processing

- `KeyboardProcessor` — converts keyboard events into normalized keyboard
  signals.
- `SpeechRecognizer` — receives audio chunks, calls `VoskSpeechModel`,
  publishes `text_ready`.
- `GestureRecognizer` — detects gestures using MediaPipe, publishes
  gesture events.

### Speech recognition

Offline recognition uses Vosk (model: `vosk-model-small-en-us-0.15`).
`SpeechRecognizer` only ever forwards FINAL recognition results — partial
recognition is ignored by the rest of the system. Grammar is generated
from `config/mapping.json`; the command list is never duplicated
elsewhere.

### IntentModel

Receives `text_ready`, converts natural language into an internal
command (e.g. `"open browser"` → `OPEN_BROWSER`), publishes
`intent_detected`. `IntentModel` is the only module responsible for
converting spoken phrases into internal commands.

### CommandInterpreter

Receives `intent_detected`, `gesture_detected`, `keyboard_detected`;
produces `normalized_signal`. Responsible for validating and normalizing
signals — it does not perform multimodal logic or voice phrase mapping
(that already happened inside `IntentModel`).

### MultimodalFusion

Synchronizes signals, applies timeouts, maintains active signals;
publishes `fusion_signal`. Fusion never decides actions.

### SignalMapper

The only module responsible for decision-making. Receives
`fusion_signal`, reads `config/fusion.json`, produces `command_event`.
Only `SignalMapper` decides whether a command should be executed.

**Try Mode** is an independent on/off flag
(`SignalMapper.try_mode_active`), not a fifth entry in `modes` — it stays
on while the user switches between the exclusive modes (`current_mode`
only ever holds one at a time), so each mode can be demonstrated safely.
Toggled by voice/keyboard/UI triggers declared in `config/fusion.json`'s
own `try_mode.triggers` list, edge-triggered the same way `_check_rules`
is (gated on `triggering_source`, not just signal presence), so a held
keyboard combo can't flip it back and forth. "exit mode"/Esc/UI-exit turn
it off too, independently of whether a regular mode is currently active.
Published as `try_mode_changed` — `SignalMapper` still decides and
publishes `command_event` exactly as normal while it's on;
`ActionExecutor` is what actually skips the OS side effect.

### ActionExecutor

Receives `command_event`, calls `OSController`. `ActionExecutor` contains
no decision logic, with one exception: while Try Mode is on
(`try_mode_active`, mirrored from `SignalMapper`'s `try_mode_changed`),
it skips the `OSController` call for every command and every continuous
stream (pointer/pinch-drag/pinch-zoom) instead of calling it. This is a
dry-run gate, not a WHICH-command decision — it doesn't change what
`SignalMapper` decided, only whether the OS actually feels it.

## Configuration files

- **`mapping.json`** — maps inputs into normalized commands (e.g.
  `"open browser"` → `OPEN_BROWSER`). Single source of truth; grammar is
  generated from this file.
- **`fusion.json`** — defines multimodal rules: `rules`, `modes`,
  `mode_rules`. Describes the behavior of the multimodal system.
- **`system.json`** — global settings (thresholds, paths).
