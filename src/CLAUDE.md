# CLAUDE.md

# Multimodal Computer Control System

This repository contains my Master's thesis project:

**"Design of a Multimodal System for Computer Control Using Gestures and Voice"**

The project is implemented in Python using an event-driven architecture. The goal is to build a modular multimodal interaction system that combines voice commands, hand gestures, keyboard shortcuts, and pointer tracking to control the operating system.

---

# Core Architecture

The project follows a strict event pipeline.

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

Every module has a single responsibility.

Modules communicate ONLY through EventBus.

No module should directly call another module.

---

# EventBus Rules

Always use EventBus.

Modules may only:

- subscribe()
- unsubscribe()
- publish()

Never introduce direct dependencies between modules.

---

# Module Responsibilities

## Input

KeyboardInput

- reads keyboard

MicrophoneInput

- captures microphone audio

CameraInput

- captures camera frames

These modules DO NOT perform recognition.

---

## Processing

KeyboardProcessor

Converts keyboard events into normalized keyboard signals.

SpeechRecognizer

Receives audio chunks.

Calls VoskSpeechModel.

Publishes:

```
text_ready
```

GestureRecognizer

Detects gestures using MediaPipe.

Publishes gesture events.

---

## Speech Recognition

Offline recognition uses:

```
Vosk
```

Current model:

```
vosk-model-small-en-us-0.15
```

SpeechRecognizer must only forward FINAL recognition results.

Partial recognition is ignored by the system.

Grammar should be automatically generated from:

```
config/mapping.json
```

Never duplicate the command list.

---

## IntentModel

Receives:

```
text_ready
```

Converts:

```
Natural Language

↓

Internal Command
```

Example:

```
"open browser"

↓

OPEN_BROWSER
```

Publishes:

```
intent_detected
```

IntentModel is the ONLY module responsible for converting spoken phrases into internal commands.

---

## CommandInterpreter

Receives:

```
intent_detected
gesture_detected
keyboard_detected
```

Produces:

```
normalized_signal
```

Responsibilities:

- validate signals
- normalize signals

It must NOT perform multimodal logic.

It must NOT perform voice phrase mapping.

Voice mapping already happened inside IntentModel.

---

## MultimodalFusion

Responsibilities:

- synchronize signals
- apply timeout
- maintain active signals

Publishes:

```
fusion_signal
```

Fusion NEVER decides actions.

---

## SignalMapper

SignalMapper is responsible for decision making.

Receives:

```
fusion_signal
```

Reads:

```
config/fusion.json
```

Produces:

```
command_event
```

Only SignalMapper decides whether a command should be executed.

---

## ActionExecutor

Receives:

```
command_event
```

Calls:

```
OSController
```

ActionExecutor must NOT contain decision logic.

---

# Configuration Files

## mapping.json

Maps inputs into normalized commands.

Example:

```
open browser

↓

OPEN_BROWSER
```

Single source of truth.

Grammar should also be generated from this file.

---

## fusion.json

Defines multimodal rules.

Contains:

- rules
- modes
- mode_rules

This file describes the behavior of the multimodal system.

---

## system.json

Contains global settings.

---

# Coding Style

Always follow the project's formatting style.

Requirements:

- one argument per line
- blank line between logical blocks
- descriptive comments
- no compact Python syntax
- avoid nested code
- keep functions small

Example:

```python
def process(
    self,
    data
):

    if data is None:
        return

    result = self.calculate(
        data
    )

    if result is None:
        return

    self.event_bus.publish(
        "event",
        result
    )
```

---

# Design Principles

Always prefer clean architecture.

Avoid hacks.

Avoid temporary fixes.

Keep modules independent.

One module = one responsibility.

Whenever possible improve the architecture instead of fixing only the immediate bug.

---

# Current Development Stage

Implemented:

- EventBus
- Keyboard input
- Voice input
- Gesture recognition
- Pointer tracking
- Offline speech recognition
- IntentModel
- CommandInterpreter
- MultimodalFusion
- SignalMapper
- ActionExecutor

---

# Current Goal

The current task is to redesign `fusion.json`.

The system should move from simple combinations like:

```
Keyboard + Voice

↓

Action
```

to a mode-based architecture.

Fusion should support:

- one-shot multimodal actions
- entering modes
- mode-specific actions

Planned modes:

- Presentation Mode
- Window Management Mode
- Coding Mode
- Study Mode

The implementation should closely follow the Master's thesis use cases.

Always think about scalability and maintainability before suggesting code changes.