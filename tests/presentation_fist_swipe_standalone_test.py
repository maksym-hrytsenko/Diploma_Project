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
# on its own for calibration. Once the
# trackbar values below look right on
# your own camera/presenting distance,
# copy the numbers into the matching
# presentation_fist_* constants in
# src/processing/gesture/gesture_recognizer.py.
#
# Unlike the index-finger swipe used by Flip mode
# (armed by a Closed_Fist -> Open_Palm transition),
# Presentation mode's slide-switch gesture needs no
# separate arm/disarm step: holding a closed fist IS
# the active state, and the WRIST (landmark 0) is
# tracked instead of a fingertip, since it stays
# reliably trackable even clenched and farther from
# the camera than desk-distance gestures were tuned
# for. Mirrors GestureRecognizer._check_fist_motion —
# simplified here by skipping its confirm_frames
# debounce, since this script's own trackbars are the
# thing being tuned, not the debounce.
#
# Also mirrors the laser-pointer behavior (Pointing_Up)
# from GestureRecognizer._update_presentation_pointer, so
# both Presentation-mode gestures — slide switching and
# the pointer — can be checked at actual presenting
# distance in one place. The pointer here is relative, not
# absolute: it snaps to the center the moment Pointing_Up
# starts, and hand movement from there is measured in
# units of the hand's own size at that instant, so the
# same physical movement sweeps the whole frame regardless
# of distance from the camera.
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

WINDOW_NAME = "Presentation Fist Swipe Standalone Test"

# ---------------------------------
# Default Thresholds (starting point —
# trackbars below let you drag these
# live, no code edits/restarts needed
# while tuning).
# ---------------------------------

# Calibrated against actual presenting distance using this
# script — see presentation_fist_velocity_threshold /
# presentation_fist_min_frame_distance in
# src/processing/gesture/gesture_recognizer.py, which now
# start from these same numbers.
DEFAULT_VELOCITY_THRESHOLD_X100 = 50
DEFAULT_MIN_FRAME_DISTANCE_X10000 = 75
DEFAULT_VERTICAL_CONE_DEGREES = 25
DEFAULT_MOTION_COOLDOWN_MS = 500

# How many hand-widths, centered on wherever Pointing_Up
# started, the presenter's hand has to cross to sweep the
# pointer across the whole preview — mirrors
# GestureRecognizer.PRESENTATION_POINTER_BOX_HANDS.
DEFAULT_POINTER_BOX_HANDS_X10 = 40

CONFIDENCE_THRESHOLD = 0.7

# Presentation mode's own mapping (config/fusion.json
# mode_rules) for the gesture-sourced swipe.
SLIDE_ACTIONS = {
    "HAND_RIGHT": "NEXT_SLIDE",
    "HAND_LEFT": "PREVIOUS_SLIDE"
}


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

    category = result.gestures[0][0]

    name = category.category_name

    confidence = category.score

    if name == "None":
        return None, None

    if confidence < CONFIDENCE_THRESHOLD:
        return None, None

    return name, confidence


# ---------------------------------
# Direction From Speed (mirrors
# GestureRecognizer._resolve_signal exactly —
# speed decides direction, distance only
# filters out landmark jitter)
# ---------------------------------

def resolve_signal(
    velocity_x,
    velocity_y,
    distance_x,
    distance_y,
    velocity_threshold,
    min_frame_distance,
    vertical_cone_degrees
):

    angle_from_vertical = math.degrees(
        math.atan2(
            abs(velocity_x),
            abs(velocity_y)
        )
    )

    vertical_motion = (
        angle_from_vertical <=
        vertical_cone_degrees
    )

    if (
        not vertical_motion
        and distance_x > min_frame_distance
    ):

        if velocity_x > velocity_threshold:
            return "HAND_LEFT"

        if velocity_x < -velocity_threshold:
            return "HAND_RIGHT"

    if (
        vertical_motion
        and distance_y > min_frame_distance
    ):

        if velocity_y > velocity_threshold:
            return "HAND_DOWN"

        if velocity_y < -velocity_threshold:
            return "HAND_UP"

    return None


