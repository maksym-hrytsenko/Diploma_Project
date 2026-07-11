"""Standalone exploratory script for testing OpenAI Whisper transcription.

Records short audio clips from the microphone in a loop, transcribes each
with a local Whisper model, prints latency, and matches a few hardcoded
phrases to command names. Used to verify Whisper's transcription API in
isolation before relying on it elsewhere in the project.
"""

import whisper
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import time
import os

# Whisper shells out to ffmpeg; on this machine it isn't on PATH by default.
os.environ["PATH"] += ";C:\\ffmpeg\\bin"

MODEL_NAME = "base"   # tiny / base / small
SAMPLE_RATE = 16000
DURATION = 5
AUDIO_FILE = "test_audio.wav"

print("Loading Whisper model...")
model = whisper.load_model(MODEL_NAME)
print("Model loaded.\n")

print("Whisper continuous mode started...")
print("Press Ctrl+C to stop\n")

while True:
    try:
        print(f"\nRecording for {DURATION} seconds... Speak now!")

        audio = sd.rec(int(DURATION * SAMPLE_RATE),
                       samplerate=SAMPLE_RATE,
                       channels=1,
                       dtype='int16')

        sd.wait()

        print("Recording finished.")

        wav.write(AUDIO_FILE, SAMPLE_RATE, audio)

        print("Processing audio...")

        start_time = time.time()

        result = model.transcribe(AUDIO_FILE)

        end_time = time.time()
        latency = end_time - start_time

        text = result["text"].strip()

        print("\n=== RESULT ===")
        print("Recognized:", text)
        print(f"Latency: {latency:.2f} sec")

        text_lower = text.lower()

        if "open browser" in text_lower:
            print("COMMAND DETECTED: OPEN BROWSER")

        elif "close window" in text_lower:
            print("COMMAND DETECTED: CLOSE WINDOW")

        elif "scroll down" in text_lower:
            print("COMMAND DETECTED: SCROLL DOWN")

        elif "scroll up" in text_lower:
            print("COMMAND DETECTED: SCROLL UP")

    except KeyboardInterrupt:
        print("\nStopped by user")
        break

    except Exception as e:
        print(f"Error: {e}")