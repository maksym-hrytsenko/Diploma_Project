"""Speech recognition stage of the Processing layer.

Receives audio_chunk, feeds it to VoskSpeechModel, and publishes text_ready
— but only for FINAL recognition results; partial hypotheses are used for
debug logging only, never forwarded downstream.
"""

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

        self.last_partial_text = None

        self.vosk_model = (
            VoskSpeechModel()
        )

    def start(self):

        self.event_bus.subscribe(
            "audio_chunk",
            self.on_audio
        )

    def stop(self):

        self.event_bus.unsubscribe(
            "audio_chunk",
            self.on_audio
        )

        self.vosk_model.close()

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

        # Partial recognition is ignored, but still shown in debug mode —
        # useful for spotting whether a phrase is getting cut short before
        # it reaches command handling. Vosk repeats the same partial
        # hypothesis many times while waiting for more audio, so only
        # print on actual changes to avoid flooding the terminal.
        if not result.get(
            "is_final",
            False
        ):

            partial_text = result.get("text")

            if (
                self.debug
                and partial_text != self.last_partial_text
            ):

                print(
                    f"[voice partial] \"{partial_text}\""
                )

                self.last_partial_text = partial_text

            return

        self.last_partial_text = None

        text = result.get(
            "text"
        )

        wake_word_heard = result.get(
            "wake_word_heard",
            False
        )

        if self.debug:

            source = (
                "open-vocab"
                if result.get("open_vocab")
                else "grammar"
            )

            print(
                f"[voice final] \"{text}\" "
                f"({source}, wake_word_heard="
                f"{wake_word_heard})"
            )

        self.event_bus.publish(
            "text_ready",
            {
                "text": text,
                "wake_word_heard": wake_word_heard
            }
        )