import math
import time

from processing.gesture.gesture_model import (
    GestureModel
)


class GestureRecognizer:

    def __init__(self, event_bus):

        self.event_bus = event_bus

        self.gesture_model = GestureModel()

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

    def start(self):

        self.event_bus.subscribe(
            "camera_frame",
            self._handle_frame
        )

    def stop(self):

        self.event_bus.unsubscribe(
            "camera_frame",
            self._handle_frame
        )

    def _handle_frame(self, event):

        frame = event.get("data")

        if frame is None:
            return

        # ---------------------------------
        # Process Frame
        # ---------------------------------

        result = self.gesture_model.process_frame(
            frame
        )

        if result is None:
            return

        gesture_name, confidence = self._read_gesture(
            result
        )

        # ---------------------------------
        # Hand Lost
        # ---------------------------------

        if not result.hand_landmarks:

            self._handle_hand_lost(
                frame,
                gesture_name,
                confidence
            )

            return

        self.hand_lost_count = 0

        # Only a gesture held for confirm_frames straight
        # frames is trusted for session start/end — the
        # raw, possibly noisy gesture_name is still used
        # below for pointer tracking and the debug overlay
        confirmed_gesture = self._confirm_gesture(
            gesture_name
        )

        self._update_session(
            confirmed_gesture
        )

        self._check_motion(
            result
        )

        self._update_pointer(
            gesture_name,
            result
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

            return None

        if gesture_name == self.candidate_gesture:

            self.candidate_count += 1

        else:

            self.candidate_gesture = gesture_name
            self.candidate_count = 1

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
    # Pointer Tracking
    # ---------------------------------

    def _update_pointer(self, gesture_name, result):

        if gesture_name != "Pointing_Up":
            return

        hand_landmarks = (
            result.hand_landmarks[0]
        )

        index_tip = hand_landmarks[8]

        self.event_bus.publish(
            "pointer_position",
            {
                "x": index_tip.x,
                "y": index_tip.y,
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

        if gesture_name == self.last_gesture:
            return

        self.last_gesture = gesture_name

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
