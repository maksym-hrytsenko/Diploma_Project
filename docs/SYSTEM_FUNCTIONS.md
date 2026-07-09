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

- **Mode** (`presentation` / `flip` / `cursor` / `call` /
  `quick_circle` / none) — an ephemeral context that decides what the
  *same physical gesture* currently means. Modes exist purely to stop
  gestures from colliding with each other (a swipe means something
  different in Flip mode than a thumbs-up means in Call mode). They
  carry no OS side effects of their own.
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

One hand is all Cursor mode needs and behaves exactly as before. A
**second hand**, if visible, unlocks two more functions — see §2.3.1.

| Gesture | Effect |
|---|---|
| `Pointing_Up`, held | The OS cursor jumps to wherever the fingertip is, every frame |
| Quick pinch (touch and release) | `CLICK` |
| Quick pinch **twice** in a row | `RIGHT_CLICK` (instead of two clicks) |
| Pinch, **held or moved**, then dragged | Scroll (see below) — no click fires |
| Off-hand Closed_Fist, held | Precision mode — see §2.3.1 |
| Off-hand present, not fisted, primary hand pointing | Two-hand zoom — see §2.3.1 |

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

**Click vs. right-click disambiguation**: a quick tap (the "click" case
above) is not published immediately — it is held as a `pending_single_pinch`
for up to `double_pinch_window` (0.3s). If a second quick tap arrives in
that window, the pair is published as one `DOUBLE_PINCH` gesture signal
(→ `RIGHT_CLICK`) instead of two `PINCH` signals. If the window expires
with no second tap, the deferred tap is committed as a plain `PINCH`
(→ `CLICK`). This means every single click in Cursor mode carries a
~0.3s latency by design — the trade-off for distinguishing it from a
right-click using the same physical gesture. `GestureRecognizer._release_pinch`
defers, `GestureRecognizer._check_pinch` commits the deferred click on a
later frame once the window has passed.

#### 2.3.1 Two-hand functions (off-hand)

`GestureModel` tracks up to two hands (`num_hands=2`). Every check
described above still operates on exactly one "primary" hand — with
two hands visible in Cursor mode, primary is whichever one is currently
doing `Pointing_Up` (`GestureRecognizer._resolve_primary_index`); the
other is the "off-hand". Outside Cursor mode, or with only one hand
visible, primary is always hand 0 — identical to pre-two-hand behavior,
so nothing here can regress any other mode.

**Precision mode (off-hand `Closed_Fist`)**: like lowering a mouse's
DPI. Engaging it anchors the primary fingertip's current position;
while the off-hand fist is held, the published cursor position only
moves `PRECISION_SCALE` (0.3) of however far the primary hand actually
moves from that anchor point — fine, deliberate positioning instead of
the normal full-speed 1:1 follow. This is necessarily a *relative*
mechanism layered on top of the otherwise strictly *absolute* mapping
described above — releasing the off-hand fist snaps straight back to
absolute 1:1 tracking, which means the cursor visibly jumps to match
wherever the primary fingertip currently, actually is. That jump is an
intentional, honest consequence of mixing a temporary relative "clutch"
into an absolute mapping, not a bug — same as lifting and repositioning
a physical mouse. See `GestureRecognizer._update_pointer`.

**Two-hand zoom (off-hand present, not fisted)**: replaces the earlier
Alt+single-hand-pinch zoom entirely — no keyboard involved at all now.
Requires the primary hand to be doing `Pointing_Up` (the same gesture
already required for the cursor to track anything) and the off-hand to
be visible but not a fist. The distance between the two hands' index
fingertips is compared frame-to-frame and published as a `pinch_zoom`
delta (`GestureRecognizer._check_two_hand_zoom`) — spreading the two
hands apart zooms in, bringing them together zooms out, the same
real-world gesture as a two-handed photo pinch-zoom. `ActionExecutor`'s
consumption of `pinch_zoom` (accumulate deltas, fire
`OSController.zoom_in()`/`zoom_out()` per `zoom_step_threshold`, 0.05)
is completely unchanged from the old Alt+pinch mechanism — only the
*source* of the delta changed, from single-hand pinch distance under
Alt to two-hand fingertip distance. `zoom_in`/`zoom_out` still send
Cmd+"="/Cmd+"-", the standard zoom shortcut in Safari, Preview, Photos
and most other macOS apps.

