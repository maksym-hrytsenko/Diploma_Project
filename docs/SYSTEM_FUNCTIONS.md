# System Functions Reference

Full reference for every voice command, gesture, keyboard combo, rule, mode,
environment and visual feature in the multimodal control system. For a
short, plain-text quick-lookup list instead ("what opens/launches what"),
see [`docs/FUNCTIONS_LIST.txt`](FUNCTIONS_LIST.txt). For the module-level
architecture (EventBus pipeline, module responsibilities), see
[`src/CLAUDE.md`](../src/CLAUDE.md). This document describes *behavior*,
not code structure.

Target platform: **macOS only**.

---

## 1. Two independent state axes

The system tracks two separate, orthogonal pieces of state at once:

- **Mode** (`presentation` / `flip` / `cursor` / `window_management` /
  `quick_circle` / none) — an ephemeral context that decides what the
  *same physical gesture* currently means. Modes exist purely to stop
  gestures from colliding with each other (a swipe means something
  different in Flip mode than in Window Management mode). They carry no
  OS side effects of their own.
- **Environment** (`work` / `study` / `movie` / `news` / none) — a
  longer-lived task backdrop. Entering one runs a real sequence of OS
  actions (opening apps, toggling Do Not Disturb, music); leaving it (by
  entering a different environment) undoes them.

You can be in a mode and an environment at the same time — e.g. `study`
environment (Safari + Preview open, focus music playing) while also
switching briefly into `cursor` mode to click something.

Saying **"exit mode"**, or pressing **Esc**, only leaves the active
**mode** — both work identically, from any mode, at any time. Environments are
only left by entering a different environment — there is no dedicated
"leave environment" phrase.

---

## 2. Modes

### 2.1 Presentation — `"presentation mode"` or `ctrl+shift+p`

