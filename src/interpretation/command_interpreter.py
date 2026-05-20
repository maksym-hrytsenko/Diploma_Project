import json
import os


class CommandInterpreter:

    def __init__(self, event_bus):

        self.event_bus = event_bus

        (
            self.keyboard_mapping,
            self.voice_mapping,
            self.gesture_mapping
        ) = self._load_mapping()

    # ---------------------------------
    # Start / Stop
    # ---------------------------------

    def start(self):

        self.event_bus.subscribe(
            "fusion_signal",
            self._handle_signal
        )

    def stop(self):

        self.event_bus.unsubscribe(
            "fusion_signal",
            self._handle_signal
        )

    # ---------------------------------
    # Load Mapping
    # ---------------------------------

    def _load_mapping(self):

        try:

            base_dir = os.path.dirname(
                os.path.dirname(
                    os.path.abspath(__file__)
                )
            )

            config_path = os.path.join(
                base_dir,
                "config",
                "mapping.json"
            )

            with open(
                config_path,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

                keyboard = data.get(
                    "keyboard",
                    {}
                )

                voice = data.get(
                    "voice",
                    {}
                )

                gesture = data.get(
                    "gesture",
                    {}
                )

                return (
                    keyboard,
                    voice,
                    gesture
                )

        except Exception:

            return {}, {}, {}

    # ---------------------------------
    # Handle Signal
    # ---------------------------------

    def _handle_signal(self, event):

        data = event.get("data", {})

        signal = data.get("signal")

        source = data.get("source")

        if not signal:
            return

        command = None

        # ---------------------------------
        # Keyboard
        # ---------------------------------

        if source == "keyboard":

            command = (
                self.keyboard_mapping.get(
                    signal
                )
            )

        # ---------------------------------
        # Voice
        # ---------------------------------

        elif source == "voice":

            command = (
                self.voice_mapping.get(
                    signal
                )
            )

        # ---------------------------------
        # Gesture
        # ---------------------------------

        elif source == "gesture":

            command = (
                self.gesture_mapping.get(
                    signal
                )
            )

        # ---------------------------------
        # Invalid Command
        # ---------------------------------

        if not command:
            return

        # ---------------------------------
        # Publish Semantic Command
        # ---------------------------------

        self.event_bus.publish(
            "command_event",
            {
                "command": command,
                "source": source
            }
        )