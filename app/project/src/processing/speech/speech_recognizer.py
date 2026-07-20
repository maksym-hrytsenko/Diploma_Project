"""Speech recognition stage of the Processing layer.

Receives audio_chunk, feeds it to VoskSpeechModel, and publishes text_ready
— but only for FINAL recognition results; partial hypotheses are used for
debug logging only, never forwarded downstream.
"""

import logging

from processing.speech.speech_model import (
    VoskSpeechModel
)

from utils.logger import get_logger


logger = get_logger(__name__)


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

        # The shared "gvcontrol" root logger (utils/logger.py) is fixed at
        # INFO, so logger.debug() below would otherwise be silently dropped
        # before it ever reaches a handler, regardless of --debug-voice.
        # Raising this module's own logger overrides that floor for it only.
        if self.debug:

            logger.setLevel(
                logging.DEBUG
            )

        self.last_partial_text = None

        # Passed to VoskSpeechModel so an async Whisper fallback result
        # (arriving later, from a background thread — see
        # VoskSpeechModel._start_fallback_transcribe) is handled by the
        # exact same logging/publishing path as a synchronous result,
        # instead of duplicating it.
        self.vosk_model = VoskSpeechModel(
            on_fallback_ready=self._handle_final_result
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

        # EventBus stamps every event with the wall-clock time it was
        # published (core/event_bus.py) — that's this chunk's own capture
        # time, which VoskSpeechModel uses (together with Silero VAD's
        # in-buffer offset) to estimate when real speech began, for manual
        # latency testing. Not used for recognition itself.
        chunk_timestamp = event.get(
            "timestamp"
        )

        result = self.vosk_model.process_audio(
            data,
            chunk_timestamp
        )

        if result is None:
            return

        # Partial recognition is never matched against commands, but a
        # non-empty partial means Vosk is still actively hearing speech
        # right now — published as voice_activity purely so IntentModel
        # can keep an already-open session's silence deadline pushed
        # forward while the person is still mid-sentence. Without this,
        # the deadline only ever advanced when a chunk FINALIZED, which
        # (confirmed against a real test session) can trail the person's
        # actual speech by several seconds on a longer phrase — Vosk's own
        # endpoint detection needs to hear the rest of the sentence before
        # it decides where the previous one ended, so a fixed timeout
        # measured from finalization time was effectively also counting
        # against how long Vosk itself takes to catch up, not just real
        # silence. See tests/MANUAL_TEST_SCENARIOS.md §4.6.
        if not result.get(
            "is_final",
            False
        ):

            partial_text = result.get("text")

            self.event_bus.publish(
                "voice_activity",
                {}
            )

            if (
                self.debug
                and partial_text != self.last_partial_text
            ):

                logger.debug(
                    "[voice partial] \"%s\"",
                    partial_text
                )

                self.last_partial_text = partial_text

            return

        self._handle_final_result(result)

    # Shared by the synchronous path above (a grammar-only or already-
    # awaited result) and VoskSpeechModel's async Whisper callback, which
    # invokes this same method later, from a different thread, once a
    # fallback transcription finishes — see VoskSpeechModel.__init__'s
    # on_fallback_ready. Either way, a final result is handled identically
    # from here on.
    def _handle_final_result(self, result):

        self.last_partial_text = None

        text = result.get(
            "text"
        )

        wake_word_heard = result.get(
            "wake_word_heard",
            False
        )

        speech_onset_estimate = result.get(
            "speech_onset_estimate"
        )

        source = (
            "open-vocab"
            if result.get("open_vocab")
            else "grammar"
        )

        # Always logged at INFO (not gated behind --debug-voice, and not
        # at DEBUG level — the root logger is configured at INFO, see
        # utils/logger.py, so a DEBUG call here would never reach the log
        # file at all) so a manual test session's log always has a
        # speech_onset value to diff against SignalMapper's "[RESOLVED]"
        # line for that same command — see
        # tests/MANUAL_TEST_SCENARIOS.md §4.6.
        logger.info(
            "[voice final] \"%s\" (%s, wake_word_heard=%s, speech_onset=%s)",
            text,
            source,
            wake_word_heard,
            (
                f"{speech_onset_estimate:.3f}"
                if speech_onset_estimate is not None
                else "unknown"
            )
        )

        self.event_bus.publish(
            "text_ready",
            {
                "text": text,
                "wake_word_heard": wake_word_heard,
                "speech_onset_estimate": speech_onset_estimate
            }
        )