Precision mode and two-hand zoom are mutually exclusive by construction
— an off-hand fist has no meaningful "index fingertip" position to zoom
from, so `_check_off_hand` only ever runs one or the other per frame.

### 2.4 Call — `"call mode"` or `ctrl+shift+w`

Static, one-hand gestures, each firing a real Microsoft Teams keyboard
shortcut — mic mute/unmute, camera toggle, raise hand. Replaces the
earlier Window Management mode entirely (see §11); the `ctrl+shift+w`
combo and voice-trigger slot were reused as-is rather than reassigned.

| Gesture | Action | Teams shortcut (Mac) |
|---|---|---|
| `Thumb_Up` (thumbs up) | `UNMUTE_MIC` | Cmd+Shift+M |
| `Thumb_Down` (thumbs down) | `MUTE_MIC` | Cmd+Shift+M |
| `Victory` (peace sign) | `TOGGLE_CAMERA` | Cmd+Shift+O |
| `OK_SIGN` (thumb+index touching) | `RAISE_HAND` | Cmd+Shift+K |

**There is no app-agnostic "mute the current call" system API** — this
is inherently tied to whichever app the user is actually calling
through. Microsoft Teams was chosen (over Zoom / browser-based Google
Meet) specifically because it supports meeting-control shortcuts that
fire even when Teams isn't the frontmost/focused window — Meet's
browser shortcuts only work while the Meet tab itself has focus, which
defeats the purpose of a gesture fired while looking at the camera, not
the call window. These are Teams for Mac's documented bindings as of
this writing, sent as real keystrokes via `pyautogui.hotkey` — Microsoft
has changed its own shortcuts before, so re-verify against Teams'
Settings → Keyboard shortcuts page if they stop firing.

**Mute/unmute is a single toggle shortcut** — the same honest limitation
already documented for `MEDIA_PLAY_PAUSE` (§5). `UNMUTE_MIC` and
`MUTE_MIC` send the *identical* keystroke, so firing the "wrong" one
(already unmuted, thumbs-up again) toggles it the other way rather than
being a no-op. `Victory`/`TOGGLE_CAMERA` is explicitly a toggle by
design already, so it has no such asymmetry.

**`OK_SIGN` is hand-coded, not a MediaPipe category.** The bundled
gesture classifier's canned label set was checked directly against the
model file (`models/gesture_recognizer.task` → `hand_gesture_recognizer
.task` → `canned_gesture_classifier.tflite`'s embedded `labels.txt`):
only `None`, `Closed_Fist`, `Open_Palm`, `Pointing_Up`, `Thumb_Down`,
`Thumb_Up`, `Victory`, `ILoveYou` exist — there is no bundled `"OK"`
category, and there is no `custom_gesture_classifier.tflite` in the
bundle to add one without retraining. `OK_SIGN` is instead computed
directly from thumb/index landmark distance
(`GestureRecognizer._check_ok_sign`) — the exact same touch-distance
geometry Cursor mode's `PINCH` already uses, just scoped to Call mode
and edge-triggered (fires once when the fingers first touch, not again
until they separate) rather than distinguishing click from drag.

**Detection is gated to Call mode at the source.** `Thumb_Up`/
`Thumb_Down`/`Victory` are real MediaPipe categories that could in
principle be classified in any mode — `GestureRecognizer.
_publish_static_gesture` only publishes them while `active_mode ==
"call"`, so an actual thumbs-up given to someone mid-swipe in Flip mode
is never detected as a system command.

### 2.5 Quick Command Circle — gesture only: Closed_Fist → Open_Palm

A visual circle appears on screen with the system's other 4 modes laid
out around it. Swiping toward one of the four sides selects that mode
and the circle closes automatically — this is a quick, gesture-only way
to jump into any mode without remembering its own voice phrase or
keyboard combo:

| Selection gesture | Enters |
|---|---|
| `HAND_UP` | Presentation mode (§2.1) |
| `HAND_DOWN` | Call mode (§2.4) |
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
Cursor/Call) don't have this restriction — you can jump straight from
one of those to another without going through the circle or idle first.

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

