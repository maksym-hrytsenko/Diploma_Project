# Gesture recognition test scenarios

Manual functional test scenarios for the gesture module (`GestureRecognizer`,
`GestureModel`/`OffHandModel`). Each scenario is graded on the same
three-point scale used throughout this test suite:

- **Correct** — the expected signal/action fires reliably, on the first
  attempt, with no unrelated side effect.
- **Partially correct** — the right signal eventually fires, but only after
  a noticeably wrong first attempt, an unexpected delay, or together with a
  minor unwanted side effect (e.g. the wrong mode briefly flashes before
  correcting itself).
- **Incorrect** — the wrong signal fires, nothing fires at all, or the
  wrong on-screen effect happens.

Run `python src/main.py --debug-gesture` for a live overlay of the detected
gesture, its confidence, and the tracked hand landmarks — use it to confirm
*what the recognizer actually saw* when a result looks wrong, before
deciding whether the problem is recognition or the downstream mapping
(`config/fusion.json`). A physical camera and a well-lit hand are required;
none of this can be automated headlessly.

---

## 1. Flip mode — directional swipes

Enter Flip mode first (voice "flip mode", keyboard `ctrl+shift+f`, or via
the Quick Circle — see §3). For each row: make a closed fist, open the
palm (this starts the tracked session), then swipe the index fingertip in
the given direction.

| # | Swipe direction | Expected signal | Expected action |
|---|---|---|---|
| 1 | Up | `HAND_UP` | Scrolls content down |
| 2 | Down | `HAND_DOWN` | Scrolls content up |
| 3 | Left | `HAND_LEFT` | `FLIP_NEXT` |
| 4 | Right | `HAND_RIGHT` | `FLIP_PREVIOUS` |

Also verify:
- A slow, deliberate hand movement that stays below the velocity threshold
  produces **no** swipe signal (jitter/accidental-motion rejection).
- Two swipes fired back-to-back faster than the `motion_cooldown` window
  (0.5 s) — confirm the second one is ignored, not queued.
- Closing the fist again ends the tracked session (`HAND_SESSION_END`) and
  a swipe attempted immediately after does nothing until the palm opens
  again.

## 2. Presentation mode — fist swipe

Enter Presentation mode. Make a closed fist and move the **wrist** (not
just the fingertip) left/right — this uses a separate, wrist-based
detector with its own thresholds (tuned for presenting distance, further
away from the camera than the Flip-mode swipe above).

| # | Fist movement | Expected action |
|---|---|---|
| 1 | Left | `PREVIOUS_SLIDE` |
| 2 | Right | `NEXT_SLIDE` |

Note: unlike the Flip-mode swipe, there is no separate arm/disarm gesture
— holding the fist itself is the active state. Confirm that opening the
hand mid-movement cancels the gesture (no swipe fires from an
already-in-progress motion that suddenly becomes an open palm).

## 3. Quick Circle — mode selection

From idle (no mode active), perform the hand-session-start gesture
(closed fist → open palm) to bring up the Quick Circle overlay, then swipe
in each direction.

| # | Swipe direction | Expected mode entered |
|---|---|---|
| 1 | Left | Presentation |
| 2 | Right | Call |
| 3 | Up | Flip |
| 4 | Down | Cursor |

Also verify:
- The Quick Circle does **not** open while another mode (e.g. Flip) is
  already active and a swipe session is in progress there.
- Closing the fist again without swiping in any direction closes the
  circle without entering any mode.

## 4. Cursor mode — pointer, click, drag, right-click

Enter Cursor mode. Point with the index finger (`Pointing_Up`).

| # | Action | Steps | Expected result |
|---|---|---|---|
| 1 | Pointer tracking | Move the pointing hand around the frame | On-screen cursor follows the fingertip; reaching close to (not exactly at) the camera frame's edge reaches the screen's edge |
| 2 | Click | Quick pinch (thumb + index touch, then release) | A single click fires *after* the double-pinch window (~0.3 s) passes with no second pinch |
| 3 | Drag / scroll | Pinch and hold while moving the hand, then release | Continuous scroll while held; releasing does **not** also fire a click |
| 4 | Right-click | Two quick pinches in a row | One `DOUBLE_PINCH` (right-click) fires — not two separate clicks |

## 5. Cursor mode — off-hand precision and zoom

Still in Cursor mode, with the primary hand `Pointing_Up`, bring a second
hand into frame.

| # | Off-hand gesture | Expected result |
|---|---|---|
| 1 | Second hand pinched (thumb+index touching), held | Cursor movement slows to roughly half speed (precision/"DPI-down" mode) relative to the same physical hand movement without it |
| 2 | Release the off-hand pinch | Cursor snaps to the primary fingertip's current absolute position (expected jump, not a bug) |
| 3 | Second hand open, move both index fingertips apart/together (primary hand's own pinch distance changes while the off-hand pinch is held) | Frontmost app zooms in (spreading) / out (closing) |

Also verify: engaging zoom while a click/drag was in progress on the
primary hand abandons the click/drag cleanly (no stray click fires once
zoom disengages).

## 6. Call mode — finger-count toggles

Enter Call mode. For each row, raise the given number of fingers (thumb
excluded from the count) and hold for at least 1.5 seconds continuously.

| # | Fingers raised | Expected action |
|---|---|---|
| 1 | One | Toggle microphone |
| 2 | Two | Toggle camera |
| 3 | Three | Toggle call audio |
| 4 | Four | Toggle background blur |

Also verify:
- Holding fewer than 1.5 s does **not** toggle anything.
- Showing the same finger count a second time *without* the hand leaving
  the camera frame in between does **not** toggle it again (lock behavior)
  — the hand must fully leave and re-enter the frame first.

## 7. Mode-gating cross-check (negative tests)

For each pairing below, confirm the gesture produces **no** effect at all
(not even a wrong one) while the wrong mode is active:

| # | Gesture | Wrong mode to test it in | Expected result |
|---|---|---|---|
| 1 | Pinch (thumb+index touch) | Flip | No click, no scroll |
| 2 | Finger-count (e.g. two fingers) | Cursor | No camera/mic toggle |
| 3 | Off-hand second hand present | Flip or Presentation | No precision/zoom behavior |

## How to test

1. Run `python src/main.py --debug-gesture`.
2. Enter the mode named in each section (voice command, keyboard shortcut,
   or the Quick Circle — see the mode-selection table above).
3. Perform each gesture and compare the console/overlay output and the
   actual on-screen/OS effect against the "Expected" column.
4. Record a grade (correct / partially correct / incorrect) per row, plus
   a short note for anything partial or incorrect (what actually
   happened instead).
