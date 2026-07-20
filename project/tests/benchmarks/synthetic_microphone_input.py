"""Synthetic replacement for MicrophoneInput.

Publishes `audio_chunk` events sourced from a pre-recorded audio file
instead of a live microphone, at the same chunk size and pacing
MicrophoneInput would produce from real hardware — so SpeechRecognizer,
IntentModel and everything downstream run completely unmodified and
unaware the signal isn't live. Exists for tests/benchmarks/run_stress_suite.py:
a recorded session is exactly reproducible across runs, which a live mic
session never is.

Lives outside src/ on purpose, same reasoning as resource_monitor.py: a
QA/benchmark tool, not part of the shipped application. Imported by
main.py only when --synthetic-audio is passed (see main.py's deferred,
path-appended import).
"""

import os
import subprocess
import threading
import time

import numpy as np
from scipy.io import wavfile

from core.event_bus import EventBus
from utils.logger import get_logger


logger = get_logger(__name__)


class SyntheticMicrophoneInput:

    def __init__(
        self,
        event_bus: EventBus,
        source_path: str,
        samplerate: int = 16000,
        blocksize: int = 8000,
        speed: float = 1.0,
        loop_count: int = 1
    ):

        self.event_bus = event_bus

        self.source_path = source_path

        self.samplerate = samplerate

        self.blocksize = blocksize

        # >1.0 compresses many playback cycles into less wall-clock time,
        # for a soak-style run that needs many repetitions rather than one
        # real-time pass — see run_stress_suite.py's looped scenario.
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

        wav_path = _ensure_wav(
            self.source_path,
            self.samplerate
        )

        _, samples = wavfile.read(
            wav_path
        )

        loops_done = 0

        chunk_sleep_seconds = (
            self.blocksize
            / self.samplerate
            / self.speed
        )

        while self.running and loops_done < self.loop_count:

            offset = 0

            while self.running and offset < len(samples):

                chunk = samples[offset:offset + self.blocksize]

                offset += self.blocksize

                # Real hardware chunks are always exactly blocksize frames
                # (sounddevice's callback contract) — pad the file's final,
                # shorter remainder so nothing downstream sees a chunk size
                # it would never see from a live mic.
                if len(chunk) < self.blocksize:

                    chunk = np.pad(
                        chunk,
                        (0, self.blocksize - len(chunk))
                    )

                self.event_bus.publish(
                    "audio_chunk",
                    chunk.tobytes()
                )

                time.sleep(
                    chunk_sleep_seconds
                )

            loops_done += 1

        # Lets main.py auto-exit once the recorded session (all loops) has
        # fully played, instead of running until someone manually stops it
        # — see main.py's "synthetic_input_finished" subscriber and
        # run_stress_suite.py, which waits on the process exiting.
        self.event_bus.publish(
            "synthetic_input_finished",
            {"source": "audio"}
        )


def _ensure_wav(
    source_path: str,
    samplerate: int
) -> str:

    if source_path.lower().endswith(".wav"):
        return source_path

    cache_path = (
        os.path.splitext(source_path)[0]
        + f".synthetic_{samplerate}hz_mono16.wav"
    )

    if os.path.exists(cache_path):
        return cache_path

    # afconvert (macOS built-in, no extra Python dependency) — cached
    # next to the source so a ~20-minute recording is decoded once, not
    # on every benchmark run.
    logger.info(
        "Converting %s -> %s (afconvert, one-time)",
        source_path,
        cache_path
    )

    subprocess.run(
        [
            "afconvert",
            "-f", "WAVE",
            "-d", f"LEI16@{samplerate}",
            "-c", "1",
            source_path,
            cache_path
        ],
        check=True
    )

    return cache_path
