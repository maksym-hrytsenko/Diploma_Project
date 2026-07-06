import math
import os
import time

import cv2
import mediapipe as mp

from mediapipe.tasks import python
from mediapipe.tasks.python import vision


# ---------------------------------
# Standalone script. No imports from
# src/ — safe to copy, run and tweak
# on its own for calibration.
# ---------------------------------

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

MODEL_PATH = os.path.join(
    BASE_DIR,
    "..",
    "models",
    "gesture_recognizer.task"
)

CONFIDENCE_THRESHOLD = 0.7

# Minimum speed (per second, normalized coordinates) for a
# frame-to-frame movement to count as a deliberate swipe.
# This is the PRIMARY signal — direction is decided by how
# fast the finger is moving, not by distance from a fixed
# point.
VELOCITY_THRESHOLD = 1.8

# Per-frame movement below this is treated as landmark
# jitter, even if it briefly spikes the velocity reading
# (a tiny distance over a tiny time can look "fast").
MIN_FRAME_DISTANCE = 0.015

# The velocity vector counts as UP/DOWN only within this
# many degrees of straight vertical. Everything else —
# including diagonals — counts as LEFT/RIGHT, giving
# horizontal movement a much wider sector than vertical
# (previously the split was an implicit 45 degrees, from
# just comparing |velocity_x| against |velocity_y|).
# This is just the STARTING value — a trackbar in the
# window lets you drag it live, no code edits needed.
VERTICAL_CONE_DEGREES = 25

# How far (in pixels) the sector boundary lines are drawn
# from the anchor
CONE_LINE_LENGTH = 150

# Minimum time between two fired signals
MOTION_COOLDOWN = 0.5

# How long the marker holds still at the trigger point
# after a swipe fires, before it resumes following the
# finger live
FREEZE_DURATION = 0.3

# Visual size only, no effect on detection
MARKER_RADIUS = 40

# How many consecutive frames a gesture must hold before
# it counts as a real Closed_Fist <-> Open_Palm transition.
# A single misclassified frame (motion blur, odd angle)
# would otherwise end and immediately restart a session,
# re-anchoring the point to wherever the finger happens to
# be at that moment.
CONFIRM_FRAMES = 4

# How many consecutive frames the hand may be undetected
# before the session actually ends. Fast finger movement
# causes motion blur, which regularly makes MediaPipe miss
# the hand for a frame or two even though it never left
# the camera — without this grace period, that alone would
# end the session and re-anchor on the very swipes we care
# about most.
HAND_LOST_FRAMES = 5


# ---------------------------------
# MediaPipe Gesture Recognizer
# ---------------------------------

base_options = python.BaseOptions(
    model_asset_path=MODEL_PATH
)

options = vision.GestureRecognizerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.VIDEO,
    num_hands=1,
    min_hand_detection_confidence=0.5,
    min_hand_presence_confidence=0.5,
    min_tracking_confidence=0.5
)

recognizer = (
    vision.GestureRecognizer.create_from_options(
        options
    )
)

start_time = time.time()


def recognize(frame):

    rgb_frame = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2RGB
    )

    mp_image = mp.Image(
        image_format=mp.ImageFormat.SRGB,
        data=rgb_frame
    )

    timestamp_ms = int(
        (time.time() - start_time) * 1000
    )

    return recognizer.recognize_for_video(
        mp_image,
        timestamp_ms
    )


def read_gesture(result):

    if not result.gestures:
        return None, None

    gesture_category = (
        result.gestures[0][0]
    )

    gesture_name = (
        gesture_category.category_name
    )

    confidence = (
        gesture_category.score
    )

    if gesture_name == "None":
        return None, None

    if confidence < CONFIDENCE_THRESHOLD:
        return None, None

    return gesture_name, confidence


# ---------------------------------
# Session / Zone State
# ---------------------------------

