import math
import os
import threading
import time

import cv2
import mediapipe as mp
import pyautogui

from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from pynput import keyboard


# ---------------------------------
# Standalone script. No imports from
# src/ — safe to copy, run and tweak
# on its own for calibration. Once the
# trackbar values below look right on
# your own camera/face/lighting, copy
# the numbers into the matching
# constants in
# src/processing/face/face_recognizer.py
# (and src/processing/face/face_debug_view.py
# has no thresholds of its own to update —
# it only ever displays whatever
# FaceRecognizer publishes).
#
# Nod/shake (CONFIRM/CANCEL) are deliberately
# left out of this test — they are reserved,
# unbound features unrelated to the head-tilt/
# eyebrows/mouth media-control use case this
# script is for calibrating.
# ---------------------------------

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

MODEL_PATH = os.path.join(
    BASE_DIR,
    "..",
    "models",
    "face_landmarker.task"
)

WINDOW_NAME = "Face Calibration Standalone Test"

# ---------------------------------
# Default Thresholds (starting point —
# trackbars below let you drag these
# live, no code edits/restarts needed
# while tuning)
# ---------------------------------

DEFAULT_TILT_ENTER_DEGREES = 15
DEFAULT_TILT_EXIT_DEGREES = 8

# Blendshape scores are 0.0-1.0; trackbars are integer-only,
# so every *_X100 value here is the real threshold times 100
# (e.g. 50 -> 0.50). Lowered 20% from the original 50/30
# defaults — confirmed by hands-on calibration to need less
# exaggerated brow-raise/mouth-open/eye-close than that to
# cross reliably; already carried over into
# src/processing/face/face_recognizer.py.
DEFAULT_EYEBROWS_RAISE_X100 = 40
DEFAULT_EYEBROWS_LOWER_X100 = 24
DEFAULT_DOUBLE_EYEBROWS_WINDOW_MS = 600

DEFAULT_MOUTH_OPEN_X100 = 40
DEFAULT_MOUTH_CLOSE_X100 = 24

DEFAULT_BLINK_CLOSE_X100 = 40
DEFAULT_BLINK_OPEN_X100 = 24
DEFAULT_DOUBLE_BLINK_WINDOW_MS = 500

BAR_WIDTH = 220
BAR_HEIGHT = 14


# ---------------------------------
# MediaPipe Face Landmarker
# ---------------------------------

