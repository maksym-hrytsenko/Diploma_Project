"""Offline speech recognition core, backing SpeechRecognizer.

Wraps Vosk's grammar-constrained recognizer (built from config/mapping.json's
voice phrases), gates results through Silero VAD to reject ambient noise,
and falls back to open-vocabulary Whisper transcription when the grammar
can't cover what was said.

Utterance segmentation — deciding WHEN a spoken phrase is actually over — is
driven by a continuous, independent Silero VAD stream (see
self.streaming_vad_model / _chunk_has_speech / process_audio's
vad_silence_hangover_ms check), not by Vosk's own AcceptWaveform() endpoint
decision. Vosk's constrained grammar decoder can flush a "final" Result()
mid-sentence, well before the person is actually done talking, on longer
phrases especially (a brief pause is enough); trusting that as "the phrase is
over" is what used to split one spoken command into multiple independent
text_ready fragments — each with its own chance to miss the wake word — for
IntentModel to try to reassemble after the fact. Vosk's per-fragment text is
still folded into a running utterance-wide transcript as it arrives (see
utterance_grammar_text), and the fast exact-grammar-match path still applies
to the WHOLE utterance once it's confirmed over — Vosk just no longer gets to
decide when "over" is.
"""

import functools
import json
import time

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
    load_system_config,
    resolve_model_path
)