# ---------------------------------
# Laser Pointer (Pointing_Up) — relative,
# hand-size-scaled box. Mirrors
# GestureRecognizer._update_presentation_pointer:
# the moment Pointing_Up starts, the pointer
# snaps to the center, and hand movement from
# there is measured in units of the hand size
# at that instant, so the same physical movement
# sweeps the whole frame regardless of distance
# from the camera.
# ---------------------------------

def hand_scale(hand_landmarks):

    wrist = hand_landmarks[0]
    middle_mcp = hand_landmarks[9]

    return math.hypot(
        middle_mcp.x - wrist.x,
        middle_mcp.y - wrist.y
    )


def reset_pointer():

    state["pointer_anchor_x"] = None
    state["pointer_anchor_y"] = None
    state["pointer_hand_size"] = None


def update_presentation_pointer(hand_landmarks, box_size_in_hands):

    index_tip = hand_landmarks[8]

    if state["pointer_anchor_x"] is None:

        state["pointer_anchor_x"] = index_tip.x
        state["pointer_anchor_y"] = index_tip.y

        state["pointer_hand_size"] = hand_scale(
            hand_landmarks
        )

        return 0.5, 0.5

    if state["pointer_hand_size"] <= 0:
        return 0.5, 0.5

    delta_x = index_tip.x - state["pointer_anchor_x"]
    delta_y = index_tip.y - state["pointer_anchor_y"]

    box_half_extent = (
        box_size_in_hands
        * state["pointer_hand_size"]
        / 2
    )

    effective_x = 0.5 + delta_x / box_half_extent
    effective_y = 0.5 + delta_y / box_half_extent

    effective_x = min(1.0, max(0.0, effective_x))
    effective_y = min(1.0, max(0.0, effective_y))

    return effective_x, effective_y


def draw_pointer(frame, hand_landmarks, box_size_in_hands):

    height, width = frame.shape[:2]

    effective_x, effective_y = update_presentation_pointer(
        hand_landmarks,
        box_size_in_hands
    )

    # Mirrors ui/pointer_overlay.py's MIRROR_X convention, so
    # the dot moves the same direction as the hand from the
    # user's own point of view.
    dot_point = (
        int((1.0 - effective_x) * width),
        int(effective_y * height)
    )

    if state["pointer_hand_size"]:

        # The virtual control box itself, drawn in the same
        # mirrored space as the dot — crossing its edge is
        # what reaches the frame's edge.
        box_half_extent = (
            box_size_in_hands
            * state["pointer_hand_size"]
            / 2
        )

        display_anchor_x = 1.0 - state["pointer_anchor_x"]
        display_anchor_y = state["pointer_anchor_y"]

        box_top_left = (
            int((display_anchor_x - box_half_extent) * width),
            int((display_anchor_y - box_half_extent) * height)
        )

        box_bottom_right = (
            int((display_anchor_x + box_half_extent) * width),
            int((display_anchor_y + box_half_extent) * height)
        )

        cv2.rectangle(
            frame,
            box_top_left,
            box_bottom_right,
            (200, 0, 200),
            1
        )

    # Magenta, deliberately distinct from the fist-tracking
    # wrist dot (which is red) so the two gestures' markers
    # are never mistaken for one another on screen.
    cv2.circle(
        frame,
        dot_point,
        14,
        (255, 0, 255),
        -1
    )

    cv2.putText(
        frame,
        "POINTER",
        (dot_point[0] + 18, dot_point[1] + 5),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 0, 255),
        2
    )


# ---------------------------------
# State
# ---------------------------------

state = {

    "previous_x": None,
    "previous_y": None,
    "previous_time": None,

    "velocity_x": 0.0,
    "velocity_y": 0.0,

    "last_motion_time": 0,

    "last_signal": None,
    "last_slide_action": None,

    "pointer_anchor_x": None,
    "pointer_anchor_y": None,
    "pointer_hand_size": None
}


