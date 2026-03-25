import cv2
import mediapipe as mp
import numpy as np
import time
import os

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# === PATH ===
BASE_DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(BASE_DIR, "..", "models", "face_landmarker.task")

# === LOAD MODEL ===
base_options = python.BaseOptions(model_asset_path=MODEL_PATH)

options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.VIDEO,
    num_faces=1
)

landmarker = vision.FaceLandmarker.create_from_options(options)

# === CAMERA ===
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

prev_time = 0

def distance(p1, p2):
    return np.linalg.norm(np.array(p1) - np.array(p2))

while True:
    success, frame = cap.read()
    if not success:
        break

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    mp_image = mp.Image(
        image_format=mp.ImageFormat.SRGB,
        data=rgb
    )

    timestamp = int(time.time() * 1000)
    result = landmarker.detect_for_video(mp_image, timestamp)

    if result.face_landmarks:
        h, w, _ = frame.shape
        face = result.face_landmarks[0]

        # === DRAW LANDMARKS ===
        for lm in face:
            cx, cy = int(lm.x * w), int(lm.y * h)
            cv2.circle(frame, (cx, cy), 1, (0, 255, 0), -1)

        # === MOUTH (indices approximate) ===
        upper_lip = face[13]
        lower_lip = face[14]

        mouth_dist = distance(
            (upper_lip.x, upper_lip.y),
            (lower_lip.x, lower_lip.y)
        )

        mouth_state = "Open" if mouth_dist > 0.02 else "Closed"

        # === EYES ===
        left_eye_top = face[159]
        left_eye_bottom = face[145]

        eye_dist = distance(
            (left_eye_top.x, left_eye_top.y),
            (left_eye_bottom.x, left_eye_bottom.y)
        )

        eye_state = "Open" if eye_dist > 0.01 else "Closed"

        # === DISPLAY ===
        cv2.putText(frame, f'Mouth: {mouth_state}',
                    (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1, (0, 255, 0), 2)

        cv2.putText(frame, f'Eyes: {eye_state}',
                    (10, 80),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1, (255, 0, 0), 2)

    # === FPS ===
    current_time = time.time()
    fps = 1 / (current_time - prev_time) if current_time != prev_time else 0
    prev_time = current_time

    cv2.putText(frame, f'FPS: {int(fps)}',
                (10, 120),
                cv2.FONT_HERSHEY_SIMPLEX,
                1, (0, 0, 255), 2)

    cv2.imshow("Face Mesh: Eyes & Mouth", frame)

    if cv2.waitKey(1) == 27:
        break

cap.release()
cv2.destroyAllWindows()