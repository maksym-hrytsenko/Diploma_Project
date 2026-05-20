import os
import json
import queue
import time

import sounddevice as sd

from vosk import (
    Model,
    KaldiRecognizer
)

# =====================================
# SETTINGS
# =====================================

SAMPLE_RATE = 16000

# -------------------------------------
# Cross-platform model path
# -------------------------------------

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

# =====================================
# AUDIO QUEUE
# =====================================

audio_queue = queue.Queue()

# =====================================
# AUDIO CALLBACK
# =====================================

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

# =====================================
# LATENCY TRACKING
# =====================================

is_recording = False

start_time = None

# =====================================
# START AUDIO STREAM
# =====================================

with sd.RawInputStream(

    samplerate=SAMPLE_RATE,

    blocksize=8000,

    dtype="int16",

    channels=1,

    callback=callback
):

    while True:

        data = audio_queue.get()

        # ---------------------------------
        # FINAL RESULT
        # ---------------------------------

        if recognizer.AcceptWaveform(data):

            result = json.loads(
                recognizer.Result()
            )

            text = result.get(
                "text",
                ""
            ).strip()

            if text:

                # Latency
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

                # ---------------------------------
                # Command detection
                # ---------------------------------

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

        # ---------------------------------
        # PARTIAL RESULT
        # ---------------------------------

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