base_options = python.BaseOptions(
    model_asset_path=MODEL_PATH
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

landmarker = (
    vision.FaceLandmarker.create_from_options(
        options
    )
)

start_time = time.time()


def detect(frame):

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

    return landmarker.detect_for_video(
        mp_image,
        timestamp_ms
    )


# Landmark index of each eye's OUTER corner in MediaPipe's
# 468/478-point face mesh, used only by compute_roll below.
RIGHT_EYE_OUTER_CORNER = 33
LEFT_EYE_OUTER_CORNER = 263


def compute_roll(face_landmarks):

    # Pure 2D geometry: the angle of the line between the two
    # outer eye corners in image space. Horizontal (~0 deg) on
    # an upright face; rotates by exactly the angle the head
    # physically tilts, with no 3D matrix convention involved —
    # see the matching comment in
    # src/processing/face/face_recognizer.py's _compute_roll
    # for why the matrix-decomposition roll was replaced with
    # this.
    right_eye = face_landmarks[RIGHT_EYE_OUTER_CORNER]
    left_eye = face_landmarks[LEFT_EYE_OUTER_CORNER]

    delta_x = left_eye.x - right_eye.x
    delta_y = left_eye.y - right_eye.y

    # Negated — see the matching comment in FaceRecognizer._compute_roll
    # for why (confirmed by testing to have the opposite sign from the
    # physical tilt direction).
    return -math.degrees(
        math.atan2(
            delta_y,
            delta_x
        )
    )


def head_pose(result):

    if (
        not result.facial_transformation_matrixes
        or not result.face_landmarks
    ):
        return None, None, None

    matrix = result.facial_transformation_matrixes[0]

    rotation = matrix[:3, :3]

    pitch = math.degrees(
        math.atan2(
            -rotation[2, 0],
            math.sqrt(
                rotation[0, 0] ** 2
                + rotation[1, 0] ** 2
            )
        )
    )

    yaw = math.degrees(
        math.atan2(
            rotation[1, 0],
            rotation[0, 0]
        )
    )

    roll = compute_roll(
        result.face_landmarks[0]
    )

    return pitch, yaw, roll


def blendshape_scores(result):

    if not result.face_blendshapes:
        return {}

    return {
        category.category_name: category.score
        for category in result.face_blendshapes[0]
    }


# ---------------------------------
# Alt Hold Tracking (pynput, same
# mechanism as
# src/input/keyboard_input.py +
# src/processing/keyboard/keyboard_processor.py)
# ---------------------------------

held_keys = set()
held_lock = threading.Lock()


def key_name(key):

    try:

        if isinstance(key, keyboard.Key):

            name = str(key).replace("Key.", "")

            if name in ("alt_l", "alt_r"):
                return "alt"

            if name in ("shift_l", "shift_r"):
                return "shift"

            return name

    except Exception:
        pass

    return None


def on_press(key):

    name = key_name(key)

    if name is None:
        return

    with held_lock:
        held_keys.add(name)


def on_release(key):

    name = key_name(key)

    if name is None:
        return

    with held_lock:
        held_keys.discard(name)


def alt_held():

    with held_lock:

        return "alt" in held_keys


keyboard_listener = keyboard.Listener(
    on_press=on_press,
    on_release=on_release
)

keyboard_listener.start()


# ---------------------------------
# OS Actions (same mechanism as
# src/execution/os_controller.py,
# copied inline so this script has
# no dependency on src/)
# ---------------------------------

NX_KEYTYPE_PLAY = 16
NX_KEYTYPE_NEXT = 17
NX_KEYTYPE_PREVIOUS = 18


def post_system_media_key(nx_keytype):

    try:

        from AppKit import NSEvent
        import Quartz

        def post(key_down):

            flags = 0xa00 if key_down else 0xb00

            data1 = (
                (nx_keytype << 16)
                | ((0xa if key_down else 0xb) << 8)
            )

            event = (
                NSEvent
                .otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
                    Quartz.NSSystemDefined,
                    (0, 0),
                    flags,
                    0,
                    0,
                    0,
                    8,
                    data1,
                    -1
                )
            )

            Quartz.CGEventPost(
                Quartz.kCGHIDEventTap,
                event.CGEvent()
            )

        post(True)
        post(False)

    except Exception as e:

        print(
            f"[MEDIA ERROR] {e}"
        )


def media_play_pause():

    post_system_media_key(NX_KEYTYPE_PLAY)


def next_track():

    post_system_media_key(NX_KEYTYPE_NEXT)


def previous_track():

    post_system_media_key(NX_KEYTYPE_PREVIOUS)


def take_screenshot():

    pyautogui.hotkey("command", "shift", "3")


# ---------------------------------
# Face Signal State
# ---------------------------------

state = {

    "tilt_zone": None,

    "eyebrows_raised": False,
    "last_eyebrows_raise_time": 0,

    "mouth_open": False,

    "eyes_closed": False,
    "last_blink_time": 0,

    "last_signal": None,
    "last_action": None
}


def fire_face_signal(signal):

    print(
        f"[FACE] {signal}"
    )

    state["last_signal"] = signal

    # Mirrors the Alt face-layer rules in config/fusion.json
    # exactly — held Alt plus a face signal fires the same real
    # OS action the full app would, so this test doubles as an
    # end-to-end check of the actions themselves, not just the
    # detection.
    if not alt_held():

        state["last_action"] = None

        return

    if signal == "HEAD_TILT_RIGHT":

        next_track()

        state["last_action"] = "NEXT_TRACK"

    elif signal == "HEAD_TILT_LEFT":

        previous_track()

        state["last_action"] = "PREVIOUS_TRACK"

    elif signal == "MOUTH_OPEN":

        media_play_pause()

        state["last_action"] = "MEDIA_PLAY_PAUSE"

    elif signal in ("DOUBLE_BLINK", "DOUBLE_EYEBROWS_UP"):

        take_screenshot()

        state["last_action"] = "TAKE_SCREENSHOT"

    else:

        state["last_action"] = None

    if state["last_action"] is not None:

        print(
            f"[ACTION] {state['last_action']}"
        )


