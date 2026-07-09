import json
import os

from concurrent.futures import ProcessPoolExecutor

from vosk import (
    Model,
    KaldiRecognizer
)

from processing.speech.open_vocab_worker import (
    transcribe_task
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

        self.utterance_chunks = []

        # Lazily created. Whisper transcription runs in a
        # separate OS process (not just a thread) so that a
        # slow/cold model load or a long transcription can
        # never hold the CPython GIL and stall other threads
        # in this process — in particular the pynput
        # CGEventTap callback thread, which macOS will
        # permanently disable if it does not return quickly.
        self.open_vocab_executor = None

        self._load_nlu_fallback_config()

    # ---------------------------------
    # Load Grammar
    # ---------------------------------

    def _load_grammar(self):

        mapping_path = os.path.join(
            self._base_dir(),
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

        wake_word = self._load_wake_word()

        if wake_word and wake_word not in grammar:

            grammar.append(
                wake_word
            )

        grammar.append(
            "[unk]"
        )

        return json.dumps(grammar)

    # ---------------------------------
    # Load Wake Word
    # ---------------------------------

    def _load_wake_word(self):

        system_path = os.path.join(
            self._base_dir(),
            "config",
            "system.json"
        )

        with open(
            system_path,
            "r",
            encoding="utf-8"
        ) as f:

            system = json.load(f)

        return system.get(
            "wake_word",
            "jack"
        )

    # ---------------------------------
    # Load NLU Fallback Config
    # ---------------------------------

    def _load_nlu_fallback_config(self):

        system_path = os.path.join(
            self._base_dir(),
            "config",
            "system.json"
        )

        with open(
            system_path,
            "r",
            encoding="utf-8"
        ) as f:

            system = json.load(f)

        nlu_fallback = system.get(
            "nlu_fallback",
            {}
        )

        self.nlu_fallback_enabled = nlu_fallback.get(
            "enabled",
            False
        )

        self.open_vocab_model_id = nlu_fallback.get(
            "open_vocab_whisper_model",
            "mlx-community/whisper-tiny"
        )

        min_fallback_audio_seconds = nlu_fallback.get(
            "min_fallback_audio_seconds",
            0.6
        )

        # 16kHz, 16-bit mono -> 32000 bytes/sec
        self.min_fallback_audio_bytes = int(
            32000 * min_fallback_audio_seconds
        )

    # ---------------------------------
    # Base Directory
    # ---------------------------------

    def _base_dir(self):

        return os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    os.path.abspath(__file__)
                )
            )
        )

    # ---------------------------------
    # Process Audio
    # ---------------------------------

    def process_audio(
        self,
        audio_chunk
    ):

        if audio_chunk is None:
            return None

        self.utterance_chunks.append(
            audio_chunk
        )

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

            buffered_audio = b"".join(
                self.utterance_chunks
            )

            self.utterance_chunks = []

            used_open_vocab = False

            if text == "[unk]":

                fallback_text = self._fallback_transcribe(
                    buffered_audio
                )

                if fallback_text:

                    text = fallback_text

                    used_open_vocab = True

                else:

                    text = ""

            if text:

                return {

                    "text": text,

                    "is_final": True,

                    "open_vocab": used_open_vocab

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

    # ---------------------------------
    # Open-Vocabulary Fallback
    # ---------------------------------

    def _fallback_transcribe(
        self,
        audio_bytes
    ):

        if not self.nlu_fallback_enabled:
            return None

        if not audio_bytes:
            return None

        # Too short to plausibly be a spoken command —
        # skip it rather than risk Whisper hallucinating
        # text out of a noise/breath blip.
        if len(audio_bytes) < self.min_fallback_audio_bytes:
            return None

        if self.open_vocab_executor is None:

            self.open_vocab_executor = ProcessPoolExecutor(
                max_workers=1
            )

        future = self.open_vocab_executor.submit(
            transcribe_task,
            self.open_vocab_model_id,
            audio_bytes
        )

        return future.result()

    # ---------------------------------
    # Shutdown
    # ---------------------------------

    def close(self):

        if self.open_vocab_executor is not None:

            self.open_vocab_executor.shutdown(
                wait=False,
                cancel_futures=True
            )

            self.open_vocab_executor = None