19 apps, each a single-condition voice rule — say the phrase, the app
opens, nothing else required:

`open browser`, `open chatgpt`, `open github`, `open vscode`, `open
terminal`, `open safari`, `open chrome`, `open spotify`, `open slack`,
`open discord`, `open mail`, `open calendar`, `open notes`, `open
telegram`, `open finder`, `open notion`, `open photos`, `open preview`,
`open settings`.

**Removed**: `open zoom`, `open messages`, `open whatsapp`, `open
figma`, `open music` no longer open anything — dropped from
`mapping.json` (voice + `valid_signals`), `fusion.json` (rules),
`ActionExecutor`'s command table, and `OSController` entirely (see §11).

**Vosk vocabulary — confirmed, not just theoretical.** Loading the
grammar logs exactly which words it silently drops as unknown. Verified
in this environment: `chatgpt` and `vscode` are **not** in
`vosk-model-small-en-us-0.15`'s fixed lexicon — the recognizer will
never match "open chatgpt" / "open vscode" no matter how clearly they're
spoken, since one of the words in each phrase can't be decoded at all.
`discord`, `telegram`, `notion`, `notes`, `spotify`, `slack`, `safari`,
`chrome`, `calendar`, `settings`, `finder`, `photos`, `preview`,
`browser`, `terminal`, `github` were **not** flagged, so those phrases
should recognize normally (subject to normal accuracy limits — actual
recognition quality wasn't tested, only vocabulary presence). Swapping
the two failing phrases for the app's own executable/process name if it
differs, or switching to a larger Vosk model, are the two ways to fix
this if it matters in practice.

---

## 7. Gestures

| Gesture | Source | Used by |
|---|---|---|
| `HAND_LEFT` / `HAND_RIGHT` / `HAND_UP` / `HAND_DOWN` | Computed from index-fingertip velocity during a swipe-tracking session | Flip mode, Quick Command Circle selection |
| `HAND_SESSION_START` | Fired once on the Closed_Fist → Open_Palm transition that starts a swipe session | Quick Command Circle's entry trigger (idle-only, §2.4) |
| `PINCH` | Computed from thumb-tip/index-tip landmark distance | Cursor mode's click (quick tap) — hold+drag instead scrolls, §2.3 |
| `DOUBLE_PINCH` | Two `PINCH` taps inside `double_pinch_window` (0.3s) | Cursor mode's right-click, §2.3 |
| `Thumb_Up` / `Thumb_Down` / `Victory` | MediaPipe canned gesture categories, gated to Call mode only | Call mode's unmute/mute/camera-toggle, §2.4 |
| `OK_SIGN` | Hand-coded thumb/index-tip touch distance (same geometry as `PINCH`), gated to Call mode only | Call mode's raise-hand, §2.4 |

`Open_Palm`/`Closed_Fist`/`Pointing_Up` are still recognized internally by
`GestureRecognizer` (they drive the swipe session and the pointer stream)
but are no longer exposed as directly rule-matchable signals — nothing in
this design needs to react to them as discrete events. `ILoveYou` is
recognized by the model but still unused anywhere in this system.

---

## 8. Keyboard combos

| Combo | Used by |
|---|---|
| `ctrl+shift+p` | Enter Presentation mode |
| `ctrl+shift+f` | Enter Flip mode |
| `ctrl+shift+c` | Enter Cursor mode |
| `ctrl+shift+w` | Enter Call mode |
| `alt+shift` | Activates the face-gesture layer (§9) — works in any mode, or no mode at all |
| Right arrow (bare) | Next slide, Presentation mode only |
| Left arrow (bare) | Previous slide, Presentation mode only |
| Esc (bare) | Exit whichever mode is active, from any mode, at any time |

All four mode-entry combos share the `ctrl+shift` base, distinguished by
a third key that's the first letter of the mode name (**p**resentation,
**f**lip, **c**ursor, **w** — Call mode kept the `w` slot inherited from
the Window Management mode it replaced, see §11) — a single, consistent,
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

