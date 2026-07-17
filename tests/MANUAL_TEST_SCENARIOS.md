# Manual Test Scenarios

Everything in this project that needs a real camera, microphone, keyboard,
or macOS desktop to verify — none of it can run headlessly, which is why
it lives here as a checklist instead of in `test_pipeline.py` (the
automated pytest suite, which drives the decision-logic pipeline with
synthetic events and a mocked `OSController` — see that file's own
docstring). This file used to be several separate documents; most are
merged here, grouped by type, so there's one place to start.

Two voice-specific documents stay separate from this file on purpose —
they're working references meant to be read from directly during a live
test session, not sections to scroll to inside a longer checklist:
[`voice_test_phrases.md`](voice_test_phrases.md) (every command's tier-1/
2/3 phrases, one table per category) and
[`voice_test_session_script.md`](voice_test_session_script.md) (the same
phrases as one continuous numbered script for a single sitting, plus how
to read command latency — microphone to executed action — out of
`logs/app.log`). §4 below only summarizes and links to both.

For what to test conceptually, see [`docs/SYSTEM_FUNCTIONS.md`](../docs/SYSTEM_FUNCTIONS.md)
(behavior reference) and [`src/CLAUDE.md`](../src/CLAUDE.md) (architecture).
For the chronological engineering log of a real voice-pipeline debugging
session, see [`voice_pipeline_fixes_log.md`](voice_pipeline_fixes_log.md)
(a different kind of document — history, not a checklist).

## Contents

