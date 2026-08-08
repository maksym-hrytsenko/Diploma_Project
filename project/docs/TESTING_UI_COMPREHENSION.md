# UI Comprehension Study

The graphical interface was built as an additional, supportive layer on
top of the gesture/voice/face control system, not one of the core
interaction modalities validated in
[`TESTING_EXTERNAL_USERS.md`](TESTING_EXTERNAL_USERS.md) — see
[`UI_SPEC.txt`](UI_SPEC.txt) §10, "Final UI decisions." Whether it was
worth building it, though, depends on whether it's actually legible to
someone who has never seen it before. This study is scoped narrowly to
that: can a first-time viewer, given a plain-language instruction, find
the right control quickly — independent of whether they can perform the
hand/face gestures tested in
[`TESTING_EXTERNAL_USERS.md`](TESTING_EXTERNAL_USERS.md).

## Contents

1. [Goal and methodology](#1-goal-and-methodology)
2. [Materials](#2-materials)
3. [Scenarios (12 tasks)](#3-scenarios-12-tasks)
4. [Status](#4-status)

---

## 1. Goal and methodology

Goal: measure how quickly and accurately a first-time viewer locates the
correct on-screen control for a given instruction, and get a rough sense
of where their attention goes while searching — **without eye-tracking
hardware**, which this kind of check does not require. Two standard
substitutes from usability research stand in for it:

- **First-click accuracy** — whether the participant's first click/point
  lands on the correct control, or on something else first. Task success
  correlates strongly with getting the first click right, which is why
  "first-click testing" is a standard low-tech substitute for gaze
  tracking in usability research (Sauro et al.).
- **Time-to-correct** — seconds from the end of the spoken instruction to
  the moment the participant reaches the correct control.
- **Think-aloud** (optional, lightweight qualitative supplement) — the
  participant narrates what they're looking at while searching, giving the
  moderator a rough sense of scan path without instrumented gaze data.

Because this tests UI legibility, not gesture recognition, running it does
not require the live camera/gesture pipeline, the app's permissions, or
even a working build — see Materials below.

## 2. Materials

A static image (or a clickable prototype built from it) of the Main
Control Panel, matching [`UI_SPEC.txt`](UI_SPEC.txt) exactly — window
1440×900, the header panel, camera preview panel, circular control wheel,
and bottom status panel with its two extra buttons. Using the specified
layout directly means every control's correct hit region is already known
precisely (`UI_SPEC.txt` gives x/y/width/height for each element), so a
participant's click coordinates can be scored as correct/incorrect without
guesswork.

## 3. Scenarios (12 tasks)

Each task is a plain-language instruction from the moderator — not the
app's own wake-word phrasing — read aloud once. The participant then
points at or clicks where they believe the correct control is; the
moderator records first-click accuracy and time-to-correct (§1).

| # | Instruction given to the participant | Correct control |
|---|---|---|
| 1 | "Turn off the microphone." | `toggle_microphone` |
| 2 | "Turn off the camera." | `toggle_camera` |
| 3 | "Disable keyboard input." | `toggle_keyboard` |
| 4 | "Switch to Cursor mode." | `btn_cursor_mode` |
| 5 | "Switch to Presentation mode." | `btn_presentation` |
| 6 | "Switch to Call mode." | `btn_call_mode` |
| 7 | "Switch to Flip mode." | `btn_mode_flip` |
| 8 | "Turn the whole system off." | `btn_system_power` |
| 9 | "Find out what commands this app understands." | `btn_functions` |
| 10 | "Put the app away without closing it — keep it running in the background." | `btn_minimize_to_bar` |
| 11 | "Open the app's settings." | `btn_window_settings` |
| 12 | "Check whether the camera can currently see you." | `panel_camera_preview` (status chip / "Detected: ..." overlay) |

Element names match [`UI_SPEC.txt`](UI_SPEC.txt) §8, "Object names for
PySide6," directly, so results can be cross-referenced against the exact
coordinates given there. The 12 instructions were chosen to cover all
three zones of the interface at least once each: the header (settings),
the circular control wheel (the 4 modes + system power), and the bottom
status panel (the 3 module toggles + functions + minimize).

## 4. Status

**Not yet executed.** The scenarios above are a designed, ready-to-run
protocol — no sessions have been held, so this document has no results
section yet. Running it needs no gesture-tracking hardware or even the
live app: a printed or on-screen static image of the Main Control Panel
and a stopwatch are enough.
