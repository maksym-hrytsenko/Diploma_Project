# Face recognition test scenarios

Manual functional test scenarios for the face module (`FaceRecognizer`,
`FaceModel`). Same three-point grading scale as `gesture_test_scenarios.md`:

- **Correct** — the expected signal/action fires reliably, on the first
  attempt, with no unrelated side effect.
- **Partially correct** — the right signal eventually fires, but only
  after an unnaturally exaggerated movement, a noticeable delay, or a
  minor unwanted side effect.
- **Incorrect** — the wrong signal fires, nothing fires at all, or the
  wrong on-screen effect happens.

Run `python src/main.py --debug-face` for a live overlay of pitch/yaw/roll
and a bar per blendshape (eyebrows/mouth/blink) with tick marks at the
enter/exit thresholds — use it to see whether a borderline result is a
recognition problem (the value never crossed the threshold) or a mapping
problem (the signal fired but nothing consumed it). A physical camera and
a well-lit face are required; none of this can be automated headlessly.

All scenarios below assume the system is **idle** (no gesture mode
active) — face tracking is suppressed entirely while any mode is active,
see §5.

## 1. Head tilt (with Alt held)

Hold `alt`, then tilt your head sideways (ear toward shoulder, face still
pointed at the camera — this is a *roll*, not turning your head to look
left/right, which is a *yaw* and produces no signal at all).

| # | Tilt direction | Expected signal | Expected action |
|---|---|---|---|
| 1 | Right | `HEAD_TILT_RIGHT` | `NEXT_TRACK` |
| 2 | Left | `HEAD_TILT_LEFT` | `PREVIOUS_TRACK` |

Also verify:
- Releasing `alt` and repeating the same tilt fires **no** action.
- The tilt only fires once on entering the tilted zone, not continuously
  while held.
- Returning to upright and tilting again re-fires correctly (hysteresis:
  enters at ~15°, exits only once back under ~8° — a value hovering right
  at the boundary should not flicker the signal repeatedly).

## 2. Eyebrows (with Alt / Ctrl held)

| # | Modifier held | Action | Expected signal | Expected action |
|---|---|---|---|---|
| 1 | `alt` | Raise eyebrows once | `EYEBROWS_UP` | `VOLUME_UP` (one tick) |
| 2 | `ctrl` | Raise eyebrows once | `EYEBROWS_UP` | `VOLUME_DOWN` (one tick) |
| 3 | none | Raise eyebrows once | `EYEBROWS_UP` fires (console/overlay only) | No action — confirm nothing happens without a modifier held |
| 4 | any | Lower eyebrows back down | `EYEBROWS_DOWN` | No action wired currently — grade on whether the signal itself fires, not on any effect |

Also verify: two eyebrow raises completing within ~0.6 s of each other
produce one `DOUBLE_EYEBROWS_UP` signal (console/overlay only — no action
wired up yet, same as `EYEBROWS_DOWN`), not two separate `EYEBROWS_UP`
volume changes.

## 3. Mouth open (with Alt held)

| # | Modifier held | Action | Expected signal | Expected action |
|---|---|---|---|---|
| 1 | `alt` | Open mouth | `MOUTH_OPEN` | Play/pause toggles |
| 2 | none | Open mouth | `MOUTH_OPEN` fires (console/overlay only) | No action — confirm nothing happens without `alt` held |

Also verify: `MOUTH_OPEN` fires once on the rising edge only — closing the
mouth again does **not** fire a second toggle.

## 4. Double blink (with Alt held) and nod

| # | Modifier held | Action | Expected signal | Expected result |
|---|---|---|---|---|
| 1 | `alt` | Blink twice quickly (within ~0.5 s) | `DOUBLE_BLINK` | A screenshot is saved to the desktop (or the configured screenshot location) |
| 2 | `alt` | Single blink only | no signal | Confirm nothing fires from a single blink |
| 3 | none | Nod your head (fast down-then-up, or up-then-down) | `CONFIRM` fires (console/overlay only) | No action wired currently — grade on whether the signal fires, not on any visible effect |

## 5. Idle-only gating (negative test)

Enter any mode (e.g. Flip, via voice or keyboard), then, while it is
active:

| # | Action | Expected result |
|---|---|---|
| 1 | Tilt your head as in §1, with `alt` held | No `HEAD_TILT_*` signal at all, no track change |
| 2 | Open your mouth with `alt` held | No `MOUTH_OPEN` signal, no play/pause |
| 3 | Nod your head | No `CONFIRM` signal |

Exit the mode (back to idle) and confirm face signals resume working
immediately without needing to restart the application.

## How to test

1. Run `python src/main.py --debug-face`.
2. From idle, work through §1–§4 in order, holding the modifier key
   (`alt`/`ctrl`) named in each row before performing the facial movement.
3. Compare the console/overlay output and the actual OS-level effect (or
   lack thereof, for the reserved/no-action signals) against the
   "Expected" columns.
4. Then enter a mode and repeat a few of the same movements per §5 to
   confirm the idle-only gating.
5. Record a grade (correct / partially correct / incorrect) per row, plus
   a short note for anything partial or incorrect.
