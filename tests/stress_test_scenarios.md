# Stress / edge-case test scenarios

Manual stress and edge-case scenarios for the running system. Unlike
`gesture_test_scenarios.md` and `face_test_scenarios.md`, these are graded
**binary** (pass/fail), and the criterion is **system stability**, not
recognition accuracy: does the system stay in a consistent, responsive
state afterward, with no crash and no permanently stuck mode?

These scenarios exist specifically for timing/concurrency conditions that
the automated regression suite (`test_command_pipeline.py`) cannot cover —
that suite drives the pipeline with synthetic, one-at-a-time `EventBus`
events, so it already fully covers whether the *decision logic itself* is
correct for a given input (e.g. that an environment's `exit_actions` run
before the next one's `enter_actions`). What it cannot cover is what
happens when real hardware produces signals with real, overlapping timing
— that is the purpose of this document. A physical camera, microphone,
and keyboard are required; none of this can be automated headlessly.

- **Pass** — the system remains fully responsive afterward: the correct
  (or at least a sane, non-contradictory) final state is reached, no
  exception is visible in the log/console, and no further input is
  permanently ignored.
- **Fail** — the application crashes, becomes unresponsive, gets stuck in
  a mode that no longer responds to exit requests, or ends up in a
  visibly self-contradictory state (e.g. the UI shows one mode active
  while the system is actually in another).

## 1. Rapid mode switching

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

## 2. Simultaneous multi-modal signals

Produce two signals from different modalities at (as close as possible
to) the same instant — e.g. say "cursor mode" at the exact moment you
also perform the Quick Circle swipe gesture, or hold a mode-entry
keyboard combo while also speaking a different mode's voice command.

- Confirm the system deterministically resolves to one outcome (does not
  try to enter two modes at once, does not crash on the conflicting
  input).
- Confirm the log's `[RESOLVED]` line names exactly one source as the
  cause, matching whichever request actually the system landed on.

## 3. Quick Circle rapid open/close

Perform the hand-session-start gesture (fist → open palm) and close the
fist again immediately, several times in a row, without ever swiping in a
direction.

- Confirm the circle opens and closes cleanly each time with no residual
  overlay left on screen.
- Confirm no mode is accidentally entered from this alone.
- Then repeat, but on one of the repetitions actually swipe to select a
  mode — confirm that one specific attempt still correctly enters the
  chosen mode despite the rapid open/close immediately before it.

## 4. Persistent modifier key held through unrelated signals

Hold `alt` down continuously. While still holding it, in sequence:
perform an unrelated gesture (e.g. a Flip-mode swipe), speak an unrelated
voice command, then finally do a face-layer action that alt should
enable (e.g. tilt your head for next track).

- Confirm the face-layer action (next track) fires exactly once, not
  repeatedly for as long as `alt` stays down, and not retroactively for
  the earlier, unrelated gesture/voice signals that happened while alt
  was already held.

## 5. System OFF mid-mode

Enter any mode (e.g. Presentation), then click the central system
ON/OFF hub button in the UI to turn the system off while the mode is
still active.

- Confirm the mode visibly exits (glow ring turns off) as part of
  turning off, not left active-but-unresponsive.
- Turn the system back on — confirm no mode is silently still active
  from before, and that voice/gesture/keyboard commands work normally
  again.

## 6. Input module disabled mid-use

While actively using a mode that depends on a given input (e.g. Cursor
mode, which needs the camera), use the bottom status panel's toggle
switch to disable that module (camera off) mid-use.

- Confirm the running mode does not crash; the camera preview should
  show its placeholder again and gesture-based cursor movement should
  simply stop, not throw a visible error.
- Re-enable the module and confirm it resumes working without needing to
  restart the application or re-enter the mode.

## 7. Rapid UI clicking

Click each of the four mode-wheel buttons in the main window in quick
succession, faster than their real-world gesture/voice equivalents could
ever be produced.

- Confirm the final active mode matches the last button clicked.
- Confirm the "Current mode: …" label and the glow ring never disagree
  with each other, even momentarily during the clicking.

## 8. Hand leaving frame during a Call-mode toggle hold

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

## 9. Packaged `.app` regression check: no duplicate process spawning

This is a targeted regression check for a specific historical bug (see
chapter 4.4 of the thesis): after packaging, `ProcessPoolExecutor` workers
used for Whisper fallback / semantic-LLM matching could end up re-launching
the whole application instead of starting as plain worker processes,
because `sys.executable` pointed at the packaged app itself.

- Launch the packaged `.app` (not `python src/main.py`).
- Deliberately trigger the Whisper fallback several times in a row (speak
  phrases designed to miss Vosk's grammar — see `voice_test_phrases.md`'s
  tier-3 phrases) and, separately, trigger the semantic/LLM command
  matching fallback several times.
- After each burst, check Activity Monitor (or `ps aux | grep
  GestureVoiceControl`) — confirm exactly one instance of the application
  is running, not one new one per fallback triggered.

## 10. Extended idle soak

Leave the application running idle (camera and microphone active, no
mode entered) for at least 30 minutes.

- Confirm it is still responsive to a voice command or gesture at the
  end of that period.
- Note: the system currently has no watchdog/auto-recovery process (see
  chapter 4.4, "known limitation") — this scenario is meant to observe
  whether that gap actually causes a practical problem over a realistic
  session length, not to test a recovery mechanism that doesn't exist.

## How to test

1. Run `python src/main.py` (scenario 9 specifically requires the packaged
   `.app` instead — see that section).
2. Work through each scenario above, watching both the on-screen behavior
   and the console/log output for exceptions or `[RESOLVED]`/`Mode ->`
   lines that don't match what you expect.
3. Record a pass/fail per scenario, with a short note of what actually
   happened for any failure (which log lines appeared, what state the UI
   was left in).
