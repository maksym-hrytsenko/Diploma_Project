"""MediaPipe-based head-pose and facial-expression gesture detection.

Consumes camera_frame events, runs FaceModel on each frame, and publishes
face_signal events (HEAD_TILT_LEFT/RIGHT, EYEBROWS_UP, MOUTH_OPEN) for
downstream fusion/mapping. Every one of these is gated behind a keyboard
modifier (Alt/Ctrl) in config/fusion.json, so this is a global layer that
works the same whether or not a gesture mode is active — it does not track
mode state itself.
"""

import math

from processing.face.face_model import (
    FaceModel
)


class FaceRecognizer:

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

    def __init__(self, event_bus):

        self.event_bus = event_bus

        self.face_model = FaceModel()

        # "left"/"right"/None — which tilt zone the head is currently in,
        # so a held tilt fires once on entry instead of every frame.
        self.tilt_zone = None

        self.eyebrows_raised = False

        self.mouth_open = False

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

            self._publish_debug(
                frame,
                None,
                None,
                None,
                {}
            )

            return

        pitch, yaw, roll = self._head_pose(result)

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

        self._publish_debug(
            frame,
            pitch,
            yaw,
            roll,
            blendshapes,
            face_landmarks=[
                (point.x, point.y) for point in result.face_landmarks[0]
            ]
        )

    # Landmark index of each eye's OUTER corner in MediaPipe's 468/478-point
    # face mesh — used only for _compute_roll, not the blendshape/matrix
    # pipeline.
    RIGHT_EYE_OUTER_CORNER = 33
    LEFT_EYE_OUTER_CORNER = 263

    # Pitch/yaw use the standard rotation-matrix -> Euler-angle
    # decomposition (kept only for the calibration debug overlay — neither
    # is consumed by a live signal here, see _check_tilt for the one that
    # is).
    #
    # Roll is NOT taken from that decomposition: it assumes one specific
    # Euler rotation order that MediaPipe's matrix doesn't necessarily
    # match, so the extracted roll came out coupled with pitch/yaw instead
    # of tracking a pure sideways tilt. Roll is instead computed directly
    # from the 2D angle between the two outer eye corners in image space —
    # horizontal on an upright face, rotating by exactly the angle the
    # head physically tilted, with no dependency on any 3D matrix
    # convention at all.
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

        # Negated: hands-on testing showed the raw atan2 value came out
        # with the opposite sign from the physical tilt direction
        # (tilting right produced a negative angle, firing
        # HEAD_TILT_LEFT). Negating is the correct fix — swapping which
        # landmark is "left"/"right" instead would rotate the angle by
        # 180 degrees (atan2(-y, -x) != -atan2(y, x)), wrecking the
        # roll ~ 0 upright baseline rather than just flipping left/right.
        return -math.degrees(
            math.atan2(
                delta_y,
                delta_x
            )
        )

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

            # Falling edge only resets the rising-edge latch so a
            # subsequent raise can fire EYEBROWS_UP again — nothing is
            # published for the lowering itself (no rule consumes it).
            self.eyebrows_raised = False

    # Fires once on the rising edge only (mouth opening) — the
    # example use case (pause/reset on Alt) is a single trigger action,
    # not a held modifier, so closing the mouth again publishes nothing.
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

    def _fire_face_signal(self, signal):

        self.event_bus.publish(
            "face_signal",
            {
                "signal": signal,
                "source": "face"
            }
        )

    # Mirrors GestureRecognizer._publish_debug's approach: publish every
    # raw number a threshold is compared against, plus the threshold
    # itself, so FaceDebugView can render live values next to the line
    # they need to cross for calibration against a real face and camera.
    def _publish_debug(
        self,
        frame,
        pitch,
        yaw,
        roll,
        blendshapes,
        face_landmarks=None
    ):

        self.event_bus.publish(
            "face_debug",
            {
                "frame": frame,

                "pitch": pitch,
                "yaw": yaw,
                "roll": roll,

                # Full set of MediaPipe face landmarks (normalized 0-1,
                # same convention as pitch/yaw/roll's own source data) —
                # None whenever the face is lost (the other _publish_debug
                # call site, line ~179, doesn't pass this). Consumed by
                # MainWindow's camera preview to draw every point the face
                # is tracked by, separately from the hand's own points.
                "face_landmarks": face_landmarks,

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
                )
            }
        )
