"""Standalone manual test of MediaPipe's GestureRecognizer for detecting
directional hand swipes (up/down/left/right) from index-fingertip velocity,
run in isolation before this logic was wired into the main app.
"""

import cv2
import mediapipe as mp
import time

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

base_options = python.BaseOptions(
    model_asset_path=
    "models/gesture_recognizer.task"
)

options = vision.GestureRecognizerOptions(
    base_options=base_options,
    num_hands=1
)

recognizer = (
    vision.GestureRecognizer.create_from_options(
        options
    )
)

cap = cv2.VideoCapture(0)

if not cap.isOpened():

    print("Failed to open camera")

    exit()

previous_x = None
previous_y = None

previous_time = None

velocity_threshold = 1.2

last_motion_time = 0

motion_cooldown = 0.5

while True:

    ret, frame = cap.read()

    if not ret:
        continue

    # Mirror image so on-screen motion matches the user's own movement
    frame = cv2.flip(frame, 1)

    rgb_frame = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2RGB
    )

    mp_image = mp.Image(
        image_format=mp.ImageFormat.SRGB,
        data=rgb_frame
    )

    result = recognizer.recognize(
        mp_image
    )

    if not result.hand_landmarks:

        cv2.imshow(
            "Gesture Motion Test",
            frame
        )

        if cv2.waitKey(1) == ord("q"):
            break

        continue

    hand_landmarks = (
        result.hand_landmarks[0]
    )

    height, width, _ = frame.shape

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

    index_tip = hand_landmarks[8]

    current_x = index_tip.x
    current_y = index_tip.y

    draw_x = int(current_x * width)
    draw_y = int(current_y * height)

    cv2.circle(
        frame,
        (draw_x, draw_y),
        10,
        (0, 0, 255),
        -1
    )

    current_time = time.time()

    if (
        previous_x is not None
        and previous_y is not None
        and previous_time is not None
    ):

        delta_x = (
            current_x -
            previous_x
        )

        delta_y = (
            current_y -
            previous_y
        )

        delta_time = (
            current_time -
            previous_time
        )

        if delta_time > 0:

            velocity_x = (
                delta_x /
                delta_time
            )

            velocity_y = (
                delta_y /
                delta_time
            )

            cv2.putText(
                frame,
                f"VX: {velocity_x:.2f}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 255),
                2
            )

            cv2.putText(
                frame,
                f"VY: {velocity_y:.2f}",
                (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 255),
                2
            )

            cooldown_ready = (
                current_time -
                last_motion_time
            ) > motion_cooldown

            horizontal_motion = (
                abs(velocity_x) >
                abs(velocity_y)
            )

            if (
                velocity_x >
                velocity_threshold
                and horizontal_motion
                and cooldown_ready
            ):

                print("HAND RIGHT")

                cv2.putText(
                    frame,
                    "HAND RIGHT",
                    (20, 140),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    3
                )

                last_motion_time = (
                    current_time
                )

            elif (
                velocity_x <
                -velocity_threshold
                and horizontal_motion
                and cooldown_ready
            ):

                print("HAND LEFT")

                cv2.putText(
                    frame,
                    "HAND LEFT",
                    (20, 140),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    3
                )

                last_motion_time = (
                    current_time
                )

            elif (
                velocity_y >
                velocity_threshold
                and not horizontal_motion
                and cooldown_ready
            ):

                print("HAND DOWN")

                cv2.putText(
                    frame,
                    "HAND DOWN",
                    (20, 140),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    3
                )

                last_motion_time = (
                    current_time
                )

            elif (
                velocity_y <
                -velocity_threshold
                and not horizontal_motion
                and cooldown_ready
            ):

                print("HAND UP")

                cv2.putText(
                    frame,
                    "HAND UP",
                    (20, 140),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    3
                )

                last_motion_time = (
                    current_time
                )

    previous_x = current_x
    previous_y = current_y

    previous_time = current_time

    cv2.imshow(
        "Gesture Motion Test",
        frame
    )

    if cv2.waitKey(1) == ord("q"):
        break

cap.release()

cv2.destroyAllWindows()