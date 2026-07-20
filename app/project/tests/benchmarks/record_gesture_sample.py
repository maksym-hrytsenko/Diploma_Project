"""Guided recorder for a real gesture/face sample video, used as the
source for SyntheticCameraInput (camera_gesture_only / combined_worst_case
scenarios in run_stress_suite.py).

Why a real recording instead of generated frames: MediaPipe's hand/face
models are trained on real imagery and need real, continuous motion to
walk GestureRecognizer's own state machine (velocity_threshold,
confirm_frames, hand_lost_frames, ... -- see src/config/system.json)
through its actual gesture-recognition path, not just the cheap
"nothing detected" path idle_baseline already covers. Nothing procedural
reliably reproduces that.

Walks you through the system's actual gesture/face signal set (see
src/fusion/signal_mapper.py's SIGNAL_METHOD table), one beat at a time,
with the instruction and a countdown burned into the live preview window
only -- never into the saved frames, since those get fed back through the
real recognizers later.

Usage:
    python tests/benchmarks/record_gesture_sample.py
    python tests/benchmarks/record_gesture_sample.py --output tests/synthesized_gesture/gesture_sample.mp4
"""

import argparse
import json
import os
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

# cv2.putText only supports its built-in blocky Hershey fonts -- draw
# overlay text through a real system font via Pillow instead. Tried in
# order; every one of these ships on a stock macOS install, but a
# missing/renamed font shouldn't crash a recording session, hence the
# fallback chain.
_OVERLAY_FONT_CANDIDATES = [
    "/System/Library/Fonts/SFNS.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _load_overlay_font(size):

    for path in _OVERLAY_FONT_CANDIDATES:

        if not os.path.exists(path):
            continue

        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue

    return ImageFont.load_default()


FONT_TITLE = _load_overlay_font(22)

FONT_INSTRUCTION = _load_overlay_font(26)

FONT_HINT = _load_overlay_font(17)

SYSTEM_CONFIG_PATH = os.path.join(
    PROJECT_ROOT,
    "src",
    "config",
    "system.json"
)

DEFAULT_OUTPUT_PATH = os.path.join(
    PROJECT_ROOT,
    "tests",
    "synthesized_gesture",
    "gesture_sample.mp4"
)


# (label, seconds, instruction shown on the live preview -- not saved)
BEATS = [

    ("baseline_still_start", 5, "Do nothing -- hands out of frame, neutral face"),

    ("session_start", 6, "Fist -> open palm, a few times (HAND_SESSION_START)"),

    ("swipe_right", 10, "Swipe your hand RIGHT, a few times"),
    ("swipe_left", 10, "Swipe your hand LEFT, a few times"),
    ("swipe_up", 10, "Swipe your hand UP, a few times"),
    ("swipe_down", 10, "Swipe your hand DOWN, a few times"),

    ("pinch", 10, "Touch thumb and index finger together (pinch), release -- a few times"),
    ("pinch_drag", 10, "Pinch and drag your hand sideways without releasing"),
    ("double_pinch", 6, "Two quick pinches in a row (double pinch)"),

    ("one_finger", 4, "Hold up ONE finger"),
    ("two_fingers", 4, "Hold up TWO fingers"),
    ("three_fingers", 4, "Hold up THREE fingers"),
    ("four_fingers", 4, "Hold up FOUR fingers"),

    ("cursor_move", 20, "Slowly move an open palm in a circle (cursor)"),

    ("session_end", 5, "Fist again -- close the session (HAND_SESSION_END)"),

    ("face_tilt_left", 4, "Tilt your head LEFT"),
    ("face_tilt_right", 4, "Tilt your head RIGHT"),
    ("face_mouth_open", 4, "Open your mouth (like a yawn)"),
    ("face_eyebrows", 4, "Raise your eyebrows"),

    ("baseline_still_end", 5, "Do nothing again")

]


def parse_args():

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_PATH,
        help=f"Output video path (default: {DEFAULT_OUTPUT_PATH})"
    )

    return parser.parse_args()


def load_camera_settings():

    with open(SYSTEM_CONFIG_PATH, encoding="utf-8") as f:

        config = json.load(f)

    camera_config = config.get(
        "camera",
        {}
    )

    return (
        camera_config.get("index", 0),
        camera_config.get("width", 1280),
        camera_config.get("height", 720)
    )