Each of the four mode-entry combos is used only as that mode's
single-source entry trigger, not as a hidden-combo gate. `alt+shift`,
however, genuinely is a multi-source combo gate — four global `rules` in
`fusion.json` require `{"keyboard": "SHIFT_ALT_KEY", "face": "..."}`
together (§9.1). This is exactly the case this held/released mechanism
was built for: holding `alt+shift` keeps `SHIFT_ALT_KEY` sitting in the
signal buffer indefinitely, so whichever `face_signal` arrives next
while it's held — a head tilt, a mouth-open, a double-blink — combines
with it correctly, no matter how far into the hold that face signal
happens to occur.

**Cursor mode's old Alt+single-hand-pinch zoom mechanism, which used to
be the one exception reading a raw modifier key outside `fusion.json`
entirely, has been removed** — zoom is now two-hand distance-based with
no keyboard involved at all (§2.3.1).

---

## 9. Face (FaceRecognizer — always on, no mode required)

A second, independent recognizer (`src/processing/face/face_recognizer
.py`, `src/processing/face/face_model.py`) running in parallel with the
hand-gesture pipeline, both subscribed to the same `camera_frame`
events. Uses `models/face_landmarker.task` (MediaPipe's Face Landmarker
task, with `output_face_blendshapes` and
`output_facial_transformation_matrixes` both enabled — the model bundle
was confirmed to include the blendshapes and geometry-pipeline files
needed for both, no custom training required).

Unlike almost everything in `GestureRecognizer`, **nothing here is mode-
gated** — every check runs and publishes regardless of `current_mode`.
Whatever consumes a `face_signal` downstream (fusion rules) decides when
it means something; this class stays unaware of modes entirely, by
design, per the user's own framing of this feature ("works without a
separate mode, always").

| Signal | How it's detected | Status |
|---|---|---|
| `CONFIRM` | Nod — head pitch swings fast one way, then fast back the other way, within `NOD_PHASE_WINDOW` (0.6s) | Reserved, unbound (same status as voice `YES`/`NO`) |
| `CANCEL` | Shake — identical two-phase swing detection, on head yaw instead of pitch | Reserved, unbound |
| `HEAD_TILT_LEFT` / `HEAD_TILT_RIGHT` | Head roll past `TILT_ENTER_DEGREES` (15°); must return within `TILT_EXIT_DEGREES` (8°) of neutral before firing again | Wired — §9.1 |
| `EYEBROWS_UP` / `EYEBROWS_DOWN` | `browInnerUp` blendshape crossing raise (0.5) / lower (0.3) thresholds, edge-triggered | Reserved, unbound — intended as a modifier for future features |
| `MOUTH_OPEN` | `jawOpen` blendshape crossing 0.5, rising edge only (closing fires nothing) | Wired — §9.1 |
| `DOUBLE_BLINK` | Two completed blinks (`eyeBlinkLeft`/`eyeBlinkRight` both crossing close/open thresholds) within `DOUBLE_BLINK_WINDOW` (0.5s) of each other. A single blink fires nothing — blinking is frequent and involuntary, only a deliberate double counts. | Wired — §9.1 |

**Nod/shake use relative sign changes, not absolute pitch/yaw
direction** — a "fast swing away, then fast swing back" round trip,
regardless of which absolute direction it starts in. This makes them
immune to the head-pose matrix's exact axis-sign convention, which was
not empirically verified against a real camera (see below).

