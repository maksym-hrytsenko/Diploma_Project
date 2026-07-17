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
from utils.logger import get_logger
from utils.permissions import ensure_camera_permission


logger = get_logger(__name__)


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

        # Set here (not inside _run) so a second start() call while the
        # first is still waiting on _run's permission check is rejected
        # by the guard above instead of spawning a duplicate thread.
        self.running = True

        self.thread = threading.Thread(
            target=self._run,
            daemon=True
        )

        self.thread.start()

        logger.info("Started")

    def _run(self):
        """Capture-thread entry point: waits for camera permission, opens
        the device, then runs the capture loop.

        All three steps happen off the Qt main thread, so a slow-to-answer
        system permission prompt delays only this thread, never the UI.
        """

        ensure_camera_permission()

        if not self.running:
            return

        if not self._open_capture():

            self.running = False

            return

        # stop() may have landed while _open_capture() was in flight — it
        # would have found self.cap still None and skipped release(),
        # so the now-open device has to be cleaned up here instead.
        if not self.running:

            self.cap.release()

            self.cap = None

            return

        self._capture_loop()

    def _open_capture(self) -> bool:
        """Open the capture device and apply the configured resolution.

        Only called after ensure_camera_permission() has settled the
        system's camera prompt — opening ahead of that decision can leave
        the capture session unable to ever deliver frames, even after the
        user grants access (see utils/permissions.py's module docstring).
        """

        self.cap = cv2.VideoCapture(
            self.camera_index
        )

        if not self.cap.isOpened():

            logger.error(
                "Failed to open camera"
            )

            return False

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

        logger.info(
            "Resolution: %dx%d",
            int(actual_width),
            int(actual_height)
        )

        return True

    def stop(self):

        if not self.running:
            return

        self.running = False

        # Wait for the capture loop to actually exit its while-loop before
        # releasing the device out from under it — a fixed sleep here would
        # race against a read() still in flight.
        if self.thread is not None:

            self.thread.join(
                timeout=1.0
            )

            self.thread = None

        if self.cap:

            self.cap.release()

            self.cap = None

        logger.info("Stopped")

    def _capture_loop(self):

        while self.running:

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