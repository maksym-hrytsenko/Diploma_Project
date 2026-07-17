"""Calibration HUD for FaceRecognizer.

Renders a cv2 window over the live camera feed showing head-pose angles and
blendshape scores next to the thresholds FaceRecognizer compares them
against, so those thresholds can be tuned against a real face and camera
instead of guessed from code alone. Enabled via the ``--debug-face`` flag;
separate from FaceRecognizer's own detection logic.
"""

import threading

import cv2


class FaceDebugView:

    def __init__(self, event_bus):

        self.event_bus = event_bus

        self.window_name = "Face Debug"

        # cv2.imshow/cv2.waitKey must run on the main thread (macOS), so the
        # event handler (camera thread) only stores the latest snapshot and
        # the main loop calls render() to draw it.
        self.lock = threading.Lock()

        self.latest_data = None

        self.window_open = False

        self.bar_width = 200
        self.bar_height = 14

    def start(self):

        self.event_bus.subscribe(
            "face_debug",
            self._handle_debug
        )

    def stop(self):

        self.event_bus.unsubscribe(
            "face_debug",
            self._handle_debug
        )

        if self.window_open:

            cv2.destroyWindow(
                self.window_name
            )

            self.window_open = False

    def _handle_debug(self, event):

        data = event.get(
            "data",
            {}
        )

        with self.lock:

            self.latest_data = data

    def render(self):

        with self.lock:

            data = self.latest_data

        if data is None:

            cv2.waitKey(1)

            return

        frame = data.get("frame")

        if frame is None:

            cv2.waitKey(1)

            return

        display = frame.copy()

        self._draw_overlay(
            display,
            data
        )

        cv2.imshow(
            self.window_name,
            display
        )

        self.window_open = True

        cv2.waitKey(1)

    def _draw_overlay(self, display, data):

        y = 25

        y = self._draw_head_pose(
            display,
            data,
            y
        )

        y = self._draw_bar(
            display,
            y,
            label="eyebrows (browInnerUp)",
            score=data.get("brow_inner_up", 0.0),
            enter_threshold=data.get(
                "eyebrows_raise_threshold",
                0.5
            ),
            exit_threshold=data.get(
                "eyebrows_lower_threshold",
                0.3
            ),
            active=data.get("eyebrows_raised", False),
            active_label="RAISED"
        )

        y = self._draw_bar(
            display,
            y,
            label="mouth (jawOpen)",
            score=data.get("jaw_open", 0.0),
            enter_threshold=data.get(
                "mouth_open_threshold",
                0.5
            ),
            exit_threshold=data.get(
                "mouth_close_threshold",
                0.3
            ),
            active=data.get("mouth_open", False),
            active_label="OPEN"
        )

    def _draw_head_pose(self, display, data, y):

        pitch = data.get("pitch")
        yaw = data.get("yaw")
        roll = data.get("roll")
        tilt_zone = data.get("tilt_zone")
        tilt_enter = data.get("tilt_enter_degrees", 15)
        tilt_exit = data.get("tilt_exit_degrees", 8)

        if pitch is None or yaw is None or roll is None:

            self._draw_line(
                display,
                "face: NOT DETECTED",
                y,
                color=(0, 0, 255)
            )

            return y + 25

        self._draw_line(
            display,
            "pitch: {:6.1f}  yaw: {:6.1f}  roll: {:6.1f}".format(
                pitch,
                yaw,
                roll
            ),
            y
        )

        y += 25

        roll_color = (255, 255, 255)

        if tilt_zone is not None:
            roll_color = (0, 255, 0)

        self._draw_line(
            display,
            "tilt_zone: {}   (enter {} deg / exit {} deg)".format(
                tilt_zone,
                tilt_enter,
                tilt_exit
            ),
            y,
            color=roll_color
        )

        return y + 25

    def _draw_line(self, display, text, y, color=(255, 255, 255)):

        cv2.putText(
            display,
            text,
            (10, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2
        )

    def _draw_bar(
        self,
        display,
        y,
        label,
        score,
        enter_threshold,
        exit_threshold,
        active,
        active_label
    ):

        state_text = active_label if active else "-"

        self._draw_line(
            display,
            "{}: {:.2f}  [{}]".format(
                label,
                score,
                state_text
            ),
            y,
            color=(0, 255, 0) if active else (255, 255, 255)
        )

        y += 8

        bar_x = 10
        bar_y = y

        cv2.rectangle(
            display,
            (bar_x, bar_y),
            (bar_x + self.bar_width, bar_y + self.bar_height),
            (80, 80, 80),
            1
        )

        filled_width = int(
            max(0.0, min(1.0, score)) * self.bar_width
        )

        cv2.rectangle(
            display,
            (bar_x, bar_y),
            (bar_x + filled_width, bar_y + self.bar_height),
            (0, 255, 0) if active else (0, 165, 255),
            -1
        )

        # Tick marks at the enter/exit thresholds each check compares the
        # live score against.
        enter_x = bar_x + int(
            max(0.0, min(1.0, enter_threshold)) * self.bar_width
        )

        exit_x = bar_x + int(
            max(0.0, min(1.0, exit_threshold)) * self.bar_width
        )

        cv2.line(
            display,
            (enter_x, bar_y - 2),
            (enter_x, bar_y + self.bar_height + 2),
            (0, 0, 255),
            2
        )

        cv2.line(
            display,
            (exit_x, bar_y - 2),
            (exit_x, bar_y + self.bar_height + 2),
            (255, 0, 0),
            2
        )

        return bar_y + self.bar_height + 18
