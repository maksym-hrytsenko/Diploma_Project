# processing/speech/speech_recognizer.py

from processing.speech.speech_model import VoskSpeechModel, WhisperSpeechModel


class SpeechRecognizer:
    def __init__(self, event_bus, state_manager):
        self.event_bus = event_bus
        self.state_manager = state_manager

        # 🔹 моделі
        self.vosk_model = VoskSpeechModel()

        self.whisper_model = WhisperSpeechModel(
            api_url="https://api.openai.com/v1/audio/transcriptions",
            api_key="YOUR_API_KEY"
        )

        self.event_bus.subscribe("audio_chunk", self.on_audio)

    def on_audio(self, audio_chunk):
        mode = self.state_manager.get_mode()

        if mode == "offline":
            text = self.vosk_model.process_audio(audio_chunk)
        else:
            text = self.whisper_model.process_audio(audio_chunk)

        if text:
            print(f"[SpeechRecognizer] Text: {text}")
            self.event_bus.publish("text_ready", text)