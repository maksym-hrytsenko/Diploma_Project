"""Microphone audio input.

Captures raw audio from the input device via sounddevice on a background
thread and publishes each chunk as `audio_chunk` through EventBus. Performs
no speech recognition itself — SpeechRecognizer does that downstream. Sits
in the Input layer of the pipeline.
"""

import queue
import threading

import sounddevice as sd

from config.config_loader import load_system_config
from core.event_bus import EventBus
from utils.logger import get_logger


logger = get_logger(__name__)


class MicrophoneInput:

    def __init__(
        self,
        event_bus: EventBus,
        samplerate: int | None = None,
        channels: int | None = None,
        device: int | None = None
    ):

        self.event_bus = event_bus

        audio_config = load_system_config().get(
            "audio",
            {}
        )

        self.samplerate = (
            samplerate
            if samplerate is not None
            else audio_config.get("sample_rate", 16000)
        )

        self.channels = (
            channels
            if channels is not None
            else audio_config.get("channels", 1)
        )

        self.blocksize = audio_config.get(
            "blocksize",
            8000
        )

        self.audio_queue = queue.Queue()

        self.running = False

        self.stream = None

        self.thread = None

        # None means: use the OS default input device
        self.device = device

    def _audio_callback(
        self,
        indata,
        frames,
        time_info,
        status
    ):

        if status:
            logger.warning(
                "Stream status: %s",
                status
            )

        self.audio_queue.put(
            bytes(indata)
        )

    def start(self):

        self.running = True

        device_info = sd.query_devices(
            self.device,
            "input"
        )

        logger.info(
            "Using input device: %s",
            device_info['name']
        )

        self.stream = sd.RawInputStream(

            samplerate=self.samplerate,

            blocksize=self.blocksize,

            dtype="int16",

            channels=self.channels,

            device=self.device,

            callback=self._audio_callback
        )

        self.stream.start()

        self.thread = threading.Thread(
            target=self._process_audio,
            daemon=True
        )

        self.thread.start()

        logger.info(
            "Started"
        )

    def stop(self):

        self.running = False

        if self.stream:

            self.stream.stop()

            self.stream.close()

            self.stream = None

        # Wait for _process_audio's while-loop to actually exit before
        # returning, rather than assuming it noticed running=False.
        if self.thread is not None:

            self.thread.join(
                timeout=1.0
            )

            self.thread = None

        logger.info(
            "Stopped"
        )

    def _process_audio(self):

        while self.running:

            try:

                audio_chunk = (
                    self.audio_queue.get(
                        timeout=0.1
                    )
                )

            except queue.Empty:

                continue

            self.event_bus.publish(
                "audio_chunk",
                audio_chunk
            )