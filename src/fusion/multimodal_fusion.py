import json
import os


class MultimodalFusion:

    def __init__(self, event_bus):

        self.event_bus = event_bus

        self.valid_signals = (
            self._load_valid_signals()
        )

    # ---------------------------------
    # Start / Stop
    # ---------------------------------

    def start(self):

        # Keyboard
        self.event_bus.subscribe(
            "keyboard_signal",
            self._handle_keyboard
        )

        # Voice
        self.event_bus.subscribe(
            "intent_detected",
            self._handle_voice
        )

        # Gesture
        self.event_bus.subscribe(
            "gesture_signal",
            self._handle_gesture
        )

    def stop(self):

        # Keyboard
        self.event_bus.unsubscribe(
            "keyboard_signal",
            self._handle_keyboard
        )

        # Voice
        self.event_bus.unsubscribe(
            "intent_detected",
            self._handle_voice
        )

        # Gesture
        self.event_bus.unsubscribe(
            "gesture_signal",
            self._handle_gesture
        )

    # ---------------------------------
    # Load Valid Signals
    # ---------------------------------

    def _load_valid_signals(self):

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

                return data.get(
                    "valid_signals",
                    {}
                )

        except Exception:

            return {}

    # ---------------------------------
    # Validation
    # ---------------------------------

    def _is_valid_signal(
        self,
        source,
        signal
    ):

        valid = self.valid_signals.get(
            source,
            []
        )

        return signal in valid

    # ---------------------------------
    # Keyboard
    # ---------------------------------

    def _handle_keyboard(self, event):

        signal = (
            event.get("data", {})
            .get("signal")
        )

        if not signal:
            return

        if not self._is_valid_signal(
            "keyboard",
            signal
        ):
            return

        self.event_bus.publish(
            "fusion_signal",
            {
                "signal": signal,
                "source": "keyboard"
            }
        )

    # ---------------------------------
    # Voice
    # ---------------------------------

    def _handle_voice(self, event):

        intent = event.get("data")

        if not intent:
            return

        signal = intent.get("command")

        if not signal:
            return

        if not self._is_valid_signal(
            "voice",
            signal
        ):
            return

        self.event_bus.publish(
            "fusion_signal",
            {
                "signal": signal,
                "source": "voice",
                "confidence": intent.get(
                    "confidence",
                    1.0
                )
            }
        )

    # ---------------------------------
    # Gesture
    # ---------------------------------

    def _handle_gesture(self, event):

        data = event.get("data")

        if not data:
            return

        signal = data.get("signal")

        if not signal:
            return

        if not self._is_valid_signal(
            "gesture",
            signal
        ):
            return

        self.event_bus.publish(
            "fusion_signal",
            {
                "signal": signal,
                "source": "gesture",
                "confidence": data.get(
                    "confidence",
                    1.0
                )
            }
        )