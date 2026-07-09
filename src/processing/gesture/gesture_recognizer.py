import math
import time

from processing.gesture.gesture_model import (
    GestureModel,
    OffHandModel
)


class GestureRecognizer:

    # Off-hand pinch ("precision mode", Cursor mode only) scales
    # cursor movement down to this fraction of the raw hand
    # movement, like a DPI switch on a physical mouse.
    PRECISION_SCALE = 0.5

    # Fraction of the camera frame trimmed from each edge before
    # mapping the fingertip position to the screen. MediaPipe's
    # hand tracking gets unreliable right at the true edges of
    # the frame, so without this the user could never
    # comfortably reach the screen's edges either — trimming the
    # margin and stretching what remains to the full 0..1 range
    # means getting close to (not exactly at) the frame's edge
    # already reaches the screen's edge.
    ACTIVE_ZONE_MARGIN = 0.1

    # Below this normalized distance between two detected
    # wrists, OffHandModel's result is treated as re-detecting
    # the SAME physical hand GestureModel already found as
    # primary, not a genuine second hand.
    SAME_HAND_DISTANCE = 0.15

    # The only two modes that ever interpret HAND_LEFT/RIGHT/
    # UP/DOWN swipes: Flip mode uses them directly, Quick
    # Circle uses them to pick a mode. Every other mode (or no
    # mode at all) has no rule that reacts to a swipe signal —
    # see _handle_mode_changed for why the tracking session is
    # force-ended on transitioning into any mode outside this
    # set.
    SWIPE_MODES = {"flip", "quick_circle"}

    # The three Call-mode gestures that toggle persistent state
    # (mic mute/unmute, camera on/off) rather than firing a
    # momentary one-shot action like OK_SIGN (raise hand).
    # Shared by the mode gate, the hold-to-confirm requirement,
    # and the per-gesture lock, all in _publish_static_gesture —
    # see call_toggle_hold_seconds and locked_toggle_gestures in
    # __init__.
    CALL_TOGGLE_GESTURES = ("Thumb_Up", "Thumb_Down", "Victory")

    def __init__(self, event_bus):

        self.event_bus = event_bus

        self.gesture_model = GestureModel()

        # Off-hand tracking (Cursor mode's precision/zoom, see
        # §2.3.1 in docs) deliberately uses a second, separate
        # model — HandLandmarker, landmarks-only, no gesture
        # classification — rather than asking GestureModel
        # itself to track two hands. GestureRecognizer (the
        # MediaPipe task) has a confirmed bug where num_hands>1
        # combined with VIDEO running mode corrupts its
        # internal tensor-concatenation calculator the first
        # time two hands are actually in frame together, and
        # the graph never recovers — every frame after that
        # fails identically, killing gesture recognition
        # entirely. See GestureModel's own comment for the
        # full explanation.
        self.off_hand_model = OffHandModel()

        # Last confidently observed static gesture. Used
        # both to avoid re-publishing the same gesture and
        # to detect Closed_Fist <-> Open_Palm transitions
        # that start/stop motion tracking.
        self.last_gesture = None

        self.confidence_threshold = 0.7

        # ---------------------------------
        # Gesture Debounce
        # ---------------------------------

        # A gesture must hold for this many consecutive
        # frames before it is trusted. A single
        # misclassified frame (motion blur, odd angle)
        # would otherwise end and immediately restart a
        # session, re-anchoring the point to wherever the
        # finger happens to be at that moment.
        self.confirm_frames = 4

        self.candidate_gesture = None
        self.candidate_count = 0

        # When the current candidate_gesture started being
        # seen, even before it crossed confirm_frames. Used by
        # the Call-mode toggle gestures (Thumb_Up/Thumb_Down/
        # Victory) to require a real, continuous hold — see
        # call_toggle_hold_seconds — on top of this debounce,
        # which by itself only filters single-frame noise.
        self.candidate_start_time = None

        # ---------------------------------
        # Hand-Lost Grace Period
        # ---------------------------------

        # How many consecutive frames the hand may be
        # undetected before the session actually ends. Fast
        # finger movement causes motion blur, which
        # regularly makes MediaPipe miss the hand for a
        # frame or two even though it never left the
        # camera.
        self.hand_lost_frames = 5

        self.hand_lost_count = 0

        # ---------------------------------
        # Motion Tracking Session
        # ---------------------------------

        # True between a Closed_Fist -> Open_Palm
        # transition and the matching Open_Palm ->
        # Closed_Fist transition (or the hand leaving the
        # frame for hand_lost_frames straight frames). The
        # hand does NOT need to stay open the whole time
        # once a session starts.
        self.tracking_active = False

        # Marker position. Follows the finger live and
        # freezes briefly at the trigger point right after
        # a swipe fires.
        self.anchor_x = None
        self.anchor_y = None

        self.freeze_until = 0

        self.freeze_duration = 0.3

        # Previous frame's fingertip position, used only to
        # compute instantaneous speed (velocity).
        self.previous_x = None
        self.previous_y = None
        self.previous_time = None

        # Latest frame-to-frame velocity, published in the
        # debug snapshot so a viewer can show exactly the
        # vector the decision was based on.
        self.velocity_x = None
        self.velocity_y = None

        self.last_signal = None

        # Minimum speed (per second, normalized coordinates)
        # for a frame-to-frame movement to count as a
        # deliberate swipe. This is the PRIMARY signal —
        # direction is decided by how fast the finger is
        # moving, not by distance from a fixed point.
        self.velocity_threshold = 1.8

        # Per-frame movement below this is treated as
        # landmark jitter, even if it briefly spikes the
        # velocity reading (a tiny distance over a tiny
        # time can look "fast").
        self.min_frame_distance = 0.015

        # The velocity vector counts as UP/DOWN only within
        # this many degrees of straight vertical. Everything
        # else, including diagonals, counts as LEFT/RIGHT.
        self.vertical_cone_degrees = 25

        # Cooldown
        self.last_motion_time = 0

        self.motion_cooldown = 0.5

        # ---------------------------------
        # Pinch / Hold-and-Drag Geometry
        # ---------------------------------

        # Distance (normalized coordinates) between thumb
        # tip and index tip below which the two fingers
        # count as "touching" — a pinch. Also reused as-is by
        # Call mode's OK-sign check (same thumb/index-touch
        # geometry, different meaning depending on which mode
        # is active — the two never run in the same mode).
        self.pinch_distance_threshold = 0.06

        # A pinch held/moved past either of these
        # thresholds stops being a quick tap (click) and
        # becomes a hold-and-drag (scroll) instead.
        self.drag_activation_seconds = 0.15
        self.drag_activation_distance = 0.03

        self.is_pinching = False
        self.is_dragging = False

        self.pinch_start_time = 0
        self.pinch_start_x = None
        self.pinch_start_y = None
        self.pinch_previous_x = None
        self.pinch_previous_y = None

        # A completed quick tap is not published as PINCH
        # right away — it waits up to double_pinch_window to
        # see whether a second tap follows, in which case the
        # pair is published as one DOUBLE_PINCH (right-click)
        # instead of two separate PINCH (click) signals.
        self.pending_single_pinch = False
        self.pending_pinch_time = 0
        self.double_pinch_window = 0.3

        # ---------------------------------
        # OK-Sign (Call Mode: raise hand)
        # ---------------------------------

        # MediaPipe's bundled gesture classifier has no "OK"
        # category (confirmed against the model's own
        # labels.txt — only None/Closed_Fist/Open_Palm/
        # Pointing_Up/Thumb_Down/Thumb_Up/Victory/ILoveYou
        # exist), so this is computed the same way PINCH is —
        # directly from thumb/index landmark distance — rather
        # than relying on a classifier category that will never
        # actually fire. Edge-triggered: fires once when the
        # fingers first touch, not again until they separate.
        self.ok_touching = False

        # Once touching, the fingers must separate past this
        # WIDER distance — not just back past
        # pinch_distance_threshold — before being considered
        # released. Unlike the classifier gestures, OK-sign has
        # no confirm_frames debounce (it can't — there is no
        # classifier category to debounce, see above), so without
        # this hysteresis gap, landmark jitter sitting right at a
        # single threshold flickers touching/not-touching frame
        # to frame, each flicker re-arming and re-firing OK_SIGN
        # in an unbroken burst instead of once per deliberate
        # touch-and-release.
        self.ok_sign_release_distance = (
            self.pinch_distance_threshold * 1.6
        )

        # Hard floor between two OK_SIGN firings, regardless of
        # finger state — a safety net under the hysteresis above
        # for jitter that plays out slower than a single-frame
        # flicker.
        self.ok_sign_cooldown = 0.6

        self.last_ok_sign_time = 0

        # ---------------------------------
        # Call Mode Toggle Gestures
        # (Thumb_Up / Thumb_Down / Victory)
        # ---------------------------------

        # Thumb_Up (unmute) and Thumb_Down (mute) send the
        # identical OS-level toggle keystroke (see
        # OSController.mute_mic/unmute_mic) rather than a
        # distinct "set muted"/"set unmuted" call, so firing
        # either one an extra time flips the mic the wrong way,
        # not just redundantly. Once a toggle gesture fires, that
        # SAME gesture name is ignored until the hand actually
        # leaves the frame (see _handle_hand_lost) and is
        # reacquired. Unlike last_gesture, this is NOT cleared by
        # seeing some other gesture in between — a gesture stays
        # in this set specifically so the classifier flickering
        # off it to something else and back, without the hand
        # ever leaving the frame, can't fire it a second time on
        # what is physically still the same held-up gesture.
        # Tracked per gesture name (not one shared flag) so, e.g.,
        # a locked Thumb_Down does not also block Thumb_Up.
        self.locked_toggle_gestures = set()

        # How long (seconds) one of these three gestures must be
        # held continuously — since it was first seen, not just
        # since it crossed confirm_frames — before it is trusted
        # enough to fire. These toggle mic/camera state, so a
        # fast or incidental gesture should not be enough to flip
        # them the way it's fine for, say, a swipe. OK_SIGN
        # (raise hand) is a momentary, repeatable notification,
        # not a toggle, so it is not held to this standard.
        self.call_toggle_hold_seconds = 1.5

        # ---------------------------------
        # Two-Hand Cursor Mode (off-hand)
        # ---------------------------------

        # True while an off-hand pinch is held during Cursor
        # mode — see _update_pointer.
        self.precision_active = False

        self.precision_anchor_x = None
        self.precision_anchor_y = None

        # ---------------------------------
        # Zoom (off-hand pinch)
        # ---------------------------------

        # Zoom used to also be engageable by holding Alt on the
        # keyboard, as a one-handed substitute for the off-hand
        # pinch. Removed once Alt became the global face-layer
        # modifier (§9.1 in docs/SYSTEM_FUNCTIONS.md) — holding
        # Alt for zoom would simultaneously arm HEAD_TILT/
        # MOUTH_OPEN/EYEBROWS_UP actions (track switching, pause,
        # volume, screenshot), firing alongside whatever zoom
        # gesture was in progress. Zoom is off-hand-pinch-only
        # now, confirmed by testing to be the only unambiguous
        # option: it uses two hands, not one, so it shares no
        # gesture or modifier with anything Alt now means.

        # Baseline thumb/index distance for zoom (see
        # _check_zoom) — reset whenever zoom disengages, so
        # re-engaging always starts from a fresh baseline
        # instead of a potentially large stale delta.
        self.zoom_previous_distance = None

        # ---------------------------------
        # Mirrored from SignalMapper's "mode_changed" event.
        # A deliberate, narrow exception to this class
        # otherwise staying mode-agnostic: a handful of checks
        # below (PINCH, OK-sign, Thumb_Up/Thumb_Down/Victory,
        # off-hand precision/zoom) only mean something in one
        # specific mode each, and are gated at the source so a
        # pose that happens to pass through during an unrelated
        # mode never gets detected or published as noise.
        self.active_mode = None

        # Tracks only whether the debug "[GESTURE] Hand
        # detected"/"Hand lost" transition print already fired
        # for the current state, so it prints once per
        # transition instead of spamming every frame — visible
        # confirmation that the camera/MediaPipe pipeline is
        # actually seeing a hand at all, independent of
        # whether any particular gesture gets recognized.
        self.hand_was_present = False

        # Tracks the last reported off-hand search outcome
        # ("none" / "same_hand" / "found"), purely so
        # _report_off_hand_state prints only on a transition
        # instead of spamming every qualifying frame — same
        # idea as hand_was_present above.
        self.off_hand_debug_state = None

    def start(self):

        self.event_bus.subscribe(
            "camera_frame",
            self._handle_frame
        )

        self.event_bus.subscribe(
            "mode_changed",
            self._handle_mode_changed
        )

    def stop(self):

        self.event_bus.unsubscribe(
            "camera_frame",
            self._handle_frame
        )

        self.event_bus.unsubscribe(
            "mode_changed",
            self._handle_mode_changed
        )

    def _handle_mode_changed(self, event):

        self.active_mode = event.get(
            "data",
            {}
        ).get("mode")

        # Leaving Cursor mode mid-window would otherwise let
        # a deferred single tap fire once the mode is
        # re-entered later, long after the user actually
        # pinched. Same idea for precision mode and the zoom
        # baseline — neither should carry over into a new
        # Cursor mode session.
        if self.active_mode != "cursor":

            self.pending_single_pinch = False

            self.precision_active = False

            self.zoom_previous_distance = None

        if self.active_mode != "call":

            self.ok_touching = False

            self.locked_toggle_gestures = set()

        # A swipe session started to pick a mode via Quick
        # Circle (or one already in progress in Flip mode) has
        # no further reason to keep running once the resulting
        # mode isn't one that interprets swipes at all —
        # without this, residual hand motion right after
        # landing in, say, Call mode kept computing velocity
        # and could still fire HAND_LEFT/RIGHT/UP/DOWN signals
        # that reach SignalMapper only to match no rule there,
        # pure noise. Ending the session here means a fresh
        # Closed_Fist -> Open_Palm is required before any
        # further swipe is interpreted, exactly as if the hand
        # had been lost and reacquired.
        if self.active_mode not in self.SWIPE_MODES:

            self._end_session()

    def _handle_frame(self, event):

        frame = event.get("data")

        if frame is None:
            return

        # ---------------------------------
        # Process Frame
        # ---------------------------------

        # GestureModel wraps a real MediaPipe task — a
        # transient internal failure here must not be able to
        # take down frame processing beyond the one frame it
        # happened on (see the num_hands>1 crash history in
        # docs/SYSTEM_FUNCTIONS.md §2.3.1 for why this
        # precaution exists).
        try:

            result = self.gesture_model.process_frame(
                frame
            )

        except Exception as e:

            print(
                f"[GESTURE MODEL ERROR] {e}"
            )

            return

        if result is None:
            return

        gesture_name, confidence = self._read_gesture(
            result
        )

        # ---------------------------------
        # Hand Lost
        # ---------------------------------

        if not result.hand_landmarks:

            if self.hand_was_present:

                print(
                    "[GESTURE] Hand lost"
                )

                self.hand_was_present = False

            self._handle_hand_lost(
                frame,
                gesture_name,
                confidence
            )

            return

        if not self.hand_was_present:

            print(
                "[GESTURE] Hand detected"
            )

            self.hand_was_present = True

        self.hand_lost_count = 0

        # Only a gesture held for confirm_frames straight
        # frames is trusted for session start/end — the
        # raw, possibly noisy gesture_name is still used
        # below for pointer tracking and the debug overlay
        confirmed_gesture = self._confirm_gesture(
            gesture_name
        )

        # Swipe/motion tracking only ever means anything from
        # idle (no mode — Quick Circle's own HAND_SESSION_START
        # trigger only ever matches from there, see
        # SignalMapper._mode_trigger_matches) or while already
        # inside Flip mode or Quick Circle (see SWIPE_MODES) —
        # gated at the source so a Closed_Fist -> Open_Palm
        # toggle in, say, Cursor mode never starts a session
        # that has no mode to end it (SignalMapper already
        # refuses to let a gesture-sourced trigger re-enter a
        # mode from inside another one, so such a session would
        # otherwise run unbounded until the mode actually
        # changes).
        if (
            self.active_mode is None
            or self.active_mode in self.SWIPE_MODES
        ):

            self._update_session(
                confirmed_gesture
            )

            self._check_motion(
                result
            )

        # A second hand only ever means anything in Cursor
        # mode — resolved to None everywhere else, and always
        # run through a separate model from the primary hand
        # (see OffHandModel / __init__ for why). Searched
        # regardless of what the primary hand is currently
        # doing (pointing, pinching to click, or pinching to
        # drive zoom) since an off-hand pinch must keep being
        # detected for as long as it's held, including the
        # whole time it's engaging zoom — by then the primary
        # hand is deliberately NOT doing Pointing_Up, so gating
        # this on the primary hand's own gesture would drop the
        # off-hand mid-zoom. The whole block is wrapped
        # defensively: OffHandModel is a
        # second, independent MediaPipe task running alongside
        # GestureModel every frame, and any failure in it must
        # never be able to block the primary hand's own
        # gesture/pointer publishing below — that already
        # happened once (see docs/SYSTEM_FUNCTIONS.md §2.3.1's
        # crash/fix history) and this is the second, defensive
        # layer against a repeat.
        off_hand_landmarks = None

        if self.active_mode == "cursor":

            try:

                off_hand_landmarks = self._find_off_hand(
                    frame,
                    result.hand_landmarks[0]
                )

            except Exception as e:

                print(
                    f"[OFF-HAND ERROR] {e}"
                )

                off_hand_landmarks = None

        try:

            off_hand_pinching = self._check_off_hand(
                off_hand_landmarks
            )

        except Exception as e:

            print(
                f"[OFF-HAND ERROR] {e}"
            )

            off_hand_pinching = False

        # Zoom (off-hand pinch) and PINCH (click / drag-to-
        # scroll) only ever mean anything in Cursor mode, and
        # are mutually exclusive on the same physical gesture —
        # while zoom is engaged, the primary hand's own
        # thumb/index distance drives zoom instead of a click or
        # drag.
        if self.active_mode == "cursor":

            zoom_engaged = off_hand_pinching

            self._check_zoom(
                result,
                zoom_engaged
            )

            if not zoom_engaged:

                self._check_pinch(
                    result
                )

            elif self.is_pinching or self.pending_single_pinch:

                # Zoom just engaged mid-click/drag — abandon
                # it cleanly instead of leaving stale state
                # around that would otherwise fire a stray
                # click once zoom disengages.
                self.is_pinching = False
                self.is_dragging = False

                self.pending_single_pinch = False

        # OK-sign (raise hand) only means anything in Call
        # mode.
        if self.active_mode == "call":

            self._check_ok_sign(
                result
            )

        self._update_pointer(
            gesture_name,
            result,
            off_hand_pinching
        )

        self._publish_static_gesture(
            confirmed_gesture,
            confidence
        )

        index_tip = result.hand_landmarks[0][8]

        self._publish_debug(
            frame,
            (index_tip.x, index_tip.y),
            gesture_name,
            confidence
        )

    # ---------------------------------
    # Off-Hand Resolution
    # ---------------------------------

    # Runs a completely separate model (OffHandModel) over the
    # same frame and finds whichever of its detected hands is
    # FARTHEST from the primary hand's wrist — rejecting it if
    # even the farthest candidate is still within
    # SAME_HAND_DISTANCE, which means OffHandModel only ever
    # re-detected the primary hand itself, not a genuine second
    # one. Returns that candidate's landmarks, or None.
    def _find_off_hand(self, frame, primary_landmarks):

        off_result = self.off_hand_model.process_frame(
            frame
        )

        if off_result is None or not off_result.hand_landmarks:

            self._report_off_hand_state(
                "none",
                len(off_result.hand_landmarks)
                if off_result else 0,
                0
            )

            return None

        primary_wrist = primary_landmarks[0]

        best_candidate = None
        best_distance = 0

        for candidate in off_result.hand_landmarks:

            wrist = candidate[0]

            distance = math.hypot(
                wrist.x - primary_wrist.x,
                wrist.y - primary_wrist.y
            )

            if distance > best_distance:

                best_distance = distance
                best_candidate = candidate

        if best_candidate is None:

            self._report_off_hand_state(
                "none",
                len(off_result.hand_landmarks),
                best_distance
            )

            return None

        if best_distance < self.SAME_HAND_DISTANCE:

            self._report_off_hand_state(
                "same_hand",
                len(off_result.hand_landmarks),
                best_distance
            )

            return None

        self._report_off_hand_state(
            "found",
            len(off_result.hand_landmarks),
            best_distance
        )

        return best_candidate

    # Diagnostic only, no effect on behavior — prints once per
    # outcome transition (not every frame) so the console shows
    # exactly why a second hand is or isn't being used right
    # now: OffHandModel detected nothing at all this frame,
    # detected something but it was rejected as just the
    # primary hand re-detected (see SAME_HAND_DISTANCE), or
    # located a genuine off-hand.
    def _report_off_hand_state(
        self,
        state,
        candidate_count,
        distance
    ):

        if state == self.off_hand_debug_state:
            return

        self.off_hand_debug_state = state

        print(
            f"[OFF-HAND] {state} "
            f"(candidates={candidate_count}, "
            f"distance={distance:.3f})"
        )

    # ---------------------------------
    # Hand Lost
    # ---------------------------------

    def _handle_hand_lost(
        self,
        frame,
        gesture_name,
        confidence
    ):

        self.hand_lost_count += 1

        # Brief dropouts (motion blur during a fast swipe)
        # are ignored — the session and its anchor stay
        # exactly as they were. Only a sustained absence
        # counts as "hand removed".
        if self.hand_lost_count >= self.hand_lost_frames:

            self._end_session()

            # Require a fresh Closed_Fist -> Open_Palm
            # sequence after the hand comes back
            self.last_gesture = None

            # The hand has genuinely left the frame (not just a
            # motion-blur blip) — every toggle gesture is
            # unlocked so the next time any of them is shown, in
            # Call mode, it counts again.
            self.locked_toggle_gestures = set()

            # Fresh debounce window once the hand returns
            self._confirm_gesture(None)

        self._publish_debug(
            frame,
            None,
            gesture_name,
            confidence
        )

    # ---------------------------------
    # Read Static Gesture
    # ---------------------------------

    def _read_gesture(self, result):

        if not result.gestures:
            return None, None

        gesture_category = (
            result.gestures[0][0]
        )

        gesture_name = (
            gesture_category.category_name
        )

        confidence = (
            gesture_category.score
        )

        if gesture_name == "None":
            return None, None

        if confidence < self.confidence_threshold:
            return None, None

        return gesture_name, confidence

    # ---------------------------------
    # Gesture Debounce
    # ---------------------------------

    def _confirm_gesture(self, gesture_name):

        # Requires the same gesture on confirm_frames
        # consecutive frames before it is trusted. Filters
        # out one-frame misclassifications so a stray
        # Closed_Fist reading can't end a session by
        # accident.

        if gesture_name is None:

            self.candidate_gesture = None
            self.candidate_count = 0
            self.candidate_start_time = None

            return None

        if gesture_name == self.candidate_gesture:

            self.candidate_count += 1

        else:

            self.candidate_gesture = gesture_name
            self.candidate_count = 1
            self.candidate_start_time = time.time()

        if self.candidate_count >= self.confirm_frames:
            return gesture_name

        return None

    # ---------------------------------
    # Start / Stop Tracking Session
    # ---------------------------------

    def _update_session(self, gesture_name):

        if gesture_name is None:
            return

        if gesture_name == self.last_gesture:
            return

        if (
            self.last_gesture == "Closed_Fist"
            and gesture_name == "Open_Palm"
        ):

            self.tracking_active = True

            self.anchor_x = None
            self.anchor_y = None

            self.previous_x = None
            self.previous_y = None
            self.previous_time = None

            self.freeze_until = 0

            self.velocity_x = None
            self.velocity_y = None

            # Set directly here, not left to the caller:
            # once tracking_active is True,
            # _publish_static_gesture ignores every gesture
            # except Closed_Fist, so it would never get the
            # chance to move last_gesture off "Closed_Fist"
            # — leaving the start condition true on every
            # following frame and re-anchoring each time.
            self.last_gesture = "Open_Palm"

            # A discrete, mode-agnostic marker for exactly
            # this transition. SignalMapper decides what it
            # means right now (e.g. opening the Quick
            # Command Circle from idle) — this class stays
            # unaware of modes.
            print(
                "[GESTURE] HAND_SESSION_START"
            )

            self.event_bus.publish(
                "gesture_signal",
                {
                    "signal": "HAND_SESSION_START",
                    "source": "gesture"
                }
            )

        elif (
            self.last_gesture == "Open_Palm"
            and gesture_name == "Closed_Fist"
        ):

            self._end_session()

            self.last_gesture = "Closed_Fist"

    def _end_session(self):

        self.tracking_active = False

        self.anchor_x = None
        self.anchor_y = None

        self.previous_x = None
        self.previous_y = None
        self.previous_time = None

        self.freeze_until = 0

        self.velocity_x = None
        self.velocity_y = None

    # ---------------------------------
    # Direction From Speed
    # ---------------------------------

    def _resolve_signal(
        self,
        velocity_x,
        velocity_y,
        distance_x,
        distance_y
    ):

        # Speed decides the direction. Distance only
        # filters out landmark jitter — it is not a "must
        # travel this far" zone.

        # 0 degrees = straight up/down, 90 degrees =
        # straight left/right
        angle_from_vertical = math.degrees(
            math.atan2(
                abs(velocity_x),
                abs(velocity_y)
            )
        )

        vertical_motion = (
            angle_from_vertical <=
            self.vertical_cone_degrees
        )

        if (
            not vertical_motion
            and distance_x > self.min_frame_distance
        ):

            if velocity_x > self.velocity_threshold:
                return "HAND_LEFT"

            if velocity_x < -self.velocity_threshold:
                return "HAND_RIGHT"

        if (
            vertical_motion
            and distance_y > self.min_frame_distance
        ):

            if velocity_y > self.velocity_threshold:
                return "HAND_DOWN"

            if velocity_y < -self.velocity_threshold:
                return "HAND_UP"

        return None

    def _fire_motion(
        self,
        signal,
        current_time,
        current_x,
        current_y
    ):

        print(
            f"[GESTURE] {signal}"
        )

        self.event_bus.publish(
            "gesture_signal",
            {
                "signal": signal,
                "source": "gesture"
            }
        )

        self.last_motion_time = current_time

        self.last_signal = signal

        # Freeze the marker at the trigger point briefly,
        # for visual feedback, then let it resume following
        # the finger live
        self.anchor_x = current_x
        self.anchor_y = current_y

        self.freeze_until = (
            current_time +
            self.freeze_duration
        )

    # ---------------------------------
    # Motion Tracking
    # ---------------------------------

    def _check_motion(self, result):

        if not self.tracking_active:
            return

        hand_landmarks = (
            result.hand_landmarks[0]
        )

        # Index fingertip
        index_tip = hand_landmarks[8]

        current_x = index_tip.x
        current_y = index_tip.y

        current_time = time.time()

        # First frame of the session: nothing to compare
        # against yet, just seed the anchor and previous
        # values
        if (
            self.previous_x is None
            or self.previous_y is None
            or self.previous_time is None
        ):

            self.anchor_x = current_x
            self.anchor_y = current_y

            self.previous_x = current_x
            self.previous_y = current_y

            self.previous_time = current_time

            return

        delta_time = (
            current_time -
            self.previous_time
        )

        if delta_time > 0:

            delta_x = (
                current_x -
                self.previous_x
            )

            delta_y = (
                current_y -
                self.previous_y
            )

            velocity_x = delta_x / delta_time

            velocity_y = delta_y / delta_time

            self.velocity_x = velocity_x
            self.velocity_y = velocity_y

            signal = self._resolve_signal(
                velocity_x,
                velocity_y,
                abs(delta_x),
                abs(delta_y)
            )

            cooldown_ready = (
                current_time -
                self.last_motion_time
            ) > self.motion_cooldown

            if signal is not None and cooldown_ready:

                self._fire_motion(
                    signal,
                    current_time,
                    current_x,
                    current_y
                )

        # Follow the finger live, except during the brief
        # freeze right after a trigger — _fire_motion
        # already placed the marker at the trigger point
        # this frame, so this check keeps it there instead
        # of immediately snapping back to "current position"
        # in the same frame
        if current_time >= self.freeze_until:

            self.anchor_x = current_x
            self.anchor_y = current_y

        self.previous_x = current_x
        self.previous_y = current_y

        self.previous_time = current_time

    # ---------------------------------
    # Pinch / Hold-and-Drag Geometry
    # ---------------------------------

    # Thumb tip (4) to index tip (8) distance — the one piece
    # of geometry PINCH, OK-sign, off-hand-pinch and zoom all
    # share, each just comparing or tracking it differently.
    def _pinch_distance(self, hand_landmarks):

        thumb_tip = hand_landmarks[4]
        index_tip = hand_landmarks[8]

        return math.hypot(
            thumb_tip.x - index_tip.x,
            thumb_tip.y - index_tip.y
        )

    # Computed directly from hand landmarks rather than the
    # MediaPipe classifier, which does not produce a pinch
    # category. A quick touch-and-release fires a single
    # PINCH gesture_signal (used for click). A touch that is
    # held or moved past a small threshold instead becomes a
    # hold-and-drag, publishing continuous "pinch_drag"
    # deltas (used for scroll) and firing no click on
    # release — this class only computes the geometry, it
    # does not know that Cursor mode is the only place any
    # of this currently matters.

    def _check_pinch(self, result):

        current_time = time.time()

        # A deferred single tap (see _release_pinch) is
        # committed here, on whichever later frame first
        # notices the double-pinch window has expired without
        # a second tap arriving.
        if (
            self.pending_single_pinch
            and not self.is_pinching
            and (current_time - self.pending_pinch_time)
            > self.double_pinch_window
        ):

            self._fire_pinch_signal("PINCH")

            self.pending_single_pinch = False

        hand_landmarks = (
            result.hand_landmarks[0]
        )

        thumb_tip = hand_landmarks[4]
        index_tip = hand_landmarks[8]

        distance = self._pinch_distance(
            hand_landmarks
        )

        currently_touching = (
            distance < self.pinch_distance_threshold
        )

        current_x = (thumb_tip.x + index_tip.x) / 2
        current_y = (thumb_tip.y + index_tip.y) / 2

        if currently_touching and not self.is_pinching:

            self._start_pinch(
                current_time,
                current_x,
                current_y
            )

            return

        if currently_touching and self.is_pinching:

            self._hold_pinch(
                current_time,
                current_x,
                current_y
            )

            return

        if not currently_touching and self.is_pinching:

            self._release_pinch()

    def _start_pinch(self, current_time, current_x, current_y):

        self.is_pinching = True
        self.is_dragging = False

        self.pinch_start_time = current_time

        self.pinch_start_x = current_x
        self.pinch_start_y = current_y

        self.pinch_previous_x = current_x
        self.pinch_previous_y = current_y

    def _hold_pinch(self, current_time, current_x, current_y):

        elapsed = current_time - self.pinch_start_time

        moved = math.hypot(
            current_x - self.pinch_start_x,
            current_y - self.pinch_start_y
        )

        if (
            not self.is_dragging
            and (
                elapsed > self.drag_activation_seconds
                or moved > self.drag_activation_distance
            )
        ):

            self.is_dragging = True

        if self.is_dragging:

            delta_x = current_x - self.pinch_previous_x
            delta_y = current_y - self.pinch_previous_y

            self.event_bus.publish(
                "pinch_drag",
                {
                    "delta_x": delta_x,
                    "delta_y": delta_y,
                    "source": "gesture"
                }
            )

        self.pinch_previous_x = current_x
        self.pinch_previous_y = current_y

    def _release_pinch(self):

        # A quick tap (never became a drag) is a click — or
        # half of a double-click. A completed drag ends
        # silently either way — it already did its job as a
        # scroll, it should not also click.
        if not self.is_dragging:

            current_time = time.time()

            if (
                self.pending_single_pinch
                and (current_time - self.pending_pinch_time)
                <= self.double_pinch_window
            ):

                # Second tap arrived in time — the pair is a
                # double-pinch (right-click), not two clicks.
                self._fire_pinch_signal("DOUBLE_PINCH")

                self.pending_single_pinch = False

            else:

                # First tap: don't fire PINCH yet, it might
                # be the start of a double-pinch. _check_pinch
                # commits it as a plain click once
                # double_pinch_window passes with no second
                # tap.
                self.pending_single_pinch = True

                self.pending_pinch_time = current_time

        self.is_pinching = False
        self.is_dragging = False

        self.pinch_start_x = None
        self.pinch_start_y = None
        self.pinch_previous_x = None
        self.pinch_previous_y = None

    def _fire_pinch_signal(self, signal):

        print(
            f"[GESTURE] {signal}"
        )

        self.event_bus.publish(
            "gesture_signal",
            {
                "signal": signal,
                "source": "gesture"
            }
        )

    # ---------------------------------
    # OK-Sign (Call Mode: raise hand)
    # ---------------------------------

    def _check_ok_sign(self, result):

        hand_landmarks = (
            result.hand_landmarks[0]
        )

        distance = self._pinch_distance(
            hand_landmarks
        )

        # Already touching: only the WIDER release distance can
        # re-arm, not a return past the (narrower) touch
        # threshold — see ok_sign_release_distance for why.
        if self.ok_touching:

            if distance > self.ok_sign_release_distance:
                self.ok_touching = False

            return

        if distance >= self.pinch_distance_threshold:
            return

        current_time = time.time()

        if (
            current_time - self.last_ok_sign_time
            < self.ok_sign_cooldown
        ):
            return

        self.ok_touching = True
        self.last_ok_sign_time = current_time

        print(
            "[GESTURE] OK_SIGN"
        )

        self.event_bus.publish(
            "gesture_signal",
            {
                "signal": "OK_SIGN",
                "source": "gesture"
            }
        )

    # ---------------------------------
    # Off-Hand (Cursor Mode: zoom engage + precision)
    # ---------------------------------

    # Returns True while the off-hand is held pinched — engages
    # zoom (see _check_zoom) using the exact same thumb/index
    # geometry as the primary hand's own PINCH. This used to be
    # an alternative to holding Alt on the keyboard; that option
    # was removed once Alt became the global face-layer modifier
    # (§9.1) — see the comment on zoom_previous_distance in
    # __init__ for why. Zoom is off-hand-pinch-only now.
    def _check_off_hand(self, off_hand_landmarks):

        if off_hand_landmarks is None:
            return False

        return (
            self._pinch_distance(off_hand_landmarks)
            < self.pinch_distance_threshold
        )

    # Two-hand zoom: while the off-hand is held pinched, the
    # primary hand's own thumb/index distance drives zoom
    # continuously — spreading thumb and index apart zooms in,
    # closing them zooms out. Same event/consumer as before
    # (ActionExecutor._handle_pinch_zoom) — only the source of
    # the distance changed, from two-hand fingertip separation
    # to one hand's own pinch geometry.
    def _check_zoom(self, result, zoom_engaged):

        if not zoom_engaged:

            self.zoom_previous_distance = None

            return

        hand_landmarks = (
            result.hand_landmarks[0]
        )

        distance = self._pinch_distance(
            hand_landmarks
        )

        if self.zoom_previous_distance is None:

            self.zoom_previous_distance = distance

            return

        delta_distance = (
            distance - self.zoom_previous_distance
        )

        self.zoom_previous_distance = distance

        self.event_bus.publish(
            "pinch_zoom",
            {
                "delta_distance": delta_distance,
                "source": "gesture"
            }
        )

    # ---------------------------------
    # Pointer Tracking
    # ---------------------------------

    # Trims ACTIVE_ZONE_MARGIN off each edge of the normalized
    # frame coordinate and stretches what remains back to the
    # full 0..1 range, so the usable input area is the central
    # portion of the camera frame rather than the whole frame
    # (where hand tracking is least reliable right at the true
    # edges). Downstream clamping handles anything beyond the
    # trimmed margin by saturating at 0 or 1.
    def _expand_active_zone(self, value):

        return (
            (value - self.ACTIVE_ZONE_MARGIN)
            / (1 - 2 * self.ACTIVE_ZONE_MARGIN)
        )

    def _update_pointer(
        self,
        gesture_name,
        result,
        off_hand_pinching
    ):

        if gesture_name != "Pointing_Up":

            # Not pointing — nothing to publish, and any
            # precision-mode engagement should not carry over
            # to the next time pointing resumes.
            self.precision_active = False

            return

        hand_landmarks = (
            result.hand_landmarks[0]
        )

        index_tip = hand_landmarks[8]

        raw_x = self._expand_active_zone(index_tip.x)
        raw_y = self._expand_active_zone(index_tip.y)

        if off_hand_pinching:

            # Precision mode: a temporary relative "clutch"
            # layered on top of the otherwise-always-absolute
            # mapping below. Engaging it anchors the current
            # raw position; while held, the published position
            # only moves PRECISION_SCALE of however far the
            # hand actually moves from that anchor — exactly
            # like lowering a mouse's DPI. Releasing the
            # off-hand pinch snaps straight back to plain
            # absolute 1:1 tracking, which means the cursor
            # jumps to match the finger's current raw position
            # — an intentional, honest consequence of mixing a
            # relative clutch into an otherwise-absolute
            # mapping, not a bug.
            if not self.precision_active:

                self.precision_active = True

                self.precision_anchor_x = raw_x
                self.precision_anchor_y = raw_y

            effective_x = (
                self.precision_anchor_x
                + (raw_x - self.precision_anchor_x)
                * self.PRECISION_SCALE
            )

            effective_y = (
                self.precision_anchor_y
                + (raw_y - self.precision_anchor_y)
                * self.PRECISION_SCALE
            )

        else:

            # Default: absolute mapping, unchanged from before
            # off-hand precision mode existed — take a camera
            # frame, find the finger, that IS the position.
            self.precision_active = False

            effective_x = raw_x
            effective_y = raw_y

        effective_x = min(1.0, max(0.0, effective_x))
        effective_y = min(1.0, max(0.0, effective_y))

        # Raw, absolute (or precision-scaled) fingertip
        # position for this frame — the consumer
        # (ActionExecutor) maps it straight onto the screen.
        self.event_bus.publish(
            "pointer_position",
            {
                "x": effective_x,
                "y": effective_y,
                "source": "gesture"
            }
        )

    # ---------------------------------
    # Publish Static Gesture
    # ---------------------------------

    def _publish_static_gesture(
        self,
        gesture_name,
        confidence
    ):

        if gesture_name is None:
            return

        # While a motion-tracking session is running, the
        # only gesture that matters is the Closed_Fist that
        # ends it. Everything else (Open_Palm, or the
        # classifier briefly flickering to something else
        # while the hand moves) is ignored completely, so
        # last_gesture stays frozen at "Open_Palm" and the
        # Open_Palm -> Closed_Fist end transition in
        # _update_session keeps working reliably.
        if (
            self.tracking_active
            and gesture_name != "Closed_Fist"
        ):
            return

        # Thumb_Up/Thumb_Down/Victory only mean anything in
        # Call mode (mic mute/unmute, camera toggle) — gated
        # at the source so, e.g., an actual thumbs-up given to
        # someone during a Flip-mode swipe session never gets
        # detected or published as noise.
        if (
            gesture_name in self.CALL_TOGGLE_GESTURES
            and self.active_mode != "call"
        ):
            return

        if gesture_name in self.CALL_TOGGLE_GESTURES:

            # Require a real, continuous hold — since the raw
            # gesture was first seen, not just since it crossed
            # confirm_frames — before a mic/camera toggle is
            # trusted enough to fire.
            held_seconds = (
                time.time() - self.candidate_start_time
                if self.candidate_start_time is not None
                else 0
            )

            if held_seconds < self.call_toggle_hold_seconds:
                return

            # Locked out on its own, independent of last_gesture
            # below — see locked_toggle_gestures in __init__ for
            # why last_gesture's ordinary same-as-before check
            # isn't enough on its own to stop a second toggle.
            if gesture_name in self.locked_toggle_gestures:
                return

            self.locked_toggle_gestures.add(gesture_name)

        if gesture_name == self.last_gesture:
            return

        self.last_gesture = gesture_name

        print(
            f"[GESTURE] {gesture_name}"
        )

        self.event_bus.publish(
            "gesture_signal",
            {
                "signal": gesture_name,
                "confidence": confidence,
                "source": "gesture"
            }
        )

    # ---------------------------------
    # Debug Snapshot (for calibration view)
    # ---------------------------------

    def _publish_debug(
        self,
        frame,
        finger_position,
        gesture_name,
        confidence
    ):

        anchor = None

        if (
            self.anchor_x is not None
            and self.anchor_y is not None
        ):

            anchor = (
                self.anchor_x,
                self.anchor_y
            )

        self.event_bus.publish(
            "gesture_debug",
            {
                "frame": frame,
                "finger": finger_position,
                "anchor": anchor,
                "tracking_active": self.tracking_active,
                "gesture_name": gesture_name,
                "confidence": confidence,
                "last_gesture": self.last_gesture,
                "last_signal": self.last_signal,
                "velocity_x": self.velocity_x,
                "velocity_y": self.velocity_y,
                "vertical_cone_degrees": (
                    self.vertical_cone_degrees
                )
            }
        )
