"""Voice-command interpretation stage.

Receives text_ready (final Vosk transcripts only), gates it behind a wake
word with a rolling silence timeout, matches it against config/mapping.json's
voice commands (exact match first, then optional semantic/LLM fallback), and
publishes intent_detected. The only module allowed to turn a spoken phrase
into an internal command.
"""

import time

from concurrent.futures import (
    ProcessPoolExecutor,
    TimeoutError as FutureTimeoutError
)

from interpretation.nlu_fallback_worker import (
    semantic_match_task,
    llm_interpret_task
)

from config.config_loader import (
    load_mapping_config,
    load_system_config
)

from utils.logger import get_logger


logger = get_logger(__name__)


class IntentModel:

    def __init__(
        self,
        event_bus,
        state_manager,
        debug=False
    ):

        self.event_bus = event_bus

        self.state_manager = state_manager

        self.debug = debug

        self.mapping = load_mapping_config()

        self.system = load_system_config()

        self.voice_commands = (
            self.mapping.get(
                "voice",
                {}
            )
        )

        self.wake_word = (
            self.system.get(
                "wake_word",
                "jack"
            )
        )

        self.silence_timeout_seconds = (
            self.system.get(
                "wake_word_silence_timeout_seconds",
                2
            )
        )

        # None means no session is open. While open, this holds the
        # time.time() deadline by which more speech must arrive or the
        # session is considered gone silent — a rolling "still talking"
        # window, not a fixed deadline from the wake word itself, since
        # every new utterance pushes it forward by silence_timeout_seconds.
        self.session_deadline = None

        self.pending_command_text = ""

        nlu_fallback = self.system.get(
            "nlu_fallback",
            {}
        )

        self.nlu_fallback_enabled = nlu_fallback.get(
            "enabled",
            False
        )

        self.semantic_threshold = nlu_fallback.get(
            "semantic_threshold",
            0.72
        )

        self.llm_confidence = nlu_fallback.get(
            "llm_confidence",
            0.6
        )

        self.llm_model_id = nlu_fallback.get(
            "llm_model",
            "mlx-community/Llama-3.2-3B-Instruct-4bit"
        )

        # Upper bound on how long a semantic/LLM worker call may block the
        # caller (the speech pipeline's own callback chain) — a cold model
        # load or a hung worker process must not freeze the app forever.
        self.nlu_worker_timeout_seconds = nlu_fallback.get(
            "worker_timeout_seconds",
            15
        )

        # Lazily created. Semantic matching and LLM inference run in a
        # separate OS process (not just a thread) so a slow/cold model
        # load or a long LLM generation can never hold the CPython GIL and
        # stall other threads — in particular the pynput CGEventTap
        # callback thread, which macOS permanently disables if it doesn't
        # return quickly.
        self.nlu_executor = None

    def start(self):

        self.event_bus.subscribe(
            "text_ready",
            self._handle_text
        )

    def stop(self):

        self.event_bus.unsubscribe(
            "text_ready",
            self._handle_text
        )

        if self.nlu_executor is not None:

            self.nlu_executor.shutdown(
                wait=False,
                cancel_futures=True
            )

            self.nlu_executor = None

    def _handle_text(self, event):

        data = event.get("data") or {}

        text = data.get("text")

        if not text:
            return

        result = self.process_text(
            text,
            wake_word_heard=data.get(
                "wake_word_heard",
                False
            )
        )

        if result:


            self.event_bus.publish(
                "intent_detected",
                result
            )

    def process_text(
        self,
        text,
        wake_word_heard=False
    ):

        if not text:
            return None

        text = (
            self._normalize(text)
            .lower()
            .strip()
        )

        cleaned_text = text

        # A previous session went silent for too long — close it out and
        # report whatever never turned into a command before considering
        # this new text, so a fresh wake word right after a timed-out
        # session starts clean instead of inheriting stale pending text.
        if self._session_timed_out():

            if self.pending_command_text:

                self._print_not_understood(
                    self.pending_command_text
                )

            self._end_session()

        # Wake word gate: "jack" opens a listening session. Every
        # utterance heard while open pushes the silence deadline forward —
        # the session only ends when a command is recognized or nothing
        # new is heard for silence_timeout_seconds.
        normalized_wake_word = (
            self._normalize(self.wake_word)
            .lower()
            .strip()
        )

        wake_prefix = (
            normalized_wake_word
            + " "
        )

        if cleaned_text == normalized_wake_word:

            self._start_session()

            return None

        if cleaned_text.startswith(wake_prefix):

            # Vosk sometimes packs the wake word and the following
            # (possibly unclear) speech into a single final result, e.g.
            # "jack [unk]" or "jack open browser". Start the session
            # either way, then try the remainder as the command right away.
            self._start_session()

            cleaned_text = cleaned_text[
                len(wake_prefix):
            ].strip()

            if not cleaned_text:
                return None

            self.pending_command_text = cleaned_text

        elif wake_word_heard:

            # The grammar recognizer caught the wake word somewhere in
            # this utterance (partial or final), even though the text
            # here — possibly rewritten by the open-vocab fallback — no
            # longer starts with it. Trust Vosk's own detection rather
            # than requiring the (sometimes lossy) free-text
            # transcription to still contain "jack".
            self._start_session()

            self.pending_command_text = cleaned_text

        elif self._session_is_active():

            # A continuation within an already-open session. Vosk
            # sometimes finalizes one spoken command as several separate
            # utterances (a brief mid-sentence pause is enough to trigger
            # an early endpoint), so accumulate instead of replacing.
            if self.pending_command_text:

                cleaned_text = (
                    f"{self.pending_command_text} "
                    f"{cleaned_text}"
                ).strip()

            self.pending_command_text = cleaned_text

        else:

            if self.debug:

                logger.debug(
                    "[wake word] ignored \"%s\" (no active session)",
                    cleaned_text
                )

            return None

        for command, phrase in (
            self.voice_commands.items()
        ):

            normalized_phrase = (
                self._normalize(phrase)
                .lower()
                .strip()
            )

            if cleaned_text == normalized_phrase:

                self._end_session()

                return {
                    "command": command,
                    "confidence": 1.0,
                    "source": "voice",
                    "tier": "exact"
                }

        if self.nlu_fallback_enabled:

            semantic_result = self._match_semantic(
                cleaned_text
            )

            if semantic_result:

                self._end_session()

                return {
                    "command": semantic_result["command"],
                    "confidence": semantic_result["confidence"],
                    "source": "voice",
                    "tier": "semantic"
                }

            llm_command = self._match_llm(
                cleaned_text
            )

            if llm_command:

                self._end_session()

                return {
                    "command": llm_command,
                    "confidence": self.llm_confidence,
                    "source": "voice",
                    "tier": "llm"
                }

        # No match yet — keep the session open (the deadline was already
        # pushed forward by _start_session/this method's callers) so a
        # continuation utterance can still complete the command before it
        # goes quiet.
        self._renew_session()

        return None

    def _start_session(self):

        self.pending_command_text = ""

        self._renew_session()

        if self.debug:

            logger.debug(
                "[wake word] \"%s\" detected, session started "
                "(%ss silence timeout)",
                self.wake_word,
                self.silence_timeout_seconds
            )

    def _renew_session(self):

        self.session_deadline = (
            time.time()
            + self.silence_timeout_seconds
        )

    def _end_session(self):

        self.session_deadline = None

        self.pending_command_text = ""

    def _session_is_active(self):

        if self.session_deadline is None:
            return False

        return (
            time.time()
            < self.session_deadline
        )

    def _session_timed_out(self):

        if self.session_deadline is None:
            return False

        return (
            time.time()
            >= self.session_deadline
        )

    def _print_not_understood(
        self,
        cleaned_text
    ):

        # Always on, not gated behind --debug-voice — this is the
        # outcome-level "did it understand me" signal, not the noisier
        # raw partial/final transcript stream.
        logger.info(
            "[RESOLVED] not understood: \"%s\"",
            cleaned_text
        )

    def _get_nlu_executor(self):

        if self.nlu_executor is None:

            self.nlu_executor = ProcessPoolExecutor(
                max_workers=1
            )

        return self.nlu_executor

    def _match_semantic(
        self,
        text
    ):

        executor = self._get_nlu_executor()

        future = executor.submit(
            semantic_match_task,
            self.voice_commands,
            self.semantic_threshold,
            text
        )

        try:

            return future.result(
                timeout=self.nlu_worker_timeout_seconds
            )

        except FutureTimeoutError:

            logger.warning(
                "Semantic match worker timed out after %ss",
                self.nlu_worker_timeout_seconds
            )

            return None

    def _match_llm(
        self,
        text
    ):

        executor = self._get_nlu_executor()

        future = executor.submit(
            llm_interpret_task,
            self.voice_commands,
            self.llm_model_id,
            text
        )

        try:

            return future.result(
                timeout=self.nlu_worker_timeout_seconds
            )

        except FutureTimeoutError:

            logger.warning(
                "LLM fallback worker timed out after %ss",
                self.nlu_worker_timeout_seconds
            )

            return None

    def _normalize(self, text):

        for char in [
            ",",
            ".",
            "!",
            "?",
            ":"
        ]:

            text = text.replace(
                char,
                ""
            )

        return text.strip()
