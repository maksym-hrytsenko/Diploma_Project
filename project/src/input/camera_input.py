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

        # Below dim_brightness_threshold, MediaPipe's hand/face detectors
        # (GestureRecognizer/FaceRecognizer) start missing real gestures
        # more than they catch — below dark_brightness_threshold they
        # essentially never detect anything at all. Publishing this as a
        # "camera_lighting" level rather than silently degrading lets the
        # UI tell the user why nothing is being recognized instead of the
        # feed just looking dark with no explanation (see MainWindow's
        # camera preview caption). Deliberately NOT a trigger for any kind
        # of auto-brightness/screen-backlight compensation — the fix is
        # telling the user to add light, not the app trying to fake it.
        self.dim_brightness_threshold = camera_config.get(
            "dim_brightness_threshold",
            60
        )

        self.dark_brightness_threshold = camera_config.get(
            "dark_brightness_threshold",
            25
        )

        # Room lighting doesn't change frame-to-frame — checking it at full
        # camera framerate (~30x/second) only added cv2.cvtColor+mean() cost
        # to every single iteration of this thread's tight capture loop for
        # no benefit, right alongside the synchronous MediaPipe hand/face
        # inference that same loop triggers via publish("camera_frame", ...)
        # below (see EventBus.publish — direct, same-thread callback
        # invocation, no queue). That extra per-frame cost was enough to
        # push some frames' total processing time past the camera's own
        # frame interval, backing up cv2.VideoCapture's internal buffer and
        # making Cursor mode's pointer (a raw, unsmoothed 1:1 mapping — see
        # GestureRecognizer._update_pointer) track in stale-frame bursts
        # instead of smoothly. Checking every LIGHTING_CHECK_INTERVAL_FRAMES
        # frames instead is still far more often than lighting can actually
        # change.
        self.LIGHTING_CHECK_INTERVAL_FRAMES = camera_config.get(
            "lighting_check_interval_frames",
            10
        )

        self._frames_since_lighting_check = 0

        # Last level published — publishing only on change (like
        # mode_changed elsewhere in the pipeline) instead of once per frame
        # keeps this from spamming subscribers while sitting still in the
        # same lighting.
        self._last_lighting_level = None

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

            logger.error(
                "Failed to open camera"
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

        logger.info(
            "Resolution: %dx%d",
            int(actual_width),
            int(actual_height)
        )

        self.running = True

        self.thread = threading.Thread(
            target=self._capture_loop,
            daemon=True
        )

        self.thread.start()

        logger.info("Started")

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

        # So the next start() re-announces the current lighting level from
        # scratch instead of assuming the previous session's last-known
        # level still holds (e.g. the room got dark while the camera was
        # off) — and checks it on that first frame rather than waiting out
        # whatever was left of the previous session's interval.
        self._last_lighting_level = None
        self._frames_since_lighting_check = 0

        logger.info("Stopped")

    def _lighting_level(self, frame):

        brightness = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY
        ).mean()

        if brightness < self.dark_brightness_threshold:
            return "dark"

        if brightness < self.dim_brightness_threshold:
            return "dim"

        return "ok"

    def _capture_loop(self):

        while self.running:

            if self.cap is None:

                time.sleep(0.01)

                continue

            ret, frame = self.cap.read()

            if not ret:

                time.sleep(0.01)

                continue

            if self._frames_since_lighting_check == 0:

                lighting_level = self._lighting_level(frame)

                if lighting_level != self._last_lighting_level:

                    self._last_lighting_level = lighting_level

                    self.event_bus.publish(
                        "camera_lighting",
                        {"level": lighting_level}
                    )

            self._frames_since_lighting_check = (
                (self._frames_since_lighting_check + 1)
                % self.LIGHTING_CHECK_INTERVAL_FRAMES
            )

            # Publish frame to EventBus
            self.event_bus.publish(
                "camera_frame",
                frame
            )

            # Reduce CPU usage
            time.sleep(0.01)