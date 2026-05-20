import json

from vosk import (
    Model,
    KaldiRecognizer
)


class VoskSpeechModel:

    def __init__(
        self,
        model_path=(
            "models/"
            "vosk-model-small-en-us-0.15"
        )
    ):

        self.model = Model(model_path)

        self.recognizer = (
            KaldiRecognizer(
                self.model,
                16000
            )
        )

    # ---------------------------------
    # Process Audio
    # ---------------------------------

    def process_audio(self, audio_chunk):

        if audio_chunk is None:
            return None

        # ---------------------------------
        # Final Result
        # ---------------------------------

        if self.recognizer.AcceptWaveform(
            audio_chunk
        ):

            result = json.loads(
                self.recognizer.Result()
            )

            text = result.get(
                "text",
                ""
            ).strip()

            if text:
                return text

        # ---------------------------------
        # Partial Result
        # ---------------------------------

        partial = json.loads(
            self.recognizer.PartialResult()
        )

        partial_text = partial.get(
            "partial",
            ""
        ).strip()

        if partial_text:
            return partial_text

        return None