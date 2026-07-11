import time

import cv2
import mediapipe as mp

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from config.config_loader import load_system_config


class GestureModel:

    def __init__(
        self,
        model_path=None
    ):

        gesture_model_config = load_system_config().get(
            "gesture_model",
            {}
        )

        if model_path is None:

            model_path = gesture_model_config.get(
                "model_path",
                "models/gesture_recognizer.task"
            )

        base_options = python.BaseOptions(
            model_asset_path=model_path
        )

        # num_hands is deliberately 1, not 2. MediaPipe's
        # GestureRecognizer task has a known bug where
        # num_hands > 1 combined with VIDEO running mode
        # corrupts its internal tensor-concatenation
        # calculator ("Packet isn't the sole owner of the
        # holder", inside multiplehandgesturerecognizergraph)
        # the first time two hands are actually detected in
        # the same frame — and the graph does not recover:
        # every frame after that fails identically, killing
        # gesture recognition entirely, not just the two-hand
        # feature. The off-hand needed for Cursor mode's
        # precision/zoom (§2.3.1 in docs) is tracked by a
        # completely separate model instead — see
        # OffHandModel below, which only needs landmarks, not
        # gesture classification, so it never touches the
        # buggy code path at all.
        options = vision.GestureRecognizerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=gesture_model_config.get(
                "min_hand_detection_confidence",
                0.5
            ),
            min_hand_presence_confidence=gesture_model_config.get(
                "min_hand_presence_confidence",
                0.5
            ),
            min_tracking_confidence=gesture_model_config.get(
                "min_tracking_confidence",
                0.5
            )
        )

        self.recognizer = (
            vision.GestureRecognizer.create_from_options(
                options
            )
        )

        self.start_time = time.time()

    def process_frame(self, frame):

        if frame is None:
            return None

        rgb_frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb_frame
        )

        # VIDEO mode lets MediaPipe track the hand across
        # frames instead of re-detecting the palm from
        # scratch every time, which is what made tracking
        # drop out on less palm-like shapes like a fist
        timestamp_ms = int(
            (time.time() - self.start_time) * 1000
        )

        result = self.recognizer.recognize_for_video(
            mp_image,
            timestamp_ms
        )

        return result

    def draw_landmarks(
        self,
        frame,
        hand_landmarks
    ):

        # Disabled for performance
        return frame


# ---------------------------------
# Off-Hand Model (Cursor Mode: precision + zoom)
# ---------------------------------

# A second, independent hand-tracking model — HandLandmarker,
# not GestureRecognizer — used only to find a SECOND hand in
# frame while the primary GestureModel (num_hands=1, above)
# tracks the primary one. HandLandmarker has no gesture
# classification step at all, so it never exercises the
# num_hands>1 concatenation bug documented above. It also runs
# in IMAGE mode rather than VIDEO: the off-hand's fist/zoom
# checks are single-frame geometric checks with no need for
# the cross-frame tracking continuity VIDEO mode provides.
class OffHandModel:

    def __init__(
        self,
        model_path=None
    ):

        gesture_model_config = load_system_config().get(
            "gesture_model",
            {}
        )

        if model_path is None:

            model_path = gesture_model_config.get(
                "off_hand_model_path",
                "models/hand_landmarker.task"
            )

        base_options = python.BaseOptions(
            model_asset_path=model_path
        )

        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_hands=2,
            min_hand_detection_confidence=gesture_model_config.get(
                "min_hand_detection_confidence",
                0.5
            ),
            min_hand_presence_confidence=gesture_model_config.get(
                "min_hand_presence_confidence",
                0.5
            ),
            min_tracking_confidence=gesture_model_config.get(
                "min_tracking_confidence",
                0.5
            )
        )

        self.landmarker = (
            vision.HandLandmarker.create_from_options(
                options
            )
        )

    def process_frame(self, frame):

        if frame is None:
            return None

        rgb_frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb_frame
        )

        return self.landmarker.detect(
            mp_image
        )