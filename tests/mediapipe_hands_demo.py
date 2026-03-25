import cv2
import mediapipe as mp
import time

# Import new MediaPipe Tasks API
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Load hand landmarker model
base_options = python.BaseOptions(model_asset_path='models/hand_landmarker.task')

options = vision.HandLandmarkerOptions(
    base_options=base_options,
    num_hands=1,
    min_hand_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

landmarker = vision.HandLandmarker.create_from_options(options)

cap = cv2.VideoCapture(0)

prev_time = 0

while True:
    success, frame = cap.read()
    if not success:
        break

    frame = cv2.flip(frame, 1)

    # Convert frame to RGB
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Convert to MediaPipe Image
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

    # Detect hands
    result = landmarker.detect(mp_image)

    if result.hand_landmarks:
        h, w, _ = frame.shape

        for hand_landmarks in result.hand_landmarks:
            for idx, lm in enumerate(hand_landmarks):
                cx, cy = int(lm.x * w), int(lm.y * h)

                # Draw all landmarks
                cv2.circle(frame, (cx, cy), 5, (0, 255, 0), cv2.FILLED)

                # Highlight index finger tip (id=8)
                if idx == 8:
                    cv2.circle(frame, (cx, cy), 10, (0, 0, 255), cv2.FILLED)
                    cv2.putText(frame, f'Index: {cx}, {cy}',
                                (cx + 10, cy - 10),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.7, (0, 0, 255), 2)

    # FPS calculation
    current_time = time.time()
    fps = 1 / (current_time - prev_time) if current_time != prev_time else 0
    prev_time = current_time

    cv2.putText(frame, f'FPS: {int(fps)}',
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1, (255, 0, 0), 2)

    cv2.putText(frame, 'Press S to save frame',
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (255, 255, 255), 2)

    cv2.imshow("MediaPipe Tasks Hands", frame)

    key = cv2.waitKey(1)

    if key == ord('s'):
        cv2.imwrite("hand_tasks_result.png", frame)
        print("Saved: hand_tasks_result.png")

    if key == 27:
        break

cap.release()
cv2.destroyAllWindows()