import whisper
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import time
import os

os.environ["PATH"] += ";C:\\ffmpeg\\bin"

# ====== Налаштування ======
MODEL_NAME = "base"   # tiny / base / small (можеш змінювати)
SAMPLE_RATE = 16000
DURATION = 5  # секунд запису

AUDIO_FILE = "test_audio.wav"

# ====== Завантаження моделі ======
print("Loading Whisper model...")
model = whisper.load_model(MODEL_NAME)
print("Model loaded.\n")

# ====== Запис аудіо ======
print(f"Recording for {DURATION} seconds... Speak now!")

audio = sd.rec(int(DURATION * SAMPLE_RATE),
               samplerate=SAMPLE_RATE,
               channels=1,
               dtype='int16')

sd.wait()

print("Recording finished.\n")

# ====== Збереження ======
wav.write(AUDIO_FILE, SAMPLE_RATE, audio)

# ====== Розпізнавання ======
print("Processing audio...")

start_time = time.time()

result = model.transcribe(AUDIO_FILE)

end_time = time.time()
latency = end_time - start_time

# ====== Результат ======
text = result["text"]

print("\n=== RESULT ===")
print("Recognized:", text)
print(f"Latency: {latency:.2f} sec")

# ====== Прості команди ======
if "open browser" in text.lower():
    print("COMMAND DETECTED: OPEN BROWSER")

elif "close window" in text.lower():
    print("COMMAND DETECTED: CLOSE WINDOW")

elif "scroll down" in text.lower():
    print("COMMAND DETECTED: SCROLL DOWN")

elif "scroll up" in text.lower():
    print("COMMAND DETECTED: SCROLL UP")