**Head tilt's left/right labeling was not empirically verified** against
a real camera, unlike nod/shake — `_check_tilt` picks a sign convention
for roll that "should" correspond to a physical left/right tilt, but if
next/previous track come out swapped in practice, flip the comparison
in `FaceRecognizer._check_tilt`. This is the same category of
unverified-mirroring caveat already documented for `PointerOverlay.
MIRROR_X` (§4) — computed from a formula, not confirmed against a live
camera in this environment.

### 9.1 The Shift+Alt face layer

Four global `rules` in `fusion.json` combine a held `alt+shift`
(`SHIFT_ALT_KEY`) with a specific `face_signal`, firing regardless of
mode (`rules`, not `mode_rules` — see §1):

| Held + face signal | Action |
|---|---|
| `alt+shift` + `HEAD_TILT_RIGHT` | `NEXT_TRACK` |
| `alt+shift` + `HEAD_TILT_LEFT` | `PREVIOUS_TRACK` |
| `alt+shift` + `MOUTH_OPEN` | `MEDIA_PLAY_PAUSE` (same toggle as voice "start"/"stop", §5) |
| `alt+shift` + `DOUBLE_BLINK` | `TAKE_SCREENSHOT` |

`NEXT_TRACK`/`PREVIOUS_TRACK` post the real macOS system Next/Previous
media keys (`OSController.next_track`/`previous_track`) — the exact
same `NSEvent`/`Quartz` mechanism as `MEDIA_PLAY_PAUSE` (§5, now
factored into a shared `_post_system_media_key` helper taking an
`NX_KEYTYPE_*` constant), so it works with whichever player owns "now
playing", not tied to one specific app. `TAKE_SCREENSHOT` sends
Cmd+Shift+3 (macOS's built-in full-screen capture, saved to the
desktop) — not the interactive region-select variant (Cmd+Shift+4),
since that needs a follow-up mouse drag a gesture-only trigger can't
provide.

**"Reset" on mouth-open was interpreted as reusing the play/pause
toggle**, not a separate "restart current track" action — no system-
level API exists for the latter, and this reading matches the
mouth-open example's other stated half ("pause") using an already-
existing, already-documented action rather than inventing a new one.

**Double-blink was explicitly removed from this system in an earlier
round of design** (this project's very first redesign explicitly said
to drop it) and has now been explicitly reintroduced, scoped narrowly
to this one Shift+Alt-gated screenshot trigger rather than restored
as a general-purpose gesture — worth knowing if `git log`/older docs
still describe it as removed.

---

## 10. Setup preconditions

- **Accessibility permission — the single most common cause of "nothing
  happens" with no error.** Must be granted to whatever process actually
  runs `python src/main.py` (Terminal.app, iTerm, your IDE's integrated
  terminal — whichever one you launch it from) — System Settings →
  Privacy & Security → Accessibility. Every synthetic input event this
  app posts (cursor movement, clicks, scrolling, key presses) is
  silently dropped by macOS without raising any exception until this is
  granted — this is different from `FLIP_NEXT`/`FLIP_PREVIOUS`'s
  frontmost-app-name lookup (`osascript`), which *does* print a visible
  `[APPLESCRIPT ERROR]` when it's missing. `OSController` checks
  `ApplicationServices.AXIsProcessTrusted()` once at startup and prints
  a loud `[ACCESSIBILITY WARNING]` banner if it isn't granted —
  if Cursor mode's cursor-follow isn't moving anything, check the
  console for this banner first.
- **`pyautogui.PAUSE`** — pyautogui inserts a 0.1s sleep after *every*
  call by default. Cursor mode calls `moveTo()` once per camera frame,
  synchronously on whichever thread published `pointer_position` — at
  the default `PAUSE`, that capped cursor updates to ~10fps and stalled
  the camera pipeline for 100ms per frame, which is what made the
  cursor look like it was barely following the finger at all even with
  Accessibility granted and every signal wired correctly. Fixed by
  setting `pyautogui.PAUSE = 0` in `OSController.__init__`, alongside
  `FAILSAFE = False`.