# ---------------------------------
# Checks (mirrors
# src/processing/face/face_recognizer.py's
# _check_tilt / _check_eyebrows / _check_mouth /
# _check_blink, reading thresholds from the
# trackbars instead of fixed class constants)
# ---------------------------------

def check_tilt(roll, tilt_enter, tilt_exit):

    if roll is None:
        return

    if state["tilt_zone"] is None:

        if roll > tilt_enter:

            state["tilt_zone"] = "right"

            fire_face_signal("HEAD_TILT_RIGHT")

        elif roll < -tilt_enter:

            state["tilt_zone"] = "left"

            fire_face_signal("HEAD_TILT_LEFT")

    elif abs(roll) < tilt_exit:

        state["tilt_zone"] = None


def check_eyebrows(
    score,
    current_time,
    raise_threshold,
    lower_threshold,
    double_window_seconds
):

    if (
        not state["eyebrows_raised"]
        and score > raise_threshold
    ):

        state["eyebrows_raised"] = True

        fire_face_signal("EYEBROWS_UP")

        if (
            current_time - state["last_eyebrows_raise_time"]
            <= double_window_seconds
        ):

            fire_face_signal("DOUBLE_EYEBROWS_UP")

            state["last_eyebrows_raise_time"] = 0

        else:

            state["last_eyebrows_raise_time"] = current_time

    elif (
        state["eyebrows_raised"]
        and score < lower_threshold
    ):

        state["eyebrows_raised"] = False

        fire_face_signal("EYEBROWS_DOWN")


def check_mouth(score, open_threshold, close_threshold):

    if (
        not state["mouth_open"]
        and score > open_threshold
    ):

        state["mouth_open"] = True

        fire_face_signal("MOUTH_OPEN")

    elif (
        state["mouth_open"]
        and score < close_threshold
    ):

        state["mouth_open"] = False


def check_blink(
    left,
    right,
    current_time,
    close_threshold,
    open_threshold,
    double_window_seconds
):

    both_closed = (
        left > close_threshold
        and right > close_threshold
    )

    both_open = (
        left < open_threshold
        and right < open_threshold
    )

    if both_closed and not state["eyes_closed"]:

        state["eyes_closed"] = True

        return

    if both_open and state["eyes_closed"]:

        state["eyes_closed"] = False

        if (
            current_time - state["last_blink_time"]
            <= double_window_seconds
        ):

            fire_face_signal("DOUBLE_BLINK")

            state["last_blink_time"] = 0

        else:

            state["last_blink_time"] = current_time


# ---------------------------------
# Drawing
# ---------------------------------

def draw_bar(
    frame,
    y,
    label,
    score,
    enter_threshold,
    exit_threshold,
    active,
    active_label
):

    cv2.putText(
        frame,
        "{}: {:.2f}  [{}]".format(
            label,
            score,
            active_label if active else "-"
        ),
        (10, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 0) if active else (255, 255, 255),
        2
    )

    y += 8

    bar_x = 10
    bar_y = y

    cv2.rectangle(
        frame,
        (bar_x, bar_y),
        (bar_x + BAR_WIDTH, bar_y + BAR_HEIGHT),
        (80, 80, 80),
        1
    )

    filled_width = int(
        max(0.0, min(1.0, score)) * BAR_WIDTH
    )

    cv2.rectangle(
        frame,
        (bar_x, bar_y),
        (bar_x + filled_width, bar_y + BAR_HEIGHT),
        (0, 255, 0) if active else (0, 165, 255),
        -1
    )

    enter_x = bar_x + int(
        max(0.0, min(1.0, enter_threshold)) * BAR_WIDTH
    )

    exit_x = bar_x + int(
        max(0.0, min(1.0, exit_threshold)) * BAR_WIDTH
    )

    cv2.line(
        frame,
        (enter_x, bar_y - 2),
        (enter_x, bar_y + BAR_HEIGHT + 2),
        (0, 0, 255),
        2
    )

    cv2.line(
        frame,
        (exit_x, bar_y - 2),
        (exit_x, bar_y + BAR_HEIGHT + 2),
        (255, 0, 0),
        2
    )

    return bar_y + BAR_HEIGHT + 18


