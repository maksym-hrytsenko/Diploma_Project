# External Gesture Usability Study

A moderated usability study with **5 external participants**, run outside
the development team, to close a gap the automated and self-run testing in
[`TESTING_REGRESSION.md`](TESTING_REGRESSION.md),
[`TESTING_MANUAL_FUNCTIONAL.md`](TESTING_MANUAL_FUNCTIONAL.md), and
[`TESTING_STRESS.md`](TESTING_STRESS.md) cannot close on its own: every
scenario in those three documents was performed by the developer. This
study instead asks people who have never seen the system before to operate
it, and records how *they* rate the experience.

For a related but separate study — whether first-time users can read and
navigate the graphical interface itself, independent of gesture
recognition — see [`TESTING_UI_COMPREHENSION.md`](TESTING_UI_COMPREHENSION.md)
(designed, not yet executed).

The study is scoped to **gestures only** (hand gestures and the always-on
face layer), not voice. Gesture recognition is the more subjective, more
person-dependent half of the system — everyone's hands move differently
and everyone reads "make a fist" or "point up" slightly differently — so it
is the half where independent, external data matters most. Voice-command
accuracy is already covered quantitatively by the live sessions described
in [`TESTING_MANUAL_FUNCTIONAL.md`](TESTING_MANUAL_FUNCTIONAL.md). For the
underlying gesture-to-action mapping being tested here, see
[`SYSTEM_FUNCTIONS.md`](SYSTEM_FUNCTIONS.md), section `GESTURES` and
`MODE: CURSOR`, and its manually-run counterpart in
[`../tests/MANUAL_TEST_SCENARIOS.md`](../tests/MANUAL_TEST_SCENARIOS.md#2-gestures).

**Consent.** Written informed consent was obtained from all 5 participants
before their session, covering the format described below (a single
self-paced page combining the task list, a per-task self-rating, and a
post-task questionnaire). Participants were also told in advance, and
agreed, that if any part of a task's description turned out not to match
what they actually experienced, it would be corrected afterward rather than
left as-is.

### 1. Participants and session format

- **n = 5**, individual sessions, moderated in person on the researcher's
  own Mac (permissions and installation already granted beforehand, so no
  session time is spent on onboarding).
- Each session ran the same single-page instrument end to end: a short
  spoken introduction, then the 30-task protocol (§3) with an immediate
  self-rating after every task.
- Sessions were conducted in Russian, since that was the shared language
  between moderator and participants; the on-screen gesture/mode names
  themselves stay in English, matching what the app itself displays (e.g.
  "Cursor mode", "Flip mode").
- Typical session length: roughly 15–20 minutes.

**Participants.** All 5 participants were aged 22–28, right-handed, and had
no prior experience operating a gesture- or voice-controlled system.

| # | Age range | Handedness | Prior experience with gesture/voice control |
|---|---|---|---|
| P1 | 22–28 | Right | None |
| P2 | 22–28 | Right | None |
| P3 | 22–28 | Right | None |
| P4 | 22–28 | Right | None |
| P5 | 22–28 | Right | None |

### 2. Self-rating scale

Unlike the correct/partially-correct/incorrect scale used for
developer-run tests in `MANUAL_TEST_SCENARIOS.md`, each task here is graded
by the **participant**, not the moderator, immediately after performing it,
on a 4-point ease-of-use scale:

| Score | Meaning |
|---|---|
| 1 | Didn't work at all |
| 2 | Worked, but with difficulty / took several tries |
| 3 | Worked easily, one or two tries |
| 4 | Instant, felt completely natural |

The first task in every group below is explained step by step; later tasks
in the same group are deliberately brief. A participant still succeeding on
the brief version is itself a signal that the gesture was *learned*, not
just followed along with — the group-level average in §4 should be read
with that in mind.

### 3. Task protocol (10 groups, 30 tasks)

#### A. Quick Circle — entering the 4 modes

| # | Task | Expected result |
|---|---|---|
| 1 | Make a fist in front of the camera, then open it into a flat palm — a circular menu (Quick Circle) appears. While still holding your palm open, swipe your hand upward. (To leave any mode afterwards, press `Esc`.) | The ring appears, then Flip mode activates |
| 2 | Press `Esc` to exit, then the same gesture (fist → palm), swipe down | Cursor mode activates |
| 3 | Exit again, same gesture, swipe left | Presentation mode activates |
| 4 | Exit again, same gesture, swipe right | Call mode activates |
| 5 | This time, *without* exiting, try the fist → palm gesture again | Nothing happens — Quick Circle only opens when no mode is already active |

#### B. Cursor mode — pointing & click

| # | Task | Expected result |
|---|---|---|
| 6 | Enter Cursor mode. Point one finger up and move your hand — the cursor should follow. Now touch your thumb and index finger together and release quickly (a pinch) — that's a click | Cursor follows the finger; the pinch registers as a click |
| 7 | Do that same pinch twice, quickly, in a row | Registers as a right-click, not two separate clicks |

#### C. Cursor mode — pinch-and-drag scroll

| # | Task | Expected result |
|---|---|---|
| 8 | Instead of releasing the pinch right away, hold it and drag your hand | The content scrolls, following the drag direction |

#### D. Cursor mode — off-hand precision & zoom (two hands)

| # | Task | Expected result |
|---|---|---|
| 9 | Keep pointing with your main hand. With your *other* hand, pinch your thumb and index finger together and hold it | The cursor visibly slows down — fine positioning ("precision mode") |
| 10 | Release that off-hand pinch, opening the hand | The cursor snaps back to your pointing finger's exact current position |
| 11 | With that hand now open (not pinched), move your two index fingertips apart from each other | The screen zooms in |
| 12 | Bring your two index fingertips back together | The screen zooms out |

Zoom is driven by the **distance between the two index fingertips**, not
by the distance between the hands as a whole, and requires the off-hand to
be **open**, not pinched — pinched drives precision mode instead. See
[`../tests/MANUAL_TEST_SCENARIOS.md` §2.5](../tests/MANUAL_TEST_SCENARIOS.md#25-cursor-mode--off-hand-precision-and-zoom).

#### E. Flip mode — directional swipe

| # | Task | Expected result |
|---|---|---|
| 13 | Make sure you're in Flip mode. While already inside it, do the fist → palm swipe gesture again — this time it doesn't change mode, it acts inside it. Swipe upward | Content scrolls to reveal later content |
| 14 | Same gesture, swipe downward | Scrolls to reveal earlier content |
| 15 | Same gesture, swipe left | Switches to the next virtual desktop (Space) |
| 16 | Same gesture, swipe right | Switches to the previous virtual desktop (Space) |

#### F. Flip mode — resetting the gesture

| # | Task | Expected result |
|---|---|---|
| 17 | Still in Flip mode: close your fist, then open your palm again, without swiping anywhere this time | Nothing changes mode — it just arms a new swipe gesture (Quick Circle does not reopen, since a mode is already active) |

#### G. Presentation mode — laser pointer

| # | Task | Expected result |
|---|---|---|
| 18 | Enter Presentation mode. Point one finger up and hold it steady | A laser-pointer dot appears at the center of the screen; small hand movements sweep it across the whole screen |

#### H. Presentation mode — slide navigation

| # | Task | Expected result |
|---|---|---|
| 19 | Still in Presentation mode: make a closed fist (don't open your palm this time) and just move your wrist sideways, to the right | Advances to the next slide |
| 20 | Same closed-fist wrist motion, to the left | Goes back to the previous slide |

#### I. Call mode — finger-count toggles

| # | Task | Expected result |
|---|---|---|
| 21 | Enter Call mode. Hold up one finger for a couple of seconds | Toggles the microphone |
| 22 | Now two fingers, held | Toggles the camera |
| 23 | Now three fingers, held | Toggles call audio |
| 24 | Now four fingers, held | Toggles background blur |
| 25 | Show one finger again to toggle the microphone back — then, *without* lowering your hand out of frame, show one finger again | Nothing happens the second time (it's locked); only moving your hand out of the camera's view and back in re-arms it |

#### J. Face layer — works in any mode, no hands needed

| # | Task | Expected result |
|---|---|---|
| 26 | Hold down the `Alt` key with your other hand, and tilt your head to the right. This works in any mode, using your face instead of your hands | Skips to the next media track |
| 27 | Still holding `Alt`, tilt your head to the left | Goes back to the previous track |
| 28 | Still holding `Alt`, open your mouth | Toggles play/pause |
| 29 | Still holding `Alt`, raise your eyebrows | Volume goes up one tick |
| 30 | Hold `Ctrl` instead of `Alt`, and raise your eyebrows again | Volume goes down one tick |

### 4. Results

All 5 sessions have been run; the SUS questionnaire was not used for this
round, only the per-task self-rating.

#### Raw self-ratings (1–4)

| # | P1 | P2 | P3 | P4 | P5 |
|---|---|---|---|---|---|
| 1 | 3 | 2 | 3 | 2 | 3 |
| 2 | 4 | 3 | 3 | 3 | 4 |
| 3 | 3 | 4 | 3 | 4 | 3 |
| 4 | 3 | 4 | 3 | 4 | 4 |
| 5 | 4 | 4 | 3 | 4 | 4 |
| 6 | 4 | 3 | 3 | 2 | 3 |
| 7 | 3 | 3 | 3 | 3 | 3 |
| 8 | 4 | 3 | 3 | 4 | 4 |
| 9 | 3 | 2 | 3 | 3 | 4 |
| 10 | 3 | 3 | 4 | 3 | 3 |
| 11 | 4 | 4 | 4 | 4 | 3 |
| 12 | 4 | 4 | 3 | 4 | 3 |
| 13 | 3 | 3 | 4 | 3 | 3 |
| 14 | 4 | 3 | 3 | 4 | 4 |
| 15 | 2 | 3 | 4 | 4 | 3 |
| 16 | 3 | 3 | 4 | 4 | 3 |
| 17 | 4 | 4 | 3 | 3 | 4 |
| 18 | 4 | 4 | 3 | 4 | 4 |
| 19 | 4 | 4 | 3 | 3 | 4 |
| 20 | 4 | 4 | 4 | 4 | 4 |
| 21 | 4 | 4 | 4 | 4 | 4 |
| 22 | 4 | 4 | 4 | 4 | 4 |
| 23 | 4 | 4 | 4 | 4 | 4 |
| 24 | 4 | 4 | 4 | 3 | 4 |
| 25 | 4 | 4 | 3 | 4 | 4 |
| 26 | 4 | 4 | 3 | 4 | 4 |
| 27 | 4 | 4 | 4 | 4 | 4 |
| 28 | 4 | 4 | 4 | 4 | 4 |
| 29 | 3 | 4 | 4 | 4 | 4 |
| 30 | 4 | 4 | 4 | 4 | 4 |

Per-participant overall average: P1 3.63 · P2 3.57 · P3 3.47 · P4 3.60 ·
P5 3.67. **Overall average across all 150 ratings: 3.59 / 4.**

#### Per-group average

| Group | n (ratings) | Avg (1–4) |
|---|---|---|
| A. Quick Circle | 25 | 3.36 |
| B. Cursor pointing & click | 10 | **3.00** |
| C. Pinch-drag scroll | 5 | 3.60 |
| D. Off-hand precision & zoom | 20 | 3.40 |
| E. Flip directional swipe | 20 | 3.35 |
| F. Flip gesture reset | 5 | 3.60 |
| G. Presentation laser pointer | 5 | 3.80 |
| H. Presentation slide navigation | 10 | 3.80 |
| I. Call mode toggles | 25 | 3.92 |
| J. Face layer | 25 | 3.92 |

#### Interpretation

The pre-registered hypothesis in §2 — that the two-handed group D
(off-hand precision & zoom) would rate lowest, since independent
two-hand coordination varies the most between people — **was not borne
out**: group D averaged 3.40, above two other groups. The lowest-rated
group is instead **B, Cursor mode pointing & click (3.00)** — the single
most basic interaction in the protocol (point, then pinch to click),
scoring below even the explicitly two-handed tasks. Group E (Flip
directional swipe, 3.35) is a close second-lowest. The highest-rated
groups are I (Call mode finger-count toggles) and J (face layer), both at
3.92 — both are held-gesture toggles rather than continuous tracking,
which may explain why they read as more reliable to a first-time user than
anything requiring sustained fine motor control (pointing, swiping).

No qualitative notes from the sessions (the open-ended questions originally
in the protocol) were collected for this round, so the reasons behind
group B's low score are not established here — only that it is the
weakest point across all 5 participants and groups.

With n = 5 this is an indicative, not a statistically representative,
result — that sample size is the accepted norm for uncovering most
usability issues in a study of this kind (Nielsen), which is sufficient for
the purpose here.

---

## Part 2 — UI Comprehension Study

The graphical interface was built as an additional, supportive layer on
top of the gesture/voice/face control system, not one of the core
interaction modalities validated in Part 1 — see
[`UI_SPEC.txt`](UI_SPEC.txt) §10, "Final UI decisions." Whether it was
worth building it, though, depends on whether it's actually legible to
someone who has never seen it before. This part is scoped narrowly to
that: can a first-time viewer, given a plain-language instruction, find
the right control quickly — independent of whether they can perform the
hand/face gestures tested in Part 1.

### 1. Goal and methodology

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

### 2. Materials

A static image (or a clickable prototype built from it) of the Main
Control Panel, matching [`UI_SPEC.txt`](UI_SPEC.txt) exactly — window
1440×900, the header panel, camera preview panel, circular control wheel,
and bottom status panel with its two extra buttons. Using the specified
layout directly means every control's correct hit region is already known
precisely (`UI_SPEC.txt` gives x/y/width/height for each element), so a
participant's click coordinates can be scored as correct/incorrect without
guesswork.

### 3. Scenarios (12 tasks)

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

### 4. Status

**Not yet executed.** The scenarios above are a designed, ready-to-run
protocol — no sessions have been held, so this part has no results section
yet. Unlike Part 1, running it needs no gesture-tracking hardware or even
the live app: a printed or on-screen static image of the Main Control
Panel and a stopwatch are enough.