state = {
    "last_gesture": None,

    "tracking_active": False,

    "anchor_x": None,
    "anchor_y": None,

    "previous_x": None,
    "previous_y": None,
    "previous_time": None,

    "last_motion_time": 0,
    "last_signal": None,

    "freeze_until": 0,

    "hand_lost_count": 0,

    "candidate_gesture": None,
    "candidate_count": 0,

    # Live value, dragged from the trackbar in the window
    "vertical_cone_degrees": VERTICAL_CONE_DEGREES,

    # Latest frame-to-frame velocity, kept only so the
    # overlay can draw exactly the vector resolve_signal
    # actually decided on
    "velocity_x": None,
    "velocity_y": None
}


def confirm_gesture(gesture_name):

    # Requires the same gesture on CONFIRM_FRAMES
    # consecutive frames before it is trusted. Filters out
    # one-frame misclassifications so a stray Closed_Fist
    # reading can't end a session by accident.

    if gesture_name is None:

        state["candidate_gesture"] = None
        state["candidate_count"] = 0

        return None

    if gesture_name == state["candidate_gesture"]:

        state["candidate_count"] += 1

    else:

        state["candidate_gesture"] = gesture_name
        state["candidate_count"] = 1

    if state["candidate_count"] >= CONFIRM_FRAMES:
        return gesture_name

    return None


def reset_session():

    state["tracking_active"] = False

    state["anchor_x"] = None
    state["anchor_y"] = None

    state["previous_x"] = None
    state["previous_y"] = None
    state["previous_time"] = None

    state["freeze_until"] = 0

    state["velocity_x"] = None
    state["velocity_y"] = None


def update_session(gesture_name):

    if gesture_name is None:
        return

    if gesture_name == state["last_gesture"]:
        return

    if (
        state["last_gesture"] == "Closed_Fist"
        and gesture_name == "Open_Palm"
    ):

        state["tracking_active"] = True

        state["anchor_x"] = None
        state["anchor_y"] = None

        state["previous_x"] = None
        state["previous_y"] = None
        state["previous_time"] = None

        state["freeze_until"] = 0

        state["velocity_x"] = None
        state["velocity_y"] = None

        # Set directly here, not left to the caller: once
        # tracking_active is True, the main loop ignores
        # every gesture except Closed_Fist, so it would
        # never get the chance to move last_gesture off
        # "Closed_Fist" — leaving the start condition true
        # on every following frame and re-anchoring each
        # time.
        state["last_gesture"] = "Open_Palm"

    elif (
        state["last_gesture"] == "Open_Palm"
        and gesture_name == "Closed_Fist"
    ):

        reset_session()

        state["last_gesture"] = "Closed_Fist"


def resolve_signal(
    velocity_x,
    velocity_y,
    distance_x,
    distance_y
):

    # Speed decides the direction. Distance only filters
    # out landmark jitter — it is not a "must travel this
    # far" zone.

    # 0 degrees = straight up/down, 90 degrees = straight
    # left/right
    angle_from_vertical = math.degrees(
        math.atan2(
            abs(velocity_x),
            abs(velocity_y)
        )
    )

    vertical_motion = (
        angle_from_vertical <=
        state["vertical_cone_degrees"]
    )

    if (
        not vertical_motion
        and distance_x > MIN_FRAME_DISTANCE
    ):

        if velocity_x > VELOCITY_THRESHOLD:
            return "HAND_LEFT"

        if velocity_x < -VELOCITY_THRESHOLD:
            return "HAND_RIGHT"

    if (
        vertical_motion
        and distance_y > MIN_FRAME_DISTANCE
    ):

        if velocity_y > VELOCITY_THRESHOLD:
            return "HAND_DOWN"

        if velocity_y < -VELOCITY_THRESHOLD:
            return "HAND_UP"

    return None


def fire_motion(signal, current_time, current_x, current_y):

    print(
        f"[SIGNAL] {signal}"
    )

    state["last_motion_time"] = current_time
    state["last_signal"] = signal

    # Freeze the marker at the trigger point briefly, for
    # visual feedback, then let it resume following the
    # finger live
    state["anchor_x"] = current_x
    state["anchor_y"] = current_y

    state["freeze_until"] = (
        current_time +
        FREEZE_DURATION
    )


