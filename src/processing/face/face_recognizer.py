import math
import time

from processing.face.face_model import (
    FaceModel
)


class FaceRecognizer:

    # Angular velocity (degrees/second) a pitch/yaw swing must
    # exceed to count as the first half of a deliberate nod or
    # shake — a slow, incidental head movement (reading text,
    # glancing around) should not trigger anything.
    NOD_VELOCITY_THRESHOLD = 80
    SHAKE_VELOCITY_THRESHOLD = 80

    # How long the return half of the swing has to arrive
    # after the first half to still count as one nod/shake,
    # and the minimum gap between two separate ones.
    NOD_PHASE_WINDOW = 0.6
    SHAKE_PHASE_WINDOW = 0.6

    NOD_COOLDOWN = 1.0
    SHAKE_COOLDOWN = 1.0

    # Roll magnitude (degrees) to enter a tilted zone, and to
    # return to neutral. The exit threshold is deliberately
    # lower than the enter threshold (hysteresis) so a roll
    # value sitting right at the boundary can't rapidly
    # flicker the zone back and forth.
    TILT_ENTER_DEGREES = 15
    TILT_EXIT_DEGREES = 8

    # Lowered 20% from the original 0.5/0.3 defaults after
    # hands-on calibration with tests/face_calibration_
    # standalone_test.py — the original values needed an
    # unnaturally exaggerated brow-raise/mouth-open/eye-close
    # to cross. Head tilt's thresholds were left unchanged;
    # only these three needed the adjustment.
    EYEBROWS_RAISE_THRESHOLD = 0.4
    EYEBROWS_LOWER_THRESHOLD = 0.24

    MOUTH_OPEN_THRESHOLD = 0.4
    MOUTH_CLOSE_THRESHOLD = 0.24

    BLINK_CLOSE_THRESHOLD = 0.4
    BLINK_OPEN_THRESHOLD = 0.24

    DOUBLE_BLINK_WINDOW = 0.5

    # Same "two within a window" idea as DOUBLE_BLINK, applied to
    # the eyebrows-raised rising edge instead of a blink. Slightly
    # more generous than DOUBLE_BLINK_WINDOW because deliberately
    # raising the eyebrows twice is a slower motion than blinking
    # twice.
    DOUBLE_EYEBROWS_WINDOW = 0.6

    def __init__(self, event_bus):

        self.event_bus = event_bus

        self.face_model = FaceModel()

        # ---------------------------------
        # Head-Pose Velocity Baseline
        # ---------------------------------

        # Previous frame's pitch/yaw (degrees), used only to
        # compute instantaneous angular velocity — the same
        # frame-to-frame velocity approach GestureRecognizer
        # uses for swipe detection, applied to head rotation
        # instead of fingertip position.
        self.previous_pitch = None
        self.previous_yaw = None
        self.previous_face_time = None

        # ---------------------------------
        # Nod (Confirm) / Shake (Cancel)
        # ---------------------------------

        # A nod/shake is a two-phase swing: a fast rotation
        # past the threshold in one direction (phase 1),
        # followed within *_PHASE_WINDOW by a fast rotation
        # back the other way (phase 2). Only the completed
        # round trip fires — a single fast glance in one
        # direction alone never does.
        self.nod_phase_sign = None
        self.nod_phase_time = 0
        self.last_nod_time = 0

        self.shake_phase_sign = None
        self.shake_phase_time = 0
        self.last_shake_time = 0

        # ---------------------------------
        # Head Tilt (direction selector)
        # ---------------------------------

        # "left"/"right"/None — which tilt zone the head is
        # currently in, so a held tilt fires once on entry
        # instead of repeatedly every frame.
        self.tilt_zone = None

        # ---------------------------------
        # Eyebrows (modifier)
        # ---------------------------------

        self.eyebrows_raised = False

        # Timestamp of the last EYEBROWS_UP rising edge, used only
        # to detect a second raise following within
        # DOUBLE_EYEBROWS_WINDOW — same pattern as last_blink_time
        # below, applied to the eyebrow instead of the eyelid.
        self.last_eyebrows_raise_time = 0

        # ---------------------------------
        # Mouth Open
        # ---------------------------------

        self.mouth_open = False

        # ---------------------------------
        # Double Blink (screenshot)
        # ---------------------------------

        self.eyes_closed = False

        self.last_blink_time = 0

        # Mirrored from SignalMapper's "mode_changed" event —
        # used to suppress head/face tracking entirely while
        # ANY mode is active (see start()/_handle_frame).
        self.active_mode = None

    # ---------------------------------
    # Start / Stop
    # ---------------------------------

    # Every signal here (nod/shake, tilt, eyebrows, mouth,
    # blink) is meant to work only from idle — i.e. no mode
    # (Flip, Presentation, Cursor, Call, Quick Circle) active.
    # Confirmed by hands-on testing that letting these keep
    # firing inside an active mode (e.g. incidental head
    # movement while swiping in Flip mode) reads as noise, not
    # a deliberate "global layer" action, even though the
    # Alt/Ctrl-gated rules in fusion.json (see docs §9.1) are
    # written as mode-independent — so tracking is suppressed
    # outright per-mode here (see _handle_frame) rather than
    # left to the consumer side.
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

    def _handle_frame(self, event):

        # Suppressed while any mode is active — not just
        # Cursor — so a mode's own gesture flow (e.g. Flip
        # mode's swipes) never gets a spurious CONFIRM/CANCEL/
        # HEAD_TILT/etc. reaction mixed in from incidental head
        # movement. These signals only mean anything from idle.
        if self.active_mode is not None:
            return

        frame = event.get("data")

        if frame is None:
            return

        result = self.face_model.process_frame(
            frame
        )

        if result is None:
            return

        if not result.face_landmarks:

            # Face lost — reset only the velocity baseline, so
            # reacquiring the face doesn't compute a huge,
            # meaningless spike from wherever the head last
            # was to wherever it is now. Everything else
            # (blink/mouth/eyebrow edge state, nod/shake phase)
            # is left as-is; a one-frame dropout is common and
            # shouldn't cancel a swing already in progress.
            self.previous_pitch = None
            self.previous_yaw = None
            self.previous_face_time = None

            self._publish_debug(
                frame,
                None,
                None,
                None,
                {}
            )

            return

        current_time = time.time()

        pitch, yaw, roll = self._head_pose(result)

        pitch_velocity, yaw_velocity = self._compute_angular_velocity(
            pitch,
            yaw,
            current_time
        )

        self._check_nod(
            current_time,
            pitch_velocity
        )

        self._check_shake(
            current_time,
            yaw_velocity
        )

        self._check_tilt(
            roll
        )

        blendshapes = self._blendshape_scores(
            result
        )

        self._check_eyebrows(
            blendshapes,
            current_time
        )

        self._check_mouth(
            blendshapes
        )

        self._check_blink(
            blendshapes,
            current_time
        )

        self._publish_debug(
            frame,
            pitch,
            yaw,
            roll,
            blendshapes
        )

    # ---------------------------------
    # Head Pose
    # ---------------------------------

    # Landmark index of each eye's OUTER corner in MediaPipe's
    # 468/478-point face mesh — used only for _compute_roll,
    # not the blendshape/matrix pipeline.
    RIGHT_EYE_OUTER_CORNER = 33
    LEFT_EYE_OUTER_CORNER = 263

    # Pitch/yaw: standard rotation-matrix -> Euler-angle
    # decomposition, unchanged. Nod/shake only ever look at
    # relative sign changes (a swing away then back), so they
    # are unaffected by the matrix's exact axis convention not
    # having been empirically verified against a real camera.
    #
    # Roll: NOT taken from the matrix decomposition anymore.
    # That decomposition assumes one specific Euler rotation
    # order (Z then Y then X); MediaPipe's actual matrix
    # convention doesn't necessarily match it, so the extracted
    # roll came out coupled with pitch/yaw instead of tracking
    # a pure sideways tilt — no threshold on a signal like that
    # can ever behave well, however it's tuned. Roll is instead
    # computed directly from the 2D angle between the two outer
    # eye corners in image space: on an upright face this line
    # is horizontal (roll ~ 0); tilting the head rotates it by
    # exactly the same angle the head physically tilted, with
    # no dependency on any 3D matrix convention at all — pure
    # 2D geometry, so it is the one number here guaranteed to
    # track physical head tilt cleanly.
    def _head_pose(self, result):

        if (
            not result.facial_transformation_matrixes
            or not result.face_landmarks
        ):
            return None, None, None

        matrix = result.facial_transformation_matrixes[0]

        rotation = matrix[:3, :3]

        pitch = math.degrees(
            math.atan2(
                -rotation[2, 0],
                math.sqrt(
                    rotation[0, 0] ** 2
                    + rotation[1, 0] ** 2
                )
            )
        )

        yaw = math.degrees(
            math.atan2(
                rotation[1, 0],
                rotation[0, 0]
            )
        )

        roll = self._compute_roll(
            result.face_landmarks[0]
        )

        return pitch, yaw, roll

    def _compute_roll(self, face_landmarks):

        right_eye = face_landmarks[self.RIGHT_EYE_OUTER_CORNER]
        left_eye = face_landmarks[self.LEFT_EYE_OUTER_CORNER]

        delta_x = left_eye.x - right_eye.x
        delta_y = left_eye.y - right_eye.y

        # Negated: confirmed by hands-on testing that the raw
        # atan2 value came out with the opposite sign from the
        # physical tilt direction (tilting the head to the
        # subject's own right produced a NEGATIVE angle, firing
        # HEAD_TILT_LEFT instead of HEAD_TILT_RIGHT). Negating
        # here is the correct fix — swapping which landmark is
        # called "left"/"right" instead would rotate the angle
        # by 180 degrees (atan2(-y, -x) != -atan2(y, x)), which
        # would wreck the roll ~ 0 upright baseline rather than
        # just flipping left vs right.
        return -math.degrees(
            math.atan2(
                delta_y,
                delta_x
            )
        )

    def _compute_angular_velocity(self, pitch, yaw, current_time):

        if pitch is None or yaw is None:
            return None, None

        if (
            self.previous_pitch is None
            or self.previous_face_time is None
        ):

            self.previous_pitch = pitch
            self.previous_yaw = yaw
            self.previous_face_time = current_time

            return None, None

        delta_time = current_time - self.previous_face_time

        if delta_time <= 0:
            return None, None

        pitch_velocity = (
            (pitch - self.previous_pitch) / delta_time
        )

        yaw_velocity = (
            (yaw - self.previous_yaw) / delta_time
        )

        self.previous_pitch = pitch
        self.previous_yaw = yaw
        self.previous_face_time = current_time

        return pitch_velocity, yaw_velocity

    # ---------------------------------
    # Nod (Confirm)
    # ---------------------------------

    def _check_nod(self, current_time, pitch_velocity):

        if pitch_velocity is None:
            return

        if current_time - self.last_nod_time < self.NOD_COOLDOWN:
            return

        fast = (
            abs(pitch_velocity) > self.NOD_VELOCITY_THRESHOLD
        )

        if self.nod_phase_sign is None:

            if fast:

                self.nod_phase_sign = (
                    1 if pitch_velocity > 0 else -1
                )

                self.nod_phase_time = current_time

            return

        if (
            current_time - self.nod_phase_time
            > self.NOD_PHASE_WINDOW
        ):

            self.nod_phase_sign = None

            return

        swing_sign = 1 if pitch_velocity > 0 else -1

        if fast and swing_sign != self.nod_phase_sign:

            self._fire_face_signal("CONFIRM")

            self.nod_phase_sign = None

            self.last_nod_time = current_time

    # ---------------------------------
    # Shake (Cancel)
    # ---------------------------------

    def _check_shake(self, current_time, yaw_velocity):

        if yaw_velocity is None:
            return

        if current_time - self.last_shake_time < self.SHAKE_COOLDOWN:
            return

        fast = (
            abs(yaw_velocity) > self.SHAKE_VELOCITY_THRESHOLD
        )

        if self.shake_phase_sign is None:

            if fast:

                self.shake_phase_sign = (
                    1 if yaw_velocity > 0 else -1
                )

                self.shake_phase_time = current_time

            return

        if (
            current_time - self.shake_phase_time
            > self.SHAKE_PHASE_WINDOW
        ):

            self.shake_phase_sign = None

            return

        swing_sign = 1 if yaw_velocity > 0 else -1

        if fast and swing_sign != self.shake_phase_sign:

            self._fire_face_signal("CANCEL")

            self.shake_phase_sign = None

            self.last_shake_time = current_time

    # ---------------------------------
    # Head Tilt (direction selector)
    # ---------------------------------

    def _check_tilt(self, roll):

        if roll is None:
            return

        if self.tilt_zone is None:

            if roll > self.TILT_ENTER_DEGREES:

                self.tilt_zone = "right"

                self._fire_face_signal("HEAD_TILT_RIGHT")

            elif roll < -self.TILT_ENTER_DEGREES:

                self.tilt_zone = "left"

                self._fire_face_signal("HEAD_TILT_LEFT")

        elif abs(roll) < self.TILT_EXIT_DEGREES:

            self.tilt_zone = None

    # ---------------------------------
    # Blendshapes (eyebrows, mouth, blink)
    # ---------------------------------

    def _blendshape_scores(self, result):

        if not result.face_blendshapes:
            return {}

        return {
            category.category_name: category.score
            for category in result.face_blendshapes[0]
        }

    def _check_eyebrows(self, blendshapes, current_time):

        score = blendshapes.get("browInnerUp", 0.0)

        if (
            not self.eyebrows_raised
            and score > self.EYEBROWS_RAISE_THRESHOLD
        ):

            self.eyebrows_raised = True

            self._fire_face_signal("EYEBROWS_UP")

            # A single raise fires nothing further — resting
            # the eyebrows naturally rises and falls sometimes.
            # Only a second raise completing within
            # DOUBLE_EYEBROWS_WINDOW of the first counts as the
            # deliberate double-raise used for the screenshot
            # trigger (§9.1), same idea as _check_blink below.
            if (
                current_time - self.last_eyebrows_raise_time
                <= self.DOUBLE_EYEBROWS_WINDOW
            ):

                self._fire_face_signal("DOUBLE_EYEBROWS_UP")

                # Reset rather than leaving it at current_time,
                # so a third raise right after doesn't chain
                # into a second DOUBLE_EYEBROWS_UP.
                self.last_eyebrows_raise_time = 0

            else:

                self.last_eyebrows_raise_time = current_time

        elif (
            self.eyebrows_raised
            and score < self.EYEBROWS_LOWER_THRESHOLD
        ):

            self.eyebrows_raised = False

            self._fire_face_signal("EYEBROWS_DOWN")

    # Fires once on the rising edge only (mouth opening) — the
    # example use case (pause/reset on Shift+Alt) is a single
    # trigger action, not a held modifier, so closing the mouth
    # again publishes nothing.
    def _check_mouth(self, blendshapes):

        score = blendshapes.get("jawOpen", 0.0)

        if (
            not self.mouth_open
            and score > self.MOUTH_OPEN_THRESHOLD
        ):

            self.mouth_open = True

            self._fire_face_signal("MOUTH_OPEN")

        elif (
            self.mouth_open
            and score < self.MOUTH_CLOSE_THRESHOLD
        ):

            self.mouth_open = False

    # A single blink publishes nothing — blinking is frequent
    # and involuntary, so only a second blink completing within
    # DOUBLE_BLINK_WINDOW of the first one fires anything.
    def _check_blink(self, blendshapes, current_time):

        left = blendshapes.get("eyeBlinkLeft", 0.0)
        right = blendshapes.get("eyeBlinkRight", 0.0)

        both_closed = (
            left > self.BLINK_CLOSE_THRESHOLD
            and right > self.BLINK_CLOSE_THRESHOLD
        )

        both_open = (
            left < self.BLINK_OPEN_THRESHOLD
            and right < self.BLINK_OPEN_THRESHOLD
        )

        if both_closed and not self.eyes_closed:

            self.eyes_closed = True

            return

        if both_open and self.eyes_closed:

            self.eyes_closed = False

            if (
                current_time - self.last_blink_time
                <= self.DOUBLE_BLINK_WINDOW
            ):

                self._fire_face_signal("DOUBLE_BLINK")

                # Reset rather than leaving it at current_time,
                # so a third blink right after doesn't chain
                # into a second DOUBLE_BLINK.
                self.last_blink_time = 0

            else:

                self.last_blink_time = current_time

    # ---------------------------------
    # Publish
    # ---------------------------------

    def _fire_face_signal(self, signal):

        self.event_bus.publish(
            "face_signal",
            {
                "signal": signal,
                "source": "face"
            }
        )

    # ---------------------------------
    # Debug Snapshot (for --debug-face calibration view)
    # ---------------------------------

    # Mirrors GestureRecognizer._publish_debug's approach: publish
    # every raw number a threshold is compared against, plus the
    # threshold itself, so FaceDebugView can render live values
    # next to the line they need to cross — that is what makes
    # tuning TILT_ENTER_DEGREES / EYEBROWS_RAISE_THRESHOLD /
    # MOUTH_OPEN_THRESHOLD against a real face and camera possible
    # instead of guessing from code alone.
    def _publish_debug(
        self,
        frame,
        pitch,
        yaw,
        roll,
        blendshapes
    ):

        self.event_bus.publish(
            "face_debug",
            {
                "frame": frame,

                "pitch": pitch,
                "yaw": yaw,
                "roll": roll,

                "tilt_zone": self.tilt_zone,
                "tilt_enter_degrees": self.TILT_ENTER_DEGREES,
                "tilt_exit_degrees": self.TILT_EXIT_DEGREES,

                "brow_inner_up": blendshapes.get(
                    "browInnerUp",
                    0.0
                ),
                "eyebrows_raised": self.eyebrows_raised,
                "eyebrows_raise_threshold": (
                    self.EYEBROWS_RAISE_THRESHOLD
                ),
                "eyebrows_lower_threshold": (
                    self.EYEBROWS_LOWER_THRESHOLD
                ),

                "jaw_open": blendshapes.get(
                    "jawOpen",
                    0.0
                ),
                "mouth_open": self.mouth_open,
                "mouth_open_threshold": (
                    self.MOUTH_OPEN_THRESHOLD
                ),
                "mouth_close_threshold": (
                    self.MOUTH_CLOSE_THRESHOLD
                ),

                "eye_blink_left": blendshapes.get(
                    "eyeBlinkLeft",
                    0.0
                ),
                "eye_blink_right": blendshapes.get(
                    "eyeBlinkRight",
                    0.0
                ),
                "eyes_closed": self.eyes_closed,
                "blink_close_threshold": (
                    self.BLINK_CLOSE_THRESHOLD
                ),
                "blink_open_threshold": (
                    self.BLINK_OPEN_THRESHOLD
                )
            }
        )
