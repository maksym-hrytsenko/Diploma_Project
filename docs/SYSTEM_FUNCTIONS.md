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

## 1. Three independent state axes

The system tracks three separate, orthogonal pieces of state at once:

- **Mode** (`presentation` / `flip` / `cursor` / `call` /
  `quick_circle` / none) — an ephemeral context that decides what the
  *same physical gesture* currently means. Modes exist purely to stop
  gestures from colliding with each other (a swipe means something
  different in Flip mode than a thumbs-up means in Call mode). They
  carry no OS side effects of their own.
- **Environment** (`work` / `job_search` / `study` / `movie` / `news` /
  none) — a
  longer-lived task backdrop. Entering one runs a real sequence of OS
  actions (opening apps, toggling Do Not Disturb, music); leaving it (by
  entering a different environment) undoes them.
- **Try Mode** (on / off, see §2.6) — an independent on/off flag, not a
  mode itself. While on, nothing above ever produces a real OS side
  effect — it only decides whether decided commands actually execute.

You can be in a mode and an environment at the same time — e.g. `study`
environment (Safari + Preview open, focus music playing) while also
switching briefly into `cursor` mode to click something. Try Mode can be
on at the same time as any mode and/or environment, precisely so
switching between them can be demonstrated without side effects.

Saying **"exit mode"**, or pressing **Esc**, leaves the active **mode**
and turns **Try Mode** off if it's on — both work identically, from any
mode, at any time. Environments are only left by entering a different
environment — there is no dedicated "leave environment" phrase.

---

## 2. Modes

### 2.1 Presentation — `"presentation mode"` or `ctrl+shift+p`

Controls slides by key, by voice, or by a hand gesture meant to be
comfortable from a few meters away (e.g. while actually presenting,
away from the keyboard):

| Trigger | Action |
|---|---|
| voice "start presentation" | `START_SLIDESHOW` |
| voice "next slide" | `NEXT_SLIDE` |
| voice "previous slide" | `PREVIOUS_SLIDE` |
| Closed fist, wrist moved right | `NEXT_SLIDE` |
| Closed fist, wrist moved left | `PREVIOUS_SLIDE` |

`START_SLIDESHOW` sends a plain **F5** keypress — PowerPoint/Keynote's
own "start slideshow from the beginning" shortcut. Entering Presentation
mode only arms this app's next/previous-slide mapping; it does not by
itself start the on-screen slideshow, so saying "start presentation"
once you're already in the mode is what actually begins it.

The gesture needs no separate "arm" step — holding a closed fist up and
moving it decisively left or right fires the switch as soon as the
motion is fast enough (mirrored the same way pointer tracking is, so it
moves the same direction as the presenter's own hand from their point
of view). It is tracked from the wrist rather than the fingertip and
uses its own thresholds, independent from Flip mode's swipe, so it can
be tuned separately for typical presenting distance without affecting
Flip mode.

Raising the index finger (`Pointing_Up`) shows the same translucent
on-screen pointer dot used elsewhere in the system (§4), acting as
a lightweight laser pointer for the current slide — no separate toggle
needed.

`NEXT_SLIDE`/`PREVIOUS_SLIDE` send a plain Right/Left arrow key press —
the same thing a real presentation clicker does, so it works with
PowerPoint, Keynote, Google Slides, and PDF viewers without any
per-app integration.

**Note on the physical arrow keys**: pressing the real Right/Left arrow
keys is *not* mapped to `NEXT_SLIDE`/`PREVIOUS_SLIDE` in this mode, on
purpose. Every presentation app already treats Right/Left as its own
native "next/previous slide" shortcut, and this system's own keyboard
listener does not (and cannot, via `pynput`) suppress the physical
keypress from also reaching the focused app — mapping it here as well
used to fire the real key press AND this app's own synthetic one for
every press, skipping a slide. Voice and the closed-fist wrist gesture
above are the two hands-free ways this system adds; the physical arrow
keys keep working exactly as they always do in the focused presentation
app, with no help (and no interference) from this system.

### 2.2 Flip — `"flip mode"` or `ctrl+shift+f`

Smooth up/down/left/right gestures for flipping through content (reels,
photos, pages) or scrolling websites:

| Gesture | Action |
|---|---|
| `HAND_UP` | `SCROLL_DOWN` (smooth multi-tick scroll — see inversion note below) |
| `HAND_DOWN` | `SCROLL_UP` (smooth multi-tick scroll) |
| `HAND_RIGHT` | `FLIP_PREVIOUS` (inverted from the physical swipe direction — see below) |
| `HAND_LEFT` | `FLIP_NEXT` (inverted from the physical swipe direction — see below) |

**Natural/drag scrolling, not wheel scrolling.** Moving the hand up feels
like grabbing the content and dragging it up with your hand — which
pulls *later* content into view, the same net effect as a traditional
"scroll down". This is why `HAND_UP` maps to the `SCROLL_DOWN` action
(and vice versa) rather than the same-named one — it matches how
touchscreens and macOS's default "natural scrolling" trackpad behavior
work, rather than an old-style scroll wheel where wheel-up and
content-up are the same direction. Cursor mode's pinch-drag scroll
(§2.3) uses the identical convention.

**Left/right is inverted, same idea as the up/down inversion above.**
`HAND_RIGHT` (physically swiping the hand to the right) maps to
`FLIP_PREVIOUS`, and `HAND_LEFT` to `FLIP_NEXT` — confirmed by hands-on
testing to read as the more natural drag direction (swiping right
"pulls" earlier content into view from off-screen left, the same
"grab and drag the content" feel as the vertical case), rather than
mapping the swipe direction directly onto the same-named action. Set in
`fusion.json`'s `flip_right`/`flip_left` mode_rules — `GestureRecognizer`
itself still reports raw, uninverted `HAND_LEFT`/`HAND_RIGHT`, exactly
as Quick Circle mode (§2.5) also consumes them; only Flip mode's own
rule mapping is inverted.

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

