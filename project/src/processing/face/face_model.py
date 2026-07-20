"""MediaPipe FaceLandmarker wrapper.

Thin adapter around MediaPipe's face-landmarker task: converts a BGR camera
frame to the format the model expects and runs it in VIDEO mode, returning
head-pose landmarks, the facial transformation matrix, and blendshape
scores. Used by FaceRecognizer, which owns all detection/threshold logic.
"""

import time

import cv2
import mediapipe as mp

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from config.config_loader import resolve_model_path


class FaceModel:

    def __init__(
        self,
        model_path: str = "models/face_landmarker.task"
    ):

        model_path = resolve_model_path(
            model_path
        )

        base_options = python.BaseOptions(
            model_asset_path=model_path
        )

        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True
        )

        self.landmarker = (
            vision.FaceLandmarker.create_from_options(
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

        # VIDEO mode lets MediaPipe track the face across frames instead of
        # re-detecting it from scratch every time (same reasoning as
        # GestureModel).
        timestamp_ms = int(
            (time.time() - self.start_time) * 1000
        )

        result = self.landmarker.detect_for_video(
            mp_image,
            timestamp_ms
        )

        return result