def draw_overlay(
    frame,
    pitch,
    yaw,
    roll,
    blendshapes,
    tilt_enter,
    tilt_exit,
    eyebrows_raise,
    eyebrows_lower,
    mouth_open_t,
    mouth_close_t,
    blink_close,
    blink_open
):

    y = 25

    if pitch is None:

        cv2.putText(
            frame,
            "face: NOT DETECTED",
            (10, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 255),
            2
        )

        y += 25

    else:

        cv2.putText(
            frame,
            "pitch: {:6.1f}  yaw: {:6.1f}  roll: {:6.1f}".format(
                pitch,
                yaw,
                roll
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
            "tilt_zone: {}   (enter {} deg / exit {} deg)".format(
                state["tilt_zone"],
                tilt_enter,
                tilt_exit
            ),
            (10, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 0) if state["tilt_zone"] else (255, 255, 255),
            2
        )

        y += 25

    y = draw_bar(
        frame,
        y,
        "eyebrows (browInnerUp)",
        blendshapes.get("browInnerUp", 0.0),
        eyebrows_raise,
        eyebrows_lower,
        state["eyebrows_raised"],
        "RAISED"
    )

    y = draw_bar(
        frame,
        y,
        "mouth (jawOpen)",
        blendshapes.get("jawOpen", 0.0),
        mouth_open_t,
        mouth_close_t,
        state["mouth_open"],
        "OPEN"
    )

    y = draw_bar(
        frame,
        y,
        "blink L (eyeBlinkLeft)",
        blendshapes.get("eyeBlinkLeft", 0.0),
        blink_close,
        blink_open,
        state["eyes_closed"],
        "CLOSED"
    )

    y = draw_bar(
        frame,
        y,
        "blink R (eyeBlinkRight)",
        blendshapes.get("eyeBlinkRight", 0.0),
        blink_close,
        blink_open,
        state["eyes_closed"],
        "CLOSED"
    )

    held = alt_held()

    cv2.putText(
        frame,
        "ALT: {}".format(
            "HELD" if held else "not held"
        ),
        (10, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 255, 0) if held else (150, 150, 150),
        2
    )

    y += 25

    cv2.putText(
        frame,
        "last signal: {}   last action: {}".format(
            state["last_signal"],
            state["last_action"]
        ),
        (10, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2
    )

    height = frame.shape[0]

    cv2.putText(
        frame,
        "hold alt, then tilt head / open mouth / "
        "double-blink / double-raise-eyebrows to fire the "
        "real OS action   q: quit",
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
    "tilt enter (deg)",
    WINDOW_NAME,
    DEFAULT_TILT_ENTER_DEGREES,
    45,
    lambda value: None
)

cv2.createTrackbar(
    "tilt exit (deg)",
    WINDOW_NAME,
    DEFAULT_TILT_EXIT_DEGREES,
    45,
    lambda value: None
)

cv2.createTrackbar(
    "eyebrows raise x100",
    WINDOW_NAME,
    DEFAULT_EYEBROWS_RAISE_X100,
    100,
    lambda value: None
)

cv2.createTrackbar(
    "eyebrows lower x100",
    WINDOW_NAME,
    DEFAULT_EYEBROWS_LOWER_X100,
    100,
    lambda value: None
)

cv2.createTrackbar(
    "eyebrows dbl window (ms)",
    WINDOW_NAME,
    DEFAULT_DOUBLE_EYEBROWS_WINDOW_MS,
    2000,
    lambda value: None
)

cv2.createTrackbar(
    "mouth open x100",
    WINDOW_NAME,
    DEFAULT_MOUTH_OPEN_X100,
    100,
    lambda value: None
)

cv2.createTrackbar(
    "mouth close x100",
    WINDOW_NAME,
    DEFAULT_MOUTH_CLOSE_X100,
    100,
    lambda value: None
)

cv2.createTrackbar(
    "blink close x100",
    WINDOW_NAME,
    DEFAULT_BLINK_CLOSE_X100,
    100,
    lambda value: None
)

cv2.createTrackbar(
    "blink open x100",
    WINDOW_NAME,
    DEFAULT_BLINK_OPEN_X100,
    100,
    lambda value: None
)

cv2.createTrackbar(
    "blink dbl window (ms)",
    WINDOW_NAME,
    DEFAULT_DOUBLE_BLINK_WINDOW_MS,
    2000,
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

        tilt_enter = cv2.getTrackbarPos(
            "tilt enter (deg)",
            WINDOW_NAME
        )

        tilt_exit = cv2.getTrackbarPos(
            "tilt exit (deg)",
            WINDOW_NAME
        )

        eyebrows_raise = cv2.getTrackbarPos(
            "eyebrows raise x100",
            WINDOW_NAME
        ) / 100.0

        eyebrows_lower = cv2.getTrackbarPos(
            "eyebrows lower x100",
            WINDOW_NAME
        ) / 100.0

        eyebrows_dbl_window = cv2.getTrackbarPos(
            "eyebrows dbl window (ms)",
            WINDOW_NAME
        ) / 1000.0

        mouth_open_t = cv2.getTrackbarPos(
            "mouth open x100",
            WINDOW_NAME
        ) / 100.0

        mouth_close_t = cv2.getTrackbarPos(
            "mouth close x100",
            WINDOW_NAME
        ) / 100.0

        blink_close = cv2.getTrackbarPos(
            "blink close x100",
            WINDOW_NAME
        ) / 100.0

        blink_open = cv2.getTrackbarPos(
            "blink open x100",
            WINDOW_NAME
        ) / 100.0

        blink_dbl_window = cv2.getTrackbarPos(
            "blink dbl window (ms)",
            WINDOW_NAME
        ) / 1000.0

        ret, frame = cap.read()

        if not ret:
            continue

        result = detect(frame)

        current_time = time.time()

        if not result.face_landmarks:

            draw_overlay(
                frame,
                None,
                None,
                None,
                {},
                tilt_enter,
                tilt_exit,
                eyebrows_raise,
                eyebrows_lower,
                mouth_open_t,
                mouth_close_t,
                blink_close,
                blink_open
            )

            cv2.imshow(WINDOW_NAME, frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

            continue

        pitch, yaw, roll = head_pose(result)

        blendshapes = blendshape_scores(result)

        check_tilt(
            roll,
            tilt_enter,
            tilt_exit
        )

        check_eyebrows(
            blendshapes.get("browInnerUp", 0.0),
            current_time,
            eyebrows_raise,
            eyebrows_lower,
            eyebrows_dbl_window
        )

        check_mouth(
            blendshapes.get("jawOpen", 0.0),
            mouth_open_t,
            mouth_close_t
        )

        check_blink(
            blendshapes.get("eyeBlinkLeft", 0.0),
            blendshapes.get("eyeBlinkRight", 0.0),
            current_time,
            blink_close,
            blink_open,
            blink_dbl_window
        )

        draw_overlay(
            frame,
            pitch,
            yaw,
            roll,
            blendshapes,
            tilt_enter,
            tilt_exit,
            eyebrows_raise,
            eyebrows_lower,
            mouth_open_t,
            mouth_close_t,
            blink_close,
            blink_open
        )

        cv2.imshow(WINDOW_NAME, frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:

    cap.release()

    cv2.destroyAllWindows()

    keyboard_listener.stop()
