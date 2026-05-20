import cv2
import mediapipe as mp
import time

from mediapipe.tasks import python
from mediapipe.tasks.python import vision


# ---------------------------------
# MediaPipe Gesture Recognizer
# ---------------------------------

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

# ---------------------------------
# Open Camera
# ---------------------------------

cap = cv2.VideoCapture(0)

if not cap.isOpened():

    print("Failed to open camera")

    exit()

# ---------------------------------
# Motion Variables
# ---------------------------------

previous_x = None
previous_y = None

previous_time = None

velocity_threshold = 1.2

last_motion_time = 0

motion_cooldown = 0.5

# ---------------------------------
# Main Loop
# ---------------------------------

while True:

    ret, frame = cap.read()

    if not ret:
        continue

    # Mirror image
    frame = cv2.flip(frame, 1)

    # ---------------------------------
    # Convert Frame
    # ---------------------------------

    rgb_frame = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2RGB
    )

    mp_image = mp.Image(
        image_format=mp.ImageFormat.SRGB,
        data=rgb_frame
    )

    # ---------------------------------
    # Gesture Recognition
    # ---------------------------------

    result = recognizer.recognize(
        mp_image
    )

    # ---------------------------------
    # No Hand
    # ---------------------------------

    if not result.hand_landmarks:

        cv2.imshow(
            "Gesture Motion Test",
            frame
        )

        if cv2.waitKey(1) == ord("q"):
            break

        continue

    # ---------------------------------
    # Hand Landmarks
    # ---------------------------------

    hand_landmarks = (
        result.hand_landmarks[0]
    )

    height, width, _ = frame.shape

    # Draw landmarks
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

    # ---------------------------------
    # Index Finger
    # ---------------------------------

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

    # ---------------------------------
    # Time
    # ---------------------------------

    current_time = time.time()

    # ---------------------------------
    # Motion Detection
    # ---------------------------------

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

        # Avoid division by zero
        if delta_time > 0:

            velocity_x = (
                delta_x /
                delta_time
            )

            velocity_y = (
                delta_y /
                delta_time
            )

            # Debug text
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

            # ---------------------------------
            # RIGHT SWIPE
            # ---------------------------------

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

            # ---------------------------------
            # LEFT SWIPE
            # ---------------------------------

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

            # ---------------------------------
            # DOWN SWIPE
            # ---------------------------------

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

            # ---------------------------------
            # UP SWIPE
            # ---------------------------------

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

    # ---------------------------------
    # Save Previous Values
    # ---------------------------------

    previous_x = current_x
    previous_y = current_y

    previous_time = current_time

    # ---------------------------------
    # Show Window
    # ---------------------------------

    cv2.imshow(
        "Gesture Motion Test",
        frame
    )

    if cv2.waitKey(1) == ord("q"):
        break

# ---------------------------------
# Cleanup
# ---------------------------------

cap.release()

cv2.destroyAllWindows()