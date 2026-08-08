"""Calibration HUD for GestureRecognizer.

Renders a cv2 window over the live camera feed showing the anchor point,
tracked finger and current directional zone, so GestureRecognizer's
angle/distance thresholds can be tuned against real footage. Enabled via
the ``--debug-gesture`` flag; separate from GestureRecognizer's own
detection logic.
"""

import math
import threading

import cv2


class GestureDebugView:

    def __init__(self, event_bus):

        self.event_bus = event_bus

        self.window_name = "Gesture Debug"

        # gesture_debug arrives from the camera capture thread.
        # cv2.imshow/cv2.waitKey must run on the main thread (required on
        # macOS), so the handler only stores the latest snapshot here, and
        # the main loop calls render() to actually draw it.
        self.lock = threading.Lock()

        self.latest_data = None

        self.window_open = False

        # Visual sizes only, no effect on detection
        self.marker_radius = 40

        self.cone_line_length = 150

    def start(self):

        self.event_bus.subscribe(
            "gesture_debug",
            self._handle_debug
        )

    def stop(self):

        self.event_bus.unsubscribe(
            "gesture_debug",
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

        height, width = display.shape[:2]

        finger = data.get("finger")

        anchor = data.get("anchor")

        finger_point = self._to_pixels(
            finger,
            width,
            height
        )

        anchor_point = self._to_pixels(
            anchor,
            width,
            height
        )

        if anchor_point is not None:

            cv2.circle(
                display,
                anchor_point,
                self.marker_radius,
                (0, 165, 255),
                2
            )

            cv2.circle(
                display,
                anchor_point,
                4,
                (0, 0, 255),
                -1
            )

            self._draw_cone_lines(
                display,
                anchor_point,
                data.get(
                    "vertical_cone_degrees",
                    25
                )
            )

        if finger_point is not None:

            cv2.circle(
                display,
                finger_point,
                8,
                (0, 255, 0),
                -1
            )

        if (
            finger_point is not None
            and anchor_point is not None
        ):

            cv2.line(
                display,
                anchor_point,
                finger_point,
                (255, 255, 0),
                2
            )

        self._draw_text(
            display,
            data
        )

    def _to_pixels(self, point, width, height):

        if point is None:
            return None

        return (
            int(point[0] * width),
            int(point[1] * height)
        )

    def _draw_cone_lines(
        self,
        display,
        anchor_point,
        cone_degrees
    ):

        # Draws the actual UP/DOWN vs LEFT/RIGHT sector split as 4 rays
        # from the anchor, matching exactly the angle GestureRecognizer
        # decides on.
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
                    direction_x * self.cone_line_length
                ),
                int(
                    anchor_point[1] +
                    direction_y * self.cone_line_length
                )
            )

            cv2.line(
                display,
                anchor_point,
                end_point,
                (0, 200, 200),
                1
            )

        cv2.putText(
            display,
            "{} deg".format(cone_degrees),
            (
                anchor_point[0] + 10,
                anchor_point[1] - self.marker_radius - 10
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 200, 200),
            1
        )

    def _draw_text(self, display, data):

        confidence = data.get("confidence")

        lines = [
            "gesture: {}".format(
                data.get("gesture_name")
            ),
            "confidence: {}".format(
                "{:.2f}".format(confidence)
                if confidence is not None
                else None
            ),
            "last_gesture: {}".format(
                data.get("last_gesture")
            ),
            "tracking: {}".format(
                data.get("tracking_active")
            ),
            "last signal: {}".format(
                data.get("last_signal")
            )
        ]

        y = 30

        for line in lines:

            cv2.putText(
                display,
                line,
                (10, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )

            y += 25
