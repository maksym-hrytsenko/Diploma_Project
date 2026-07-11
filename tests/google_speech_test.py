"""Standalone manual test of the SpeechRecognition library's Google Web
Speech API backend: records a fixed-length audio clip, transcribes it, and
checks the transcript against a few hardcoded voice commands, to evaluate
latency/accuracy before wiring speech recognition into the main app.
"""

import speech_recognition as sr
import sounddevice as sd
import scipy.io.wavfile as wav
import time
import os

SAMPLE_RATE = 16000
DURATION = 5  # seconds per recording
AUDIO_FILE = "google_test.wav"

recognizer = sr.Recognizer()

print("Google Speech Recognition started...")
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

        with sr.AudioFile(AUDIO_FILE) as source:
            audio_data = recognizer.record(source)

        print("Processing with Google Speech Recognition...")

        start_time = time.time()

        text = recognizer.recognize_google(audio_data)

        end_time = time.time()
        latency = end_time - start_time

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

    except sr.UnknownValueError:
        print("Could not understand audio")

    except sr.RequestError as e:
        print(f"API error: {e}")

    except KeyboardInterrupt:
        print("\nStopped by user")
        break