Controls slides two ways at once — by key or by voice, no gesture
involved (gestures are reserved for Flip mode, so the two can't collide):

| Trigger | Action |
|---|---|
| Right arrow key (bare, no modifier) | `NEXT_SLIDE` |
| Left arrow key (bare, no modifier) | `PREVIOUS_SLIDE` |
| voice "next slide" | `NEXT_SLIDE` |
| voice "previous slide" | `PREVIOUS_SLIDE` |

`NEXT_SLIDE`/`PREVIOUS_SLIDE` send a plain Right/Left arrow key press —
the same thing a real presentation clicker does, so it works with
PowerPoint, Keynote, Google Slides, and PDF viewers without any
per-app integration.

**Note on bare arrow keys**: while in Presentation mode, plain Right/Left
arrow presses are captured system-wide (the same way a physical
clicker's key presses would be) but only produce an action while this
mode is active — outside it they're silently ignored.

### 2.2 Flip — `"flip mode"` or `ctrl+shift+f`

Smooth up/down/left/right gestures for flipping through content (reels,
photos, pages) or scrolling websites:

| Gesture | Action |
|---|---|
| `HAND_UP` | `SCROLL_DOWN` (smooth multi-tick scroll — see inversion note below) |
| `HAND_DOWN` | `SCROLL_UP` (smooth multi-tick scroll) |
| `HAND_RIGHT` | `FLIP_NEXT` |
| `HAND_LEFT` | `FLIP_PREVIOUS` |

**Natural/drag scrolling, not wheel scrolling.** Moving the hand up feels
like grabbing the content and dragging it up with your hand — which
pulls *later* content into view, the same net effect as a traditional
"scroll down". This is why `HAND_UP` maps to the `SCROLL_DOWN` action
(and vice versa) rather than the same-named one — it matches how
touchscreens and macOS's default "natural scrolling" trackpad behavior
work, rather than an old-style scroll wheel where wheel-up and
content-up are the same direction. Cursor mode's pinch-drag scroll
(§2.3) uses the identical convention.

**`PINCH` is only ever recognized in Cursor mode** (§2.3) — nowhere
else, including Flip mode. Swiping (or any other gesture) naturally
passes the hand through poses where thumb and index momentarily satisfy
the pinch-touch distance — with detection running unconditionally this
produced noise with no effect anywhere it wasn't Cursor mode.
`GestureRecognizer` mirrors `SignalMapper`'s `mode_changed` event (a
narrow, deliberate exception to staying mode-agnostic otherwise) and
only runs the pinch/hold-and-drag check when `active_mode == "cursor"`
— not just "no rule fires from it downstream", the geometry is never
computed at all outside Cursor mode.

`FLIP_NEXT`/`FLIP_PREVIOUS` behave differently depending on what's in
front, since macOS has no generic way to ask an arbitrary app "is there
more content in this direction":

- If the frontmost app is one that actually responds to arrow-key
  navigation (**Preview, Photos, Safari, Google Chrome, QuickTime
  Player** — `OSController.FLIPPABLE_APPS`) → sends a Right/Left arrow
  key press (flips the photo/page).
- Otherwise → sends `Ctrl+Right`/`Ctrl+Left` (macOS's built-in shortcut
  for switching between Spaces/desktops).

**Smooth, short-distance scroll.** `SCROLL_UP`/`SCROLL_DOWN` no longer
jump the full distance in one motion — each swipe scrolls a total of
`OSController.FLIP_SCROLL_PIXELS` (90px) split across
`FLIP_SCROLL_TICKS` (18) small ticks with a `FLIP_SCROLL_TICK_DELAY`
(14ms) pause between each, using a real pixel-precise scroll event
(`Quartz.CGEventCreateScrollWheelEvent` with `kCGScrollEventUnitPixel`,
not `pyautogui`'s coarser line/click units) so the glide is both visibly
animated (~250ms total) and covers noticeably less on-screen distance
per swipe than before. Tune `FLIP_SCROLL_PIXELS` up/down if it still
feels too far or too short.

Gestures reuse the same Closed_Fist → Open_Palm swipe-tracking session
as everywhere else in the system (see `src/processing/gesture/
gesture_recognizer.py`) — nothing new was added to gesture detection
itself for this mode, only new mode_rules interpreting the existing
`HAND_LEFT/RIGHT/UP/DOWN` signals.

### 2.3 Cursor — `"cursor mode"` or `ctrl+shift+c`

The **only** mode where pointing and pinching touch the real mouse.
Outside this mode, `Pointing_Up` only drives the purely-visual laser
pointer (§4) and `PINCH` does nothing.

| Gesture | Effect |
|---|---|
| `Pointing_Up`, held | The OS cursor jumps to wherever the fingertip is, every frame |
| Quick pinch (touch and release) | `CLICK` |
| Pinch, **held or moved**, then dragged | Scroll (see below) — no click fires |

**Cursor motion is absolute, mapped directly from the camera frame** —
the same mechanism the laser pointer (§4) uses. Every frame,
`GestureRecognizer._update_pointer` publishes the fingertip's raw
normalized position (`x`, `y`); `ActionExecutor` converts it to real
screen pixels (mirrored on X the same way the laser dot is, so the
cursor sits on the same side as the user's hand from their own point of
view) and moves the OS cursor straight there
(`OSController.move_cursor_to`, an absolute `pyautogui.moveTo`). The
full range of the camera's view maps onto the full screen, so the
fingertip's position in the frame *is* the cursor's position on screen
— take a camera frame, find the finger, put the cursor at that same
spot, every frame.

**Scroll distance matches hand distance, same natural/drag direction as
Flip mode.** Pinch-and-drag scroll converts its normalized `delta_y` to
real screen pixels the same way, then posts that many pixels via the
same pixel-precise Quartz scroll event Flip mode uses
(`OSController.scroll_by`) — the content moves close to the same
on-screen distance the hand just moved, not an arbitrarily scaled
amount, and dragging up/down follows the identical natural/drag
convention as §2.2 (drag up → pulls later content into view; drag down
→ reveals earlier content) — `ActionExecutor._handle_pinch_drag`.

**Click vs. scroll disambiguation**: a pinch is tracked from the moment
thumb and index touch. If released quickly with minimal movement, it's a
click. If held past ~150ms or moved past a small distance while still
pinched, it becomes a drag — continuous vertical movement while pinched
scrolls the frontmost window, and releasing afterward does **not** also
fire a click. This state machine lives in `GestureRecognizer._check_pinch`
— cursor-mode-agnostic; `ActionExecutor` decides whether to actually move
the OS cursor / scroll based on which mode is currently active.

### 2.4 Window Management — `"window management mode"` or `ctrl+shift+w`

Gesture-only window control — no keyboard modifier needed for the
gestures themselves once you're in this mode (unlike, say, quickly
nudging a window from outside any mode, which this design doesn't
otherwise support):

| Gesture | Action |
|---|---|
| `HAND_UP` | `MAXIMIZE_WINDOW` |
| `HAND_DOWN` | `MINIMIZE_WINDOW` (hides the app — see §10 known limitations) |
| `HAND_LEFT` | `MOVE_WINDOW_LEFT` (snaps to the left half of the screen) |
| `HAND_RIGHT` | `MOVE_WINDOW_RIGHT` (snaps to the right half) |

Window bounds are set via AppleScript driving System Events
(`OSController._set_frontmost_window_bounds`) — macOS has no built-in
"snap window" shortcut without third-party apps, so this positions the
frontmost window's bounds directly. Requires Accessibility permission
(§9); fails gracefully and prints an error without it.

### 2.5 Quick Command Circle — gesture only: Closed_Fist → Open_Palm

A visual circle appears on screen with the system's other 4 modes laid
out around it. Swiping toward one of the four sides selects that mode
and the circle closes automatically — this is a quick, gesture-only way
to jump into any mode without remembering its own voice phrase or
keyboard combo:

| Selection gesture | Enters |
|---|---|
| `HAND_UP` | Presentation mode (§2.1) |
| `HAND_DOWN` | Window Management mode (§2.4) |
| `HAND_LEFT` | Flip mode (§2.2) |
| `HAND_RIGHT` | Cursor mode (§2.3) |

Picking a direction is a genuine mode **transition** (`SignalMapper`'s
`enters_mode` mechanism on a `mode_rule` — exits `quick_circle`, enters
the target mode directly), not a command followed by closing the menu —
Quick Circle itself has no "action" of its own, it only ever redirects
into one of the other four modes.

**Entry is gesture-only, and only fires from idle** (no other mode
active). The same Closed_Fist → Open_Palm transition already means
"start a new swipe/scroll session" while Flip mode is active — so a
gesture-sourced mode trigger is deliberately only honored when
`current_mode is None`, otherwise using Flip mode would constantly
reopen the circle. Voice/keyboard-sourced triggers (Presentation/Flip/
Cursor/Window Management) don't have this restriction — you can jump
straight from one of those to another without going through the circle
or idle first.

The circle itself is `src/ui/quick_command_overlay.py` — a click-through
PyQt6 overlay that shows/hides purely by listening to the same
`mode_changed` event `ActionExecutor` uses, no coupling between the two.

---

## 3. Environments

Entered by voice, each runs a real sequence of actions; switching directly
to a different environment runs the old one's `exit_actions` before the
new one's `enter_actions`.

### 3.1 Work — `"work mode"`

| On enter | On exit |
|---|---|
| `ENABLE_DO_NOT_DISTURB` | `DISABLE_DO_NOT_DISTURB` |
| `OPEN_SLACK` | — |
| `OPEN_MAIL` | — |
| `OPEN_CALENDAR` | — |

### 3.2 Study — `"study mode"`

| On enter | On exit |
|---|---|
| `ENABLE_DO_NOT_DISTURB` | `DISABLE_DO_NOT_DISTURB` |
| `OPEN_SAFARI` | — |
| `OPEN_PREVIEW` | — |
| `PLAY_FOCUS_MUSIC` (resumes whatever Spotify was last on — no fake playlist invented) | `PAUSE_FOCUS_MUSIC` |

### 3.3 Movie — `"movie mode"`

| On enter | On exit |
|---|---|
| `ENABLE_DO_NOT_DISTURB` | `DISABLE_DO_NOT_DISTURB` |
| `PREVENT_DISPLAY_SLEEP` (`caffeinate -d`, so the screen doesn't dim mid-movie) | `ALLOW_DISPLAY_SLEEP` |
| `OPEN_TV` (macOS's built-in TV.app) | — |

### 3.4 News — `"news mode"`

| On enter | On exit |
|---|---|
| `OPEN_NEWS` (macOS's built-in News.app) | — (nothing was disruptively changed) |

`OPEN_TV`/`OPEN_NEWS` deliberately use Apple's own pre-installed TV/News
apps rather than a specific third-party streaming/news site — real,
always present on stock macOS, no invented URLs.

---

## 4. Laser pointer (Pointing_Up, outside Cursor mode)

Holding `Pointing_Up` publishes a live stream of index fingertip
coordinates (`pointer_position`, every camera frame). `src/ui/
pointer_overlay.py` is a frameless, translucent, always-on-top,
**click-through** PyQt6 window painting a small red dot at the mapped
screen position.

- **Purely visual outside Cursor mode.** The overlay is
  `WindowTransparentForInput` — it never intercepts clicks or focus. A
  way to point at the screen (e.g. during a presentation), nothing more.
- **Becomes real cursor control inside Cursor mode** (§2.3) — the exact
  same `pointer_position` stream is routed to `OSController.
  move_cursor_to` instead of the overlay, decided by `ActionExecutor`
  caching the latest `mode_changed` event.
- **Auto-hides** ~200ms after updates stop arriving (no explicit
  "pointer gesture ended" event exists, so a watchdog timer substitutes).
- **Mirroring**: camera frames are never flipped anywhere in the
  pipeline, so both the overlay dot and real-cursor-mode mirror the X
  coordinate so movement matches the user's own point of view. Verify
  empirically — flip `PointerOverlay.MIRROR_X` / the mirroring line in
  `ActionExecutor._move_real_cursor` if it moves backwards for your
  camera setup.

---

## 5. Global commands (always active, regardless of mode or environment)

| Command | Phrase | Effect |
|---|---|---|
| `START` | "start" | `MEDIA_PLAY_PAUSE` |
| `STOP` | "stop" | `MEDIA_PLAY_PAUSE` |
| `EXIT_MODE` | "exit mode" | Leaves the active mode only (§1) |
| `YES` / `NO` | "yes" / "no" | Reserved, unbound — for a future confirmation prompt |

**`MEDIA_PLAY_PAUSE`** posts the real macOS system Play/Pause media key
(via `pyobjc`'s `NSEvent`/`Quartz`, the same event a physical keyboard's
media key sends) — this is what lets it control **whichever** player
currently owns "now playing" (Spotify, Music, a browser tab, QuickTime,
...) rather than being tied to one specific app.

**Known limitation**: macOS only exposes a single toggle-style
Play/Pause media key, not separate absolute Play-only/Pause-only system
keys. So "start" and "stop" both send the *identical* event — saying
"stop" while already paused resumes playback. This is an honest
consequence of using the one truly universal mechanism rather than
app-specific AppleScript (which would only work for one player, breaking
the "any open player" requirement).

---

## 6. Opening applications (unchanged — all voice-only, no gesture/keyboard)

24 apps, each a single-condition voice rule — say the phrase, the app
opens, nothing else required:

`open browser`, `open chatgpt`, `open github`, `open vscode`, `open
terminal`, `open safari`, `open chrome`, `open spotify`, `open slack`,
`open discord`, `open zoom`, `open mail`, `open calendar`, `open notes`,
`open messages`, `open whatsapp`, `open telegram`, `open finder`, `open
notion`, `open figma`, `open photos`, `open music`, `open preview`,
`open settings`.

**Vosk vocabulary — confirmed, not just theoretical.** Loading the
grammar logs exactly which words it silently drops as unknown. Verified
in this environment: `chatgpt`, `vscode`, `whatsapp`, and `figma` are
**not** in `vosk-model-small-en-us-0.15`'s fixed lexicon — the
recognizer will never match "open chatgpt" / "open vscode" / "open
whatsapp" / "open figma" no matter how clearly they're spoken, since one
of the words in each phrase can't be decoded at all. `discord`,
`telegram`, `zoom`, `notion`, `notes`, `messages`, `spotify`, `slack`,
`safari`, `chrome`, `calendar`, `settings`, `finder`, `photos`, `music`,
`preview`, `browser`, `terminal`, `github` were **not** flagged, so
those phrases should recognize normally (subject to normal accuracy
limits — actual recognition quality wasn't tested, only vocabulary
presence). Swapping the four failing phrases for the app's own
executable/process name if it differs, or switching to a larger Vosk
model, are the two ways to fix this if it matters in practice.

---

## 7. Gestures

| Gesture | Source | Used by |
|---|---|---|
| `HAND_LEFT` / `HAND_RIGHT` / `HAND_UP` / `HAND_DOWN` | Computed from index-fingertip velocity during a swipe-tracking session | Flip mode, Quick Command Circle selection |
| `HAND_SESSION_START` | Fired once on the Closed_Fist → Open_Palm transition that starts a swipe session | Quick Command Circle's entry trigger (idle-only, §2.4) |
| `PINCH` | Computed from thumb-tip/index-tip landmark distance | Cursor mode's click (quick tap) — hold+drag instead scrolls, §2.3 |

`Open_Palm`/`Closed_Fist`/`Pointing_Up` are still recognized internally by
`GestureRecognizer` (they drive the swipe session and the pointer stream)
but are no longer exposed as directly rule-matchable signals — nothing in
this design needs to react to them as discrete events. `OK`, `Victory`,
`Thumb_Up`, `Thumb_Down`, `ILoveYou` are no longer used anywhere and were
removed from `mapping.json`'s vocabulary.

---

## 8. Keyboard combos

| Combo | Used by |
|---|---|
| `ctrl+shift+p` | Enter Presentation mode |
| `ctrl+shift+f` | Enter Flip mode |
| `ctrl+shift+c` | Enter Cursor mode |
| `ctrl+shift+w` | Enter Window Management mode |
| Right arrow (bare) | Next slide, Presentation mode only |
| Left arrow (bare) | Previous slide, Presentation mode only |
| Esc (bare) | Exit whichever mode is active, from any mode, at any time |

All four mode-entry combos share the `ctrl+shift` base, distinguished by
a third key that's the first letter of the mode name (**p**resentation,
**f**lip, **c**ursor, **w**indow management) — a single, consistent,
memorable pattern rather than four unrelated combos. `mapping.json`'s
`keyboard` and `valid_signals.keyboard` must always list the exact same
combo strings — a mismatch between the two silently drops every press of
the affected combo with no error (this happened once during development
and is why every keyboard combo is worth double-checking after an edit).

`src/processing/keyboard/keyboard_processor.py` builds any modifier
combination (and bare single-key presses) dynamically — only combos
listed in `mapping.json`'s `keyboard` section pass through to the rest of
the pipeline.

### 8.1 Press and release are tracked as two separate moments

A combo is announced the instant it becomes fully held ("down"), and
announced again the instant it breaks ("up") — not, as before, only
once at the end of a full press-then-release cycle. Concretely:

- Pressing `ctrl` then `alt` publishes `keyboard_signal` for `"ctrl"`
  (down), then immediately `"ctrl"` (up) + `"ctrl+alt"` (down) — the
  currently-held combo is always kept in sync with what's actually
  physically pressed.
- A held combo is stored as a **persistent** signal in
  `TemporalSync` (`src/fusion/temporal_sync.py`) — unlike voice/gesture
  signals, it does **not** expire after `settings.signal_timeout` (2s).
  Holding a key for 10 seconds keeps it valid for all 10 seconds, not
  just the first 2.
- Releasing any key in the combo clears it from the buffer immediately
  (`MultimodalFusion._handle_signal` reacts to the "up" event), rather
  than waiting for the timeout.

**What this enables**: a rule requiring `{"keyboard": "X", "gesture":
"Y"}` now works correctly even if the gesture happens well into the
hold (not just in the instant right around release), and — since the
combo doesn't get consumed after a match the way voice/gesture signals
do (`TemporalSync.clear_non_persistent` only clears the momentary
sources) — **multiple different gesture/voice actions can fire in
sequence while the same combo stays held**, not just one.

**Repeat-fire guard**: a rule only gets evaluated on the specific pass
whose triggering signal is one of that rule's own condition sources
(`SignalMapper._check_rules`/`_check_mode_rules`, filtered by
`triggering_source`). Without this, a rule keyed on a held combo alone
would refire on every unrelated voice/gesture event that happens to
arrive while the key stays down — the filter means it only fires on the
actual edge of its own condition becoming satisfied.

There is currently no rule in `fusion.json` that combines a held
keyboard combo with a gesture or voice condition — `ctrl+alt+shift` is
used only as Window Management mode's single-source entry trigger (see
§2.4), not as a hidden-combo gate. This section documents the held/
released mechanism, ready for whenever a genuine multi-source combo
rule is added.

---

## 9. Setup preconditions

- **Accessibility permission — the single most common cause of "nothing
  happens" with no error.** Must be granted to whatever process actually
  runs `python src/main.py` (Terminal.app, iTerm, your IDE's integrated
  terminal — whichever one you launch it from) — System Settings →
  Privacy & Security → Accessibility. Every synthetic input event this
  app posts (cursor movement, clicks, scrolling, key presses) is
  silently dropped by macOS without raising any exception until this is
  granted — this is different from `FLIP_NEXT`/`FLIP_PREVIOUS`'s and
  Window Management's frontmost-app-name/window-bounds lookups
  (`osascript`), which *do* print a visible `[APPLESCRIPT ERROR]` when
  it's missing. `OSController` checks
  `ApplicationServices.AXIsProcessTrusted()` once at startup and prints
  a loud `[ACCESSIBILITY WARNING]` banner if it isn't granted —
  if Cursor mode's cursor-follow isn't moving anything, check the
  console for this banner first.
- **Do Not Disturb automation** requires two Shortcuts authored once in
  the macOS Shortcuts app, named exactly: **"Enable Do Not Disturb"** and
  **"Disable Do Not Disturb"**. Modern macOS has no supported scriptable
  API for Focus/DND outside the Shortcuts app — the older
  `defaults write ... killall NotificationCenter` trick is deprecated
  and version-fragile, so this codebase intentionally does not use it.
- **Spotify** must be installed for Study mode's focus music
  (`PLAY_FOCUS_MUSIC`/`PAUSE_FOCUS_MUSIC` silently no-op otherwise).
- **VS Code's `code` CLI** must be on `PATH` for `OPEN_VSCODE`.
- Third-party apps (Chrome, Slack, Discord, Zoom, WhatsApp, Telegram,
  Notion, Figma) must be installed for their `open_*` voice commands to
  do anything.

---

## 10. What changed from the previous design (removed features)

This system has gone through several rounds of revision. Rather than a
single "before/after", here's the current, accurate state of what
exists and what was tried and dropped along the way:

- **Window Management is back**, as the 4th mode (§2.4) — it was removed
  in an earlier round for not being described in that round's spec, then
  reintroduced as the Quick Command Circle's 4th destination once the
  circle was redefined as a mode selector (§2.5). Same behavior as its
  original design: gesture-only maximize/minimize/snap-left/snap-right.
- **The Quick Command Circle no longer holds "hidden" system functions.**
  Its original role (admin terminal, lock screen, force-quit, toggle DND
  — one per direction) was replaced entirely: it's now a mode selector
  (§2.5). Because of this, `open_admin_terminal`, `lock_screen`,
  `force_quit_frontmost_app`, and `toggle_do_not_disturb` (and their
  `OPEN_ADMIN_TERMINAL`/`LOCK_SCREEN`/`FORCE_QUIT_APP`/
  `TOGGLE_DO_NOT_DISTURB` commands) have no trigger anywhere in the
  system anymore and were removed from `OSController`/`ActionExecutor`.
  `enable_do_not_disturb`/`disable_do_not_disturb` are unaffected (still
  used by the Work/Study/Movie environments, §3).
- **Cursor sensitivity adjustment** (an earlier `ctrl+alt+shift` hidden
  combo) was dropped entirely — Cursor mode's cursor position is now a
  direct 1:1 mapping from the camera frame (§2.3), so a separate
  step-size concept doesn't apply.
- **Global voice utility commands**: `TAKE_SCREENSHOT`, `CLICK`,
  `SCROLL_UP`/`SCROLL_DOWN` (voice), `MOVE_LEFT/RIGHT/UP/DOWN` (voice
  cursor nudging), `COPY`, `PASTE`, `SWITCH_APP` — none of these were
  described when the modes/environments split was introduced, so they
  were pruned along with their `OSController` methods.
- **`OK` gesture and the `ctrl+alt` + `OK` → ChatGPT combo rule** — voice
  already opens ChatGPT directly; keeping a whole gesture just for one
  redundant alternate path didn't fit the "lean vocabulary" goal.
- **The original Study/Coding/Presentation/Window-Management "modes"**
  (each with app-opening side effects) were replaced by the
  Work/Study/Movie/News environments (§3, side effects) and the
  Presentation/Flip/Cursor/Window-Management/Quick-Circle modes (§2,
  pure gesture-scoping, no side effects) — not a 1:1 rename; Work
  environment is a broader "office" app set rather than specifically
  development tools.

If any of these turn out to be missed rather than intentionally dropped,
they're easy to reintroduce — the mechanisms (`rules`, `mode_rules`,
environment `enter_actions`/`exit_actions`) all still exist.

---

## 11. Testing / verification guide

Cannot be fully automated headlessly — needs a real camera, microphone,
macOS desktop, and Accessibility permission. Run `python src/main.py`
(add `--debug-gesture` for a live gesture-calibration overlay) and
manually verify:

- **Voice**: speak each app-opening phrase and each mode/environment
  trigger, confirm `[EXECUTOR] <ACTION>` prints and the effect happens.
- **Keyboard**: hold each mode-entry combo; press bare Right/Left arrows
  only while in Presentation mode.
- **Gestures**: use `--debug-gesture` to calibrate `pinch_distance_
  threshold` against your hand/camera distance; verify a quick pinch
  clicks and a held-and-dragged pinch scrolls without also clicking.
- **Modes**: confirm Presentation/Flip/Cursor/Window Management are
  mutually exclusive and switching between them doesn't require going
  through "exit mode" first; confirm the Quick Command Circle only opens
  from idle (not while Flip mode's swipe session is active) and that
  swiping in each of the 4 directions enters the right mode and closes
  the circle.
- **Environments**: confirm entering one runs its full `enter_actions` in
  order, and switching directly to a different environment runs the old
  one's `exit_actions` first.
- **"exit mode" scope**: enter an environment, then a mode, say "exit
  mode", confirm only the mode cleared and the environment's apps/DND
  state are untouched.

Visual-inspection-only: laser pointer / Cursor-mode cursor position
accuracy and mirroring direction, the Quick Command Circle's on-screen
appearance, Flip mode's frontmost-app heuristic (test with a flippable
app like Preview vs. a non-flippable one to confirm the Space-switch
fallback).
