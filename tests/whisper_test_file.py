import whisper
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import time
import os

# ====== FIX для ffmpeg ======
os.environ["PATH"] += ";C:\\ffmpeg\\bin"

# ====== Налаштування ======
MODEL_NAME = "base"   # tiny / base / small
SAMPLE_RATE = 16000
DURATION = 5
AUDIO_FILE = "test_audio.wav"

# ====== Завантаження моделі ======
print("Loading Whisper model...")
model = whisper.load_model(MODEL_NAME)
print("Model loaded.\n")

print("Whisper continuous mode started...")
print("Press Ctrl+C to stop\n")

while True:
    try:
        # ====== Запис ======
        print(f"\nRecording for {DURATION} seconds... Speak now!")

        audio = sd.rec(int(DURATION * SAMPLE_RATE),
                       samplerate=SAMPLE_RATE,
                       channels=1,
                       dtype='int16')

        sd.wait()

        print("Recording finished.")

        # ====== Збереження ======
        wav.write(AUDIO_FILE, SAMPLE_RATE, audio)

        # ====== Розпізнавання ======
        print("Processing audio...")

        start_time = time.time()

        result = model.transcribe(AUDIO_FILE)

        end_time = time.time()
        latency = end_time - start_time

        # ====== Результат ======
        text = result["text"].strip()

        print("\n=== RESULT ===")
        print("Recognized:", text)
        print(f"Latency: {latency:.2f} sec")

        # ====== Команди ======
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