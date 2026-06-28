import json
import os

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

        self.model = Model(
            model_path
        )

        grammar = self._load_grammar()

        self.recognizer = KaldiRecognizer(
            self.model,
            16000,
            grammar
        )

    # ---------------------------------
    # Load Grammar
    # ---------------------------------

    def _load_grammar(self):

        base_dir = os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    os.path.abspath(__file__)
                )
            )
        )

        mapping_path = os.path.join(
            base_dir,
            "config",
            "mapping.json"
        )

        with open(
            mapping_path,
            "r",
            encoding="utf-8"
        ) as f:

            mapping = json.load(f)

        grammar = list(
            mapping.get(
                "voice",
                {}
            ).values()
        )

        grammar.append(
            "[unk]"
        )

        return json.dumps(grammar)

    # ---------------------------------
    # Process Audio
    # ---------------------------------

    def process_audio(
        self,
        audio_chunk
    ):

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

                return {

                    "text": text,

                    "is_final": True

                }

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

            return {

                "text": partial_text,

                "is_final": False

            }

        return None