def draw_overlay(
    frame,
    beat_label,
    instruction,
    seconds_left,
    beat_index,
    beat_count
):

    overlay = frame.copy()

    cv2.rectangle(
        overlay,
        (0, 0),
        (frame.shape[1], 110),
        (20, 20, 20),
        -1
    )

    frame = cv2.addWeighted(
        overlay,
        0.65,
        frame,
        0.35,
        0
    )

    # PIL draws in RGB and wants a PIL Image, not a BGR numpy array --
    # convert there and back around the actual text drawing.
    pil_image = Image.fromarray(
        cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    )

    draw = ImageDraw.Draw(pil_image)

    draw.text(
        (20, 6),
        f"[{beat_index}/{beat_count}] {beat_label}",
        font=FONT_TITLE,
        fill=(255, 255, 255)
    )

    draw.text(
        (20, 36),
        instruction,
        font=FONT_INSTRUCTION,
        fill=(255, 210, 0)
    )

    draw.text(
        (20, 78),
        f"{seconds_left:.0f}s   (q = stop early)",
        font=FONT_HINT,
        fill=(200, 200, 200)
    )

    return cv2.cvtColor(
        np.array(pil_image),
        cv2.COLOR_RGB2BGR
    )


def main():

    args = parse_args()

    output_path = args.output

    os.makedirs(
        os.path.dirname(output_path) or ".",
        exist_ok=True
    )

    camera_index, frame_width, frame_height = load_camera_settings()

    capture = cv2.VideoCapture(
        camera_index
    )

    capture.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        frame_width
    )

    capture.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        frame_height
    )

    if not capture.isOpened():

        print("Failed to open the camera.")

        return

    actual_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))

    actual_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # cap.get(CAP_PROP_FPS) reports a nominal value that doesn't
    # necessarily match what this recorder actually captures -- the beat
    # loop below has no throttling of its own (no time.sleep between
    # reads), so it writes frames as fast as the camera truly delivers
    # them. Trusting the nominal value here silently mislabels the file's
    # timing if it's wrong (confirmed once: a session came out declaring
    # 15fps while frame_count implied ~30fps was actually captured --
    # SyntheticCameraInput would then have paced playback at half the
    # real speed, which halves every computed gesture velocity in
    # GestureRecognizer._check_motion's delta_x/delta_time). Record into
    # a temp file at a placeholder fps, measure the TRUE fps from actual
    # wall-clock elapsed time once recording is done, then re-encode a
    # single time with the correct value.
    placeholder_fps = 30.0

    temp_path = output_path + ".raw_capture.mp4"

    writer = cv2.VideoWriter(
        temp_path,
        cv2.VideoWriter_fourcc(*"mp4v"),
        placeholder_fps,
        (actual_width, actual_height)
    )

    total_seconds = sum(
        duration for _, duration, _ in BEATS
    )

    print(
        f"Recording to {output_path} ({actual_width}x{actual_height}). "
        f"Total ~{total_seconds}s ({total_seconds / 60:.1f} min). "
        f"The preview window will open now."
    )

    aborted = False

    frames_written = 0

    recording_start = time.time()

    try:

        for beat_index, (label, duration, instruction) in enumerate(BEATS, start=1):

            beat_start = time.time()

            while True:

                elapsed = time.time() - beat_start

                if elapsed >= duration:
                    break

                ret, frame = capture.read()

                if not ret:
                    continue

                # Raw frame goes to the file -- no overlay burned in, since
                # this footage later gets fed back through the real
                # GestureRecognizer/FaceRecognizer as if it were live.
                writer.write(frame)

                frames_written += 1

                preview = draw_overlay(
                    frame,
                    label,
                    instruction,
                    duration - elapsed,
                    beat_index,
                    len(BEATS)
                )

                # cv2's HighGUI window title (unlike the frame overlay
                # above) is plain OS chrome, not something Pillow touches --
                # macOS's Cocoa backend mangles non-ASCII here, so this one
                # stays in English on purpose. All real instructions are in
                # the overlay itself, not the title bar.
                cv2.imshow("Gesture recording -- press Q to stop early", preview)

                if cv2.waitKey(1) & 0xFF == ord("q"):

                    aborted = True

                    break

            if aborted:
                break

    finally:

        capture.release()

        writer.release()

        cv2.destroyAllWindows()

    recording_elapsed = time.time() - recording_start

    if frames_written == 0 or recording_elapsed <= 0:

        print("Nothing was recorded.")

        os.remove(temp_path)

        return

    true_fps = frames_written / recording_elapsed

    print(
        f"Recorded {frames_written} frames in {recording_elapsed:.1f}s "
        f"-> true fps ~{true_fps:.1f} (not trusting the camera's own "
        f"metadata for this, measuring it myself)."
    )

    reencode_with_fps(
        temp_path,
        output_path,
        true_fps
    )

    os.remove(temp_path)

    if aborted:

        print(f"Stopped early. What was recorded is saved to {output_path}.")

    else:

        print(f"Done: {output_path}")


def reencode_with_fps(
    source_path,
    dest_path,
    fps
):

    capture = cv2.VideoCapture(source_path)

    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))

    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

    writer = cv2.VideoWriter(
        dest_path,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height)
    )

    try:

        while True:

            ret, frame = capture.read()

            if not ret:
                break

            writer.write(frame)

    finally:

        capture.release()

        writer.release()


if __name__ == "__main__":
    main()
