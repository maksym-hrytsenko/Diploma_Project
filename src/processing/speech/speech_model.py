# processing/speech/speech_model.py

import json
import requests
from vosk import Model, KaldiRecognizer


# 🔹 OFFLINE (Vosk)
class VoskSpeechModel:
    def __init__(self, model_path="models/vosk"):
        self.model = Model(model_path)
        self.recognizer = KaldiRecognizer(self.model, 16000)

    def process_audio(self, audio_chunk):
        if self.recognizer.AcceptWaveform(audio_chunk.tobytes()):
            result = json.loads(self.recognizer.Result())
            return result.get("text", "")
        return None


# 🔹 ONLINE 
class WhisperSpeechModel:
    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.api_key = api_key

    def process_audio(self, audio_chunk):
        try:
            response = requests.post(
                self.api_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": ("audio.wav", audio_chunk.tobytes())},
                data={"model": "whisper-1"}
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("text", "")
            else:
                print("[Whisper] Error:", response.text)
                return None

        except Exception as e:
            print("[Whisper] Exception:", e)
            return None