def check_motion(hand_landmarks):

    if not state["tracking_active"]:
        return

    # Index fingertip
    index_tip = hand_landmarks[8]

    current_x = index_tip.x
    current_y = index_tip.y

    current_time = time.time()

    # First frame of the session: nothing to compare
    # against yet, just seed the anchor and previous values
    if (
        state["previous_x"] is None
        or state["previous_y"] is None
        or state["previous_time"] is None
    ):

        state["anchor_x"] = current_x
        state["anchor_y"] = current_y

        state["previous_x"] = current_x
        state["previous_y"] = current_y

        state["previous_time"] = current_time

        return

    delta_time = (
        current_time -
        state["previous_time"]
    )

    if delta_time > 0:

        delta_x = (
            current_x -
            state["previous_x"]
        )

        delta_y = (
            current_y -
            state["previous_y"]
        )

        velocity_x = delta_x / delta_time

        velocity_y = delta_y / delta_time

        state["velocity_x"] = velocity_x
        state["velocity_y"] = velocity_y

        signal = resolve_signal(
            velocity_x,
            velocity_y,
            abs(delta_x),
            abs(delta_y)
        )

        cooldown_ready = (
            current_time -
            state["last_motion_time"]
        ) > MOTION_COOLDOWN

        if signal is not None and cooldown_ready:

            fire_motion(
                signal,
                current_time,
                current_x,
                current_y
            )

    # Follow the finger live, except during the brief
    # freeze right after a trigger — fire_motion already
    # placed the marker at the trigger point this frame, so
    # this check keeps it there instead of immediately
    # snapping back to "current position" in the same frame
    if current_time >= state["freeze_until"]:

        state["anchor_x"] = current_x
        state["anchor_y"] = current_y

    state["previous_x"] = current_x
    state["previous_y"] = current_y

    state["previous_time"] = current_time


# ---------------------------------
# Drawing
# ---------------------------------

def to_pixels(x, y, width, height):

    return (
        int(x * width),
        int(y * height)
    )


def draw_cone_lines(frame, anchor_point):

    # Draws the actual UP/DOWN vs LEFT/RIGHT sector split
    # as 4 rays from the anchor, so the cone angle can be
    # seen (and tuned via the trackbar) directly on screen.

    cone_degrees = state["vertical_cone_degrees"]

    cone_radians = math.radians(cone_degrees)

    dx = math.sin(cone_radians)
    dy = math.cos(cone_radians)

    directions = [
        (dx, -dy),
        (-dx, -dy),
        (dx, dy),
        (-dx, dy)
    ]

    for direction_x, direction_y in directions:

        end_point = (
            int(
                anchor_point[0] +
                direction_x * CONE_LINE_LENGTH
            ),
            int(
                anchor_point[1] +
                direction_y * CONE_LINE_LENGTH
            )
        )

        cv2.line(
            frame,
            anchor_point,
            end_point,
            (0, 200, 200),
            1
        )

    cv2.putText(
        frame,
        "{} deg".format(cone_degrees),
        (
            anchor_point[0] + 10,
            anchor_point[1] - MARKER_RADIUS - 10
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0, 200, 200),
        1
    )


