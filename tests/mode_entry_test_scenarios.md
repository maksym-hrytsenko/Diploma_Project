# Mode entry/exit test scenarios (all input methods)

Every mode in this system (Presentation, Flip, Cursor, Call) can be
entered through up to **four independent paths** — voice, keyboard,
the UI control wheel, and (for the four regular modes) indirectly via
the Quick Circle gesture menu — and exited through several independent
paths as well. Each path is a separate code path in `SignalMapper`
(`_update_mode`/`_mode_trigger_matches`), so recognizing a mode's
gestures correctly is not enough — every way of *getting into* that
mode must also be verified. This document exists specifically to cover
that matrix; the gesture/face documents assume the mode is already
active.

Grading: **binary** (pass/fail) — the correct mode is entered/exited,
full stop. There is no partial credit for a mode transition.

## 1. Presentation mode — every entry path

| # | Entry method | Steps | Expected result |
|---|---|---|---|
| 1 | Voice, tier 1 (exact) | Say "jack presentation mode" | Presentation mode active |
| 2 | Voice, tier 2 (semantic) | Say "jack switch to presentation mode" | Presentation mode active |
| 3 | Voice, tier 3 (LLM) | Say "jack I'm about to give a talk, could you switch me into presentation mode" | Presentation mode active |
| 4 | Keyboard | Press `ctrl+shift+p` | Presentation mode active |
| 5 | UI | Click the Presentation icon on the control wheel | Presentation mode active |
| 6 | Gesture (Quick Circle) | From idle, closed fist → open palm, swipe left | Presentation mode active |

## 2. Flip mode — every entry path

| # | Entry method | Steps | Expected result |
|---|---|---|---|
| 1 | Voice, tier 1 | Say "jack flip mode" | Flip mode active |
| 2 | Voice, tier 2 | Say "jack switch to flip mode" | Flip mode active |
| 3 | Voice, tier 3 | Say "jack I want to scroll through pages, can you put me in flip mode please" | Flip mode active |
| 4 | Keyboard | Press `ctrl+shift+f` | Flip mode active |
| 5 | UI | Click the Flip icon on the control wheel | Flip mode active |
| 6 | Gesture (Quick Circle) | From idle, closed fist → open palm, swipe up | Flip mode active |

## 3. Cursor mode — every entry path

| # | Entry method | Steps | Expected result |
|---|---|---|---|
| 1 | Voice, tier 1 | Say "jack cursor mode" | Cursor mode active |
| 2 | Voice, tier 2 | Say "jack switch to cursor mode" | Cursor mode active |
| 3 | Voice, tier 3 | Say "jack I need to control the mouse with my hand, switch to cursor mode please" | Cursor mode active |
| 4 | Keyboard | Press `ctrl+shift+c` | Cursor mode active |
| 5 | UI | Click the Cursor icon on the control wheel | Cursor mode active |
| 6 | Gesture (Quick Circle) | From idle, closed fist → open palm, swipe down | Cursor mode active |

## 4. Call mode — every entry path

| # | Entry method | Steps | Expected result |
|---|---|---|---|
| 1 | Voice, tier 1 | Say "jack call mode" | Call mode active |
| 2 | Voice, tier 2 | Say "jack switch to call mode" | Call mode active |
| 3 | Voice, tier 3 | Say "jack I'm joining a meeting, could you put me into call mode" | Call mode active |
| 4 | Keyboard | Press `ctrl+shift+w` | Call mode active |
| 5 | UI | Click the Call icon on the control wheel | Call mode active |
| 6 | Gesture (Quick Circle) | From idle, closed fist → open palm, swipe right | Call mode active |

## 5. Exiting the active mode — every exit path

Enter any one mode, then try each exit path in turn (re-entering the
mode between attempts):

| # | Exit method | Steps | Expected result |
|---|---|---|---|
| 1 | Voice | Say "jack exit mode" | Returns to idle (no mode active) |
| 2 | Voice, tier 3 | Say "jack could you please take me out of this mode" | Returns to idle |
| 3 | Keyboard | Press `Esc` | Returns to idle |
| 4 | UI | Click the same mode's icon again on the control wheel (toggle off) | Returns to idle |
| 5 | Gesture, Quick Circle only | While Quick Circle is open, closed fist → open palm → closed fist again without swiping | Quick Circle closes without entering any mode (this is Quick Circle's *own* exit — closing the fist mid-swipe in Flip/Presentation/Cursor/Call does **not** exit those modes) |

## 6. Direct mode-to-mode switching (no explicit exit)

| # | Steps | Expected result |
|---|---|---|
| 1 | While Flip mode is active, say "jack cursor mode" directly (no "exit mode" first) | Switches directly to Cursor mode — the old mode is exited internally before the new one is entered, with no need to exit first |
| 2 | While Cursor mode is active, click the Call icon on the control wheel directly | Switches directly to Call mode |
| 3 | Try switching from a mode to itself (e.g. say "jack flip mode" while already in Flip mode) | No-op — stays in Flip mode, no exit/re-enter cycle, no duplicate `mode_changed` event |

## 7. System OFF interaction

| # | Steps | Expected result |
|---|---|---|
| 1 | Turn the system OFF (UI hub button) while idle, then try any entry method for any mode | Nothing happens — no mode is entered while the system is off |
| 2 | Turn the system OFF while a mode is active | The mode visibly exits as part of turning off (see also `stress_test_scenarios.md` §5) |
| 3 | With the system OFF, click a mode icon on the control wheel | The system turns back ON automatically as part of that click, then the requested mode is entered — the UI never ends up showing an active mode while the hub still displays OFF |

## How to test

1. Run `python src/main.py --debug-voice` (add `--debug-gesture` too if
   testing the Quick Circle entry path in the same pass).
2. For each mode, work through all six entry rows, confirming via the
   console log's `Mode -> <name>` line and the UI's glow ring/label,
   not just the on-screen visual alone.
3. Record pass/fail per row. A tier-2/tier-3 voice phrase that falls
   through to "command not understood" is a fail for that specific row
   even if tier-1 for the same mode passes — note which tier broke.