def reset_baseline():

    state["previous_x"] = None
    state["previous_y"] = None
    state["previous_time"] = None


def check_fist_motion(
    is_closed_fist,
    wrist,
    velocity_threshold,
    min_frame_distance,
    vertical_cone_degrees,
    motion_cooldown
):

    if not is_closed_fist:

        # Hand relaxed (or lost) — the next fist starts a
        # fresh baseline instead of computing one big,
        # spurious delta across the gap.
        reset_baseline()

        return

    current_x = wrist.x
    current_y = wrist.y

    current_time = time.time()

    if (
        state["previous_x"] is None
        or state["previous_y"] is None
        or state["previous_time"] is None
    ):

        state["previous_x"] = current_x
        state["previous_y"] = current_y
        state["previous_time"] = current_time

        return

    delta_time = current_time - state["previous_time"]

    if delta_time <= 0:
        return

    delta_x = current_x - state["previous_x"]
    delta_y = current_y - state["previous_y"]

    velocity_x = delta_x / delta_time
    velocity_y = delta_y / delta_time

    state["velocity_x"] = velocity_x
    state["velocity_y"] = velocity_y

    signal = resolve_signal(
        velocity_x,
        velocity_y,
        abs(delta_x),
        abs(delta_y),
        velocity_threshold,
        min_frame_distance,
        vertical_cone_degrees
    )

    cooldown_ready = (
        current_time - state["last_motion_time"]
    ) > motion_cooldown

    if signal is not None and cooldown_ready:

        state["last_signal"] = signal

        state["last_slide_action"] = SLIDE_ACTIONS.get(
            signal,
            "(no slide action for this direction)"
        )

        state["last_motion_time"] = current_time

        print(
            "[GESTURE] {} (fist) -> {}".format(
                signal,
                state["last_slide_action"]
            )
        )

    state["previous_x"] = current_x
    state["previous_y"] = current_y
    state["previous_time"] = current_time


# ---------------------------------
# Drawing
# ---------------------------------

def draw_cone(display, anchor_point, cone_degrees):

    # Draws the actual UP/DOWN vs LEFT/RIGHT sector split
    # as 4 rays from the wrist, matching exactly the angle
    # resolve_signal decides on — same idea as
    # GestureDebugView._draw_cone_lines, applied to the
    # wrist instead of the fingertip anchor.
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
            int(anchor_point[0] + direction_x * 150),
            int(anchor_point[1] + direction_y * 150)
        )

        cv2.line(
            display,
            anchor_point,
            end_point,
            (0, 200, 200),
            1
        )


