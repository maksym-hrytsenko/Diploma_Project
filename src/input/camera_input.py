import cv2
import threading
import time


class CameraInput:
    def __init__(self, event_bus, camera_index=0):
        self.event_bus = event_bus
        self.camera_index = camera_index

        self.cap = None
        self.running = False
        self.thread = None

    def start(self):
        self.cap = cv2.VideoCapture(self.camera_index)

        if not self.cap.isOpened():
            print("[CameraInput] Failed to open camera")
            return

        self.running = True

        self.thread = threading.Thread(
            target=self._capture_loop,
            daemon=True
        )

        self.thread.start()

        print("[CameraInput] Started")

    def stop(self):
        self.running = False

        # Small delay to safely stop thread loop
        time.sleep(0.1)

        if self.cap:
            self.cap.release()
            self.cap = None

        print("[CameraInput] Stopped")

    def _capture_loop(self):
        while self.running:
            ret, frame = self.cap.read()

            if not ret:
                continue

            # Publish frame to EventBus
            self.event_bus.publish("camera_frame", frame)

            # Reduce CPU usage a little
            time.sleep(0.01)