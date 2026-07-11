"""Hand-gesture recognition from camera frames using MediaPipe.

Consumes camera_frame events, runs MediaPipe hand/gesture models on each
frame, and publishes gesture_signal, pointer_position, pinch_drag and
pinch_zoom events over the EventBus for downstream fusion/mapping. Stays
mode-agnostic overall, but reads the active mode from SignalMapper's
mode_changed event for a handful of mode-gated checks (PINCH, OK-sign,
the finger-count toggles, off-hand precision/zoom).
"""

import math
import time

from processing.gesture.gesture_model import (
    GestureModel,
    OffHandModel
)

from config.config_loader import load_system_config


class GestureRecognizer:

    # The only two modes that ever interpret HAND_LEFT/RIGHT/UP/DOWN
    # swipes: Flip mode uses them directly, Quick Circle uses them to
    # pick a mode. See _handle_mode_changed for why the tracking session
    # is force-ended on transitioning into any mode outside this set.
    SWIPE_MODES = {"flip", "quick_circle"}

    # The four Call-mode gestures that toggle persistent state (mic,
    # camera, call audio, background blur) rather than firing a
    # momentary one-shot action like OK_SIGN. Shared by the mode gate,
    # the hold-to-confirm requirement, and the per-gesture lock in
    # _publish_static_gesture — see call_toggle_hold_seconds and
    # locked_toggle_gestures in __init__. Produced by
    # _read_call_finger_gesture, not MediaPipe's own classifier — see
    # FINGER_COUNT_GESTURES below for why.
    CALL_TOGGLE_GESTURES = (
        "ONE_FINGER",
        "TWO_FINGERS",
        "THREE_FINGERS",
        "FOUR_FINGERS"
    )

    # (tip landmark, PIP landmark) pairs for the four non-thumb fingers,
    # used by _count_extended_fingers. The thumb is deliberately left
    # out of the count — whether it's tucked in or splayed out while
    # raising N fingers varies too much between people to be a reliable
    # fourth bit.
    FINGER_TIP_PIP_LANDMARKS = (
        (8, 6),    # index
        (12, 10),  # middle
        (16, 14),  # ring
        (20, 18)   # pinky
    )

    # MediaPipe's bundled classifier has no "two/three/four fingers"
    # category (confirmed against labels.txt — only None/Closed_Fist/
    # Open_Palm/Pointing_Up/Thumb_Down/Thumb_Up/Victory/ILoveYou exist),
    # so Call mode's toggle gestures are keyed off a raw extended-finger
    # count computed from landmark geometry instead.
    FINGER_COUNT_GESTURES = {
        1: "ONE_FINGER",
        2: "TWO_FINGERS",
        3: "THREE_FINGERS",
        4: "FOUR_FINGERS"
    }

    def __init__(self, event_bus):
        """Load gesture-tuning config and reset all detector state."""

        self.event_bus = event_bus

        config = load_system_config().get(
            "gesture",
            {}
        )

        presentation_fist_config = config.get(
            "presentation_fist",
            {}
        )

        # Off-hand pinch ("precision mode", Cursor mode only) scales
        # cursor movement down to this fraction of the raw hand
        # movement, like a DPI switch on a physical mouse.
        self.PRECISION_SCALE = config.get(
            "precision_scale",
            0.5
        )

        # Fraction of the camera frame trimmed from each edge before
        # mapping the fingertip position to the screen. MediaPipe's
        # hand tracking gets unreliable right at the true edges of
        # the frame, so without this the user could never
        # comfortably reach the screen's edges either — trimming the
        # margin and stretching what remains to the full 0..1 range
        # means getting close to (not exactly at) the frame's edge
        # already reaches the screen's edge.
        self.ACTIVE_ZONE_MARGIN = config.get(
            "active_zone_margin",
            0.1
        )

        # Presentation mode's own pointer (see
        # _update_presentation_pointer) measures its relative
        # control box in units of the presenter's own hand size —
        # this many hand-widths, centered on wherever pointing
        # started, sweep the full screen. Deliberately an
        # approximate, user-tuned comfort setting rather than
        # something derived geometrically.
        self.PRESENTATION_POINTER_BOX_HANDS = config.get(
            "presentation_pointer_box_hands",
            4.0
        )

        # Below this normalized distance between two detected
        # wrists, OffHandModel's result is treated as re-detecting
        # the SAME physical hand GestureModel already found as
        # primary, not a genuine second hand.
        self.SAME_HAND_DISTANCE = config.get(
            "same_hand_distance",
            0.15
        )

        # A finger counts as extended once its tip sits this much
        # farther from the wrist than its own PIP joint is —
        # comparing distances-from-wrist rather than a raw
        # y-coordinate keeps this working regardless of how the hand
        # is rotated in frame, not just when held perfectly upright.
        # The margin above 1.0 keeps a nearly-straight finger sitting
        # right at the boundary from flickering extended/folded
        # frame to frame.
        self.FINGER_EXTENSION_MARGIN = config.get(
            "finger_extension_margin",
            1.05
        )

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

        self.confidence_threshold = config.get(
            "confidence_threshold",
            0.7
        )

        # A gesture must hold for this many consecutive frames before
        # it is trusted, so a single misclassified frame (motion blur,
        # odd angle) can't end and immediately restart a session.
        self.confirm_frames = config.get(
            "confirm_frames",
            4
        )

        self.candidate_gesture = None
        self.candidate_count = 0

        # When the current candidate_gesture started being seen, even
        # before it crossed confirm_frames. Used by the Call-mode
        # toggle gestures to require a real, continuous hold — see
        # call_toggle_hold_seconds — on top of this debounce, which by
        # itself only filters single-frame noise.
        self.candidate_start_time = None

        # How many consecutive frames the hand may be undetected before
        # the session actually ends. Fast finger movement causes motion
        # blur, which regularly makes MediaPipe miss the hand for a
        # frame or two even though it never left the camera.
        self.hand_lost_frames = config.get(
            "hand_lost_frames",
            5
        )

        self.hand_lost_count = 0

        # True between a Closed_Fist -> Open_Palm transition and the
        # matching Open_Palm -> Closed_Fist transition (or the hand
        # leaving the frame for hand_lost_frames straight frames). The
        # hand does NOT need to stay open the whole time once a session
        # starts.
        self.tracking_active = False

        # Marker position. Follows the finger live and
        # freezes briefly at the trigger point right after
        # a swipe fires.
        self.anchor_x = None
        self.anchor_y = None

        self.freeze_until = 0

        self.freeze_duration = config.get(
            "freeze_duration",
            0.3
        )

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
        self.velocity_threshold = config.get(
            "velocity_threshold",
            1.8
        )

        # Per-frame movement below this is treated as landmark jitter,
        # even if it briefly spikes the velocity reading (a tiny
        # distance over a tiny time can look "fast").
        self.min_frame_distance = config.get(
            "min_frame_distance",
            0.015
        )

        # The velocity vector counts as UP/DOWN only within this many
        # degrees of straight vertical. Everything else, including
        # diagonals, counts as LEFT/RIGHT.
        self.vertical_cone_degrees = config.get(
            "vertical_cone_degrees",
            25
        )

        self.last_motion_time = 0

        self.motion_cooldown = config.get(
            "motion_cooldown",
            0.5
        )

        # Unlike the swipe above (armed by a Closed_Fist -> Open_Palm
        # transition, tracks the index fingertip), Presentation mode's
        # slide-switch gesture needs no separate "arm" step: holding a
        # closed fist IS the active state, and the WRIST (landmark 0)
        # is tracked instead since it stays reliably trackable even
        # clenched and farther from the camera. Kept as its own
        # detector — reusing _resolve_signal's direction math with its
        # own thresholds below — so calibrating it for presenting
        # distance never touches the Flip-mode swipe above.
        self.presentation_fist_previous_x = None
        self.presentation_fist_previous_y = None
        self.presentation_fist_previous_time = None

        self.presentation_fist_last_motion_time = 0

        # Tuned down from the Flip-mode swipe's defaults (1.8 / 0.015)
        # after live testing at actual presenting distance with
        # tests/presentation_fist_swipe_standalone_test.py — a wrist
        # swipe reads as slower/smaller motion than a fingertip swipe
        # at the same physical speed.
        self.presentation_fist_velocity_threshold = (
            presentation_fist_config.get(
                "velocity_threshold",
                0.5
            )
        )

        self.presentation_fist_min_frame_distance = (
            presentation_fist_config.get(
                "min_frame_distance",
                0.0075
            )
        )

        self.presentation_fist_vertical_cone_degrees = (
            presentation_fist_config.get(
                "vertical_cone_degrees",
                25
            )
        )

        self.presentation_fist_motion_cooldown = (
            presentation_fist_config.get(
                "motion_cooldown",
                0.5
            )
        )

        # Distance-invariant alternative to the absolute fingertip
        # mapping _update_pointer otherwise uses: the moment
        # Pointing_Up starts, the pointer snaps to the screen center,
        # and hand movement from there is measured in units of the
        # presenter's own hand size — see _update_presentation_pointer.
        # An absolute mapping would otherwise force a physically larger
        # sweep the farther the presenter stands, since the camera's
        # field of view covers more real-world space at range.
        self.presentation_pointer_anchor_x = None
        self.presentation_pointer_anchor_y = None

        # Frozen the moment pointing starts, not re-measured every
        # frame, so the control box doesn't subtly resize (and the
        # pointer drift) if the hand-size estimate jitters slightly.
        self.presentation_pointer_hand_size = None

        # Distance (normalized coordinates) between thumb tip and
        # index tip below which the two fingers count as "touching" —
        # a pinch. Also reused as-is by Call mode's OK-sign check
        # (same geometry, different meaning — the two never run in
        # the same mode).
        self.pinch_distance_threshold = config.get(
            "pinch_distance_threshold",
            0.06
        )

        # A pinch held/moved past either of these thresholds stops
        # being a quick tap (click) and becomes a hold-and-drag
        # (scroll) instead.
        self.drag_activation_seconds = config.get(
            "drag_activation_seconds",
            0.15
        )
        self.drag_activation_distance = config.get(
            "drag_activation_distance",
            0.03
        )

        self.is_pinching = False
        self.is_dragging = False

        self.pinch_start_time = 0
        self.pinch_start_x = None
        self.pinch_start_y = None
        self.pinch_previous_x = None
        self.pinch_previous_y = None

        # A completed quick tap is not published as PINCH right away —
        # it waits up to double_pinch_window to see whether a second
        # tap follows, in which case the pair is published as one
        # DOUBLE_PINCH (right-click) instead of two separate PINCH
        # (click) signals.
        self.pending_single_pinch = False
        self.pending_pinch_time = 0
        self.double_pinch_window = config.get(
            "double_pinch_window",
            0.3
        )

        # MediaPipe's bundled gesture classifier has no "OK" category
        # (confirmed against labels.txt — only None/Closed_Fist/
        # Open_Palm/Pointing_Up/Thumb_Down/Thumb_Up/Victory/ILoveYou
        # exist), so this is computed the same way PINCH is — directly
        # from thumb/index landmark distance. Edge-triggered: fires
        # once when the fingers first touch, not again until they
        # separate.
        self.ok_touching = False

        # Once touching, the fingers must separate past this WIDER
        # distance — not just back past pinch_distance_threshold —
        # before being considered released. OK-sign has no
        # confirm_frames debounce (there's no classifier category to
        # debounce), so without this hysteresis gap, landmark jitter
        # at a single threshold would flicker touching/not-touching
        # frame to frame and re-fire OK_SIGN in an unbroken burst
        # instead of once per deliberate touch-and-release.
        self.ok_sign_release_distance = (
            self.pinch_distance_threshold
            * config.get(
                "ok_sign_release_multiplier",
                1.6
            )
        )

        # Hard floor between two OK_SIGN firings, regardless of finger
        # state — a safety net under the hysteresis above for jitter
        # that plays out slower than a single-frame flicker.
        self.ok_sign_cooldown = config.get(
            "ok_sign_cooldown",
            0.6
        )

        self.last_ok_sign_time = 0

        # Each of the four finger-count gestures sends a single
        # OS-level toggle keystroke (see OSController.toggle_mic/
        # toggle_camera/toggle_call_audio/toggle_background_blur)
        # rather than a distinct "turn on"/"turn off" call, so firing
        # the same one twice in a row flips the state the wrong way.
        # Once a toggle gesture fires, that SAME gesture name is
        # ignored until the hand actually leaves the frame (see
        # _handle_hand_lost) and is reacquired — "show once to turn
        # on, hand must leave frame, show again to turn off". Unlike
        # last_gesture, NOT cleared by seeing some other gesture in
        # between — a gesture stays locked so finger count flickering
        # off it and back, without the hand leaving frame, can't
        # refire it. Tracked per gesture name so a locked ONE_FINGER
        # does not also block TWO_FINGERS.
        self.locked_toggle_gestures = set()

        # How long (seconds) one of these four gestures must be held
        # continuously — since it was first seen, not just since it
        # crossed confirm_frames — before it is trusted enough to fire.
        # These toggle mic/camera/call-audio/background-blur state, so
        # a fast or incidental gesture shouldn't be enough to flip
        # them. OK_SIGN is a momentary, repeatable notification, not a
        # toggle, so it is not held to this standard.
        self.call_toggle_hold_seconds = config.get(
            "call_toggle_hold_seconds",
            1.5
        )

        # True while an off-hand pinch is held during Cursor mode —
        # see _update_pointer.
        self.precision_active = False

        self.precision_anchor_x = None
        self.precision_anchor_y = None

        # Zoom used to also be engageable by holding Alt on the
        # keyboard, as a one-handed substitute for the off-hand pinch.
        # Removed once Alt became the global face-layer modifier
        # (§9.1 in docs/SYSTEM_FUNCTIONS.md) — holding Alt for zoom
        # would simultaneously arm HEAD_TILT/MOUTH_OPEN/EYEBROWS_UP
        # actions, firing alongside whatever zoom gesture was in
        # progress. Zoom is off-hand-pinch-only now: it uses two
        # hands, not one, so it shares no gesture or modifier with
        # anything Alt now means.

        # Baseline thumb/index distance for zoom (see _check_zoom) —
        # reset whenever zoom disengages, so re-engaging always starts
        # from a fresh baseline instead of a potentially large stale
        # delta.
        self.zoom_previous_distance = None

        # Mirrored from SignalMapper's "mode_changed" event. A
        # deliberate, narrow exception to this class otherwise staying
        # mode-agnostic: a handful of checks below (PINCH, OK-sign,
        # the finger-count toggles, off-hand precision/zoom) only mean
        # something in one specific mode each, and are gated at the
        # source so a pose passing through during an unrelated mode
        # never gets detected or published as noise.
        self.active_mode = None

        # Tracks only whether the debug "Hand detected"/"Hand lost"
        # transition print already fired for the current state, so it
        # prints once per transition instead of spamming every frame.
        self.hand_was_present = False

        # Tracks the last reported off-hand search outcome ("none" /
        # "same_hand" / "found"), purely so _report_off_hand_state
        # prints only on a transition — same idea as hand_was_present.
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
        """Update the active mode and reset any mode-scoped state.

        Prevents state from one mode's session (a deferred pinch tap,
        a stale swipe baseline, a locked toggle) leaking into a later
        session in the same or a different mode.
        """

        self.active_mode = event.get(
            "data",
            {}
        ).get("mode")

        # Leaving Cursor mode mid-window would otherwise let a
        # deferred single tap fire once the mode is re-entered later,
        # long after the user actually pinched. Same idea for
        # precision mode and the zoom baseline.
        if self.active_mode != "cursor":

            self.pending_single_pinch = False

            self.precision_active = False

            self.zoom_previous_distance = None

        if self.active_mode != "call":

            self.ok_touching = False

            self.locked_toggle_gestures = set()

        # Leaving Presentation mode mid-fist-move would otherwise let
        # a stale previous wrist position survive into a later
        # Presentation session and produce one large, spurious delta
        # on the first frame back.
        if self.active_mode != "presentation":

            self.presentation_fist_previous_x = None
            self.presentation_fist_previous_y = None
            self.presentation_fist_previous_time = None

            self.presentation_pointer_anchor_x = None
            self.presentation_pointer_anchor_y = None
            self.presentation_pointer_hand_size = None

        # A swipe session has no reason to keep running once the
        # resulting mode isn't one that interprets swipes at all —
        # without this, residual hand motion right after landing in,
        # say, Call mode would keep computing velocity and could fire
        # HAND_LEFT/RIGHT/UP/DOWN signals that match no rule there,
        # pure noise. Ending it here means a fresh Closed_Fist ->
        # Open_Palm is required before any further swipe is
        # interpreted, as if the hand had been lost and reacquired.
        if self.active_mode not in self.SWIPE_MODES:

            self._end_session()

    def _handle_frame(self, event):
        """Run gesture/pointer detection for one camera frame and
        publish the resulting signals.
        """

        frame = event.get("data")

        if frame is None:
            return

        # GestureModel wraps a real MediaPipe task — a transient
        # internal failure here must not be able to take down frame
        # processing beyond the one frame it happened on (see the
        # num_hands>1 crash history in docs/SYSTEM_FUNCTIONS.md §2.3.1
        # for why this precaution exists).
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

        # Call mode's four toggle functions are keyed off how many
        # fingers are raised, not off whatever MediaPipe's own
        # classifier reports — substituted in here, ahead of the
        # shared confirm_frames debounce, so the rest of the
        # debounce/hold/lock pipeline in _publish_static_gesture works
        # identically to any other gesture name. gesture_name/
        # confidence themselves are left untouched — pointer tracking
        # and the debug overlay below still read the classifier's own
        # raw output.
        confirm_input = gesture_name
        confirm_confidence = confidence

        if self.active_mode == "call":

            confirm_input, confirm_confidence = (
                self._read_call_finger_gesture(
                    result
                )
            )

        # Only a gesture held for confirm_frames straight frames is
        # trusted for session start/end — the raw, possibly noisy
        # gesture_name is still used below for pointer tracking and
        # the debug overlay.
        confirmed_gesture = self._confirm_gesture(
            confirm_input
        )

        # Swipe/motion tracking only ever means anything from idle (no
        # mode — Quick Circle's own HAND_SESSION_START trigger only
        # matches from there, see SignalMapper._mode_trigger_matches)
        # or while already inside Flip mode or Quick Circle (see
        # SWIPE_MODES) — gated here so a Closed_Fist -> Open_Palm
        # toggle in, say, Cursor mode never starts a session with no
        # mode to end it.
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

        # A second hand only ever means anything in Cursor mode —
        # resolved to None everywhere else, and always run through a
        # separate model from the primary hand (see OffHandModel /
        # __init__ for why). Searched regardless of what the primary
        # hand is currently doing, since an off-hand pinch must keep
        # being detected for as long as it's held, including the whole
        # time it's engaging zoom — by then the primary hand is
        # deliberately NOT doing Pointing_Up, so gating this on the
        # primary hand's own gesture would drop the off-hand mid-zoom.
        # Wrapped defensively: OffHandModel is a second, independent
        # MediaPipe task running alongside GestureModel every frame,
        # and any failure in it must never block the primary hand's
        # own gesture/pointer publishing below (see docs/
        # SYSTEM_FUNCTIONS.md §2.3.1's crash/fix history).
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

        # Zoom (off-hand pinch) and PINCH (click / drag-to-scroll) only
        # mean anything in Cursor mode, and are mutually exclusive on
        # the same physical gesture — while zoom is engaged, the
        # primary hand's own thumb/index distance drives zoom instead
        # of a click or drag.
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

        # Wrist-based fist swipe (slide navigation) only means
        # anything in Presentation mode.
        if self.active_mode == "presentation":

            self._check_fist_motion(
                confirmed_gesture,
                result
            )

        self._update_pointer(
            gesture_name,
            result,
            off_hand_pinching
        )

        self._publish_static_gesture(
            confirmed_gesture,
            confirm_confidence
        )

        index_tip = result.hand_landmarks[0][8]

        self._publish_debug(
            frame,
            (index_tip.x, index_tip.y),
            gesture_name,
            confidence
        )

    def _find_off_hand(self, frame, primary_landmarks):
        """Locate the off-hand (Cursor mode's second hand), if any.

        Runs OffHandModel over the same frame and picks whichever
        detected hand is FARTHEST from the primary hand's wrist,
        rejecting it if even the farthest candidate is still within
        SAME_HAND_DISTANCE — meaning OffHandModel only re-detected the
        primary hand itself, not a genuine second one.

        Returns:
            The candidate's landmarks, or None.
        """

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

    def _report_off_hand_state(
        self,
        state,
        candidate_count,
        distance
    ):
        """Print once per off-hand outcome transition.

        Diagnostic only, no effect on behavior — shows whether
        OffHandModel found nothing, rejected a candidate as just the
        primary hand re-detected (see SAME_HAND_DISTANCE), or located
        a genuine off-hand.
        """

        if state == self.off_hand_debug_state:
            return

        self.off_hand_debug_state = state

        print(
            f"[OFF-HAND] {state} "
            f"(candidates={candidate_count}, "
            f"distance={distance:.3f})"
        )

    def _handle_hand_lost(
        self,
        frame,
        gesture_name,
        confidence
    ):
        """Track consecutive no-hand frames and end the session once
        the hand has been gone for hand_lost_frames straight frames.
        """

        self.hand_lost_count += 1

        # Brief dropouts (motion blur during a fast swipe) are
        # ignored — the session and its anchor stay exactly as they
        # were. Only a sustained absence counts as "hand removed".
        if self.hand_lost_count >= self.hand_lost_frames:

            self._end_session()

            # Require a fresh Closed_Fist -> Open_Palm sequence after
            # the hand comes back
            self.last_gesture = None

            # The hand has genuinely left the frame (not just a
            # motion-blur blip) — every toggle gesture is unlocked so
            # the next time any of them is shown, in Call mode, it
            # counts again.
            self.locked_toggle_gestures = set()

            # Fresh debounce window once the hand returns
            self._confirm_gesture(None)

        self._publish_debug(
            frame,
            None,
            gesture_name,
            confidence
        )

    def _read_gesture(self, result):
        """Extract the top gesture category from a MediaPipe result.

        Returns:
            (gesture_name, confidence), or (None, None) if there is
            no gesture, it's the "None" category, or confidence is
            below confidence_threshold.
        """

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

    def _confirm_gesture(self, gesture_name):
        """Debounce a raw gesture reading against confirm_frames.

        Requires the same gesture on confirm_frames consecutive
        frames before it is trusted, filtering out one-frame
        misclassifications so a stray Closed_Fist reading can't end a
        session by accident.

        Returns:
            The gesture name once confirmed, else None.
        """

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

    def _update_session(self, gesture_name):
        """Start or end a motion-tracking session on a confirmed
        Closed_Fist <-> Open_Palm transition.
        """

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

            # Set directly here, not left to the caller: once
            # tracking_active is True, _publish_static_gesture ignores
            # every gesture except Closed_Fist, so it would never get
            # the chance to move last_gesture off "Closed_Fist" —
            # leaving the start condition true and re-anchoring every
            # frame.
            self.last_gesture = "Open_Palm"

            # A discrete, mode-agnostic marker for exactly this
            # transition. SignalMapper decides what it means right now
            # (e.g. opening the Quick Command Circle from idle) — this
            # class stays unaware of modes.
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

            # Mirrors HAND_SESSION_START above — a discrete,
            # mode-agnostic marker for the reverse transition.
            # SignalMapper decides what it means right now (e.g.
            # closing the Quick Command Circle without picking
            # anything).
            print(
                "[GESTURE] HAND_SESSION_END"
            )

            self.event_bus.publish(
                "gesture_signal",
                {
                    "signal": "HAND_SESSION_END",
                    "source": "gesture"
                }
            )

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

    def _resolve_signal(
        self,
        velocity_x,
        velocity_y,
        distance_x,
        distance_y,
        velocity_threshold,
        min_frame_distance,
        vertical_cone_degrees
    ):
        """Classify a frame-to-frame velocity as a swipe direction.

        Speed decides the direction; distance only filters out
        landmark jitter, it is not a "must travel this far" zone.
        Thresholds are passed in rather than read from self.* so this
        same math is shared by the index-tip swipe (Flip/Quick Circle)
        and the wrist-based fist swipe (Presentation mode, see
        _check_fist_motion), each with its own tunable thresholds.

        Returns:
            One of "HAND_LEFT"/"HAND_RIGHT"/"HAND_UP"/"HAND_DOWN", or
            None if the motion doesn't qualify as a swipe.
        """

        # 0 degrees = straight up/down, 90 degrees = straight
        # left/right
        angle_from_vertical = math.degrees(
            math.atan2(
                abs(velocity_x),
                abs(velocity_y)
            )
        )

        vertical_motion = (
            angle_from_vertical <=
            vertical_cone_degrees
        )

        if (
            not vertical_motion
            and distance_x > min_frame_distance
        ):

            if velocity_x > velocity_threshold:
                return "HAND_LEFT"

            if velocity_x < -velocity_threshold:
                return "HAND_RIGHT"

        if (
            vertical_motion
            and distance_y > min_frame_distance
        ):

            if velocity_y > velocity_threshold:
                return "HAND_DOWN"

            if velocity_y < -velocity_threshold:
                return "HAND_UP"

        return None

    def _fire_motion(
        self,
        signal,
        current_time,
        current_x,
        current_y
    ):
        """Publish a swipe gesture_signal and freeze the anchor at the
        trigger point for visual feedback.
        """

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

        self.anchor_x = current_x
        self.anchor_y = current_y

        self.freeze_until = (
            current_time +
            self.freeze_duration
        )

    def _check_motion(self, result):
        """Compute index-fingertip velocity for the active tracking
        session and fire a swipe signal when it crosses threshold.
        """

        if not self.tracking_active:
            return

        hand_landmarks = (
            result.hand_landmarks[0]
        )

        index_tip = hand_landmarks[8]

        current_x = index_tip.x
        current_y = index_tip.y

        current_time = time.time()

        # First frame of the session: nothing to compare against yet,
        # just seed the anchor and previous values
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
                abs(delta_y),
                self.velocity_threshold,
                self.min_frame_distance,
                self.vertical_cone_degrees
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

        # Follow the finger live, except during the brief freeze right
        # after a trigger — _fire_motion already placed the marker at
        # the trigger point this frame, so this keeps it there instead
        # of immediately snapping back to the current position.
        if current_time >= self.freeze_until:

            self.anchor_x = current_x
            self.anchor_y = current_y

        self.previous_x = current_x
        self.previous_y = current_y

        self.previous_time = current_time

    def _check_fist_motion(self, confirmed_gesture, result):
        """Wrist-based fist-swipe detector for Presentation mode.

        No arm/disarm gesture pair — the closed fist itself is the
        active state. As long as the confirmed gesture is Closed_Fist,
        the wrist's frame-to-frame velocity is fed through the same
        direction math as the index-tip swipe (_resolve_signal), with
        its own thresholds so tuning for presenting distance never
        affects Flip mode's swipe.
        """

        if confirmed_gesture != "Closed_Fist":

            # Hand relaxed (or lost) — the next fist starts a fresh
            # baseline instead of computing one big, spurious delta
            # across the gap.
            self.presentation_fist_previous_x = None
            self.presentation_fist_previous_y = None
            self.presentation_fist_previous_time = None

            return

        hand_landmarks = (
            result.hand_landmarks[0]
        )

        # Wrist, not fingertip — stays reliably trackable even
        # with the hand clenched into a fist.
        wrist = hand_landmarks[0]

        current_x = wrist.x
        current_y = wrist.y

        current_time = time.time()

        if (
            self.presentation_fist_previous_x is None
            or self.presentation_fist_previous_y is None
            or self.presentation_fist_previous_time is None
        ):

            self.presentation_fist_previous_x = current_x
            self.presentation_fist_previous_y = current_y

            self.presentation_fist_previous_time = current_time

            return

        delta_time = (
            current_time -
            self.presentation_fist_previous_time
        )

        if delta_time > 0:

            delta_x = (
                current_x -
                self.presentation_fist_previous_x
            )

            delta_y = (
                current_y -
                self.presentation_fist_previous_y
            )

            velocity_x = delta_x / delta_time

            velocity_y = delta_y / delta_time

            signal = self._resolve_signal(
                velocity_x,
                velocity_y,
                abs(delta_x),
                abs(delta_y),
                self.presentation_fist_velocity_threshold,
                self.presentation_fist_min_frame_distance,
                self.presentation_fist_vertical_cone_degrees
            )

            cooldown_ready = (
                current_time -
                self.presentation_fist_last_motion_time
            ) > self.presentation_fist_motion_cooldown

            if signal is not None and cooldown_ready:

                print(
                    f"[GESTURE] {signal} (fist)"
                )

                self.event_bus.publish(
                    "gesture_signal",
                    {
                        "signal": signal,
                        "source": "gesture"
                    }
                )

                self.presentation_fist_last_motion_time = (
                    current_time
                )

        self.presentation_fist_previous_x = current_x
        self.presentation_fist_previous_y = current_y

        self.presentation_fist_previous_time = current_time

    def _pinch_distance(self, hand_landmarks):
        """Thumb-tip-to-index-tip distance.

        The one piece of geometry PINCH, OK-sign, off-hand-pinch and
        zoom all share, each just comparing or tracking it
        differently.
        """

        thumb_tip = hand_landmarks[4]
        index_tip = hand_landmarks[8]

        return math.hypot(
            thumb_tip.x - index_tip.x,
            thumb_tip.y - index_tip.y
        )

    def _check_pinch(self, result):
        """Detect thumb/index touch and route it to click or drag.

        Computed directly from hand landmarks rather than the
        MediaPipe classifier, which has no pinch category. A quick
        touch-and-release fires a single PINCH gesture_signal (click).
        A touch held or moved past a small threshold instead becomes a
        hold-and-drag, publishing continuous "pinch_drag" deltas
        (scroll) and firing no click on release. This class only
        computes the geometry — it doesn't know Cursor mode is the
        only place any of this currently matters.
        """

        current_time = time.time()

        # A deferred single tap (see _release_pinch) is committed
        # here, on whichever later frame first notices the
        # double-pinch window has expired without a second tap
        # arriving.
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
        """Handle thumb/index release: fire a click, a double-click,
        or nothing if the pinch was a completed drag.
        """

        # A quick tap (never became a drag) is a click — or half of a
        # double-click. A completed drag ends silently either way — it
        # already did its job as a scroll, it should not also click.
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

                # First tap: don't fire PINCH yet, it might be the
                # start of a double-pinch. _check_pinch commits it as
                # a plain click once double_pinch_window passes with
                # no second tap.
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

    def _check_ok_sign(self, result):
        """Edge-triggered OK-sign detector for Call mode's raise-hand
        notification (see ok_touching / ok_sign_release_distance).
        """

        hand_landmarks = (
            result.hand_landmarks[0]
        )

        distance = self._pinch_distance(
            hand_landmarks
        )

        # Already touching: only the WIDER release distance can re-arm,
        # not a return past the (narrower) touch threshold — see
        # ok_sign_release_distance for why.
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

    def _count_extended_fingers(self, hand_landmarks):
        """Count extended non-thumb fingers via landmark geometry.

        Uses FINGER_TIP_PIP_LANDMARKS — a finger is extended once its
        tip sits farther from the wrist than its own PIP joint does,
        past FINGER_EXTENSION_MARGIN. Distance-from-wrist rather than a
        raw y-coordinate comparison, so this keeps working regardless
        of how the hand is rotated in frame.
        """

        wrist = hand_landmarks[0]

        extended_count = 0

        for tip_index, pip_index in self.FINGER_TIP_PIP_LANDMARKS:

            tip = hand_landmarks[tip_index]
            pip = hand_landmarks[pip_index]

            tip_distance = math.hypot(
                tip.x - wrist.x,
                tip.y - wrist.y
            )

            pip_distance = math.hypot(
                pip.x - wrist.x,
                pip.y - wrist.y
            )

            if (
                tip_distance
                > pip_distance * self.FINGER_EXTENSION_MARGIN
            ):

                extended_count += 1

        return extended_count

    def _read_call_finger_gesture(self, result):
        """Read the Call-mode toggle gesture from finger count.

        Mirrors _read_gesture's (name, confidence) shape, but sourced
        from landmark geometry rather than MediaPipe's classifier —
        the same relationship OK_SIGN has to PINCH's classifier-free
        thumb/index check. Confidence is fixed at 1.0 rather than left
        as None: this is a direct geometric read, and
        _publish_static_gesture's hold-to-confirm/lock pipeline only
        cares whether the name is None.
        """

        hand_landmarks = (
            result.hand_landmarks[0]
        )

        extended_count = self._count_extended_fingers(
            hand_landmarks
        )

        gesture_name = self.FINGER_COUNT_GESTURES.get(
            extended_count
        )

        if gesture_name is None:
            return None, None

        return gesture_name, 1.0

    def _check_off_hand(self, off_hand_landmarks):
        """Return True while the off-hand is held pinched.

        Engages zoom (see _check_zoom) using the same thumb/index
        geometry as the primary hand's own PINCH. Zoom is
        off-hand-pinch-only — see zoom_previous_distance in __init__
        for why the old Alt-key alternative was removed.
        """

        if off_hand_landmarks is None:
            return False

        return (
            self._pinch_distance(off_hand_landmarks)
            < self.pinch_distance_threshold
        )

    def _check_zoom(self, result, zoom_engaged):
        """Publish continuous zoom deltas while the off-hand pinch is
        engaged.

        The primary hand's own thumb/index distance drives zoom —
        spreading apart zooms in, closing zooms out. Same event/
        consumer as before (ActionExecutor._handle_pinch_zoom); only
        the distance source changed, from two-hand fingertip
        separation to one hand's own pinch geometry.
        """

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

    def _expand_active_zone(self, value):
        """Remap a margin-trimmed frame coordinate back to 0..1.

        Trims ACTIVE_ZONE_MARGIN off each edge of the normalized
        frame coordinate and stretches what remains to the full 0..1
        range, so the usable input area is the central portion of the
        camera frame (where hand tracking is most reliable).
        Downstream clamping saturates anything beyond the trimmed
        margin at 0 or 1.
        """

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
        """Publish the pointer_position for a Pointing_Up frame.

        Routes to the Presentation-mode relative box or the default
        absolute mapping (optionally precision-scaled), depending on
        active_mode and off_hand_pinching.
        """

        if gesture_name != "Pointing_Up":

            # Not pointing — nothing to publish, and any
            # precision-mode engagement should not carry over to the
            # next time pointing resumes.
            self.precision_active = False

            # Presentation's own pointer re-anchors to the screen
            # center fresh every time pointing starts (see
            # _update_presentation_pointer) — clearing this here, not
            # just in _handle_mode_changed, also covers re-arming
            # within the same Presentation session.
            self.presentation_pointer_anchor_x = None
            self.presentation_pointer_anchor_y = None
            self.presentation_pointer_hand_size = None

            return

        hand_landmarks = (
            result.hand_landmarks[0]
        )

        index_tip = hand_landmarks[8]

        if self.active_mode == "presentation":

            effective_x, effective_y = (
                self._update_presentation_pointer(
                    hand_landmarks,
                    index_tip
                )
            )

        else:

            raw_x = self._expand_active_zone(index_tip.x)
            raw_y = self._expand_active_zone(index_tip.y)

            if off_hand_pinching:

                # Precision mode: a temporary relative "clutch"
                # layered on top of the otherwise-always-absolute
                # mapping below. Engaging it anchors the current raw
                # position; while held, the published position only
                # moves PRECISION_SCALE of however far the hand
                # actually moves from that anchor — like lowering a
                # mouse's DPI. Releasing the off-hand pinch snaps back
                # to plain absolute 1:1 tracking, so the cursor jumps
                # to the finger's current raw position — an
                # intentional consequence of mixing a relative clutch
                # into an absolute mapping, not a bug.
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

                # Default: absolute mapping — take a camera frame,
                # find the finger, that IS the position.
                self.precision_active = False

                effective_x = raw_x
                effective_y = raw_y

            effective_x = min(1.0, max(0.0, effective_x))
            effective_y = min(1.0, max(0.0, effective_y))

        # Raw absolute, precision-scaled, or Presentation relative-box
        # (see _update_presentation_pointer) fingertip position for
        # this frame — the consumer (ActionExecutor) maps it straight
        # onto the screen.
        self.event_bus.publish(
            "pointer_position",
            {
                "x": effective_x,
                "y": effective_y,
                "source": "gesture"
            }
        )

    def _hand_scale(self, hand_landmarks):
        """Wrist-to-middle-MCP distance, a rough proxy for how big the
        hand looks in frame (i.e. how close the presenter is
        standing). Used as the unit _update_presentation_pointer
        measures its control box in.
        """

        wrist = hand_landmarks[0]
        middle_mcp = hand_landmarks[9]

        return math.hypot(
            middle_mcp.x - wrist.x,
            middle_mcp.y - wrist.y
        )

    def _update_presentation_pointer(self, hand_landmarks, index_tip):
        """Relative, distance-invariant pointer for Presentation mode.

        The moment Pointing_Up starts, the pointer snaps to the screen
        CENTER, and the presenter's hand size at that instant is
        frozen as the unit a PRESENTATION_POINTER_BOX_HANDS-wide
        virtual box (centered on the starting hand position) is
        measured in. Moving the hand across that box sweeps the
        pointer across the whole screen, so the same comfortable hand
        motion works whether presenting from 1m or 4m away — an
        absolute mapping would otherwise force a physically larger
        sweep the farther the presenter stands.

        Returns:
            (effective_x, effective_y) in 0..1 screen coordinates.
        """

        if self.presentation_pointer_anchor_x is None:

            self.presentation_pointer_anchor_x = index_tip.x
            self.presentation_pointer_anchor_y = index_tip.y

            self.presentation_pointer_hand_size = (
                self._hand_scale(hand_landmarks)
            )

            return 0.5, 0.5

        if self.presentation_pointer_hand_size <= 0:
            return 0.5, 0.5

        delta_x = (
            index_tip.x -
            self.presentation_pointer_anchor_x
        )

        delta_y = (
            index_tip.y -
            self.presentation_pointer_anchor_y
        )

        box_half_extent = (
            self.PRESENTATION_POINTER_BOX_HANDS
            * self.presentation_pointer_hand_size
            / 2
        )

        effective_x = 0.5 + delta_x / box_half_extent
        effective_y = 0.5 + delta_y / box_half_extent

        effective_x = min(1.0, max(0.0, effective_x))
        effective_y = min(1.0, max(0.0, effective_y))

        return effective_x, effective_y

    def _publish_static_gesture(
        self,
        gesture_name,
        confidence
    ):
        """Publish a confirmed static gesture as a gesture_signal.

        Applies the tracking-session gate, the Call-mode toggle
        gate/hold/lock, and the last_gesture repeat filter before
        publishing.
        """

        if gesture_name is None:
            return

        # While a motion-tracking session is running, the only gesture
        # that matters is the Closed_Fist that ends it. Everything
        # else (Open_Palm, or the classifier briefly flickering to
        # something else while the hand moves) is ignored, so
        # last_gesture stays frozen at "Open_Palm" and the Open_Palm
        # -> Closed_Fist end transition in _update_session keeps
        # working reliably.
        if (
            self.tracking_active
            and gesture_name != "Closed_Fist"
        ):
            return

        # ONE_FINGER/TWO_FINGERS/THREE_FINGERS/FOUR_FINGERS only ever
        # get produced by _read_call_finger_gesture while
        # active_mode == "call" (see _handle_frame) — this is a
        # defensive backstop, not the primary gate, so nothing
        # downstream can publish one of these names outside Call mode
        # even if the override above were ever bypassed.
        if (
            gesture_name in self.CALL_TOGGLE_GESTURES
            and self.active_mode != "call"
        ):
            return

        if gesture_name in self.CALL_TOGGLE_GESTURES:

            # Require a real, continuous hold — since the raw gesture
            # was first seen, not just since it crossed confirm_frames
            # — before a mic/camera/call-audio/background-blur toggle
            # is trusted enough to fire.
            held_seconds = (
                time.time() - self.candidate_start_time
                if self.candidate_start_time is not None
                else 0
            )

            if held_seconds < self.call_toggle_hold_seconds:
                return

            # Locked out on its own, independent of last_gesture below
            # — see locked_toggle_gestures in __init__ for why
            # last_gesture's ordinary same-as-before check isn't
            # enough on its own to stop a second toggle.
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

    def _publish_debug(
        self,
        frame,
        finger_position,
        gesture_name,
        confidence
    ):
        """Publish a gesture_debug snapshot for the calibration view."""

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