- **Do Not Disturb automation** requires two Shortcuts authored once in
  the macOS Shortcuts app, named exactly: **"Enable Do Not Disturb"** and
  **"Disable Do Not Disturb"**. Modern macOS has no supported scriptable
  API for Focus/DND outside the Shortcuts app — the older
  `defaults write ... killall NotificationCenter` trick is deprecated
  and version-fragile, so this codebase intentionally does not use it.
- **Spotify** must be installed for Study mode's focus music
  (`PLAY_FOCUS_MUSIC`/`PAUSE_FOCUS_MUSIC` silently no-op otherwise).
- **VS Code's `code` CLI** must be on `PATH` for `OPEN_VSCODE`.
- Third-party apps (Chrome, Slack, Discord, Telegram, Notion) must be
  installed for their `open_*` voice commands to do anything.
- **Microsoft Teams** installed, for Call mode's mute/camera/raise-hand
  shortcuts (§2.4) to have an app actually listening for them — sending
  Cmd+Shift+M/O/K with Teams not running or not the app in the call does
  nothing useful.
- **`models/face_landmarker.task`** must be present for `FaceRecognizer`
  to start at all — verified present in this repo with the blendshapes
  and geometry-pipeline components needed for §9's blendshape/head-pose
  detection (not just bare landmarks).

---

## 11. What changed from the previous design (removed features)

This system has gone through several rounds of revision. Rather than a
single "before/after", here's the current, accurate state of what
exists and what was tried and dropped along the way:

- **Window Management existed briefly as the 4th mode, then was removed
  again** and replaced by Call mode (§2.4) — same `ctrl+shift+w` slot,
  same position as the Quick Command Circle's 4th destination (§2.5),
  different purpose entirely (mic/camera/raise-hand for Microsoft Teams
  instead of maximize/minimize/snap-left/snap-right). Its
  `MAXIMIZE_WINDOW`/`MINIMIZE_WINDOW`/`MOVE_WINDOW_LEFT`/
  `MOVE_WINDOW_RIGHT` commands and their `OSController`/`ActionExecutor`
  entries were removed outright, not kept around unused.
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
  Presentation/Flip/Cursor/Call/Quick-Circle modes (§2, pure
  gesture-scoping, no side effects) — not a 1:1 rename; Work environment
  is a broader "office" app set rather than specifically development
  tools.

If any of these turn out to be missed rather than intentionally dropped,
they're easy to reintroduce — the mechanisms (`rules`, `mode_rules`,
environment `enter_actions`/`exit_actions`) all still exist.

- **`open zoom`/`open messages`/`open whatsapp`/`open figma`/`open
  music`** were dropped — removed from `mapping.json` (`voice` +
  `valid_signals.voice`), `fusion.json` (their five `rules` entries),
  `ActionExecutor`'s command table, and `OSController`'s
  `open_zoom`/`open_messages`/`open_whatsapp`/`open_figma`/`open_music`
  methods. §6 now lists 19 apps instead of 24.
- **Cursor mode gained `DOUBLE_PINCH`** (two quick pinches within 0.3s →
  right-click, §2.3) — an addition, not a replacement; plain single-pinch
  click and pinch-hold-drag scroll behave exactly as before.
- **Cursor-follow root cause found and fixed**: `pyautogui.PAUSE`'s
  default 100ms-per-call sleep was throttling every `moveTo()` call
  Cursor mode made once per camera frame (see §10). This, not the
  `valid_signals` keyboard mismatch fixed in an earlier round, was the
  actual reason the cursor kept failing to visibly track the finger.
- **Window Management mode was replaced by Call mode** (§2.4) — see the
  bullet above.
- **Cursor mode now supports a second hand** (§2.3.1): off-hand
  `Closed_Fist` engages a 0.3x "precision mode" for fine cursor
  positioning; an off-hand present but not fisted drives zoom by
  two-hand fingertip distance. `GestureModel.num_hands` changed from 1
  to 2 to support this — every existing single-hand check still operates
  on exactly one "primary" hand, resolved per-frame, so single-hand use
  is unaffected.
