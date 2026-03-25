import queue
import sounddevice as sd
import json
import time
from vosk import Model, KaldiRecognizer

# ====== Налаштування ======
MODEL_PATH = r"C:\Users\mgric\OneDrive\Documents\Diploma_Project\models\vosk-model-small-en-us-0.15"
SAMPLE_RATE = 16000

# ====== Черга для аудіо ======
q = queue.Queue()

def callback(indata, frames, time_info, status):
    if status:
        print(status)
    q.put(bytes(indata))


# ====== Завантаження моделі ======
print("Loading model...")
model = Model(MODEL_PATH)
recognizer = KaldiRecognizer(model, SAMPLE_RATE)

print("Model loaded.")
print("Speak into the microphone...\n")

# ====== Логіка latency ======
is_recording = False
start_time = None

# ====== Запуск стріму ======
with sd.RawInputStream(
    samplerate=SAMPLE_RATE,
    blocksize=8000,
    dtype='int16',
    channels=1,
    callback=callback
):
    while True:
        data = q.get()

        if recognizer.AcceptWaveform(data):
            result = json.loads(recognizer.Result())
            text = result.get("text", "")

            if text:
                if start_time:
                    latency = time.time() - start_time
                else:
                    latency = 0

                print("\n=== RESULT ===")
                print("Recognized:", text)
                print(f"Latency: {latency:.2f} sec")

                # ====== Простий аналіз команд ======
                if "open browser" in text:
                    print("COMMAND DETECTED: OPEN BROWSER")

                elif "close window" in text:
                    print("COMMAND DETECTED: CLOSE WINDOW")

                elif "scroll down" in text:
                    print("COMMAND DETECTED: SCROLL DOWN")

                elif "scroll up" in text:
                    print("COMMAND DETECTED: SCROLL UP")

            # reset після фрази
            is_recording = False
            start_time = None

        else:
            partial = json.loads(recognizer.PartialResult())
            partial_text = partial.get("partial", "")

            if partial_text:
                # старт таймера тільки коли почалась мова
                if not is_recording:
                    start_time = time.time()
                    is_recording = True

                print("Partial:", partial_text, end="\r")