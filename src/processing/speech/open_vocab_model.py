"""Open-vocabulary speech transcription fallback.

Wraps a local MLX-hosted Whisper model, used when Vosk's fixed grammar
doesn't cover what was said (e.g. free-text phrases IntentModel's NLU
fallback needs to interpret) rather than for primary recognition.
"""

import numpy as np

import mlx_whisper

from config.config_loader import load_system_config


class OpenVocabSpeechModel:

    def __init__(
        self,
        model_repo=None
    ):

        system_config = load_system_config()

        if model_repo is None:

            model_repo = system_config.get(
                "nlu_fallback",
                {}
            ).get(
                "open_vocab_whisper_model",
                "mlx-community/whisper-base.en-mlx"
            )

        self.model_repo = model_repo

        open_vocab_config = system_config.get(
            "speech",
            {}
        ).get(
            "open_vocab",
            {}
        )

        self.language = open_vocab_config.get(
            "language",
            "en"
        )

        self.condition_on_previous_text = open_vocab_config.get(
            "condition_on_previous_text",
            False
        )

    def transcribe(
        self,
        audio_bytes
    ):

        if not audio_bytes:
            return None

        audio = self._to_float32(
            audio_bytes
        )

        result = mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=self.model_repo,
            language=self.language,
            condition_on_previous_text=self.condition_on_previous_text
        )

        text = result.get(
            "text",
            ""
        ).strip()

        if not text:
            return None

        return text

    def _to_float32(
        self,
        audio_bytes
    ):

        samples = np.frombuffer(
            audio_bytes,
            dtype=np.int16
        )

        return (
            samples.astype(np.float32) / 32768.0
        )
