"""Camera capture input.

Reads frames from the webcam on a background thread and publishes each one
as a raw `camera_frame` event through EventBus. Performs no gesture or face
recognition itself — GestureRecognizer and FaceRecognizer do that
downstream. Sits in the Input layer of the pipeline.
"""

import cv2
import threading
import time

from config.config_loader import load_system_config


class CameraInput:

    def __init__(
        self,
        event_bus,
        camera_index: int | None = None
    ):

        self.event_bus = event_bus

        camera_config = load_system_config().get(
            "camera",
            {}
        )

        self.camera_index = (
            camera_index
            if camera_index is not None
            else camera_config.get("index", 0)
        )

        self.frame_width = camera_config.get(
            "width",
            1280
        )

        self.frame_height = camera_config.get(
            "height",
            720
        )

        self.cap = None

        self.running = False

        self.thread = None

        # Lets the Camera toggle in MainWindow's bottom status panel
        # actually start/stop capture, instead of only updating the UI —
        # see MainWindow._on_camera_toggled, which is the only publisher
        # of this event.
        self.event_bus.subscribe(
            "ui_camera_toggle",
            self._handle_ui_toggle
        )

    def _handle_ui_toggle(self, event):

        active = event.get(
            "data",
            {}
        ).get(
            "active",
            True
        )

        if active:
            self.start()
        else:
            self.stop()

    def start(self):

        if self.running:
            return

        self.cap = cv2.VideoCapture(
            self.camera_index
        )

        if not self.cap.isOpened():

            print(
                "[CameraInput] Failed to open camera"
            )

            return

        # Request a higher-than-default resolution: more pixels on the hand
        # matter most at Presentation Mode's typical 2-4m distance, where a
        # hand covers much less of the frame than at desk distance. The
        # camera may not grant this exactly, so what it actually applied is
        # read back and logged below.
        self.cap.set(
            cv2.CAP_PROP_FRAME_WIDTH,
            self.frame_width
        )

        self.cap.set(
            cv2.CAP_PROP_FRAME_HEIGHT,
            self.frame_height
        )

        actual_width = self.cap.get(
            cv2.CAP_PROP_FRAME_WIDTH
        )

        actual_height = self.cap.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )

        print(
            f"[CameraInput] Resolution: "
            f"{int(actual_width)}x{int(actual_height)}"
        )

        self.running = True

        self.thread = threading.Thread(
            target=self._capture_loop,
            daemon=True
        )

        self.thread.start()

        print("[CameraInput] Started")

    def stop(self):

        if not self.running:
            return

        self.running = False

        # Give the capture loop a moment to notice running=False before the
        # capture device is released out from under it.
        time.sleep(0.1)

        if self.cap:

            self.cap.release()

            self.cap = None

        print("[CameraInput] Stopped")

    def _capture_loop(self):

        while self.running:

            if self.cap is None:

                time.sleep(0.01)

                continue

            ret, frame = self.cap.read()

            if not ret:

                time.sleep(0.01)

                continue

            # Publish frame to EventBus
            self.event_bus.publish(
                "camera_frame",
                frame
            )

            # Reduce CPU usage
            time.sleep(0.01)