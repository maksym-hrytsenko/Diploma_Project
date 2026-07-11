import cv2
import threading
import time

from config.config_loader import load_system_config


class CameraInput:

    def __init__(
        self,
        event_bus,
        camera_index=None
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

    def start(self):

        self.cap = cv2.VideoCapture(
            self.camera_index
        )

        if not self.cap.isOpened():

            print(
                "[CameraInput] Failed to open camera"
            )

            return

        # Request a higher capture resolution than most
        # webcams default to. More pixels on the hand matters
        # most at Presentation Mode's typical 2-4m distance,
        # where a hand covers a much smaller part of the frame
        # than it does at desk distance — the camera may not
        # honor this exactly, so the actually granted size is
        # read back and logged.
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

        self.running = False

        # Small delay to safely stop thread
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