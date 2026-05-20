import json


class IntentModel:

    def __init__(
        self,
        event_bus,
        state_manager,
        mapping_path="config/mapping.json",
        system_path="config/system.json"
    ):

        self.event_bus = event_bus

        self.state_manager = state_manager

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

        # ---------------------------------
        # TEMP:
        # Disable wake word
        # ---------------------------------

        cleaned_text = text

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

        return None

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