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

    EYEBROWS_RAISE_THRESHOLD = 0.5
    EYEBROWS_LOWER_THRESHOLD = 0.3

    MOUTH_OPEN_THRESHOLD = 0.5
    MOUTH_CLOSE_THRESHOLD = 0.3

    BLINK_CLOSE_THRESHOLD = 0.5
    BLINK_OPEN_THRESHOLD = 0.3

    DOUBLE_BLINK_WINDOW = 0.5

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

        # ---------------------------------
        # Mouth Open
        # ---------------------------------

        self.mouth_open = False

        # ---------------------------------
        # Double Blink (screenshot)
        # ---------------------------------

        self.eyes_closed = False

        self.last_blink_time = 0

    # ---------------------------------
    # Start / Stop
    # ---------------------------------

    # No mode gating anywhere in this class — unlike most of
    # GestureRecognizer's checks, every signal here is meant to
    # work "always", regardless of which mode (if any) is
    # active. Whatever consumes a given face_signal (e.g. the
    # Shift+Alt-held global rules in fusion.json) decides when
    # it actually means something.
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
            blendshapes
        )

        self._check_mouth(
            blendshapes
        )

        self._check_blink(
            blendshapes,
            current_time
        )

    # ---------------------------------
    # Head Pose (from the facial transformation matrix)
    # ---------------------------------

    # Standard rotation-matrix -> Euler-angle decomposition.
    # The transformation matrix's exact axis convention has not
    # been empirically verified against a real camera — pitch/
    # yaw/roll's absolute signs may come out flipped from what
    # "looks right". This only matters for the tilt-left/tilt-
    # right labeling below (_check_tilt); nod and shake both
    # work off relative sign changes (a swing away then back),
    # so they are unaffected either way.
    def _head_pose(self, result):

        if not result.facial_transformation_matrixes:
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

        roll = math.degrees(
            math.atan2(
                rotation[2, 1],
                rotation[2, 2]
            )
        )

        return pitch, yaw, roll

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

    def _check_eyebrows(self, blendshapes):

        score = blendshapes.get("browInnerUp", 0.0)

        if (
            not self.eyebrows_raised
            and score > self.EYEBROWS_RAISE_THRESHOLD
        ):

            self.eyebrows_raised = True

            self._fire_face_signal("EYEBROWS_UP")

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
