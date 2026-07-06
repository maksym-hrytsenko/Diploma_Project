import time

import cv2
import mediapipe as mp

from mediapipe.tasks import python
from mediapipe.tasks.python import vision


class GestureModel:

    def __init__(
        self,
        model_path="models/gesture_recognizer.task"
    ):

        base_options = python.BaseOptions(
            model_asset_path=model_path
        )

        options = vision.GestureRecognizerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5
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