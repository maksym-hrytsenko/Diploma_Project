import numpy as np

import mlx_whisper


class OpenVocabSpeechModel:

    def __init__(
        self,
        model_repo="mlx-community/whisper-tiny"
    ):

        self.model_repo = model_repo

    # ---------------------------------
    # Transcribe
    # ---------------------------------

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
            language="en",
            condition_on_previous_text=False
        )

        text = result.get(
            "text",
            ""
        ).strip()

        if not text:
            return None

        return text

    # ---------------------------------
    # Convert PCM16 Bytes -> float32
    # ---------------------------------

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
