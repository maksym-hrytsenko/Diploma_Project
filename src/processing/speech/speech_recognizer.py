from processing.speech.speech_model import (
    VoskSpeechModel
)


class SpeechRecognizer:

    def __init__(
        self,
        event_bus,
        state_manager,
        debug=False
    ):

        self.event_bus = event_bus

        self.state_manager = state_manager

        self.debug = debug

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

        self.vosk_model.close()

    # ---------------------------------
    # Audio Handler
    # ---------------------------------

    def on_audio(self, event):

        data = event.get(
            "data"
        )

        if data is None:
            return

        result = self.vosk_model.process_audio(
            data
        )

        if result is None:
            return

        # Ignore partial recognition
        if not result.get(
            "is_final",
            False
        ):
            return

        text = result.get(
            "text"
        )

        if self.debug:

            source = (
                "open-vocab"
                if result.get("open_vocab")
                else "grammar"
            )

            print(
                f"[voice heard] \"{text}\" "
                f"({source})"
            )

        self.event_bus.publish(
            "text_ready",
            text
        )