1. [Mode entry/exit (all input methods)](#1-mode-entryexit-all-input-methods)
2. [Gestures](#2-gestures)
3. [Face](#3-face)
4. [Voice — phrases and tiers](#4-voice--phrases-and-tiers)
5. [Environments](#5-environments)
6. [Global functions (app launching, media)](#6-global-functions-app-launching-media)
7. [UI and macOS integration](#7-ui-and-macos-integration)
8. [Try Mode](#8-try-mode)
9. [Presentation — slide switching (regression)](#9-presentation--slide-switching-regression)
10. [Stress / edge cases](#10-stress--edge-cases)

---

## 1. Mode entry/exit (all input methods)

Every mode in this system (Presentation, Flip, Cursor, Call) can be
entered through up to **four independent paths** — voice, keyboard, the
UI control wheel, and (for the four regular modes) indirectly via the
Quick Circle gesture menu — and exited through several independent paths
as well. Each path is a separate code path in `SignalMapper`
(`_update_mode`/`_mode_trigger_matches`), so recognizing a mode's gestures
correctly is not enough — every way of *getting into* that mode must also
be verified. This section covers that matrix; §2/§3 assume the mode is
already active.

Grading: **binary** (pass/fail) — the correct mode is entered/exited, full
stop. There is no partial credit for a mode transition.

### 1.1 Presentation mode — every entry path

| # | Entry method | Steps | Expected result |
|---|---|---|---|
| 1 | Voice, tier 1 (exact) | Say "jack presentation mode" | Presentation mode active |
| 2 | Voice, tier 2 (semantic) | Say "jack switch to presentation mode" | Presentation mode active |
| 3 | Voice, tier 3 (LLM) | Say "jack I'm about to give a talk, could you switch me into presentation mode" | Presentation mode active |
| 4 | Keyboard | Press `ctrl+shift+p` | Presentation mode active |
| 5 | UI | Click the Presentation icon on the control wheel | Presentation mode active |
| 6 | Gesture (Quick Circle) | From idle, closed fist → open palm, swipe left | Presentation mode active |

### 1.2 Flip mode — every entry path

| # | Entry method | Steps | Expected result |
|---|---|---|---|
| 1 | Voice, tier 1 | Say "jack flip mode" | Flip mode active |
| 2 | Voice, tier 2 | Say "jack switch to flip mode" | Flip mode active |
| 3 | Voice, tier 3 | Say "jack I want to scroll through pages, can you put me in flip mode please" | Flip mode active |
| 4 | Keyboard | Press `ctrl+shift+f` | Flip mode active |
| 5 | UI | Click the Flip icon on the control wheel | Flip mode active |
| 6 | Gesture (Quick Circle) | From idle, closed fist → open palm, swipe up | Flip mode active |

### 1.3 Cursor mode — every entry path

| # | Entry method | Steps | Expected result |
|---|---|---|---|
| 1 | Voice, tier 1 | Say "jack cursor mode" | Cursor mode active |
| 2 | Voice, tier 2 | Say "jack switch to cursor mode" | Cursor mode active |
| 3 | Voice, tier 3 | Say "jack I need to control the mouse with my hand, switch to cursor mode please" | Cursor mode active |
| 4 | Keyboard | Press `ctrl+shift+c` | Cursor mode active |
| 5 | UI | Click the Cursor icon on the control wheel | Cursor mode active |
| 6 | Gesture (Quick Circle) | From idle, closed fist → open palm, swipe down | Cursor mode active |

### 1.4 Call mode — every entry path

| # | Entry method | Steps | Expected result |
|---|---|---|---|
| 1 | Voice, tier 1 | Say "jack call mode" | Call mode active |
| 2 | Voice, tier 2 | Say "jack switch to call mode" | Call mode active |
| 3 | Voice, tier 3 | Say "jack I'm joining a meeting, could you put me into call mode" | Call mode active |
| 4 | Keyboard | Press `ctrl+shift+w` | Call mode active |
| 5 | UI | Click the Call icon on the control wheel | Call mode active |
| 6 | Gesture (Quick Circle) | From idle, closed fist → open palm, swipe right | Call mode active |

### 1.5 Exiting the active mode — every exit path

Enter any one mode, then try each exit path in turn (re-entering the mode
between attempts):

| # | Exit method | Steps | Expected result |
|---|---|---|---|
| 1 | Voice | Say "jack exit mode" | Returns to idle (no mode active) |
| 2 | Voice, tier 3 | Say "jack could you please take me out of this mode" | Returns to idle |
| 3 | Keyboard | Press `Esc` | Returns to idle |
| 4 | UI | Click the same mode's icon again on the control wheel (toggle off) | Returns to idle |
| 5 | Gesture, Quick Circle only | While Quick Circle is open, closed fist → open palm → closed fist again without swiping | Quick Circle closes without entering any mode (this is Quick Circle's *own* exit — closing the fist mid-swipe in Flip/Presentation/Cursor/Call does **not** exit those modes) |

### 1.6 Direct mode-to-mode switching (no explicit exit)

| # | Steps | Expected result |
|---|---|---|
| 1 | While Flip mode is active, say "jack cursor mode" directly (no "exit mode" first) | Switches directly to Cursor mode — the old mode is exited internally before the new one is entered, with no need to exit first |
| 2 | While Cursor mode is active, click the Call icon on the control wheel directly | Switches directly to Call mode |
| 3 | Try switching from a mode to itself (e.g. say "jack flip mode" while already in Flip mode) | No-op — stays in Flip mode, no exit/re-enter cycle, no duplicate `mode_changed` event |

### 1.7 System OFF interaction

| # | Steps | Expected result |
|---|---|---|
| 1 | Turn the system OFF (UI hub button) while idle, then try any entry method for any mode | Nothing happens — no mode is entered while the system is off |
| 2 | Turn the system OFF while a mode is active | The mode visibly exits as part of turning off (see also §10.5) |
| 3 | With the system OFF, click a mode icon on the control wheel | The system turns back ON automatically as part of that click, then the requested mode is entered — the UI never ends up showing an active mode while the hub still displays OFF |

**How to test:** run `python src/main.py --debug-voice` (add `--debug-gesture`
too if testing the Quick Circle entry path in the same pass). For each
mode, work through all six entry rows, confirming via the console log's
`Mode -> <name>` line and the UI's glow ring/label, not just the on-screen
visual alone. Record pass/fail per row — a tier-2/tier-3 voice phrase that
falls through to "command not understood" is a fail for that specific row
even if tier-1 for the same mode passes, note which tier broke.

---

## 2. Gestures

Manual functional test scenarios for the gesture module (`GestureRecognizer`,
`GestureModel`/`OffHandModel`). Each scenario is graded on a three-point
scale:

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
(`config/fusion.json`). A physical camera and a well-lit hand are required.

### 2.1 Flip mode — directional swipes

Enter Flip mode first. For each row: make a closed fist, open the palm
(this starts the tracked session), then swipe the index fingertip in the
given direction.

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

### 2.2 Presentation mode — fist swipe

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
already-in-progress motion that suddenly becomes an open palm). Physical
arrow keys are **not** wired to slide navigation on purpose — see §9.

### 2.3 Quick Circle — mode selection

From idle (no mode active), perform the hand-session-start gesture (closed
fist → open palm) to bring up the Quick Circle overlay, then swipe in each
direction.

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

### 2.4 Cursor mode — pointer, click, drag, right-click

Enter Cursor mode. Point with the index finger (`Pointing_Up`).

| # | Action | Steps | Expected result |
|---|---|---|---|
| 1 | Pointer tracking | Move the pointing hand around the frame | On-screen cursor follows the fingertip; reaching close to (not exactly at) the camera frame's edge reaches the screen's edge |
| 2 | Click | Quick pinch (thumb + index touch, then release) | A single click fires *after* the double-pinch window (~0.3 s) passes with no second pinch |
| 3 | Drag / scroll | Pinch and hold while moving the hand, then release | Continuous scroll while held; releasing does **not** also fire a click |
| 4 | Right-click | Two quick pinches in a row | One `DOUBLE_PINCH` (right-click) fires — not two separate clicks |

### 2.5 Cursor mode — off-hand precision and zoom

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

### 2.6 Call mode — finger-count toggles

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

### 2.7 Mode-gating cross-check (negative tests)

For each pairing below, confirm the gesture produces **no** effect at all
(not even a wrong one) while the wrong mode is active:

| # | Gesture | Wrong mode to test it in | Expected result |
|---|---|---|---|
| 1 | Pinch (thumb+index touch) | Flip | No click, no scroll |
| 2 | Finger-count (e.g. two fingers) | Cursor | No camera/mic toggle |
| 3 | Off-hand second hand present | Flip or Presentation | No precision/zoom behavior |

**How to test:** run `python src/main.py --debug-gesture`. Enter the mode
named in each section (voice command, keyboard shortcut, or the Quick
Circle), perform each gesture, and compare the console/overlay output and
the actual on-screen/OS effect against the "Expected" column. Record a
grade (correct / partially correct / incorrect) per row.

---

## 3. Face

Manual functional test scenarios for the face module (`FaceRecognizer`,
`FaceModel`). Same three-point grading scale as §2. Run
`python src/main.py --debug-face` for a live overlay of pitch/yaw/roll and
a bar per blendshape (eyebrows/mouth) with tick marks at the enter/exit
thresholds — use it to see whether a borderline result is a recognition
problem (the value never crossed the threshold) or a mapping problem (the
signal fired but nothing consumed it). A physical camera and a well-lit
face are required.

This is a global layer — every scenario below is expected to behave
identically whether the system is idle or a mode (Flip/Presentation/
Cursor/Call) is active. Run each row once from idle and once with a mode
active to confirm both.

### 3.1 Head tilt (with Alt held)

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

### 3.2 Eyebrows (with Alt / Ctrl held)

| # | Modifier held | Action | Expected signal | Expected action |
|---|---|---|---|---|
| 1 | `alt` | Raise eyebrows once | `EYEBROWS_UP` | `VOLUME_UP` (one tick) |
| 2 | `ctrl` | Raise eyebrows once | `EYEBROWS_UP` | `VOLUME_DOWN` (one tick) |
| 3 | none | Raise eyebrows once | `EYEBROWS_UP` fires (console/overlay only) | No action — confirm nothing happens without a modifier held |

### 3.3 Mouth open (with Alt held)

| # | Modifier held | Action | Expected signal | Expected action |
|---|---|---|---|---|
| 1 | `alt` | Open mouth | `MOUTH_OPEN` | Play/pause toggles |
| 2 | none | Open mouth | `MOUTH_OPEN` fires (console/overlay only) | No action — confirm nothing happens without `alt` held |

Also verify: `MOUTH_OPEN` fires once on the rising edge only — closing the
mouth again does **not** fire a second toggle.

**How to test:** run `python src/main.py --debug-face`. Work through
§3.1–§3.3 in order, holding the modifier key (`alt`/`ctrl`) named in each
row before performing the facial movement, once from idle and once with
any mode active. Compare the console/overlay output and the actual
OS-level effect (or lack thereof) against "Expected" — both passes should
match. Record a grade per row.

---

## 4. Voice — phrases and tiers

Kept as two separate, dedicated documents rather than inline here — see
the note at the top of this file:

- **[`voice_test_phrases.md`](voice_test_phrases.md)** — every command's
  tier-1 (exact) / tier-2 (semantic) / tier-3 (LLM) phrases, one table per
  category (apps, modes, environments, navigation, control words). Say a
  phrase and watch the console (`--debug-voice`) for which tier resolved
  it (`tier=exact` / `tier=semantic` / `tier=llm`), or `command not
  understood` if none did.
- **[`voice_test_session_script.md`](voice_test_session_script.md)** — the
  same phrases as one continuous numbered script for a single sitting
  (faster than testing each row in isolation, and it's how the VAD-driven
  utterance segmentation — see `speech_model.py`'s module docstring and
  [`voice_pipeline_fixes_log.md`](voice_pipeline_fixes_log.md) — gets
  exercised most realistically). Also documents how to read
  microphone-to-executed-command latency out of `logs/app.log`'s
  `speech_onset` field, and how to run `--debug-voice` on its own.

---

## 5. Environments

Manual test scenarios for the five voice-triggered environments (Work,
Job Search, Study, Movie, News) defined in `config/fusion.json`. Unlike
modes, environments are longer-lived and have real side effects on the OS
(opening apps, toggling Do Not Disturb, preventing display sleep) —
`test_pipeline.py` already verifies the *decision logic* (the right
`enter_actions`/`exit_actions` fire in the right order) against a mocked
`OSController`, so these scenarios exist to verify the **real** OS-level
effects actually happen, which the mocked automated suite cannot see.

Grading: **binary** (pass/fail) per real-world effect.

### 5.1 Work environment

| # | Action | Expected result |
|---|---|---|
| 1 | Say "jack work mode" | Do Not Disturb turns on; Slack, Mail, and Calendar all actually open |

### 5.2 Job Search environment

| # | Action | Expected result |
|---|---|---|
| 1 | Say "jack job search mode" | Do Not Disturb turns on; the job-search browser windows actually open |

### 5.3 Study environment

| # | Action | Expected result |
|---|---|---|
| 1 | Say "jack study mode" | Do Not Disturb turns on; the study browser windows actually open |

### 5.4 Movie environment

| # | Action | Expected result |
|---|---|---|
| 1 | Say "jack movie mode" | Do Not Disturb turns on; display sleep is prevented (screen does not dim/lock during playback); TV app and Netflix actually open; the cinema-mode Shortcuts automation (smart lighting) actually runs |

### 5.5 News environment

| # | Action | Expected result |
|---|---|---|
| 1 | Say "jack news mode" | The news browser tabs actually open (no Do Not Disturb change — News has no `enter_actions` DND toggle) |

### 5.6 Exiting an environment

| # | Action | Expected result |
|---|---|---|
| 1 | From Work environment, say "jack exit mode" | Do Not Disturb turns back off (Work's `exit_actions`) |
| 2 | From Movie environment, exit it | Do Not Disturb turns back off AND display-sleep prevention is lifted (both of Movie's `exit_actions` run) |
| 3 | From News environment, exit it | Nothing happens — News has an empty `exit_actions` list, which is correct, not a bug |

### 5.7 Direct environment-to-environment switching

| # | Action | Expected result |
|---|---|---|
| 1 | While Work environment is active, say "jack movie mode" directly | Ends up fully in Movie: Work's apps/DND are cleanly unwound and Movie's are cleanly applied — verify via the actual DND state and app windows, not just the console log |
| 2 | Switch to the same environment you're already in (e.g. say "jack work mode" again while Work is active) | No-op — no duplicate enter/exit cycle |

### 5.8 Environment and mode independence

| # | Action | Expected result |
|---|---|---|
| 1 | Enter Work environment, then enter Flip mode on top of it | Both are active simultaneously; Flip mode's gestures work normally |
| 2 | Exit Flip mode (voice/Esc/UI) while Work environment is still active | Only the mode exits — Work's apps/DND state are untouched |
| 3 | Exit the Work environment while a mode is active | Only the environment's state (DND, apps) unwinds; the active mode is untouched |

**How to test:** run `python src/main.py --debug-voice`. Before each
environment test, close any apps that environment would open and confirm
Do Not Disturb is off, so you can actually observe the change. For Movie
mode specifically, let the display sit idle longer than its normal sleep
timeout to confirm sleep prevention is real, not just logged. Record
pass/fail per row.

---

## 6. Global functions (app launching, media)

These voice-triggered functions work identically regardless of mode —
always available, not scoped to Presentation/Flip/Cursor/Call. §4 already
exhaustively covers all three recognition tiers for every command below;
this section instead verifies that the command, once recognized, actually
produces the correct **real** OS-level effect.

Grading: **binary** (pass/fail).

### 6.1 App launching (all 19 apps)

Say "jack open &lt;app&gt;" for each row (tier-1 phrasing — tier coverage
itself is §4's job).

| # | Command | Expected real-world effect |
|---|---|---|
| 1 | "jack open browser" | Default browser opens to google.com |
| 2 | "jack open chatgpt" | Browser opens chatgpt.com |
| 3 | "jack open github" | Browser opens github.com |
| 4 | "jack open vscode" | VS Code opens (requires the `code` CLI on `PATH`) |
| 5 | "jack open terminal" | Terminal.app opens |
| 6 | "jack open safari" | Safari opens |
| 7 | "jack open chrome" | Google Chrome opens |
| 8 | "jack open spotify" | Spotify opens |
| 9 | "jack open slack" | Slack opens |
| 10 | "jack open discord" | Discord opens |
| 11 | "jack open mail" | Mail.app opens |
| 12 | "jack open calendar" | Calendar.app opens |
| 13 | "jack open notes" | Notes.app opens |
| 14 | "jack open telegram" | Telegram opens |
| 15 | "jack open finder" | A Finder window opens |
| 16 | "jack open notion" | Notion opens |
| 17 | "jack open photos" | Photos.app opens |
| 18 | "jack open preview" | Preview.app opens |
| 19 | "jack open settings" | System Settings opens |

### 6.2 Global media commands

Start playing something first (Spotify track or a YouTube tab in a plain
browser window — not a screen share, see §6.3).

| # | Command | Expected result |
|---|---|---|
| 1 | "jack start" | Play/pause toggles |
| 2 | "jack stop" | Play/pause toggles (same underlying toggle as "start" — it does **not** stop/rewind playback, since `STOP`/`PAUSE`/`RESET` all map to the same `MEDIA_PLAY_PAUSE` action) |
| 3 | "jack pause" | Play/pause toggles |
| 4 | "jack reset" | Play/pause toggles — confirm it does **not** restart the track from the beginning |
| 5 | "jack next track" | Skips to the next track |
| 6 | "jack previous track" | Skips to the previous track |

### 6.3 Media commands vs. screen-share / embedded video (known limitation)

| # | Action | Expected result |
|---|---|---|
| 1 | Play a video in a plain Safari/Chrome tab, say "jack next track" | Track/video actually advances |
| 2 | Share that same tab's content via a video-conferencing app's screen share (e.g. Zoom's "optimize for video clip" share mode), then say "jack next track" | The console still prints `[EXECUTOR] NEXT_TRACK`, but the shared video does **not** advance — confirm this is the app swallowing the media key with no error (a known platform limitation, not a bug in this system), not a silent failure of recognition |

### 6.4 Face-layer media combos (cross-reference)

Already covered in §3.1/§3.3 (head tilt, mouth open, with `alt` held) —
re-run them here only for a combined pass covering every media-control
path (voice + face) in one session.

**How to test:** run `python src/main.py --debug-voice`. For §6.1, close
each app first so opening is actually observable, and confirm the
specific window/URL named above, not just "something opened." For
§6.2–§6.3, have real media actually playing before issuing a command.
Record pass/fail per row.

---

## 7. UI and macOS integration

Manual scenarios for the desktop UI (`MainWindow`, `FloatingStatusBar`,
`PointerOverlay`, `QuickCommandOverlay`) and macOS-specific window
behavior (`native_window.py`). Mode entry via UI is already covered in §1;
this section covers everything else the UI and OS-integration layer is
responsible for.

Grading: **binary** (pass/fail).

### 7.1 Module toggle switches (bottom status panel)

| # | Action | Expected result |
|---|---|---|
| 1 | Click the Camera toggle off | Camera preview shows its placeholder; camera-driven gestures stop working |
| 2 | Click the Camera toggle back on | Live preview resumes, gestures work again, no restart needed |
| 3 | Click the Microphone toggle off | Voice commands stop being recognized |
| 4 | Click the Microphone toggle back on | Voice commands work again |
| 5 | Click the Keyboard toggle off | Keyboard shortcuts (mode-entry combos, `alt`/`ctrl` face-layer, `Esc`) stop working |
| 6 | Click the Keyboard toggle back on | Keyboard shortcuts work again |

### 7.2 System ON/OFF hub button

See §10.5 for the mode-interaction edge case. This section covers the
simple cases:

| # | Action | Expected result |
|---|---|---|
| 1 | Click the hub to turn the system OFF while idle | Hub dims/shows OFF state; no voice/gesture/keyboard command produces any effect |
| 2 | Click the hub to turn the system back ON | Normal operation resumes immediately |

### 7.3 Settings and Info windows

| # | Action | Expected result |
|---|---|---|
| 1 | Click the gear/settings icon in the header | A Settings window opens |
| 2 | Click it again while the Settings window is already open | The existing window is raised/focused, not duplicated |
| 3 | Click "Functions description" | An Info window opens |
| 4 | Click it again while already open | The existing window is raised/focused, not duplicated |

### 7.4 Minimize-to-bar / Floating status bar

| # | Action | Expected result |
|---|---|---|
| 1 | Click "Minimize to bar" | `MainWindow` hides; the small `FloatingStatusBar` appears top-right, reflecting current module/mode state (dimmed icons for disabled modules, a highlighted ring on the active mode, if any) |
| 2 | While the floating bar is visible, toggle a module or change mode through voice/gesture | The floating bar's icons update to match, without needing `MainWindow` open |
| 3 | Click the floating bar's expand arrow | `MainWindow` reappears; the floating bar hides |
| 4 | Turn Try Mode on/off (§8) while the floating bar is visible | Hovering the bar shows "Try Mode: ON" in its tooltip |

### 7.5 Window chrome

| # | Action | Expected result |
|---|---|---|
| 1 | Drag the header area with the mouse | The window follows the cursor |
| 2 | Click the minimize button in the header | The window minimizes to the Dock |
| 3 | Click the close (✕) button in the header | The application fully quits — camera, microphone, gesture/voice recognition, and any overlay all stop, not just the window closing |

### 7.6 Debug flags

| # | Action | Expected result |
|---|---|---|
| 1 | Launch with `--debug-gesture` | A live gesture-calibration overlay window appears |
| 2 | Launch with `--debug-face` | A separate live face-calibration window appears (pitch/yaw/roll, blendshape bars with threshold ticks) |
| 3 | Launch with `--debug-voice` | The console prints detailed recognition info: partial phrases, final result, which tier resolved it (or that none did) |
| 4 | Launch with multiple flags at once (e.g. `--debug-gesture --debug-face`) | Both debug windows open together with no conflict |

### 7.7 macOS Dock, Spaces, and fullscreen behavior

| # | Action | Expected result |
|---|---|---|
| 1 | Check the Dock and Cmd+Tab app switcher while the app (including `MainWindow`) is running | No separate Dock icon or Cmd+Tab entry appears for this app — it runs as a background accessory app by design |
| 2 | Show the laser pointer (`Pointing_Up`, no mode active) or open the Quick Circle, then switch to a different macOS Space | The overlay stays visible on the new Space too |
| 3 | Show the same overlay while a different app is in fullscreen | The overlay still renders on top of the fullscreen app |
| 4 | Click into a different app (taking focus away from this one), then trigger the overlay | The overlay still appears even though this app isn't frontmost |
| 5 | Switch to a different Space while `MainWindow` itself (not an overlay) is open | `MainWindow` does **not** follow you — it is an ordinary window and stays on its original Space, unlike the overlays above |

### 7.8 Laser pointer and external display (projector)

| # | Action | Expected result |
|---|---|---|
| 1 | Connect a second display (projector) *before* launching the app, then show `Pointing_Up` with no mode active | The laser dot appears on the external display, not the laptop screen |
| 2 | Use only a single display | The dot appears on the primary screen |
| 3 | Connect a second display *after* the app is already running, then show `Pointing_Up` | The dot still appears on the original screen — the target display is only selected once, at startup; a restart is required to pick up a newly connected display |

### 7.9 Terminal/console cross-check (final pass)

Run through a representative sample of the scenarios in the other sections
once more, this time watching only the terminal output:

| # | Action | Expected result |
|---|---|---|
| 1 | Perform any normal, in-scope action | Exactly one `[EXECUTOR] <COMMAND>` line appears, no duplicates |
| 2 | Say a command without the "jack" activation word first | No command line appears at all — no session was open |
| 3 | Perform a gesture/voice signal that doesn't belong to the current mode | No command line appears |
| 4 | Say a phrase after "jack" that matches nothing in any tier | A `[RESOLVED] not understood: ...`-style line eventually appears once the session times out |
| 5 | Click UI buttons directly (mode wheel, toggles, System ON/OFF, Try Mode) | These do **not** print `[EXECUTOR] ...` lines themselves — they publish `ui_*` events that flow through the same pipeline as any other source, so the resulting command (if any) is what prints, not the click itself |
| 6 | Run through a full session touching every mode/environment/global command at least once | No line tagged `ERROR` appears anywhere in the log |

**How to test:** run `python src/main.py` (add debug flags per §7.6 as
needed). Work through each section, comparing on-screen behavior against
"Expected result". Record pass/fail per row, noting log lines for
anything unexpected.

---

## 8. Try Mode

Manual scenarios for Try Mode — the independent on/off flag (not a mode
itself) that suppresses every real OS side effect. See
`docs/SYSTEM_FUNCTIONS.md` §2.6 for the full behavior reference.

Grading: **binary** (pass/fail).

### 8.1 Turning it on/off — every path

| # | Method | Steps | Expected result |
|---|---|---|---|
| 1 | Voice | Say "jack try mode" | Try Mode turns on; the switch next to the camera preview and the "● TRY MODE" badge both update |
| 2 | Voice again | Say "jack try mode" a second time | Try Mode turns back off |
| 3 | Keyboard | Press `ctrl+shift+t` | Try Mode toggles, switch/badge update the same way |
| 4 | UI | Click the switch next to the camera preview | Try Mode toggles, same as voice/keyboard |
| 5 | Voice, tier 3 | Say "jack can you let me try things out safely without actually doing anything" | Try Mode turns on |

### 8.2 No real effect while active

With Try Mode on, for each row, confirm the console prints
`[TRY MODE] would execute: <COMMAND>` and that nothing actually happens on
the computer:

| # | Action | Expected result |
|---|---|---|
| 1 | Enter Presentation mode, say "jack next slide" | No slide changes anywhere; `[TRY MODE] would execute: NEXT_SLIDE` prints |
| 2 | Enter Flip mode, swipe up | No scroll happens |
| 3 | Enter Cursor mode, point and move your hand | The laser-pointer dot shows where the cursor would go, but the real OS cursor does not move |
| 4 | Still in Cursor mode, pinch to click | No real click happens |
| 5 | Say "jack open browser" | No browser opens |
| 6 | Enter Call mode, hold up one finger for 1.5s | No mic toggle happens |

### 8.3 Everything else keeps working

| # | Action | Expected result |
|---|---|---|
| 1 | With Try Mode on, switch between Presentation/Flip/Cursor/Call in turn | Mode switching works exactly as normal — the wheel's glow ring and "Current mode: …" label update normally |
| 2 | With Try Mode on, look at the camera preview while making different gestures | The "Detected: …" caption keeps updating live, same as with Try Mode off |

### 8.4 Turning it off

| # | Action | Expected result |
|---|---|---|
| 1 | With Try Mode on and no regular mode active, say "jack exit mode" (or press Esc) | Try Mode turns off |
| 2 | With Try Mode on AND a regular mode active, say "jack exit mode" | Both the active mode and Try Mode turn off together |
| 3 | With Try Mode on and the system turned OFF via the hub button, click a mode icon | The system turns back on (as usual) — confirm whether Try Mode is still on or off matches whatever it's set to log as `try_mode_changed`, and isn't left visually out of sync with the switch |

**How to test:** run `python src/main.py --debug-voice --debug-gesture`.
Work through §8.1–§8.4 in order. For §8.2 specifically, keep a close eye
on whether anything at all visibly happens on the real desktop (an app
window, a cursor jump, a slide change) — the bar is "nothing", not "mostly
nothing."

---

## 9. Presentation — slide switching (regression)

Regression check for a fixed bug: slide switching used to skip two slides
at once. Root cause: `pynput` can't suppress the physical Right/Left
arrow keypress from also reaching the focused presentation app, so the
system's own synthetic arrow press (sent for the SAME physical keypress)
doubled up with the real one. Fixed by removing the keyboard trigger for
`NEXT_SLIDE`/`PREVIOUS_SLIDE` entirely — see
[`voice_pipeline_fixes_log.md`](voice_pipeline_fixes_log.md) and
`docs/SYSTEM_FUNCTIONS.md` §2.1.

Grading: **binary** (pass/fail).

| # | Action | Expected result |
|---|---|---|
| 1 | Enter Presentation mode with a real presentation app (Keynote/PowerPoint/Google Slides) frontmost and press the physical Right arrow key once | Exactly **one** slide advances, not two |
| 2 | Same, physical Left arrow key | Exactly one slide goes back, not two |
| 3 | Hold the physical Right arrow key down (OS auto-repeat kicks in) | The presentation app's own native auto-repeat behavior applies (whatever that app normally does when you hold the arrow key) — the console must **not** print a matching flood of `[EXECUTOR] NEXT_SLIDE` lines from this system, since no `KEY_RIGHT`-based rule exists anymore |
| 4 | Say "jack next slide" / "jack previous slide" | Still works normally — one slide per phrase |
| 5 | Closed-fist wrist swipe right/left | Still works normally — one slide per swipe |

**How to test:** run `python src/main.py --debug-voice`, open a real
presentation file so slide changes are actually visible, enter
Presentation mode, and count slides advanced per keypress.

---

## 10. Stress / edge cases

Manual stress and edge-case scenarios for the running system. Unlike §2/§3,
these are graded **binary** (pass/fail), and the criterion is **system
stability**, not recognition accuracy: does the system stay in a
consistent, responsive state afterward, with no crash and no permanently
stuck mode?

These scenarios exist specifically for timing/concurrency conditions that
the automated regression suite (`test_pipeline.py`) cannot cover — that
suite drives the pipeline with synthetic, one-at-a-time `EventBus` events,
so it already fully covers whether the *decision logic itself* is correct
for a given input. What it cannot cover is what happens when real hardware
produces signals with real, overlapping timing. A physical camera,
microphone, and keyboard are required.

- **Pass** — the system remains fully responsive afterward: the correct
  (or at least a sane, non-contradictory) final state is reached, no
  exception is visible in the log/console, and no further input is
  permanently ignored.
- **Fail** — the application crashes, becomes unresponsive, gets stuck in
  a mode that no longer responds to exit requests, or ends up in a
  visibly self-contradictory state (e.g. the UI shows one mode active
  while the system is actually in another).

### 10.1 Rapid mode switching

Trigger mode changes back-to-back, faster than a human would normally
pause between them — e.g. say "flip mode", then immediately "cursor
mode", then immediately "call mode", all within a couple of seconds
(within `signal_timeout`, 2 s).

- Confirm the final active mode is the last one requested, not an earlier
  one "stuck" mid-transition.
- Confirm the UI (glow ring on the control wheel / floating status bar)
  agrees with the actual active mode at every point, not just at the end.
- Repeat using the keyboard shortcuts (`ctrl+shift+f`, `ctrl+shift+c`,
  `ctrl+shift+w`, `ctrl+shift+p`) pressed in quick succession instead of
  voice.

### 10.2 Simultaneous multi-modal signals

Produce two signals from different modalities at (as close as possible
to) the same instant — e.g. say "cursor mode" at the exact moment you
also perform the Quick Circle swipe gesture, or hold a mode-entry
keyboard combo while also speaking a different mode's voice command.

- Confirm the system deterministically resolves to one outcome (does not
  try to enter two modes at once, does not crash on the conflicting
  input).
- Confirm the log's `[RESOLVED]` line names exactly one source as the
  cause, matching whichever request the system actually landed on.

### 10.3 Quick Circle rapid open/close

Perform the hand-session-start gesture (fist → open palm) and close the
fist again immediately, several times in a row, without ever swiping in a
direction.

- Confirm the circle opens and closes cleanly each time with no residual
  overlay left on screen.
- Confirm no mode is accidentally entered from this alone.
- Then repeat, but on one of the repetitions actually swipe to select a
  mode — confirm that one specific attempt still correctly enters the
  chosen mode despite the rapid open/close immediately before it.

### 10.4 Persistent modifier key held through unrelated signals

Hold `alt` down continuously. While still holding it, in sequence:
perform an unrelated gesture (e.g. a Flip-mode swipe), speak an unrelated
voice command, then finally do a face-layer action that alt should
enable (e.g. tilt your head for next track).

- Confirm the face-layer action (next track) fires exactly once, not
  repeatedly for as long as `alt` stays down, and not retroactively for
  the earlier, unrelated gesture/voice signals that happened while alt
  was already held.

Repeat with `ctrl+shift+t` (Try Mode) held instead of `alt`: while it's
held, perform an unrelated voice command and gesture — confirm Try Mode
does not flip on/off/on repeatedly just because those unrelated signals
kept arriving while the combo stayed down (only OS key auto-repeat on
the SAME combo can cause that — see the known limitation noted in
`src/CLAUDE.md`'s Try Mode section — this row is specifically about
*other* signals, not repeats of the same key).

### 10.5 System OFF mid-mode

Enter any mode (e.g. Presentation), then click the central system ON/OFF
hub button in the UI to turn the system off while the mode is still
active.

- Confirm the mode visibly exits (glow ring turns off) as part of
  turning off, not left active-but-unresponsive.
- Turn the system back on — confirm no mode is silently still active
  from before, and that voice/gesture/keyboard commands work normally
  again.

### 10.6 Input module disabled mid-use

While actively using a mode that depends on a given input (e.g. Cursor
mode, which needs the camera), use the bottom status panel's toggle
switch to disable that module (camera off) mid-use.

- Confirm the running mode does not crash; the camera preview should
  show its placeholder again and gesture-based cursor movement should
  simply stop, not throw a visible error.
- Re-enable the module and confirm it resumes working without needing to
  restart the application or re-enter the mode.

### 10.7 Rapid UI clicking

Click each of the four mode-wheel buttons in the main window in quick
succession, faster than their real-world gesture/voice equivalents could
ever be produced.

- Confirm the final active mode matches the last button clicked.
- Confirm the "Current mode: …" label and the glow ring never disagree
  with each other, even momentarily during the clicking.

### 10.8 Hand leaving frame during a Call-mode toggle hold

In Call mode, raise the number of fingers for a toggle (e.g. two, for
camera) and, partway through the required 1.5 s hold, briefly move your
hand out of frame and back in before the hold completes.

- Confirm a brief dropout (a frame or two, e.g. from motion blur) does
  not reset the hold timer in a way that makes the gesture impossible to
  complete in practice.
- Confirm a hand *fully* leaving the frame for a sustained period does
  reset the hold, requiring the gesture to be shown again from the
  start (this is the documented, correct behavior — verify it still
  holds, not that it's absent).

### 10.9 Packaged `.app` regression check: no duplicate process spawning

This is a targeted regression check for a specific historical bug (see
chapter 4.4 of the thesis): after packaging, `ProcessPoolExecutor` workers
used for Whisper fallback / semantic-LLM matching could end up re-launching
the whole application instead of starting as plain worker processes,
because `sys.executable` pointed at the packaged app itself.

- Launch the packaged `.app` (not `python src/main.py`).
- Deliberately trigger the Whisper fallback several times in a row (speak
  phrases designed to miss Vosk's grammar — see §4's tier-3 phrases) and,
  separately, trigger the semantic/LLM command matching fallback several
  times.
- After each burst, check Activity Monitor (or `ps aux | grep
  GestureVoiceControl`) — confirm exactly one instance of the application
  is running, not one new one per fallback triggered.

### 10.10 Extended idle soak

Leave the application running idle (camera and microphone active, no
mode entered) for at least 30 minutes.

- Confirm it is still responsive to a voice command or gesture at the
  end of that period.
- Note: the system currently has no watchdog/auto-recovery process (see
  chapter 4.4, "known limitation") — this scenario is meant to observe
  whether that gap actually causes a practical problem over a realistic
  session length, not to test a recovery mechanism that doesn't exist.

### 10.11 Boundary timing: gesture confirmation debounce

`confirm_frames` requires a gesture to hold for 4 consecutive frames
before it is trusted (see `gesture_recognizer.py`).

- Hold a static gesture (e.g. `Closed_Fist`) for just 2-3 frames, then
  relax — confirm it is treated as noise and does **not** start/end a
  tracking session.
- Hold it for clearly more than 4 frames — confirm it is trusted
  reliably, not intermittently.

### 10.12 Boundary timing: double-pinch window

The double-pinch window is 0.3 s (`double_pinch_window`).

- In Cursor mode, do two quick pinches with a gap noticeably *under*
  0.3 s between them — confirm a single `DOUBLE_PINCH` (right-click).
- Do two quick pinches with a gap noticeably *over* 0.3 s — confirm two
  separate `PINCH` clicks instead, not a right-click.
- Do two pinches with the gap as close to exactly 0.3 s as you can
  manage by feel — confirm the system lands on one behavior or the
  other consistently rather than behaving unpredictably run to run.

### 10.13 Boundary timing: Call-mode toggle hold

The hold requirement is 1.5 s (`call_toggle_hold_seconds`).

- Hold a finger-count gesture for clearly *under* 1.5 s and release —
  confirm nothing toggles.
- Hold for clearly *over* 1.5 s — confirm it toggles reliably.
- Change the finger count partway through the hold (e.g. show two
  fingers, then three, before either reaches 1.5 s) — confirm the hold
  timer restarts for the new count rather than crediting time already
  spent on the old one, and that neither toggle fires from a hold that
  was never sustained at a single count for the full 1.5 s.

### 10.14 Rapid switching between an environment and a mode

- With Work environment active, rapidly enter and exit Flip mode
  several times in a row (voice/keyboard/UI, mixed) — confirm the
  environment's state (DND, open apps) is never touched by any of the
  mode transitions, and the final state is: Work still active, no mode
  active.
- With a mode active, rapidly trigger environment switches (e.g. Work
  → Study → Movie in quick succession) — confirm the active mode is
  undisturbed throughout and the final environment is the last one
  requested, with that environment's own `enter_actions` having fully
  run (not interrupted mid-sequence by the next request).

### 10.15 Call-mode toggle when the target app isn't running

- Enter Call mode without Microsoft Teams running at all, then trigger
  one of the finger-count toggles (e.g. two fingers for camera).
- Confirm the system does not crash and prints its normal
  `[EXECUTOR] TOGGLE_CAMERA`-style line — the keystroke is sent
  regardless of whether Teams is the frontmost/running app, so this is
  expected to silently do nothing useful, not to error out.

### 10.16 Voice recognition load during active gesture tracking

- Enter Flip mode and perform a continuous, ongoing swipe-tracking
  session (fist held open, hand moving) while simultaneously speaking
  a voice command with the activation word.
- Confirm the voice command is still recognized correctly (no dropped
  audio, no missed activation word) despite the camera-processing loop
  running concurrently, and that the gesture tracking itself does not
  stutter or drop frames noticeably while speech recognition is
  active.

**How to test:** run `python src/main.py` (§10.9 specifically requires the
packaged `.app` instead). Work through each scenario, watching both the
on-screen behavior and the console/log output for exceptions or
`[RESOLVED]`/`Mode ->` lines that don't match what you expect. Record a
pass/fail per scenario, with a short note of what actually happened for
any failure.
