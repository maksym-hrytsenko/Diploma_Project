import queue
import threading

import sounddevice as sd

from config.config_loader import load_system_config


class MicrophoneInput:

    def __init__(
        self,
        event_bus,
        samplerate=None,
        channels=None,
        device=None
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

        # None means: use the OS default input device
        self.device = device

    # ---------------------------------
    # Audio Callback
    # ---------------------------------

    def _audio_callback(
        self,
        indata,
        frames,
        time_info,
        status
    ):

        if status:
            print(
                f"[MicrophoneInput] Stream status: {status}"
            )

        self.audio_queue.put(
            bytes(indata)
        )

    # ---------------------------------
    # Start
    # ---------------------------------

    def start(self):

        self.running = True

        device_info = sd.query_devices(
            self.device,
            "input"
        )

        print(
            f"[MicrophoneInput] Using input device: {device_info['name']}"
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

        threading.Thread(
            target=self._process_audio,
            daemon=True
        ).start()

        print(
            "[MicrophoneInput] Started"
        )

    # ---------------------------------
    # Stop
    # ---------------------------------

    def stop(self):

        self.running = False

        if self.stream:

            self.stream.stop()

            self.stream.close()

        print(
            "[MicrophoneInput] Stopped"
        )

    # ---------------------------------
    # Audio Processing Loop
    # ---------------------------------

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