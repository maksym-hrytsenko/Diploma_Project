"""Synthetic replacement for CameraInput.

Publishes `camera_frame` events sourced from a pre-recorded video file
instead of a live webcam, at the recording's own frame rate, so
GestureRecognizer, FaceRecognizer and everything downstream run completely
unmodified and unaware the signal isn't live -- same reasoning as
synthetic_microphone_input.py.

Lives outside src/ on purpose, same reasoning as resource_monitor.py: a
QA/benchmark tool, not part of the shipped application. Imported by
main.py only when --synthetic-camera is passed (see main.py's deferred,
path-appended import).
"""

import os
import threading
import time

import cv2

from core.event_bus import EventBus
from utils.logger import get_logger


logger = get_logger(__name__)


class SyntheticCameraInput:

    def __init__(
        self,
        event_bus: EventBus,
        source_path: str,
        speed: float = 1.0,
        loop_count: int = 1
    ):

        self.event_bus = event_bus

        self.source_path = source_path

        # >1.0 compresses playback into less wall-clock time -- see
        # run_stress_suite.py's combined scenario, which loops a short
        # gesture recording many times to outlast a much longer voice
        # session rather than needing a longer recording.
        self.speed = speed

        self.loop_count = loop_count

        self.running = False

        self.thread = None

    def start(self):

        self.running = True

        self.thread = threading.Thread(
            target=self._play,
            daemon=True
        )

        self.thread.start()

        logger.info(
            "Started (synthetic source: %s, speed=%sx, loops=%s)",
            self.source_path,
            self.speed,
            self.loop_count
        )

    def stop(self):

        self.running = False

        if self.thread is not None:

            self.thread.join(
                timeout=1.0
            )

            self.thread = None

        logger.info(
            "Stopped (synthetic)"
        )

    def _play(self):

        if not os.path.exists(self.source_path):

            logger.error(
                "Synthetic camera source not found: %s",
                self.source_path
            )

            self._announce_finished()

            return

        loops_done = 0

        while self.running and loops_done < self.loop_count:

            self._play_once()

            loops_done += 1

        self._announce_finished()

    def _play_once(self):

        capture = cv2.VideoCapture(
            self.source_path
        )

        fps = capture.get(
            cv2.CAP_PROP_FPS
        )

        # Some containers/codecs don't report a usable FPS -- fall back to
        # a plausible default rather than dividing by zero below.
        if not fps or fps <= 0:
            fps = 30.0

        frame_sleep_seconds = (
            1.0
            / fps
            / self.speed
        )

        try:

            while self.running:

                ret, frame = capture.read()

                if not ret:
                    break

                self.event_bus.publish(
                    "camera_frame",
                    frame
                )

                time.sleep(
                    frame_sleep_seconds
                )

        finally:

            capture.release()

    def _announce_finished(self):

        # Lets main.py auto-exit once every active synthetic source (this
        # one and/or SyntheticMicrophoneInput) has finished -- see
        # main.py's "synthetic_input_finished" subscriber.
        self.event_bus.publish(
            "synthetic_input_finished",
            {"source": "camera"}
        )
