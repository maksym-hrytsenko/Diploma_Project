import cv2
import mediapipe as mp
import time
import os

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# === PATH ===
BASE_DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(BASE_DIR, "..", "models", "gesture_recognizer.task")

# === LOAD MODEL ===
base_options = python.BaseOptions(model_asset_path=MODEL_PATH)

options = vision.GestureRecognizerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.VIDEO,
    num_hands=1
)

recognizer = vision.GestureRecognizer.create_from_options(options)

# === CAMERA ===
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

if not cap.isOpened():
    print("ERROR: Camera not opened")
    exit()

prev_time = 0

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

    # === RECOGNITION ===

    timestamp = int(time.time() * 1000)
    result = recognizer.recognize_for_video(mp_image, timestamp)

    if result.gestures:
        gesture = result.gestures[0][0]

        name = gesture.category_name
        score = gesture.score

        cv2.putText(frame,
                    f'{name} ({score:.2f})',
                    (10, 80),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2)

    # === FPS ===
    current_time = time.time()
    fps = 1 / (current_time - prev_time) if current_time != prev_time else 0
    prev_time = current_time

    cv2.putText(frame,
                f'FPS: {int(fps)}',
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 0, 0),
                2)

    cv2.imshow("Gesture Recognizer", frame)

    if cv2.waitKey(1) == 27:
        break

cap.release()
cv2.destroyAllWindows()