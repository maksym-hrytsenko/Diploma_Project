# input/microphone_input.py

import sounddevice as sd
import queue
import threading


class MicrophoneInput:
    def __init__(self, event_bus, samplerate=16000, channels=1):
        self.event_bus = event_bus
        self.samplerate = samplerate
        self.channels = channels

        self.audio_queue = queue.Queue()
        self.running = False

    def _audio_callback(self, indata, frames, time, status):
        if status:
            print("Audio status:", status)
        self.audio_queue.put(indata.copy())

    def start(self):
        self.running = True

        self.stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            callback=self._audio_callback
        )

        self.stream.start()

        threading.Thread(target=self._process_audio, daemon=True).start()
        print("[MicrophoneInput] Started")

    def stop(self):
        self.running = False
        self.stream.stop()
        self.stream.close()
        print("[MicrophoneInput] Stopped")

    def _process_audio(self):
        while self.running:
            audio_chunk = self.audio_queue.get()

            # 🔥 відправляємо далі
            self.event_bus.publish("audio_chunk", audio_chunk)