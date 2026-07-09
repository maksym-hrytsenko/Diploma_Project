import json
import time


class IntentModel:

    def __init__(
        self,
        event_bus,
        state_manager,
        mapping_path="config/mapping.json",
        system_path="config/system.json",
        debug=False
    ):

        self.event_bus = event_bus

        self.state_manager = state_manager

        self.debug = debug

        import os

        base_dir = os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        )

        mapping_full_path = os.path.join(
            base_dir,
            mapping_path
        )

        system_full_path = os.path.join(
            base_dir,
            system_path
        )

        with open(
            mapping_full_path,
            "r",
            encoding="utf-8"
        ) as f:

            self.mapping = json.load(f)

        with open(
            system_full_path,
            "r",
            encoding="utf-8"
        ) as f:

            self.system = json.load(f)

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

        self.wake_word_window_seconds = (
            self.system.get(
                "wake_word_window_seconds",
                5
            )
        )

        self.awaiting_command_until = None

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

        self.semantic_matcher = None

        self.llm_fallback = None

    # ---------------------------------
    # Start / Stop
    # ---------------------------------

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

    # ---------------------------------
    # Handle Text
    # ---------------------------------

    def _handle_text(self, event):

        text = event.get("data")

        if not text:
            return

        result = self.process_text(text)

        if result:


            self.event_bus.publish(
                "intent_detected",
                result
            )

    # ---------------------------------
    # Process Text
    # ---------------------------------

    def process_text(self, text):

        if not text:
            return None

        # Normalize
        text = (
            self._normalize(text)
            .lower()
            .strip()
        )

        cleaned_text = text

        # ---------------------------------
        # Wake Word Gate
        #
        # "jack" alone opens a time-limited
        # window; only the next recognized
        # phrase inside that window is
        # treated as a command. Everything
        # heard outside the window is
        # ignored, so the system does not
        # act on background speech.
        # ---------------------------------

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

            self._open_wake_window()

            return None

        if cleaned_text.startswith(wake_prefix):

            # Vosk sometimes packs the wake word and the
            # following (possibly unclear) speech into a
            # single final result, e.g. "jack [unk]" or
            # "jack open browser". Open the grace window
            # either way, then try the remainder as the
            # command right away.

            self._open_wake_window()

            cleaned_text = cleaned_text[
                len(wake_prefix):
            ].strip()

            if not cleaned_text:
                return None

        elif not self._is_awaiting_command():

            if self.debug:

                print(
                    f"[wake word] ignored \"{cleaned_text}\" "
                    f"(no active window)"
                )

            return None

        else:

            self.awaiting_command_until = None

        # ---------------------------------
        # Match Commands
        # ---------------------------------

        for command, phrase in (
            self.voice_commands.items()
        ):

            normalized_phrase = (
                self._normalize(phrase)
                .lower()
                .strip()
            )

            if cleaned_text == normalized_phrase:

                return {
                    "command": command,
                    "confidence": 1.0,
                    "source": "voice"
                }

        if not self.nlu_fallback_enabled:
            return None

        semantic_result = self._match_semantic(
            cleaned_text
        )

        if semantic_result:

            return {
                "command": semantic_result["command"],
                "confidence": semantic_result["confidence"],
                "source": "voice"
            }

        llm_command = self._match_llm(
            cleaned_text
        )

        if llm_command:

            return {
                "command": llm_command,
                "confidence": self.llm_confidence,
                "source": "voice"
            }

        return None

    # ---------------------------------
    # Wake Word Window
    # ---------------------------------

    def _open_wake_window(self):

        self.awaiting_command_until = (
            time.time()
            + self.wake_word_window_seconds
        )

        if self.debug:

            print(
                f"[wake word] \"{self.wake_word}\" "
                f"detected, listening for "
                f"{self.wake_word_window_seconds}s"
            )

    def _is_awaiting_command(self):

        if self.awaiting_command_until is None:
            return False

        return (
            time.time()
            < self.awaiting_command_until
        )

    # ---------------------------------
    # Semantic Fallback (lazy)
    # ---------------------------------

    def _match_semantic(
        self,
        text
    ):

        if self.semantic_matcher is None:

            from interpretation.semantic_matcher import (
                SemanticMatcher
            )

            self.semantic_matcher = SemanticMatcher(
                self.voice_commands
            )

        return self.semantic_matcher.match(
            text,
            self.semantic_threshold
        )

    # ---------------------------------
    # LLM Fallback (lazy)
    # ---------------------------------

    def _match_llm(
        self,
        text
    ):

        if self.llm_fallback is None:

            from interpretation.llm_intent_fallback import (
                LLMIntentFallback
            )

            self.llm_fallback = LLMIntentFallback(
                self.voice_commands,
                model_repo=self.llm_model_id
            )

        return self.llm_fallback.interpret(
            text
        )

    # ---------------------------------
    # Normalize Text
    # ---------------------------------

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