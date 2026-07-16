"""Voice-command interpretation stage.

Receives text_ready (final Vosk transcripts only), gates it behind a wake
word with a rolling silence timeout, matches it against config/mapping.json's
voice commands (exact match first, then optional semantic/LLM fallback), and
publishes intent_detected. The only module allowed to turn a spoken phrase
into an internal command.
"""

import functools
import threading
import time

from concurrent.futures import ProcessPoolExecutor

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
        #
        # This only matters BETWEEN separate utterances now (e.g. "jack"
        # ... pause ... "open browser" as two utterances completing one
        # command) — a single utterance's own internal pauses no longer
        # depend on this at all, VoskSpeechModel's own VAD-hangover check
        # (system.json's vad_silence_hangover_ms, much shorter) decides
        # when ONE spoken phrase is over before text_ready is even
        # published. See speech_model.py's module docstring.
        self.session_deadline = None

        self.pending_command_text = ""

        # Bumped every time a fresh (or newly-concatenated) piece of text
        # is about to be sent for semantic/LLM matching. Semantic/LLM
        # results now arrive asynchronously (see _start_nlu_fallback), so
        # by the time one comes back a LATER fragment may already have
        # superseded it — each async callback checks its own captured
        # token against the current value here and discards itself if a
        # newer attempt has since started, instead of acting on stale text.
        self.session_token = 0

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

        self.event_bus.subscribe(
            "voice_activity",
            self._handle_voice_activity
        )

    def stop(self):

        self.event_bus.unsubscribe(
            "text_ready",
            self._handle_text
        )

        self.event_bus.unsubscribe(
            "voice_activity",
            self._handle_voice_activity
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

    # Vosk still actively hearing speech (a non-empty partial hypothesis)
    # is real evidence the person hasn't gone quiet, even though it isn't
    # itself a command to act on — pushes an already-open session's
    # deadline forward so it isn't measured against how long Vosk takes to
    # finalize the next chunk, only against genuine silence. Mostly a
    # secondary safety net now that VoskSpeechModel's own VAD-hangover
    # check (system.json's vad_silence_hangover_ms) owns keeping a SINGLE
    # utterance from being cut short before text_ready is even published —
    # see speech_model.py's module docstring; session_deadline here only
    # matters BETWEEN separate utterances. Does nothing if no session is
    # open: partial speech alone must never start one — that stays gated
    # on the wake word in process_text.
    def _handle_voice_activity(self, event):

        if self._session_is_active():

            self._renew_session()

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

            # Bumped before dispatching, not after — see session_token —
            # so this attempt's own eventual callback carries a token that
            # is still current at the moment it's launched.
            self.session_token += 1

            self._start_nlu_fallback(
                cleaned_text,
                self.session_token
            )

        # No exact match. If NLU fallback is enabled, semantic/LLM matching
        # was just kicked off in the background (see _start_nlu_fallback)
        # rather than awaited here — either callback may still end the
        # session and publish intent_detected later. Either way, keep the
        # session open for now (the deadline was already pushed forward by
        # _start_session/this method's callers) so a continuation
        # utterance can still complete the command before it goes quiet.
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

        # Invalidates any semantic/LLM callback still in flight from this
        # session — see session_token above.
        self.session_token += 1

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

    # Fire-and-forget: submits semantic matching and returns immediately
    # instead of blocking the caller (previously the speech pipeline's own
    # callback chain, all the way back to the microphone thread) for
    # however long a cold model load or a slow match takes. Confirmed
    # against a real test session: this used to stall recognition of
    # whatever the person kept saying next until the worker returned.
    # add_done_callback's callback runs on the executor's own result-
    # watching thread, never on the calling thread.
    def _start_nlu_fallback(
        self,
        text,
        token
    ):

        executor = self._get_nlu_executor()

        future = executor.submit(
            semantic_match_task,
            self.voice_commands,
            self.semantic_threshold,
            text
        )

        self._warn_if_slow(
            future,
            "Semantic match"
        )

        future.add_done_callback(
            functools.partial(
                self._handle_semantic_future,
                text=text,
                token=token
            )
        )

    def _handle_semantic_future(
        self,
        future,
        text,
        token
    ):

        # A newer fragment already started its own attempt (concatenated
        # continuation, or a fresh wake word) — this result is for text
        # that's no longer current, so it must not end the session or
        # publish anything on its behalf.
        if token != self.session_token:
            return

        try:

            semantic_result = future.result()

        except Exception:

            logger.exception(
                "Semantic match worker failed"
            )

            semantic_result = None

        if semantic_result:

            self._end_session()

            self.event_bus.publish(
                "intent_detected",
                {
                    "command": semantic_result["command"],
                    "confidence": semantic_result["confidence"],
                    "source": "voice",
                    "tier": "semantic"
                }
            )

            return

        self._start_llm_fallback(
            text,
            token
        )

    def _start_llm_fallback(
        self,
        text,
        token
    ):

        if token != self.session_token:
            return

        executor = self._get_nlu_executor()

        future = executor.submit(
            llm_interpret_task,
            self.voice_commands,
            self.llm_model_id,
            text
        )

        self._warn_if_slow(
            future,
            "LLM fallback"
        )

        future.add_done_callback(
            functools.partial(
                self._handle_llm_future,
                token=token
            )
        )

    def _handle_llm_future(
        self,
        future,
        token
    ):

        if token != self.session_token:
            return

        try:

            llm_command = future.result()

        except Exception:

            logger.exception(
                "LLM fallback worker failed"
            )

            llm_command = None

        if llm_command:

            self._end_session()

            self.event_bus.publish(
                "intent_detected",
                {
                    "command": llm_command,
                    "confidence": self.llm_confidence,
                    "source": "voice",
                    "tier": "llm"
                }
            )

            return

        # Neither tier matched. The session was already renewed when this
        # attempt was dispatched (process_text) — renew again now, at the
        # moment the attempt actually finished, so a slow match doesn't
        # eat into the silence window a continuation still needs.
        if self._session_is_active():

            self._renew_session()

    # No artificial cancellation — ProcessPoolExecutor can't cleanly
    # interrupt a running worker — just a log line so a genuinely hung
    # model call is visible instead of silently never resolving. The
    # actual done-callback still fires normally whenever (if ever) the
    # future completes, however late.
    def _warn_if_slow(
        self,
        future,
        label
    ):

        def check():

            if not future.done():

                logger.warning(
                    "%s worker still running after %ss",
                    label,
                    self.nlu_worker_timeout_seconds
                )

        timer = threading.Timer(
            self.nlu_worker_timeout_seconds,
            check
        )

        timer.daemon = True

        timer.start()

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
