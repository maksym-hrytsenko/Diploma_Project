"""Standalone exploratory script for testing real-time speech recognition with Vosk.

Streams microphone audio through a Vosk KaldiRecognizer, prints partial and
final transcription results with latency, and matches a few hardcoded
phrases to command names. Used to verify Vosk's real-time recognition API
in isolation before relying on it elsewhere in the project.
"""

import os
import json
import queue
import time

import sounddevice as sd

from vosk import (
    Model,
    KaldiRecognizer
)

SAMPLE_RATE = 16000

# Path built relative to this file so the script works regardless of the
# working directory it's launched from.
BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "vosk-model-small-en-us-0.15"
)

audio_queue = queue.Queue()

def callback(
    indata,
    frames,
    time_info,
    status
):

    if status:

        print(status)

        return

    audio_queue.put(
        bytes(indata)
    )

# =====================================
# LOAD MODEL
# =====================================

print("Loading model...")

model = Model(MODEL_PATH)

recognizer = KaldiRecognizer(
    model,
    SAMPLE_RATE
)

print("Model loaded.")

print("Speak into the microphone...\n")

is_recording = False

start_time = None

with sd.RawInputStream(

    samplerate=SAMPLE_RATE,

    blocksize=8000,

    dtype="int16",

    channels=1,

    callback=callback
):

    while True:

        data = audio_queue.get()

        if recognizer.AcceptWaveform(data):

            result = json.loads(
                recognizer.Result()
            )

            text = result.get(
                "text",
                ""
            ).strip()

            if text:

                if start_time:

                    latency = (
                        time.time()
                        - start_time
                    )

                else:

                    latency = 0

                print("\n=== RESULT ===")

                print(
                    f"Recognized: {text}"
                )

                print(
                    f"Latency: "
                    f"{latency:.2f} sec"
                )

                if "open browser" in text:

                    print(
                        "COMMAND: OPEN_BROWSER"
                    )

                elif "close window" in text:

                    print(
                        "COMMAND: CLOSE_WINDOW"
                    )

                elif "scroll down" in text:

                    print(
                        "COMMAND: SCROLL_DOWN"
                    )

                elif "scroll up" in text:

                    print(
                        "COMMAND: SCROLL_UP"
                    )

            # Reset phrase state
            is_recording = False

            start_time = None

        else:

            partial = json.loads(
                recognizer.PartialResult()
            )

            partial_text = partial.get(
                "partial",
                ""
            ).strip()

            if partial_text:

                # Start timer on first speech
                if not is_recording:

                    start_time = time.time()

                    is_recording = True

                print(
                    f"Partial: {partial_text}",
                    end="\r"
                )