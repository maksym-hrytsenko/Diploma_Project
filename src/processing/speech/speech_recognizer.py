from processing.speech.speech_model import (
    VoskSpeechModel
)


class SpeechRecognizer:

    def __init__(
        self,
        event_bus,
        state_manager
    ):

        self.event_bus = event_bus

        self.state_manager = state_manager

        self.vosk_model = (
            VoskSpeechModel()
        )

    # ---------------------------------
    # Start
    # ---------------------------------

    def start(self):

        self.event_bus.subscribe(
            "audio_chunk",
            self.on_audio
        )

    # ---------------------------------
    # Stop
    # ---------------------------------

    def stop(self):

        self.event_bus.unsubscribe(
            "audio_chunk",
            self.on_audio
        )

    # ---------------------------------
    # Audio Handler
    # ---------------------------------

    def on_audio(self, event):

        audio_chunk = event.get("data")

        if audio_chunk is None:
            return

        text = (
            self.vosk_model.process_audio(
                audio_chunk
            )
        )

        if not text:
            return

        self.event_bus.publish(
            "text_ready",
            text
        )