"""Offline speech recognition core, backing SpeechRecognizer.

Wraps Vosk's grammar-constrained recognizer (built from config/mapping.json's
voice phrases), gates results through Silero VAD to reject ambient noise,
and falls back to open-vocabulary Whisper transcription when the grammar
can't cover what was said.
"""

import json

from concurrent.futures import ProcessPoolExecutor

import numpy as np
import torch

from vosk import (
    Model,
    KaldiRecognizer
)

from silero_vad import (
    load_silero_vad,
    get_speech_timestamps
)

from processing.speech.open_vocab_worker import (
    transcribe_task
)

from config.config_loader import (
    load_mapping_config,
    load_system_config
)


class VoskSpeechModel:

    def __init__(
        self,
        model_path=None
    ):

        system_config = load_system_config()

        self.sample_rate = system_config.get(
            "audio",
            {}
        ).get(
            "sample_rate",
            16000
        )

        if model_path is None:

            model_path = system_config.get(
                "speech",
                {}
            ).get(
                "vosk_model_path",
                "models/vosk-model-small-en-us-0.15"
            )

        self.model = Model(
            model_path
        )

        self.wake_word = self._load_wake_word()

        grammar = self._load_grammar()

        self.recognizer = KaldiRecognizer(
            self.model,
            self.sample_rate,
            grammar
        )

        self.utterance_chunks = []

        # True the moment the grammar recognizer sees the wake word in ANY
        # partial or final hypothesis during the current utterance —
        # tracked independently of the final text, since Whisper's
        # open-vocab re-transcription can fail to reproduce "jack" even
        # when Vosk's own grammar decoder caught it clearly a moment earlier.
        self.utterance_heard_wake_word = False

        # Lazily created. Whisper transcription runs in a separate OS
        # process (not just a thread) so a slow/cold model load or a long
        # transcription can never hold the CPython GIL and stall other
        # threads — in particular the pynput CGEventTap callback thread,
        # which macOS permanently disables if it doesn't return quickly.
        self.open_vocab_executor = None

        self._load_nlu_fallback_config()

        # Tiny/fast (~1s load, ~40ms per check) — safe to run in-process,
        # unlike Whisper/LLM. Filters out ambient sound (background
        # video/music/room noise) before it reaches the grammar result or
        # the open-vocab fallback.
        self.vad_model = (
            load_silero_vad()
            if self.vad_enabled
            else None
        )

    def _load_grammar(self):

        mapping = load_mapping_config()

        grammar = list(
            mapping.get(
                "voice",
                {}
            ).values()
        )

        if self.wake_word and self.wake_word not in grammar:

            grammar.append(
                self.wake_word
            )

        grammar.append(
            "[unk]"
        )

        return json.dumps(grammar)

    def _load_wake_word(self):

        system = load_system_config()

        return system.get(
            "wake_word",
            "jack"
        )

    def _load_nlu_fallback_config(self):

        system = load_system_config()

        self.vad_enabled = system.get(
            "vad_enabled",
            True
        )

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
            "mlx-community/whisper-base.en-mlx"
        )

        min_fallback_audio_seconds = nlu_fallback.get(
            "min_fallback_audio_seconds",
            0.6
        )

        # 16-bit mono -> 2 bytes/sample
        bytes_per_second = self.sample_rate * 2

        self.min_fallback_audio_bytes = int(
            bytes_per_second * min_fallback_audio_seconds
        )

    def process_audio(
        self,
        audio_chunk
    ):

        if audio_chunk is None:
            return None

        self.utterance_chunks.append(
            audio_chunk
        )

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

            heard_wake_word = (
                self.utterance_heard_wake_word
                or self.wake_word in text.split()
            )

            self.utterance_heard_wake_word = False

            buffered_audio = b"".join(
                self.utterance_chunks
            )

            self.utterance_chunks = []

            # Discard the whole utterance if no actual speech was detected
            # in it — this is what keeps a TV/video/music playing nearby
            # from being treated as spoken commands.
            if not self._has_speech(buffered_audio):

                return None

            used_open_vocab = False

            # Vosk's phrase-list grammar can chain multiple list entries
            # into one final result, so any "[unk]" token anywhere means
            # part of the utterance fell outside the grammar —
            # re-transcribe the whole thing with the open-vocabulary model
            # rather than only acting on an exact "[unk]" match, which
            # would leave the literal token "[unk]" to be matched against
            # commands downstream.
            if "[unk]" in text.split():

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

                    "open_vocab": used_open_vocab,

                    "wake_word_heard": heard_wake_word

                }

        partial = json.loads(
            self.recognizer.PartialResult()
        )

        partial_text = partial.get(
            "partial",
            ""
        ).strip()

        if self.wake_word in partial_text.split():

            self.utterance_heard_wake_word = True

        if partial_text:

            return {

                "text": partial_text,

                "is_final": False

            }

        return None

    def _has_speech(
        self,
        audio_bytes
    ):

        if not self.vad_enabled:
            return True

        if not audio_bytes:
            return False

        samples = np.frombuffer(
            audio_bytes,
            dtype=np.int16
        )

        audio_tensor = torch.from_numpy(
            samples.astype(np.float32) / 32768.0
        )

        speech_timestamps = get_speech_timestamps(
            audio_tensor,
            self.vad_model,
            sampling_rate=self.sample_rate
        )

        return len(speech_timestamps) > 0

    def _fallback_transcribe(
        self,
        audio_bytes
    ):

        if not self.nlu_fallback_enabled:
            return None

        if not audio_bytes:
            return None

        # Too short to plausibly be a spoken command — skip it rather than
        # risk Whisper hallucinating text out of a noise/breath blip.
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

    def close(self):

        if self.open_vocab_executor is not None:

            self.open_vocab_executor.shutdown(
                wait=False,
                cancel_futures=True
            )

            self.open_vocab_executor = None