- **Alt+single-hand-pinch zoom was removed and replaced** by the
  two-hand distance zoom above — no keyboard involved in Cursor-mode
  zoom anymore. `GestureRecognizer._handle_keyboard_raw`/`alt_held`/
  `_check_zoom` no longer exist.
- **A second, independent recognizer was added**: `FaceRecognizer`
  (§9), running in parallel with `GestureRecognizer` off the same
  camera frames, using `models/face_landmarker.task`. Publishes
  `CONFIRM`/`CANCEL`/`HEAD_TILT_LEFT`/`HEAD_TILT_RIGHT`/`EYEBROWS_UP`/
  `EYEBROWS_DOWN`/`MOUTH_OPEN`/`DOUBLE_BLINK` as a new `face` signal
  source, parallel to `voice`/`gesture`/`keyboard` — required a new
  `_handle_face` method in `CommandInterpreter` and a `face` section in
  `mapping.json`/`valid_signals`, but needed zero changes to
  `MultimodalFusion`, `TemporalSync`, or `SignalMapper`, which were
  already fully generic over signal source.
- **Double-blink was reintroduced**, narrowly, as one of the new
  Shift+Alt face-layer triggers (§9.1) — it was explicitly removed from
  this system in an earlier round of design and has now been brought
  back for this one specific use, not restored as a general gesture.

---

## 12. Testing / verification guide

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
  clicks (after the ~0.3s double-pinch window passes) and a
  held-and-dragged pinch scrolls without also clicking. Verify two quick
  pinches in a row right-click instead of clicking twice.
- **Two-hand Cursor mode**: with primary hand `Pointing_Up`, bring a
  second hand into frame as a `Closed_Fist` — confirm cursor movement
  visibly slows to roughly 0.3x, and that opening/removing that hand
  snaps the cursor back to the primary fingertip's current absolute
  position (an expected jump, not a bug — see §2.3.1). Then bring the
  second hand in open (not fisted) and move both index fingertips apart/
  together — confirm the frontmost app zooms in/out with no keyboard
  involved.
- **Call mode**: enter it, confirm Teams is running and in a call, then
  thumbs-up/thumbs-down/peace-sign/OK-sign in turn — confirm each Teams
  meeting control actually fires. Confirm doing an actual thumbs-up
  gesture in Flip or Presentation mode does nothing (gated at the
  source, §2.4).
- **Modes**: confirm Presentation/Flip/Cursor/Call are mutually
  exclusive and switching between them doesn't require going through
  "exit mode" first; confirm the Quick Command Circle only opens from
  idle (not while Flip mode's swipe session is active) and that swiping
  in each of the 4 directions enters the right mode and closes the
  circle.
- **Environments**: confirm entering one runs its full `enter_actions` in
  order, and switching directly to a different environment runs the old
  one's `exit_actions` first.
- **"exit mode" scope**: enter an environment, then a mode, say "exit
  mode", confirm only the mode cleared and the environment's apps/DND
  state are untouched.
- **Face layer**: hold `alt+shift` and tilt your head right/left —
  confirm next/previous track fires (and note which physical direction
  actually maps to which, per the unverified-labeling caveat in §9).
  Open your mouth — confirm play/pause. Blink twice quickly — confirm a
  screenshot appears on the desktop; confirm a single blink does
  nothing. Release `alt+shift` and repeat — confirm nothing fires
  without it held. Separately, without `alt+shift` held, nod and shake
  your head — confirm the console shows `CONFIRM`/`CANCEL` firing
  (reserved, no visible effect yet).

Visual-inspection-only: laser pointer / Cursor-mode cursor position
accuracy and mirroring direction, the Quick Command Circle's on-screen
appearance, Flip mode's frontmost-app heuristic (test with a flippable
app like Preview vs. a non-flippable one to confirm the Space-switch
fallback), precision-mode's cursor slowdown feel.
