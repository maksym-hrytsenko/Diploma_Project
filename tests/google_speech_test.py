import speech_recognition as sr
import sounddevice as sd
import scipy.io.wavfile as wav
import time
import os

# ====== Налаштування ======
SAMPLE_RATE = 16000
DURATION = 5  # секунд запису
AUDIO_FILE = "google_test.wav"

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
recognizer = sr.Recognizer()

with sr.AudioFile(AUDIO_FILE) as source:
    audio_data = recognizer.record(source)

print("Processing with Google Speech Recognition...")

start_time = time.time()

try:
    text = recognizer.recognize_google(audio_data)

    end_time = time.time()
    latency = end_time - start_time

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

except sr.UnknownValueError:
    print("Could not understand audio")

except sr.RequestError as e:
    print(f"API error: {e}")