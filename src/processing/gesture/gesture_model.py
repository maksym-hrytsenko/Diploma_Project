import cv2
import mediapipe as mp

from mediapipe.tasks import python
from mediapipe.tasks.python import vision


class GestureModel:
    def __init__(self,
                 model_path="models/gesture_recognizer.task"):

        base_options = python.BaseOptions(
            model_asset_path=model_path
        )

        options = vision.GestureRecognizerOptions(
            base_options=base_options,
            num_hands=1
        )

        self.recognizer = vision.GestureRecognizer.create_from_options(
            options
        )

    def process_frame(self, frame):
        if frame is None:
            return None

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb_frame
        )

        result = self.recognizer.recognize(mp_image)

        return result

    def draw_landmarks(self, frame, hand_landmarks):
        if frame is None or hand_landmarks is None:
            return frame

        height, width, _ = frame.shape

        # Draw points
        for landmark in hand_landmarks:
            x = int(landmark.x * width)
            y = int(landmark.y * height)

            cv2.circle(
                frame,
                (x, y),
                5,
                (0, 255, 0),
                -1
            )

        return frame