def draw_overlay(
    frame,
    gesture_name,
    confidence,
    wrist_point,
    velocity_threshold,
    min_frame_distance,
    vertical_cone_degrees,
    motion_cooldown
):

    height, width = frame.shape[:2]

    y = 25

    is_fist = gesture_name == "Closed_Fist"
    is_pointing = gesture_name == "Pointing_Up"

    if is_fist:
        gesture_color = (0, 255, 0)
    elif is_pointing:
        gesture_color = (255, 0, 255)
    else:
        gesture_color = (255, 255, 255)

    cv2.putText(
        frame,
        "gesture: {}  ({:.2f})".format(
            gesture_name,
            confidence or 0.0
        ),
        (10, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        gesture_color,
        2
    )

    y += 25

    cv2.putText(
        frame,
        "velocity x: {:6.2f}  y: {:6.2f}  (threshold {:.2f})".format(
            state["velocity_x"],
            state["velocity_y"],
            velocity_threshold
        ),
        (10, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2
    )

    y += 25

    cv2.putText(
        frame,
        "last signal: {}   slide action: {}".format(
            state["last_signal"],
            state["last_slide_action"]
        ),
        (10, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 255),
        2
    )

    y += 25

    cv2.putText(
        frame,
        "min_frame_distance: {:.3f}   cooldown: {:.2f}s   "
        "cone: {} deg".format(
            min_frame_distance,
            motion_cooldown,
            vertical_cone_degrees
        ),
        (10, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (200, 200, 200),
        1
    )

    if wrist_point is not None:

        pixel_point = (
            int(wrist_point.x * width),
            int(wrist_point.y * height)
        )

        cv2.circle(
            frame,
            pixel_point,
            10,
            (0, 0, 255) if is_fist else (150, 150, 150),
            -1
        )

        draw_cone(
            frame,
            pixel_point,
            vertical_cone_degrees
        )

    cv2.putText(
        frame,
        "closed fist + move L/R/U/D = slide signal   "
        "raise index finger = pointer   q: quit",
        (10, height - 15),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (200, 200, 200),
        1
    )


# ---------------------------------
# Trackbars
# ---------------------------------

cv2.namedWindow(WINDOW_NAME)

cv2.createTrackbar(
    "velocity threshold x100",
    WINDOW_NAME,
    DEFAULT_VELOCITY_THRESHOLD_X100,
    500,
    lambda value: None
)

cv2.createTrackbar(
    "min frame distance x10000",
    WINDOW_NAME,
    DEFAULT_MIN_FRAME_DISTANCE_X10000,
    1000,
    lambda value: None
)

cv2.createTrackbar(
    "vertical cone (deg)",
    WINDOW_NAME,
    DEFAULT_VERTICAL_CONE_DEGREES,
    90,
    lambda value: None
)

cv2.createTrackbar(
    "motion cooldown (ms)",
    WINDOW_NAME,
    DEFAULT_MOTION_COOLDOWN_MS,
    2000,
    lambda value: None
)

cv2.createTrackbar(
    "pointer box (hands x10)",
    WINDOW_NAME,
    DEFAULT_POINTER_BOX_HANDS_X10,
    100,
    lambda value: None
)


# ---------------------------------
# Camera Loop
# ---------------------------------

cap = cv2.VideoCapture(0)

if not cap.isOpened():

    print("Failed to open camera")

    raise SystemExit(1)

try:

    while True:

        velocity_threshold = cv2.getTrackbarPos(
            "velocity threshold x100",
            WINDOW_NAME
        ) / 100.0

        min_frame_distance = cv2.getTrackbarPos(
            "min frame distance x10000",
            WINDOW_NAME
        ) / 10000.0

        vertical_cone_degrees = cv2.getTrackbarPos(
            "vertical cone (deg)",
            WINDOW_NAME
        )

        motion_cooldown = cv2.getTrackbarPos(
            "motion cooldown (ms)",
            WINDOW_NAME
        ) / 1000.0

        pointer_box_hands = cv2.getTrackbarPos(
            "pointer box (hands x10)",
            WINDOW_NAME
        ) / 10.0

        ret, frame = cap.read()

        if not ret:
            continue

        result = recognize(frame)

        gesture_name, confidence = read_gesture(result)

        wrist_point = None

        if result.hand_landmarks:

            wrist_point = result.hand_landmarks[0][0]

            check_fist_motion(
                gesture_name == "Closed_Fist",
                wrist_point,
                velocity_threshold,
                min_frame_distance,
                vertical_cone_degrees,
                motion_cooldown
            )

        else:

            reset_baseline()

        if gesture_name != "Pointing_Up":

            reset_pointer()

        draw_overlay(
            frame,
            gesture_name,
            confidence,
            wrist_point,
            velocity_threshold,
            min_frame_distance,
            vertical_cone_degrees,
            motion_cooldown
        )

        if gesture_name == "Pointing_Up" and result.hand_landmarks:

            draw_pointer(
                frame,
                result.hand_landmarks[0],
                pointer_box_hands
            )

        cv2.imshow(WINDOW_NAME, frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:

    cap.release()

    cv2.destroyAllWindows()
