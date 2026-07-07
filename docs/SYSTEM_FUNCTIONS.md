# System Functions Reference

Full reference for every voice command, gesture, keyboard combo, rule, mode,
environment and visual feature in the multimodal control system. For the
module-level architecture (EventBus pipeline, module responsibilities), see
[`src/CLAUDE.md`](../src/CLAUDE.md). This document describes *behavior*,
not code structure.

Target platform: **macOS only**.

---

## 1. Two independent state axes

The system tracks two separate, orthogonal pieces of state at once:

- **Mode** (`presentation` / `flip` / `cursor` / `quick_circle` / none) —
  an ephemeral context that decides what the *same physical gesture*
  currently means. Modes exist purely to stop gestures from colliding
  with each other (a swipe means something different in Flip mode than
  in the Quick Command Circle). They carry no OS side effects of their
  own.
- **Environment** (`work` / `study` / `movie` / `news` / none) — a
  longer-lived task backdrop. Entering one runs a real sequence of OS
  actions (opening apps, toggling Do Not Disturb, music); leaving it (by
  entering a different environment) undoes them.

You can be in a mode and an environment at the same time — e.g. `study`
environment (Safari + Preview open, focus music playing) while also
switching briefly into `cursor` mode to click something.

Saying **"exit mode"** only leaves the active **mode**. Environments are
only left by entering a different environment — there is no dedicated
"leave environment" phrase.

---

## 2. Modes

### 2.1 Presentation — `"presentation mode"` or `ctrl+alt`

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

### 2.2 Flip — `"flip mode"` or `alt+shift`

Smooth up/down/left/right gestures for flipping through content (reels,
photos, pages) or scrolling websites:

| Gesture | Action |
|---|---|
| `HAND_UP` | `SCROLL_UP` (smooth multi-tick scroll) |
| `HAND_DOWN` | `SCROLL_DOWN` (smooth multi-tick scroll) |
| `HAND_RIGHT` | `FLIP_NEXT` |
| `HAND_LEFT` | `FLIP_PREVIOUS` |

`FLIP_NEXT`/`FLIP_PREVIOUS` behave differently depending on what's in
front, since macOS has no generic way to ask an arbitrary app "is there
more content in this direction":

- If the frontmost app is one that actually responds to arrow-key
  navigation (**Preview, Photos, Safari, Google Chrome, QuickTime
  Player** — `OSController.FLIPPABLE_APPS`) → sends a Right/Left arrow
  key press (flips the photo/page).
- Otherwise → sends `Ctrl+Right`/`Ctrl+Left` (macOS's built-in shortcut
  for switching between Spaces/desktops).

Gestures reuse the same Closed_Fist → Open_Palm swipe-tracking session
as everywhere else in the system (see `src/processing/gesture/
gesture_recognizer.py`) — nothing new was added to gesture detection
itself for this mode, only new mode_rules interpreting the existing
`HAND_LEFT/RIGHT/UP/DOWN` signals.

### 2.3 Cursor — `"cursor mode"` or `ctrl+shift`

The **only** mode where pointing and pinching touch the real mouse.
Outside this mode, `Pointing_Up` only drives the purely-visual laser
pointer (§4) and `PINCH` does nothing.

| Gesture | Effect |
|---|---|
| `Pointing_Up`, held | The OS cursor follows your index fingertip in real time |
| Quick pinch (touch and release) | `CLICK` |
| Pinch, **held or moved**, then dragged | Scroll (see below) — no click fires |

**Click vs. scroll disambiguation**: a pinch is tracked from the moment
thumb and index touch. If released quickly with minimal movement, it's a
click. If held past ~150ms or moved past a small distance while still
pinched, it becomes a drag — continuous vertical movement while pinched
scrolls the frontmost window, and releasing afterward does **not** also
fire a click. This state machine lives in `GestureRecognizer._check_pinch`
— cursor-mode-agnostic; `ActionExecutor` decides whether to actually move
the OS cursor / scroll based on which mode is currently active.

### 2.4 Quick Command Circle — gesture only: Closed_Fist → Open_Palm

A visual circle appears on screen with 4 "heavy" functions — actions that
reach deep into the system and are worth a dedicated, deliberate gesture
rather than being one accidental swipe away:

| Selection gesture | Function |
|---|---|
| `HAND_UP` | `OPEN_ADMIN_TERMINAL` |
| `HAND_DOWN` | `LOCK_SCREEN` |
| `HAND_LEFT` | `FORCE_QUIT_APP` |
| `HAND_RIGHT` | `TOGGLE_DO_NOT_DISTURB` |

Picking any one of the four **automatically closes the circle** — it's a
one-shot menu, not a mode you have to explicitly leave.