def draw_overlay(frame, hand_landmarks, gesture_name):

    height, width = frame.shape[:2]

    if hand_landmarks is not None:

        for landmark in hand_landmarks:

            point = to_pixels(
                landmark.x,
                landmark.y,
                width,
                height
            )

            cv2.circle(
                frame,
                point,
                3,
                (0, 255, 0),
                -1
            )

        index_tip = hand_landmarks[8]

        finger_point = to_pixels(
            index_tip.x,
            index_tip.y,
            width,
            height
        )

        cv2.circle(
            frame,
            finger_point,
            10,
            (0, 255, 0),
            -1
        )

    if (
        state["anchor_x"] is not None
        and state["anchor_y"] is not None
    ):

        anchor_point = to_pixels(
            state["anchor_x"],
            state["anchor_y"],
            width,
            height
        )

        # Follows the finger live; freezes briefly at the
        # trigger point right after a swipe fires — purely
        # a visual reference now, not a threshold boundary
        cv2.circle(
            frame,
            anchor_point,
            MARKER_RADIUS,
            (0, 165, 255),
            2
        )

        cv2.circle(
            frame,
            anchor_point,
            4,
            (0, 0, 255),
            -1
        )

        draw_cone_lines(
            frame,
            anchor_point
        )

        if hand_landmarks is not None:

            index_tip = hand_landmarks[8]

            finger_point = to_pixels(
                index_tip.x,
                index_tip.y,
                width,
                height
            )

            cv2.line(
                frame,
                anchor_point,
                finger_point,
                (255, 255, 0),
                2
            )

    lines = [
        "gesture: {}".format(gesture_name),
        "last_gesture: {}".format(state["last_gesture"]),
        "session active: {}".format(state["tracking_active"]),
        "last signal: {}".format(state["last_signal"])
    ]

    y = 30

    for line in lines:

        cv2.putText(
            frame,
            line,
            (10, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        y += 30

    cv2.putText(
        frame,
        "start: fist then open hand   "
        "end: open hand then fist, or hand leaves frame   "
        "q: quit",
        (10, height - 15),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (200, 200, 200),
        1
    )


# ---------------------------------
# Camera Loop
# ---------------------------------

cap = cv2.VideoCapture(0)

if not cap.isOpened():

    print("Failed to open camera")

    raise SystemExit(1)

WINDOW_NAME = "Gesture Joystick Standalone Test"

cv2.namedWindow(WINDOW_NAME)

cv2.createTrackbar(
    "cone (deg)",
    WINDOW_NAME,
    VERTICAL_CONE_DEGREES,
    90,
    lambda value: None
)

try:

    while True:

        state["vertical_cone_degrees"] = cv2.getTrackbarPos(
            "cone (deg)",
            WINDOW_NAME
        )

        ret, frame = cap.read()

        if not ret:
            continue

        result = recognize(frame)

        gesture_name, confidence = read_gesture(
            result
        )

        if not result.hand_landmarks:

            state["hand_lost_count"] += 1

            # Brief dropouts (motion blur during a fast
            # swipe) are ignored — the session and its
            # anchor stay exactly as they were. Only a
            # sustained absence counts as "hand removed".
            if state["hand_lost_count"] >= HAND_LOST_FRAMES:

                reset_session()

                # Require a fresh Closed_Fist -> Open_Palm
                # sequence after the hand comes back
                state["last_gesture"] = None

                # Fresh debounce window once the hand
                # returns
                confirm_gesture(None)

            draw_overlay(frame, None, gesture_name)

            cv2.imshow(WINDOW_NAME, frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

            continue

        state["hand_lost_count"] = 0

        hand_landmarks = result.hand_landmarks[0]

        # Only a gesture held for CONFIRM_FRAMES straight
        # frames is trusted for session start/end — the
        # raw, possibly noisy gesture_name is still shown
        # on screen below for visibility
        confirmed_gesture = confirm_gesture(gesture_name)

        update_session(confirmed_gesture)

        check_motion(hand_landmarks)

        # Static gesture is only tracked/printed here for
        # calibration visibility. While a motion session is
        # running, only Closed_Fist matters (it ends the
        # session) — everything else is ignored so
        # last_gesture stays frozen at "Open_Palm" and the
        # end transition keeps working reliably.
        if confirmed_gesture is not None:

            ignore_during_session = (
                state["tracking_active"]
                and confirmed_gesture != "Closed_Fist"
            )

            if (
                not ignore_during_session
                and confirmed_gesture != state["last_gesture"]
            ):

                print(
                    f"[GESTURE] {confirmed_gesture} "
                    f"({confidence:.2f})"
                )

                state["last_gesture"] = confirmed_gesture

        draw_overlay(frame, hand_landmarks, gesture_name)

        cv2.imshow(WINDOW_NAME, frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:

    cap.release()

    cv2.destroyAllWindows()