`FLIP_NEXT`/`FLIP_PREVIOUS` always send `Ctrl+Right`/`Ctrl+Left`
(macOS's built-in shortcut for switching between Spaces/desktops) —
one predictable action every time. An earlier revision tried to guess
the frontmost app via an AppleScript lookup against a hardcoded
allowlist (Preview/Photos/Safari/Chrome/QuickTime Player) and sent a
plain arrow key instead when the app "looked flippable"; that
context-dependent heuristic was removed at the user's request, since a
left/right swipe should mean the same thing regardless of what's in
front.

**Smooth scroll, tuned for a longer glide.** `SCROLL_UP`/`SCROLL_DOWN`
don't jump the full distance in one motion — each swipe scrolls a total
of `OSController.FLIP_SCROLL_PIXELS` (500px, raised in two rounds of
user feedback: an original 90px, then 200px, then a further 2.5x jump
to 500px after up/down swipes still needed to travel noticeably
farther) split across `FLIP_SCROLL_TICKS` (18) small ticks with a
`FLIP_SCROLL_TICK_DELAY` (14ms) pause between each, using a real
pixel-precise scroll event (`Quartz.CGEventCreateScrollWheelEvent` with
`kCGScrollEventUnitPixel`, not `pyautogui`'s coarser line/click units)
so the glide stays visibly animated (~250ms total) despite covering
much more on-screen distance per swipe. Tune `FLIP_SCROLL_PIXELS`
up/down further if it still feels too far or too short.

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
| Off-hand pinch (thumb+index touching), held | Precision mode AND zoom engage together — see §2.3.1 |

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

**The off-hand is tracked by a completely separate model from the
primary hand — not by asking the primary gesture model to track two
hands.** The primary hand's identity/gesture always comes from
`GestureModel` (`num_hands=1`, VIDEO mode, exactly as before this
feature existed — zero change in behavior for the primary hand or any
mode other than Cursor). A second, independent model,
`OffHandModel` (`src/processing/gesture/gesture_model.py`,
`models/hand_landmarker.task`, `num_hands=2`, IMAGE mode, landmarks
only — no gesture classification step at all) runs in parallel,
**only while `active_mode == "cursor"`**, purely to find a second hand.

This split exists because of a confirmed MediaPipe bug: `GestureRecognizer`
with `num_hands > 1` combined with `running_mode=VIDEO` corrupts its
internal tensor-concatenation calculator
(`multiplehandgesturerecognizergraph`'s `ConcatenateTensorVectorCalculator`,
error: `"Packet isn't the sole owner of the holder"`) the first time two
hands are genuinely detected in the same frame — and the graph does
**not** recover: every frame afterward fails identically, permanently
killing gesture recognition, not just the two-hand feature, until the
process is restarted. `HandLandmarker` (no gesture classification, so
it never reaches the buggy calculator at all) does not have this bug
even with `num_hands=2`, which is why the off-hand uses it instead.

**Matching the off-hand to the primary hand**: `OffHandModel` has no
concept of "primary" vs. "off" — it just returns up to two detected
hands, in no particular guaranteed order. `GestureRecognizer._find_off_hand`
resolves this by comparing each of `OffHandModel`'s detected wrists
against the primary hand's wrist (from `GestureModel`'s own, separate
result) and picking whichever is **farthest away** — if even the
farthest candidate is within `SAME_HAND_DISTANCE` (0.15, normalized),
it's rejected as just `OffHandModel` re-detecting the primary hand
itself, not a genuine second one, and there is no off-hand this frame.

**Off-hand pinch detection reuses the exact same thumb/index geometry as
the primary hand's own `PINCH`** (`GestureRecognizer._pinch_distance` <
`pinch_distance_threshold`) — not a fist shape, and not a MediaPipe
gesture category (`HandLandmarker` provides no gesture classification at
all). One off-hand state — pinched or not — now drives both precision
mode and zoom engagement together, rather than a fist-vs-open shape
choosing between them.

**Precision mode (off-hand pinch, held)**: like lowering a mouse's DPI.
Engaging it anchors the primary fingertip's current position; while the
off-hand pinch is held, the published cursor position only moves
`PRECISION_SCALE` (0.5) of however far the primary hand actually moves
from that anchor point — fine, deliberate positioning instead of the
normal full-speed 1:1 follow. This is necessarily a *relative* mechanism
layered on top of the otherwise strictly *absolute* mapping described
above — releasing the off-hand pinch snaps straight back to absolute
1:1 tracking, which means the cursor visibly jumps to match wherever the
primary fingertip currently, actually is. That jump is an intentional,
honest consequence of mixing a temporary relative "clutch" into an
absolute mapping, not a bug — same as lifting and repositioning a
physical mouse. See `GestureRecognizer._update_pointer`.