**Entry is gesture-only, and only fires from idle** (no other mode
active). The same Closed_Fist → Open_Palm transition already means
"start a new swipe/scroll session" while Flip mode is active — so a
gesture-sourced mode trigger is deliberately only honored when
`current_mode is None`, otherwise using Flip mode would constantly
reopen the circle. Voice/keyboard-sourced triggers (Presentation/Flip/
Cursor) don't have this restriction — you can jump straight from one of
those to another.

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
| `ctrl+alt` | Enter Presentation mode |
| `alt+shift` | Enter Flip mode |
| `ctrl+shift` | Enter Cursor mode |
| Right arrow (bare) | Next slide, Presentation mode only |
| Left arrow (bare) | Previous slide, Presentation mode only |

`src/processing/keyboard/keyboard_processor.py` builds any modifier
combination (and bare single-key presses) dynamically — only combos
listed in `mapping.json`'s `keyboard` section pass through to the rest of
the pipeline.

---

## 9. Setup preconditions

- **Accessibility permission** must be granted to whatever process runs
  `python src/main.py` — System Settings → Privacy & Security →
  Accessibility. Required for `FORCE_QUIT_APP`'s and `FLIP_NEXT`/
  `FLIP_PREVIOUS`'s frontmost-app-name lookup (`osascript` driving System
  Events). Without it, these calls fail gracefully and print an error.
- **Do Not Disturb automation** requires three Shortcuts authored once in
  the macOS Shortcuts app, named exactly: **"Enable Do Not Disturb"**,
  **"Disable Do Not Disturb"**, **"Toggle Do Not Disturb"**. Modern macOS
  has no supported scriptable API for Focus/DND outside the Shortcuts
  app — the older `defaults write ... killall NotificationCenter` trick
  is deprecated and version-fragile, so this codebase intentionally does
  not use it.
- **Spotify** must be installed for Study mode's focus music
  (`PLAY_FOCUS_MUSIC`/`PAUSE_FOCUS_MUSIC` silently no-op otherwise).
- **VS Code's `code` CLI** must be on `PATH` for `OPEN_VSCODE`.
- Third-party apps (Chrome, Slack, Discord, Zoom, WhatsApp, Telegram,
  Notion, Figma) must be installed for their `open_*` voice commands to
  do anything.
- **"Require password after sleep"** must be enabled in System Settings
  → Lock Screen for the Quick Command Circle's `LOCK_SCREEN`
  (`pmset displaysleepnow`) to function as an actual lock.

---

## 10. What changed from the previous design (removed features)

The previous iteration of this system had a different set of modes
(Presentation/Study/Coding/Window Management, all with app-opening side
effects), a `ctrl+alt+shift`-gated set of "hidden" rules, a click gesture
and voice-driven cursor nudging that worked globally, and several
voice-only utility commands. All of the following were removed as part of
this redesign, since they either collided with the new gesture-mode
design or fell outside what this design explicitly covers:

- **Window management** (`MAXIMIZE_WINDOW`, `MINIMIZE_WINDOW`,
  `MOVE_WINDOW_LEFT/RIGHT`, the `alt+shift` + swipe global rules, the old
  Window Management mode) — no longer present anywhere.
- **Old hidden combos** (`ctrl+alt+shift` + gesture/voice for cursor
  sensitivity, admin terminal, force quit, toggle DND, lock screen) —
  admin terminal / force quit / lock screen / toggle DND are now Quick
  Command Circle selections instead (§2.4); cursor sensitivity
  adjustment was dropped entirely (cursor movement in the new design
  follows your fingertip 1:1 in Cursor mode, so a separate step-size
  concept no longer applies).
- **Global voice utility commands**: `TAKE_SCREENSHOT`, `CLICK`,
  `SCROLL_UP`/`SCROLL_DOWN` (voice), `MOVE_LEFT/RIGHT/UP/DOWN` (voice
  cursor nudging), `COPY`, `PASTE`, `SWITCH_APP` — none of these were
  described in the current design, so they were pruned along with their
  `OSController` methods (`take_screenshot`, `alt_tab`, `ctrl_c`,
  `ctrl_v`, `clipboard_copy`, `clipboard_paste`, the relative
  `move_cursor_left/right/up/down`).
- **`OK` gesture and the `ctrl+alt` + `OK` → ChatGPT combo rule** — voice
  already opens ChatGPT directly; keeping a whole gesture just for one
  redundant alternate path didn't fit the "lean vocabulary" goal.
- **The old Study/Coding/Presentation/Window-Management "modes"** — fully
  replaced by the Work/Study/Movie/News environments (§3) and the
  Presentation/Flip/Cursor/Quick-Circle modes (§2), which are not a
  1:1 rename (Coding mode's app-opening behavior doesn't have a direct
  successor; Work environment is a broader "office" set of apps rather
  than specifically development tools).

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
- **Modes**: confirm Presentation/Flip/Cursor are mutually exclusive and
  switching between them doesn't require going through "exit mode"
  first; confirm the Quick Command Circle only opens from idle (not
  while Flip mode's swipe session is active) and closes itself after a
  selection.
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