class VoskSpeechModel:

    # Silero VAD's documented streaming window size at 16kHz — see
    # _chunk_has_speech. A trailing partial window shorter than this within
    # a chunk is simply skipped rather than padded (~20ms of a 500ms chunk
    # at the default 8000-sample blocksize; negligible, and any speech
    # spanning it is still caught by the next chunk's full windows).
    VAD_STREAM_WINDOW_SAMPLES = 512

    def __init__(
        self,
        model_path=None,
        on_fallback_ready=None
    ):

        # Called (from a background thread — see _start_fallback_transcribe)
        # with a result dict once an async Whisper fallback finishes,
        # instead of process_audio blocking the caller until it's done —
        # a slow/cold subprocess call previously stalled the whole audio
        # pipeline, so no further chunks (i.e. the rest of what the person
        # was still saying) got processed until it returned. Confirmed
        # against a real test session: an 8+ second gap between two
        # fragments of one spoken phrase that turned out to be processing
        # backlog, not the person actually pausing that long. None means
        # the caller doesn't want fallback results at all.
        self.on_fallback_ready = on_fallback_ready

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

        model_path = resolve_model_path(
            model_path
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

        # Raw audio bytes buffered for the utterance currently in progress
        # — only accumulated once self.utterance_active goes True (see
        # process_audio), so silence between utterances never sits here.
        self.utterance_chunks = []

        # Wall-clock time (time.time()) the FIRST chunk of the current
        # utterance started, estimated from that chunk's own EventBus
        # publish timestamp minus the chunk's own duration (the publish
        # timestamp lands at the END of the block, once it's fully
        # captured, not its start). Combined with Silero VAD's own
        # within-buffer speech-onset offset in _finalize_utterance, this
        # gives an estimate of the real wall-clock moment speech began —
        # used for manual latency testing (see
        # tests/MANUAL_TEST_SCENARIOS.md §4.6) so a test session doesn't
        # need a separate stopwatch. None whenever the caller didn't
        # supply a chunk timestamp.
        self.utterance_start_time = None

        # True from the moment self.streaming_vad_model first detects real
        # speech in the utterance currently in progress until it's
        # finalized (see process_audio/_finalize_utterance) — the
        # authority on whether an utterance is still open, independent of
        # Vosk's own AcceptWaveform() endpoint decisions (see module
        # docstring).
        self.utterance_active = False

        # Wall-clock time of the most recent chunk in which
        # self.streaming_vad_model detected speech, during the utterance
        # currently in progress. process_audio finalizes the utterance
        # once vad_silence_hangover_ms has passed since this without new
        # speech — the real "gone quiet" signal, not a fixed timeout
        # measured from Vosk's own last fragment.
        self.last_speech_chunk_time = None

        # Vosk's own per-fragment Result() text, concatenated as each
        # arrives during the utterance currently in progress — Vosk can
        # flush several of these within one spoken phrase (see module
        # docstring); this is the whole utterance's grammar-path
        # transcript once it's finalized, used for the fast exact-match
        # path so most short in-grammar commands still skip Whisper
        # entirely.
        self.utterance_grammar_text = ""

        # True if ANY fragment folded into utterance_grammar_text
        # contained "[unk]" — the whole utterance falls back to Whisper
        # once finalized if so, same as the old per-fragment behavior, just
        # decided once per utterance instead of once per Vosk fragment.
        self.utterance_saw_unk = False

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
        # the open-vocab fallback. Used only for the whole-buffer,
        # one-shot _speech_timestamps() gate at utterance finalization.
        self.vad_model = (
            load_silero_vad()
            if self.vad_enabled
            else None
        )

        # A SEPARATE model instance, never touched by _speech_timestamps'
        # one-shot get_speech_timestamps() calls above — those reset
        # Silero VAD's own internal streaming state on every call, which
        # would corrupt _chunk_has_speech's continuity (it calls this
        # model directly, chunk by chunk, expecting an uninterrupted
        # stream) every time an utterance finalizes. Loading the model
        # twice is cheap (~1s each, at startup only).
        self.streaming_vad_model = (
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

        # Silero VAD's own defaults (threshold=0.5, min_speech_duration_ms=
        # 250) are loose enough that quiet room tone/breathing/fan noise
        # occasionally reads as "possibly speech" — that's not enough
        # signal to transcribe anything real, but it's enough to let a
        # near-empty buffer through to the Whisper fallback below, which
        # then hallucinates plausible-looking text from noise rather than
        # reporting silence (see _looks_like_hallucination for the second
        # half of this mitigation). Raised from the library defaults after
        # exactly this was observed in a real quiet-room test session.
        self.vad_threshold = system.get(
            "vad_threshold",
            0.65
        )

        self.vad_min_speech_duration_ms = system.get(
            "vad_min_speech_duration_ms",
            300
        )

        # How long of confirmed silence (no speech detected by
        # self.streaming_vad_model) after the last speech ends an
        # utterance — see process_audio/_finalize_utterance. This is what
        # now absorbs a longer phrase's natural mid-sentence pauses
        # (breathing, thinking) instead of Vosk's own endpoint decision;
        # IntentModel's wake_word_silence_timeout_seconds is a separate,
        # much longer gap that only matters BETWEEN whole utterances.
        self.vad_silence_hangover_ms = system.get(
            "vad_silence_hangover_ms",
            900
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
        audio_chunk,
        chunk_timestamp=None
    ):

        if audio_chunk is None:
            return None

        now = (
            chunk_timestamp
            if chunk_timestamp is not None
            else time.time()
        )

        if self.vad_enabled:

            if self._chunk_has_speech(audio_chunk):

                self.utterance_active = True

                self.last_speech_chunk_time = now

        else:

            # No independent speech/silence signal available to hang a
            # hangover timer off of — fall back to trusting Vosk's own
            # endpoint decision directly, exactly as before this rework
            # (see the vosk_finalized branch and utterance_ended below).
            self.utterance_active = True

        # Only buffer raw audio once an utterance has actually started —
        # otherwise silence between utterances would accumulate here
        # forever, since finalization below is gated on utterance_active
        # now, not on Vosk's own endpoint decision (see module docstring).
        if self.utterance_active:

            # First buffered chunk of a fresh utterance — record its
            # estimated start time (see utterance_start_time in __init__
            # for why the chunk's own duration is subtracted from its
            # publish timestamp).
            if not self.utterance_chunks:

                if chunk_timestamp is not None:

                    chunk_duration = (
                        len(audio_chunk) / 2 / self.sample_rate
                    )

                    self.utterance_start_time = (
                        chunk_timestamp - chunk_duration
                    )

                else:

                    self.utterance_start_time = None

            self.utterance_chunks.append(
                audio_chunk
            )

        vosk_finalized = self.recognizer.AcceptWaveform(
            audio_chunk
        )

        partial_text = ""

        if vosk_finalized:

            # Vosk's OWN endpoint decision — may fire more than once
            # within a single spoken phrase (see module docstring). Its
            # text is folded into the running utterance-wide transcript
            # instead of being treated as the utterance being over; only
            # the streaming-VAD hangover check below decides that.
            result = json.loads(
                self.recognizer.Result()
            )

            fragment_text = result.get(
                "text",
                ""
            ).strip()

            if fragment_text:

                fragment_words = fragment_text.split()

                if self.wake_word in fragment_words:
                    self.utterance_heard_wake_word = True

                if "[unk]" in fragment_words:
                    self.utterance_saw_unk = True

                self.utterance_grammar_text = (
                    f"{self.utterance_grammar_text} {fragment_text}"
                ).strip()

        else:

            partial = json.loads(
                self.recognizer.PartialResult()
            )

            partial_text = partial.get(
                "partial",
                ""
            ).strip()

            if self.wake_word in partial_text.split():
                self.utterance_heard_wake_word = True

        if self.vad_enabled:

            utterance_ended = (
                self.utterance_active
                and self.last_speech_chunk_time is not None
                and (
                    (now - self.last_speech_chunk_time) * 1000
                    >= self.vad_silence_hangover_ms
                )
            )

        else:

            # No streaming VAD signal to hang a hangover timer off of —
            # Vosk's own endpoint decision IS the utterance boundary here,
            # same as before this rework.
            utterance_ended = vosk_finalized

        if utterance_ended:
            return self._finalize_utterance()

        if partial_text:

            return {

                "text": partial_text,

                "is_final": False

            }

        return None

    # Streaming speech/no-speech decision for ONE incoming chunk —
    # independent of Vosk's own endpointing, and the actual authority on
    # when an utterance has gone quiet (see process_audio/
    # _finalize_utterance and the module docstring). Uses
    # self.streaming_vad_model, never self.vad_model (see that attribute's
    # own comment in __init__ for why the two must stay separate).
    def _chunk_has_speech(
        self,
        audio_chunk
    ):

        if not self.vad_enabled:
            return True

        if not audio_chunk:
            return False

        samples = np.frombuffer(
            audio_chunk,
            dtype=np.int16
        )

        if len(samples) == 0:
            return False

        audio_tensor = torch.from_numpy(
            samples.astype(np.float32) / 32768.0
        )

        window = self.VAD_STREAM_WINDOW_SAMPLES

        for start in range(
            0,
            len(audio_tensor) - window + 1,
            window
        ):

            segment = audio_tensor[start:start + window]

            speech_probability = self.streaming_vad_model(
                segment,
                self.sample_rate
            ).item()

            if speech_probability >= self.vad_threshold:
                return True

        return False

    # The utterance currently in progress has just been confirmed over
    # (vad_silence_hangover_ms of real silence since the last speech, see
    # process_audio) — resolves it to either a fast exact-grammar-match
    # result or a single whole-utterance Whisper fallback call, and resets
    # every piece of per-utterance state for the next one.
    def _finalize_utterance(self):

        buffered_audio = b"".join(
            self.utterance_chunks
        )

        utterance_start_time = self.utterance_start_time

        heard_wake_word = self.utterance_heard_wake_word

        grammar_text = self.utterance_grammar_text

        saw_unk = self.utterance_saw_unk

        self._reset_utterance_state()

        speech_timestamps = self._speech_timestamps(
            buffered_audio
        )

        # Discard the whole utterance if no actual speech was detected in
        # it — this is what keeps a TV/video/music playing nearby from
        # being treated as spoken commands. speech_timestamps is None (not
        # an empty list) when VAD is disabled — nothing to gate on in that
        # case, same as the old _has_speech behavior.
        if (
            speech_timestamps is not None
            and len(speech_timestamps) == 0
        ):

            return None

        # Estimated wall-clock moment real speech began: the utterance's
        # own start time plus how far into the buffer VAD's first detected
        # speech segment sits. Used only for manual latency testing — see
        # utterance_start_time in __init__.
        speech_onset_estimate = None

        if (
            utterance_start_time is not None
            and speech_timestamps
        ):

            speech_onset_estimate = (
                utterance_start_time
                + speech_timestamps[0]["start"] / self.sample_rate
            )

        # A clean, fully in-grammar transcript for the WHOLE utterance —
        # the fast path, no Whisper needed. Vosk's phrase-list grammar can
        # chain multiple list entries into one fragment, so any "[unk]"
        # token anywhere in ANY fragment means part of the utterance fell
        # outside the grammar and the whole thing needs Whisper instead —
        # never acting on a partial match that would leave the literal
        # token "[unk]" to be matched against commands downstream.
        if grammar_text and not saw_unk:

            return {

                "text": grammar_text,

                "is_final": True,

                "open_vocab": False,

                "wake_word_heard": heard_wake_word,

                "speech_onset_estimate": speech_onset_estimate

            }

        # No usable in-grammar transcript for the whole utterance — send
        # ALL of its audio to Whisper in a single call, now that the
        # utterance's real end is known, instead of guessing at a fragment
        # boundary Vosk picked on its own (the original source of longer
        # phrases getting split, and the wake word sometimes landing in
        # the wrong fragment and being missed entirely). Started in the
        # background, not awaited here — see _start_fallback_transcribe.
        # This returns None for this utterance; if Whisper does produce
        # usable text, it arrives later via on_fallback_ready instead.
        self._start_fallback_transcribe(
            buffered_audio,
            heard_wake_word,
            speech_onset_estimate
        )

        return None

    def _reset_utterance_state(self):

        self.utterance_chunks = []

        self.utterance_start_time = None

        self.utterance_active = False

        self.last_speech_chunk_time = None

        self.utterance_grammar_text = ""

        self.utterance_saw_unk = False

        self.utterance_heard_wake_word = False

    def _speech_timestamps(
        self,
        audio_bytes
    ):
        """Silero VAD's own speech-segment offsets within audio_bytes.

        Returns None when VAD is disabled (caller has no speech/no-speech
        signal and no timing info to gate or estimate onset from — treated
        as "assume speech present"), or a (possibly empty) list of
        {"start": sample_index, "end": sample_index} dicts otherwise. An
        empty list means no speech was detected anywhere in the buffer.
        """

        if not self.vad_enabled:
            return None

        if not audio_bytes:
            return []

        samples = np.frombuffer(
            audio_bytes,
            dtype=np.int16
        )

        audio_tensor = torch.from_numpy(
            samples.astype(np.float32) / 32768.0
        )

        return get_speech_timestamps(
            audio_tensor,
            self.vad_model,
            sampling_rate=self.sample_rate,
            threshold=self.vad_threshold,
            min_speech_duration_ms=self.vad_min_speech_duration_ms
        )

    # Fire-and-forget: submits the Whisper transcription and returns
    # immediately, instead of blocking process_audio's caller (the
    # microphone thread) for however long a cold model load or a slow
    # transcription takes. add_done_callback's callback runs on the
    # executor's own result-watching thread once the worker process
    # finishes, never on the calling thread, so audio_chunk events for
    # whatever the person keeps saying in the meantime keep flowing
    # through the pipeline instead of queuing up behind this call.
    def _start_fallback_transcribe(
        self,
        audio_bytes,
        heard_wake_word,
        speech_onset_estimate
    ):

        if not self.nlu_fallback_enabled:
            return

        if not audio_bytes:
            return

        # Too short to plausibly be a spoken command — skip it rather than
        # risk Whisper hallucinating text out of a noise/breath blip.
        if len(audio_bytes) < self.min_fallback_audio_bytes:
            return

        if self.open_vocab_executor is None:

            self.open_vocab_executor = ProcessPoolExecutor(
                max_workers=1
            )

        future = self.open_vocab_executor.submit(
            transcribe_task,
            self.open_vocab_model_id,
            audio_bytes
        )

        future.add_done_callback(
            functools.partial(
                self._handle_fallback_future,
                heard_wake_word=heard_wake_word,
                speech_onset_estimate=speech_onset_estimate
            )
        )

    def _handle_fallback_future(
        self,
        future,
        heard_wake_word,
        speech_onset_estimate
    ):

        try:

            fallback_text = future.result()

        except Exception:

            fallback_text = None

        if fallback_text and self._looks_like_hallucination(
            fallback_text
        ):

            fallback_text = None

        if not fallback_text:
            return

        if self.on_fallback_ready is None:
            return

        self.on_fallback_ready(
            {

                "text": fallback_text,

                "is_final": True,

                "open_vocab": True,

                "wake_word_heard": heard_wake_word,

                "speech_onset_estimate": speech_onset_estimate

            }
        )

    # Whisper's classic failure mode on audio with little or no real
    # speech content (quiet-room tone, breathing, a stray noise VAD let
    # through) isn't an empty transcription — it's a fluent-looking but
    # made-up word or phrase, often looped several times in a row (e.g.
    # "Parallel Parallel Parallel..."), confirmed against a real quiet-room
    # test session. Three identical words back to back is not something a
    # real spoken command in this project's vocabulary would ever produce,
    # so it's treated as a hallucination and discarded rather than passed
    # on to be matched against commands.
    def _looks_like_hallucination(
        self,
        text
    ):

        words = text.lower().split()

        for index in range(len(words) - 2):

            if (
                words[index] == words[index + 1]
                and words[index] == words[index + 2]
            ):
                return True

        return False

    def close(self):

        if self.open_vocab_executor is not None:

            self.open_vocab_executor.shutdown(
                wait=False,
                cancel_futures=True
            )

            self.open_vocab_executor = None