**Zoom (off-hand pinch, held, primary hand's own pinch distance)**: the
off-hand pinch simultaneously *engages* zoom; the *amount* comes from
spreading or closing the **primary** hand's own thumb and index apart
(`GestureRecognizer._check_zoom`, reusing `_pinch_distance` on the
primary hand) — spreading zooms in, closing zooms out. While zoom is
engaged this way, the primary hand's own pinch no longer means `CLICK`/
drag-scroll (see `_handle_frame`'s `zoom_engaged` branch) — the same
physical touch means one thing or the other depending on whether the
off-hand is currently pinched. `ActionExecutor`'s consumption of
`pinch_zoom` (accumulate deltas, fire `OSController.zoom_in()`/
`zoom_out()` per `zoom_step_threshold`, 0.05) is unchanged; only the
*source* of the delta changed over this feature's history — first
single-hand pinch distance while holding Alt, then two-hand fingertip
distance, now primary-hand pinch distance engaged by an off-hand pinch.
`zoom_in`/`zoom_out` still send Cmd+"="/Cmd+"-", the standard zoom
shortcut in Safari, Preview, Photos and most other macOS apps.

**Holding Alt to engage zoom (as a one-handed alternative to the
off-hand pinch) was removed.** It existed for a while as an `OR`
alongside the off-hand pinch (`zoom_engaged = self.alt_held or
off_hand_pinching`, tracked via a raw `keyboard_raw` subscription in
`GestureRecognizer`, bypassing `KeyboardProcessor`/`mapping.json`
entirely). Once Alt became the global face-layer modifier (§9.1) —
`ALT_KEY` held plus `HEAD_TILT_*`/`MOUTH_OPEN`/`EYEBROWS_UP` firing
track-switch/pause/volume actions — the
two uses of Alt collided: holding it to zoom in Cursor mode would
simultaneously arm all of those face-layer actions, so any incidental
head movement while zooming (very likely, since zooming draws the eyes
to the screen) fired an unrelated command. Zoom is off-hand-pinch-only
now — confirmed by testing to be unambiguous, since it is the only zoom
trigger that shares no gesture or modifier key with anything else Alt
now does.

Precision mode and zoom are **not** mutually exclusive anymore — both
are driven by the same off-hand-pinch state simultaneously, unlike the
earlier fist-vs-open-shape design that chose one or the other.

### 2.4 Call — `"call mode"` or `ctrl+shift+w`

Static, one-hand gestures, each firing a real Microsoft Teams keyboard
shortcut — mic toggle, camera toggle, call-audio toggle, background-blur
toggle. Replaces the earlier Window Management mode entirely (see §11);
the `ctrl+shift+w` combo and voice-trigger slot were reused as-is rather
than reassigned. There is deliberately no raise-hand gesture — Call mode
only ever toggles persistent state, nothing momentary.

| Gesture | Action | Teams shortcut (Mac) |
|---|---|---|
| 1 finger raised | `TOGGLE_MIC` | Cmd+Shift+M |
| 2 fingers raised | `TOGGLE_CAMERA` | Cmd+Shift+O |
| 3 fingers raised | `TOGGLE_CALL_AUDIO` | macOS system output mute (no Teams shortcut exists) |
| 4 fingers raised | `TOGGLE_BACKGROUND_BLUR` | Cmd+Shift+P |

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

**The finger count is computed from hand landmarks, not a MediaPipe
category.** The bundled gesture classifier's canned label set was
checked directly against the model file (`models/gesture_recognizer
.task` → `hand_gesture_recognizer.task` →
`canned_gesture_classifier.tflite`'s embedded `labels.txt`): only
`None`, `Closed_Fist`, `Open_Palm`, `Pointing_Up`, `Thumb_Down`,
`Thumb_Up`, `Victory`, `ILoveYou` exist — there is no bundled "one
finger"/"two fingers"/"three fingers"/"four fingers" category to rely
on. `GestureRecognizer._count_extended_fingers` instead counts how many
of the four non-thumb fingers currently sit farther from the wrist than
their own PIP joint (`FINGER_TIP_PIP_LANDMARKS`), independent of hand
rotation. The thumb is left out of the count entirely — whether it
happens to be tucked in or splayed out while counting 1–4 with the
other fingers varies too much between people to be a reliable signal.

**Each toggle fires once per raised hand, not once per frame.** Showing
a finger count turns its function ON; the hand must then leave the
frame entirely before showing that same count again turns it back OFF —
this is `GestureRecognizer.locked_toggle_gestures`, the same mechanism
already used to stop a single held gesture from re-firing every frame.
Each of the four gestures is also a single OS-level toggle shortcut
(same honest limitation already documented for `MEDIA_PLAY_PAUSE`, §5):
firing it while already in the target state flips it the other way
rather than being a no-op.

**`TOGGLE_CALL_AUDIO` has no dedicated Teams shortcut.** Only mic and
camera are exposed as Teams keyboard shortcuts — muting the call's own
incoming audio specifically is not. `OSController.toggle_call_audio`
instead toggles the Mac's system-wide audio output mute via
`osascript`, which silences the call's sound along with everything else
on the machine. This is the only way to reliably silence a call's audio
from outside the Teams window without UI-scripting a click on Teams'
own volume control.

**Detection is gated to Call mode at the source.**
`GestureRecognizer._handle_frame` only computes a finger-count gesture
at all while `active_mode == "call"` — so someone naturally counting on
their fingers mid-swipe in Flip mode is never detected as a system
command.

**The overlay pointer is suppressed in Call mode.** One raised finger
(`ONE_FINGER`, mic toggle) is, landmark-for-landmark, the exact same
hand shape MediaPipe's own classifier calls `Pointing_Up` — the
gesture every other mode uses to drive the translucent overlay dot (a
lightweight laser pointer, see §2.1) or, in Cursor mode, the real OS
cursor. Without a guard, raising one finger to toggle the mic would
also move that overlay dot across the screen, which reads as "the
Presentation-mode pointer fired instead of the toggle" even though the
toggle itself fired correctly underneath it. `GestureRecognizer.
_update_pointer` returns immediately whenever `active_mode == "call"`,
before even checking `Pointing_Up` — Call mode has no pointer/cursor
use of its own, so nothing is lost by suppressing it entirely.

### 2.5 Quick Command Circle — gesture only: Closed_Fist → Open_Palm

A visual circle appears on screen with the system's other 4 modes laid
out around it. Swiping toward one of the four sides selects that mode
and the circle closes automatically — this is a quick, gesture-only way
to jump into any mode without remembering its own voice phrase or
keyboard combo:

| Selection gesture | Enters |
|---|---|
| `HAND_UP` | Flip mode (§2.2) |
| `HAND_DOWN` | Cursor mode (§2.3) |
| `HAND_LEFT` | Presentation mode (§2.1) |
| `HAND_RIGHT` | Call mode (§2.4) |

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

### 2.6 Try Mode — voice `"try mode"`, `ctrl+shift+t`, or the switch next to the camera preview

Not one of the five modes above — an independent on/off flag that can be
active **at the same time as** Presentation/Flip/Cursor/Call/Quick Circle,
so switching between them can be demonstrated safely. While Try Mode is
on:

- `ActionExecutor` skips every real OS side effect — no key presses, no
  clicks, no cursor movement, no app/URL launches, nothing. It logs what
  it *would* have run instead (`[TRY MODE] would execute: ...`).
- Everything upstream of that keeps working exactly as normal: mode
  switching, gesture/voice/keyboard recognition, the camera preview's
  live "Detected: ..." caption, the laser-pointer dot (Cursor mode's
  pointer stream still draws the dot where the real cursor would go,
  it just doesn't move the actual mouse).

| Trigger | Effect |
|---|---|
| voice "try mode" | Toggles Try Mode on/off |
| `ctrl+shift+t` | Toggles Try Mode on/off |
| Switch next to the camera preview (top-right corner) | Toggles Try Mode on/off |
| voice "exit mode" / Esc / clicking the active mode's icon | Turns Try Mode off too, in addition to leaving whichever regular mode is active (either, both, or neither may be true at that moment) |

Turning Try Mode on while the System ON/OFF hub shows OFF turns the
system back on first, the same detour clicking a mode icon already uses
— see `MainWindow._on_try_mode_toggled`.

---

## 3. Environments

Entered by voice, each runs a real sequence of actions; switching
directly from one environment to another cleanly ends up in the new one,
with none of the old one's state left behind.

### 3.1 Work — `"work mode"`

| On enter | On exit |
|---|---|
| `ENABLE_DO_NOT_DISTURB` | `DISABLE_DO_NOT_DISTURB` |
| `OPEN_SLACK` | — |
| `OPEN_MAIL` | — |
| `OPEN_CALENDAR` | — |

Reuses the same `OPEN_SLACK`/`OPEN_MAIL`/`OPEN_CALENDAR` actions the
global "open slack"/"open mail"/"open calendar" voice commands use
(§6) — no window-group config, just three real apps actually opening,
so the effect is immediately visible. (Previously removed from
`config/fusion.json`/`mapping.json` — apparently by accident, during an
unrelated commit — and restored.)

### 3.2 Job Search — `"job search mode"`

| On enter | On exit |
|---|---|
| `ENABLE_DO_NOT_DISTURB` | `DISABLE_DO_NOT_DISTURB` |
| `OPEN_JOB_SEARCH_WINDOWS` | — |

`OPEN_JOB_SEARCH_WINDOWS` opens the `job_search` entry of
`os_controller.window_groups` (`config/system.json`) — one Chrome
window with job-board searches, and a second with generic ChatGPT +
Overleaf entry points. See §3.5 for how window groups are opened.

### 3.3 Study — `"study mode"`

| On enter | On exit |
|---|---|
| `ENABLE_DO_NOT_DISTURB` | `DISABLE_DO_NOT_DISTURB` |
| `OPEN_STUDY_WINDOWS` | — |

`OPEN_STUDY_WINDOWS` opens the `study` entry of
`os_controller.window_groups` — three Chrome windows: a generic ChatGPT
+ NotebookLM entry point, a generic Overleaf + PlantUML entry point, and
research (Google Scholar/Images + IEEE Xplore).

### 3.4 Movie — `"movie mode"`

| On enter | On exit |
|---|---|
| `ENABLE_DO_NOT_DISTURB` | `DISABLE_DO_NOT_DISTURB` |
| `PREVENT_DISPLAY_SLEEP` (`caffeinate -d`, so the screen doesn't dim mid-movie) | `ALLOW_DISPLAY_SLEEP` |
| `OPEN_TV` (macOS's built-in TV.app) | — |
| `OPEN_NETFLIX` (opens `netflix.com` in the browser) | — |
| `RUN_CINEMA_MODE` (runs the user-authored **"Turn on cinema mode"** Shortcut, which drives the Magic Home smart lights) | — |

### 3.5 News — `"news mode"`

| On enter | On exit |
|---|---|
| `OPEN_NEWS_TABS` | — (nothing was disruptively changed) |

`OPEN_NEWS_TABS` opens the `news` entry of `window_groups` — one Chrome
window with a few default neutral news tabs (BBC World, Reuters World,
TechCrunch); edit the URL list in `config/system.json` to change them.

`OPEN_JOB_SEARCH_WINDOWS`/`OPEN_STUDY_WINDOWS`/`OPEN_NEWS_TABS` all go
through `OSController.open_window_group`: for each inner URL list in the
named `window_groups` entry, the first URL opens a brand-new Chrome
window (`open -na "Google Chrome" --args --new-window <url>`) and, after
a 1s pause for the window to actually open, the rest of that list's URLs
join it as tabs (`open -a "Google Chrome" <url>`). `OPEN_TV` deliberately
still uses Apple's own pre-installed TV.app — real, always present on
stock macOS, no invented URL.

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
- **Targets the projector, not the laptop screen.** When a second
  display is connected (`PointerOverlay._select_presentation_screen`),
  the overlay places itself on the first non-primary screen it finds —
  the projector/external display an audience actually sees — rather
  than the primary screen, which normally stays with the presenter's
  own view. Falls back to the primary screen when only one is
  connected. Selected once at construction, so connect the projector
  before starting the app — plugging it in mid-session needs a
  restart to be picked up.

**Presentation mode maps the fingertip differently from every other
mode** (`GestureRecognizer._update_presentation_pointer`). Cursor mode
and every other mode use an absolute mapping — the fingertip's raw
position in the camera frame directly is the screen position. In
Presentation mode, the pointer instead:

1. Snaps to the **screen center** the instant `Pointing_Up` starts.
2. Freezes the presenter's current hand size (wrist-to-middle-knuckle
   distance) as a unit.
3. Maps hand movement from the starting position onto the whole
   screen across a virtual box `PRESENTATION_POINTER_BOX_HANDS` (4.0)
   hand-widths wide, centered on that starting position.

This makes the same comfortable hand movement sweep the whole screen
whether presenting from 1m or 4m away — an absolute mapping would
otherwise need a physically larger sweep the farther the presenter
stands, since the camera's field of view covers more real-world space
at range. The box re-anchors to center every time pointing restarts
(lowering the finger and raising it again), it does not persist across
a session the way Cursor mode's cursor position does.

---

## 5. Global commands (always active, regardless of mode or environment)

| Command | Phrase | Effect |
|---|---|---|
| `START` | "start" | `MEDIA_PLAY_PAUSE` |
| `STOP` | "stop" | `MEDIA_PLAY_PAUSE` |
| `PAUSE` | "pause" | `MEDIA_PLAY_PAUSE` |
| `RESET` | "reset" | `MEDIA_PLAY_PAUSE` |
| `NEXT_TRACK` | "next track" | `NEXT_TRACK` |
| `PREVIOUS_TRACK` | "previous track" | `PREVIOUS_TRACK` |
| `EXIT_MODE` | "exit mode" | Leaves the active mode only (§1) |

**`MEDIA_PLAY_PAUSE`** posts the real macOS system Play/Pause media key
(via `pyobjc`'s `NSEvent`/`Quartz`, the same event a physical keyboard's
media key sends) — this is what lets it control **whichever** player
currently owns "now playing" (Spotify, Music, a browser tab, QuickTime,
...) rather than being tied to one specific app. `NEXT_TRACK`/
`PREVIOUS_TRACK` use the matching system Next/Previous media keys
(`OSController.next_track`/`previous_track`), same universal reach.

**Known limitation**: macOS only exposes a single toggle-style
Play/Pause media key, not separate absolute Play-only/Pause-only system
keys. So "start", "stop", "pause" and "reset" all send the *identical*
event — saying "stop" or "reset" while already paused resumes playback
instead of restarting the track. This is an honest consequence of using
the one truly universal mechanism rather than app-specific AppleScript
(which would only work for one player, breaking the "any open player"
requirement). "Reset" was deliberately given no separate "restart from
the beginning" behavior — no cross-player system API for that exists —
matching the same reasoning already applied to the face layer's
mouth-open "reset" (§9.1).

**Voice recognition is English-only** (`vosk-model-small-en-us-0.15`) —
every phrase above must be spoken in English; there is no Ukrainian
grammar loaded. Grammar is generated automatically from this file's
`voice` section (`VoskSpeechModel._load_grammar`), so a phrase not
listed here will never be recognized, no matter how clearly it's said.

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
| `HAND_LEFT` / `HAND_RIGHT` | Computed from wrist velocity while the gesture is held as `Closed_Fist` — no separate arm/disarm step, own thresholds (`presentation_fist_*`) independent of the swipe above | Presentation mode's slide navigation, §2.1 |
| `HAND_SESSION_START` | Fired once on the Closed_Fist → Open_Palm transition that starts a swipe session | Quick Command Circle's entry trigger (idle-only, §2.4) |
| `HAND_SESSION_END` | Fired once on the Open_Palm → Closed_Fist transition that ends a swipe session | Closes the Quick Command Circle without picking a mode (§2.5), quick_circle only |
| `PINCH` | Computed from thumb-tip/index-tip landmark distance | Cursor mode's click (quick tap) — hold+drag instead scrolls, §2.3 |
| `DOUBLE_PINCH` | Two `PINCH` taps inside `double_pinch_window` (0.3s) | Cursor mode's right-click, §2.3 |
| `ONE_FINGER` / `TWO_FINGERS` / `THREE_FINGERS` / `FOUR_FINGERS` | Count of non-thumb fingers extended (distance-from-wrist vs. each finger's own PIP joint), gated to Call mode only | Call mode's mic/camera/call-audio/background-blur toggles, §2.4 |

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
| `ctrl+shift+t` | Toggle Try Mode (§2.6) — independent of the four mode combos above, can be pressed at any time |
| `alt` (bare) | Activates the face-gesture layer (§9) — works in any mode, or no mode at all |
| `ctrl` (bare) | Volume-down variant of the face-gesture layer (§9.1) — `ctrl` + `EYEBROWS_UP` only, nothing else is bound to bare `ctrl` |
| Esc (bare) | Exit whichever mode is active, from any mode, at any time — also turns Try Mode off if it's on (§2.6) |

Right/Left arrow are deliberately **not** bound to anything here anymore
— see the "Note on the physical arrow keys" in §2.1.

All four mode-entry combos share the `ctrl+shift` base, distinguished by
a third key that's the first letter of the mode name (**p**resentation,
**f**lip, **c**ursor, **w** — Call mode kept the `w` slot inherited from
the Window Management mode it replaced, see §11; **t**ry Mode reuses the
same pattern). `mapping.json`'s `keyboard` and `valid_signals.keyboard`
must always list the exact same combo strings — a mismatch between the
two silently drops every press of the affected combo with no error (this
happened once during development and is why every keyboard combo is
worth double-checking after an edit).

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
single-source entry trigger, not as a hidden-combo gate. Bare `alt`,
however, genuinely is a multi-source combo gate — five global `rules` in
`fusion.json` require `{"keyboard": "ALT_KEY", "face": "..."}` together
(§9.1). This is exactly the case this held/released mechanism was built
for: holding `alt` keeps `ALT_KEY` sitting in the signal buffer
indefinitely, so whichever `face_signal` arrives next while it's held —
a head tilt, a mouth-open, an eyebrow-raise — combines with it
correctly, no matter how far into the hold that face signal happens to
occur.

**Originally gated on `alt+shift`, simplified to bare `alt`** after
hands-on testing showed the extra modifier added friction without
adding anything — one held key plus a face movement is enough, and nothing
else in this app's keyboard section uses bare `alt` alone, so there is
no collision risk.

**Cursor mode's old Alt+single-hand-pinch zoom mechanism, which used to
be the one exception reading a raw modifier key outside `fusion.json`
entirely, has been removed** — zoom is now two-hand distance-based with
no keyboard involved at all (§2.3.1).

---

## 9. Face (FaceRecognizer — global layer, works regardless of active mode)

A second, independent recognizer (`src/processing/face/face_recognizer
.py`, `src/processing/face/face_model.py`) running in parallel with the
hand-gesture pipeline, both subscribed to the same `camera_frame`
events. Uses `models/face_landmarker.task` (MediaPipe's Face Landmarker
task, with `output_face_blendshapes` and
`output_facial_transformation_matrixes` both enabled — the model bundle
was confirmed to include the blendshapes and geometry-pipeline files
needed for both, no custom training required).

**Not gated on mode state.** `FaceRecognizer` used to suppress itself
entirely whenever any mode (Flip, Presentation, Cursor, Call, Quick
Circle) was active, after hands-on testing found incidental head
movement during a mode's own gesture flow (most noticeably Flip mode's
swipes) produced spurious reactions. That suppression has been removed
— every signal below now fires the same whether idle or inside a mode,
matching how the Alt/Ctrl rules in `fusion.json` (§9.1) were always
written (`rules`, not `mode_rules` — mode-independent by design). Each
of the three remaining signals requires a held modifier key to do
anything (§9.1), which is what keeps incidental head movement from
misfiring in practice — the modifier itself is the noise filter.

The unbound signals this recognizer used to also detect and publish
(`CONFIRM`/nod, `EYEBROWS_DOWN`, `DOUBLE_EYEBROWS_UP`, `DOUBLE_BLINK`)
have been removed from the codebase — none had a `fusion.json` rule
consuming them, so they never did anything (see §9.1 for `DOUBLE_BLINK`'s
prior, since-removed screenshot binding).

| Signal | How it's detected | Status |
|---|---|---|
| `HEAD_TILT_LEFT` / `HEAD_TILT_RIGHT` | Head roll past `TILT_ENTER_DEGREES` (15°); must return within `TILT_EXIT_DEGREES` (8°) of neutral before firing again | Wired — §9.1 |
| `EYEBROWS_UP` | `browInnerUp` blendshape crossing the raise threshold (0.4), rising edge only | Wired — §9.1 (volume) |
| `MOUTH_OPEN` | `jawOpen` blendshape crossing 0.4, rising edge only (closing fires nothing) | Wired — §9.1 |

**Eyebrows/mouth thresholds were lowered 20% from their original
0.5/0.3 defaults** (`EYEBROWS_RAISE_THRESHOLD`/`MOUTH_OPEN_THRESHOLD`
0.5 → 0.4, `EYEBROWS_LOWER_THRESHOLD`/`MOUTH_CLOSE_THRESHOLD` 0.3 →
0.24) after hands-on calibration with `tests/face_calibration_
standalone_test.py` — the original values needed an unnaturally
exaggerated brow-raise/mouth-open to cross reliably. Head tilt's
`TILT_ENTER_DEGREES`/`TILT_EXIT_DEGREES` were left unchanged — only
these two blendshape-based signals needed the adjustment.

**Roll (used only for head tilt) is no longer read from the
transformation matrix.** It originally used the same rotation-matrix ->
Euler-angle decomposition as pitch/yaw, but that decomposition assumes
one specific Euler rotation order; MediaPipe's actual matrix convention
did not match it in practice, so the extracted roll came out coupled
with pitch/yaw instead of tracking a clean sideways tilt — no
`TILT_ENTER_DEGREES`/`TILT_EXIT_DEGREES` value behaved well against a
signal like that, confirmed by hands-on calibration testing.
`FaceRecognizer._compute_roll` now computes it directly from 2D image
geometry instead: the angle of the line between the two outer eye
corners (landmark indices 33 and 263). Upright, that line is
horizontal (roll ~ 0); tilting the head rotates it by exactly the
physical tilt angle, with no 3D matrix convention involved at all —
pure geometry, so this is the one signal here guaranteed to track
physical head tilt cleanly. Pitch and yaw still come from the matrix
and are shown in `--debug-face` (§9.2) for calibration, but neither
feeds a live signal any more now that nod/`CONFIRM` and shake/`CANCEL`
have both been removed (§11).

**Head tilt's left/right labeling WAS verified against a real camera,
and came out backwards.** Tilting the head to the subject's own right
produced a *negative* `roll` from the raw `atan2(delta_y, delta_x)`
geometry, which fired `HEAD_TILT_LEFT` instead of `HEAD_TILT_RIGHT` —
confirmed by hands-on testing (physical right tilt was switching to
the *previous* track, not the next one). `_compute_roll` now negates
the whole angle to correct this: `return -math.degrees(atan2(...))`.

**Do not "fix" a direction flip like this by swapping
`RIGHT_EYE_OUTER_CORNER`/`LEFT_EYE_OUTER_CORNER` instead** — that
negates *both* `delta_x` and `delta_y`, which rotates the angle by 180
degrees (`atan2(-y, -x) != -atan2(y, x)`), wrecking the roll ~ 0
upright baseline rather than just flipping which physical tilt reads
as positive vs negative. Negating the final returned angle is the only
correct way to mirror this signal. This is the same category of
unverified-mirroring caveat already documented for
`PointerOverlay.MIRROR_X` (§4) — computed from a formula, and now
actually confirmed (and corrected) against a live camera, unlike that
one.

### 9.1 The Alt/Ctrl face layer

Five global `rules` in `fusion.json` combine a held bare `alt`
(`ALT_KEY`) or `ctrl` (`CTRL_KEY`) with a specific `face_signal` (`rules`,
not `mode_rules` — see §1), and now genuinely fire regardless of mode —
`FaceRecognizer` no longer suppresses itself while a mode is active (§9):

| Held + face signal | Action |
|---|---|
| `alt` + `HEAD_TILT_RIGHT` | `NEXT_TRACK` |
| `alt` + `HEAD_TILT_LEFT` | `PREVIOUS_TRACK` |
| `alt` + `MOUTH_OPEN` | `MEDIA_PLAY_PAUSE` (same toggle as voice "start"/"stop"/"pause"/"reset", §5) |
| `alt` + `EYEBROWS_UP` | `VOLUME_UP` |
| `ctrl` + `EYEBROWS_UP` | `VOLUME_DOWN` |

`NEXT_TRACK`/`PREVIOUS_TRACK` post the real macOS system Next/Previous
media keys (`OSController.next_track`/`previous_track`) — the exact
same `NSEvent`/`Quartz` mechanism as `MEDIA_PLAY_PAUSE` (§5, now
factored into a shared `_post_system_media_key` helper taking an
`NX_KEYTYPE_*` constant), so it works with whichever player owns "now
playing", not tied to one specific app. `VOLUME_UP`/`VOLUME_DOWN` post
`NX_KEYTYPE_SOUND_UP`/`NX_KEYTYPE_SOUND_DOWN` through the same helper —
unlike the other two, these are handled directly by CoreAudio at the
system level and do **not** depend on any app registering as "Now
Playing", so they work regardless of what (if anything) is playing. One
eyebrow-raise = one volume tick (the same step a physical volume key
press does, ~6.25% of the range), not a continuous ramp —
`_check_eyebrows` is edge-triggered, so holding the eyebrows raised does
not repeat-fire it.

**"Reset" on mouth-open was interpreted as reusing the play/pause
toggle**, not a separate "restart current track" action — no system-
level API exists for the latter, and this reading matches the
mouth-open example's other stated half ("pause") using an already-
existing, already-documented action rather than inventing a new one.

**`DOUBLE_BLINK`'s screenshot trigger (`alt` + `DOUBLE_BLINK` →
`TAKE_SCREENSHOT`) and the unbound `CONFIRM`/`EYEBROWS_DOWN`/
`DOUBLE_EYEBROWS_UP` signals have all been removed** — none of the
latter three ever had a `fusion.json` rule consuming them, and
double-blink as a trigger was judged not worth keeping. `FaceRecognizer`
no longer detects any of the four; `TAKE_SCREENSHOT` has no remaining
trigger and was dropped from `ActionExecutor`'s command table too.

**Known limitation: system media keys don't reach video played
*through* an app that doesn't register as "Now Playing".** Confirmed in
practice with a YouTube video played inside Zoom (e.g. via its
screen-share "optimize for video clip" path, which renders through
Zoom's own engine rather than a real browser tab) — `NEXT_TRACK`/
`PREVIOUS_TRACK`/`MEDIA_PLAY_PAUSE` printed correctly in the console
(the pipeline and `OSController` both did their job) but had no effect,
because Zoom itself never told macOS it has a "Now Playing" session for
that content. A real physical hardware media key would face the
identical limitation — this is not something fixable from this app's
side. The same YouTube video played in a plain Safari/Chrome tab (which
*does* use the Media Session API) is the way to confirm the feature
itself works.

### 9.2 `--debug-face` calibration view

`src/processing/face/face_debug_view.py` — same role as
`GestureDebugView` (§2), for `FaceRecognizer`'s thresholds instead of
the hand. Subscribes to a new `face_debug` event (published every frame
by `FaceRecognizer._publish_debug`) carrying pitch/yaw/roll, `tilt_zone`,
and the raw `browInnerUp`/`jawOpen` blendshape scores alongside the
exact threshold constants each one is compared against.

Opened with `python src/main.py --debug-face`. Draws pitch/yaw/roll as
text, the current `tilt_zone` next to its enter/exit degrees, and one
progress bar per blendshape score with a red tick at the "enter"
threshold and a blue tick at the "exit" (hysteresis) threshold — the
bar visibly crossing a tick is the same moment the matching
`face_signal` fires in the console, which is what makes it useful for
tuning `TILT_ENTER_DEGREES`/`EYEBROWS_RAISE_THRESHOLD`/
`MOUTH_OPEN_THRESHOLD`/etc. against a specific face and camera instead
of guessing at the numbers from source alone. Like
`GestureDebugView`, rendering happens on the main thread only (`main
()`'s loop calls `render()`), since `cv2.imshow`/`cv2.waitKey` require
that on macOS; `_handle_debug` just stores the latest snapshot from
whichever thread published it.

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
- **Cinema mode automation** (Movie environment, `RUN_CINEMA_MODE`)
  requires a Shortcut authored once, named exactly **"Turn on cinema
  mode"**, that drives whatever Magic Home smart-light scene the user
  wants — same `shortcuts run <name>` mechanism as Do Not Disturb above.
- `PLAY_FOCUS_MUSIC`/`PAUSE_FOCUS_MUSIC` (resumes/pauses whatever
  Spotify was last on) remain wired into the command table but are no
  longer used by any environment — Study mode now opens Chrome window
  groups instead (§3.3). Spotify must still be installed if a rule is
  later added that calls them.
- **VS Code's `code` CLI** must be on `PATH` for `OPEN_VSCODE`.
- Third-party apps (Chrome, Slack, Discord, Telegram, Notion) must be
  installed for their `open_*` voice commands to do anything.
- **Microsoft Teams** installed, for Call mode's mic/camera/background-
  blur shortcuts (§2.4) to have an app actually listening for them —
  sending Cmd+Shift+M/O/P with Teams not running or not the app in the
  call does nothing useful.
- **`models/face_landmarker.task`** must be present for `FaceRecognizer`
  to start at all — verified present in this repo with the blendshapes
  and geometry-pipeline components needed for §9's blendshape/head-pose
  detection (not just bare landmarks).
- **`models/hand_landmarker.task`** must be present for `OffHandModel`
  (Cursor mode's off-hand tracking, §2.3.1) — verified present in this
  repo. Like the other two model files, a missing file raises at
  `GestureRecognizer` construction time (app startup), not a silent
  no-op — `OffHandModel` is built unconditionally in `__init__`, same as
  `GestureModel` and `FaceModel`.

---

## 11. What changed from the previous design (removed features)

This system has gone through several rounds of revision. Rather than a
single "before/after", here's the current, accurate state of what
exists and what was tried and dropped along the way:

- **Window Management existed briefly as the 4th mode, then was removed
  again** and replaced by Call mode (§2.4) — same `ctrl+shift+w` slot,
  same position as the Quick Command Circle's 4th destination (§2.5),
  different purpose entirely (mic/camera/call-audio/background-blur for
  Microsoft Teams instead of maximize/minimize/snap-left/snap-right). Its
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
- **Cursor mode now supports a second hand** (§2.3.1): an off-hand pinch,
  held, engages a 0.5x "precision mode" for fine cursor positioning and
  simultaneously arms zoom, whose amount then comes from the primary
  hand's own pinch distance (this design has since moved twice more —
  see §2.3.1 for its current, accurate description; treat the shape/
  distance details in this bullet as history, not current behavior).
  Tracked by a brand new, separate `OffHandModel`
  (`HandLandmarker`, landmarks only), not by giving the primary
  `GestureModel` `num_hands=2` — see the crash/fix bullet immediately
  below for why. Every existing single-hand check (motion tracking,
  pinch, static gestures) is completely untouched — the primary hand's
  model, options, and running mode are byte-for-byte what they were
  before this feature existed.
- **Fixed: `GestureModel` with `num_hands=2` crashed gesture recognition
  entirely once two hands appeared in frame together** —
  `RuntimeError: CalculatorGraph::Run() failed: ... "Packet isn't the
  sole owner of the holder"`, and every frame afterward failed
  identically (the graph does not self-recover). This was the two-hand
  Cursor mode's first implementation, briefly in this codebase's history
  — reverted to `num_hands=1` for `GestureModel`, off-hand tracking
  moved entirely to the separate `OffHandModel` described above. See
  §2.3.1 for the full explanation.
- **Alt+single-hand-pinch zoom was removed, replaced by two-hand
  fingertip-distance zoom, which was itself later replaced** by the
  off-hand-pinch-engages/primary-hand-pinch-drives design in §2.3.1 —
  and Alt came back a second time (as an alternative "or" alongside the
  off-hand pinch) before being removed again for good once Alt became
  the global face-layer modifier (§9.1), which it could no longer share
  cleanly. `GestureRecognizer._handle_keyboard_raw`/`alt_held` no longer
  exist; `_check_zoom` still does, it just never reads Alt.
- **A second, independent recognizer was added**: `FaceRecognizer`
  (§9), running in parallel with `GestureRecognizer` off the same
  camera frames, using `models/face_landmarker.task`. Originally
  published `CONFIRM`/`CANCEL`/`HEAD_TILT_LEFT`/`HEAD_TILT_RIGHT`/
  `EYEBROWS_UP`/`EYEBROWS_DOWN`/`MOUTH_OPEN`/`DOUBLE_BLINK` as a new
  `face` signal source, parallel to `voice`/`gesture`/`keyboard` —
  required a new `_handle_face` method in `CommandInterpreter` and a
  `face` section in `mapping.json`/`valid_signals`, but needed zero
  changes to `MultimodalFusion`, `TemporalSync`, or `SignalMapper`,
  which were already fully generic over signal source. `CANCEL` was
  later removed entirely (see below).
- **Shake detection (`CANCEL`) was removed entirely**, at the user's
  request — it had briefly ended up wired to `MEDIA_PLAY_PAUSE`
  (`face_cancel_pause` in `fusion.json`) despite the signal table
  above documenting it as "reserved, unbound," so an accidental head
  shake could unexpectedly pause whatever was playing with no
  indication of why. Removed: `FaceRecognizer`'s `SHAKE_*` constants,
  `shake_phase_sign`/`shake_phase_time`/`last_shake_time` state, and
  `_check_shake` (and, with it, yaw-velocity tracking — nod only ever
  needed pitch velocity); `CANCEL` from `mapping.json`'s `face`
  mapping and `valid_signals`; and the `face_cancel_pause` rule from
  `fusion.json`. Nod (`CONFIRM`) was left reserved, unbound at the time
  — later removed outright, see below. Raw `yaw` (the angle, not its
  velocity) is still computed and shown in `--debug-face` (§9.2) — only
  shake's use of it as a gesture trigger is gone.
- **Double-blink was reintroduced**, narrowly, as one of the Alt
  face-layer triggers (§9.1) — it had been explicitly removed from this
  system in an earlier round of design and was brought back for this
  one specific use, not restored as a general gesture. (Removed again
  since — see below.)
- **`CONFIRM` (nod), `EYEBROWS_DOWN`, `DOUBLE_EYEBROWS_UP`, and
  `DOUBLE_BLINK` were all removed**, at the user's request, along with
  the mode-idle suppression `FaceRecognizer` used to apply to itself —
  none of the four signals had ever done anything (no `fusion.json`
  rule consumed the first three; double-blink's one screenshot binding
  was judged not worth keeping either), and the remaining three signals
  (`HEAD_TILT_*`/`MOUTH_OPEN`/`EYEBROWS_UP`) are Alt/Ctrl-gated already,
  so the idle-only suppression was no longer earning its complexity.
  `TAKE_SCREENSHOT` was dropped from `ActionExecutor` too, having lost
  its only trigger. See §9/§9.1 for the current, smaller signal set.

---

## 12. Testing / verification guide

Cannot be fully automated headlessly — needs a real camera, microphone,
macOS desktop, and Accessibility permission. Run `python src/main.py`
(add `--debug-gesture` for a live gesture-calibration overlay, or
`--debug-face` for the equivalent head-pose/eyebrows/mouth overlay —
see §9.2) and manually verify:

- **Voice**: speak each app-opening phrase and each mode/environment
  trigger, confirm `[EXECUTOR] <ACTION>` prints and the effect happens.
  Also test the media phrases with something actually playing (Spotify,
  a YouTube tab, ...): "next track", "previous track", "pause", "reset",
  "start", "stop" — confirm each fires and that "pause"/"reset"/"stop"
  all just toggle play/pause (§5's documented single-toggle-key
  limitation), they do not restart the track.
- **Keyboard**: hold each mode-entry combo, including `ctrl+shift+t` for
  Try Mode. Confirm bare Right/Left arrows do **not** produce a
  `NEXT_SLIDE`/`PREVIOUS_SLIDE` `[EXECUTOR]` line even while in
  Presentation mode (see §2.1's note) — they should only visibly move the
  slide once, via whichever presentation app is focused, not twice.
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
  hold up one/two/three/four fingers in turn (thumb excluded from the
  count, held continuously for ~1.5s) — confirm each toggles
  mic/camera/call-audio/background-blur respectively. Confirm the same
  finger count does not toggle a second time without the hand leaving
  and re-entering the frame first, and that doing the same gesture in
  Flip or Presentation mode does nothing (gated at the source, §2.4).
- **Modes**: confirm Presentation/Flip/Cursor/Call are mutually
  exclusive and switching between them doesn't require going through
  "exit mode" first; confirm the Quick Command Circle only opens from
  idle (not while Flip mode's swipe session is active) and that swiping
  in each of the 4 directions enters the right mode and closes the
  circle.
- **Environments**: confirm entering one runs its full `enter_actions` in
  order, and switching directly to a different environment ends up
  cleanly in the new one, with none of the old one's state left behind.
- **"exit mode" scope**: enter an environment, then a mode, say "exit
  mode", confirm only the mode cleared and the environment's apps/DND
  state are untouched.
- **Try Mode** (§2.6): turn it on via voice, `ctrl+shift+t`, and the
  switch next to the camera preview in turn — confirm each updates the
  switch and the "● TRY MODE" indicator the same way. With it on, enter
  each mode in turn and trigger a command from each (a slide change, a
  scroll, an app-opening voice command, a Cursor-mode pinch) — confirm
  none of them produce any real effect on the computer, but `[TRY MODE]
  would execute: ...` prints for each and the camera preview's
  "Detected: ..." caption keeps updating live. Confirm "exit mode"/Esc
  turns Try Mode off too.
- **Face layer**: hold `alt` and tilt your head right/left — confirm
  next/previous track fires (and note which physical direction actually
  maps to which, per the unverified-labeling caveat in §9 — this was
  checked against a real camera and corrected once already, but re-verify
  after any further change to `_compute_roll`). A tilt is a sideways
  lean (ear toward shoulder) with the face still pointed at the camera —
  turning/rotating the head to look left or right is a different motion
  (yaw) and produces no signal at all (shake/`CANCEL` was removed); use
  `--debug-face` to watch `roll` vs `yaw` live if it's unclear which one
  a given movement produced. Open your mouth — confirm play/pause. Hold
  `alt` and raise your eyebrows once — confirm the volume goes up one
  tick; hold `ctrl` and raise your eyebrows once — confirm it goes down
  one tick instead. Release `alt`/`ctrl` and repeat — confirm nothing
  fires without one of them held. Repeat all of the above while a mode
  (Flip/Presentation/Cursor/Call) is active — confirm it fires exactly
  the same way as from idle (§9's suppression was removed; this is the
  regression check for that).
- **Media keys vs. an app that doesn't register "Now Playing"**: if
  next/previous/play-pause print correctly in the console
  (`[EXECUTOR] NEXT_TRACK`, etc.) but nothing happens to the actual
  video, first confirm the video is playing in a real Safari/Chrome tab,
  not embedded in another app (Zoom's screen-share "optimize for video
  clip" path was confirmed to swallow these keys with no error at all —
  see §9.1). If it works in a plain browser tab but not elsewhere,
  that's this limitation, not a bug in this app.
- **`--debug-face` calibration**: run with the flag, confirm a "Face
  Debug" window opens showing live pitch/yaw/roll and a bar per
  blendshape (eyebrows/mouth) with red/blue tick marks at the
  enter/exit thresholds. Tilt your head until `tilt_zone` flips to
  `left`/`right` at roughly `TILT_ENTER_DEGREES`; raise your eyebrows
  and confirm the bar crosses the red tick at the same moment
  `EYEBROWS_UP` prints in the console. If a threshold fires too early/
  late/not at all for your face and lighting, adjust the matching
  constant in `FaceRecognizer` (`TILT_ENTER_DEGREES`,
  `EYEBROWS_RAISE_THRESHOLD`, `MOUTH_OPEN_THRESHOLD`, etc.) and re-run.

Visual-inspection-only: laser pointer / Cursor-mode cursor position
accuracy and mirroring direction, the Quick Command Circle's on-screen
appearance, Flip mode's left/right Space-switch (`Ctrl+Right`/
`Ctrl+Left`, now unconditional — see §2.2), precision-mode's cursor
slowdown feel.
