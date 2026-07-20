"""Validation/normalization stage of the interpretation layer.

Receives keyboard_signal, intent_detected, gesture_signal, face_signal and
ui_signal, checks each against config/mapping.json's valid_signals and
per-modality mappings, and republishes matches as normalized_signal.
Performs no multimodal logic and no voice phrase mapping — that already
happened in IntentModel.

ui_signal is MainWindow's mode-icon clicks — the UI already knows the
final internal command name (e.g. "PRESENTATION_MODE"), so it is handled
the same way voice's pre-mapped intent_detected is: validated, not
looked up in a mapping table.
"""

from config.config_loader import load_mapping_config
from utils.logger import get_logger


logger = get_logger(__name__)


class CommandInterpreter:

    def __init__(self, event_bus):

        self.event_bus = event_bus

        self.keyboard_mapping = {}

        self.voice_mapping = {}

        self.gesture_mapping = {}

        self.face_mapping = {}

        self.ui_mapping = {}

        self.valid_signals = {}

        self._load_mapping()

    def start(self):

        self.event_bus.subscribe(
            "keyboard_signal",
            self._handle_keyboard
        )

        self.event_bus.subscribe(
            "intent_detected",
            self._handle_voice
        )

        self.event_bus.subscribe(
            "gesture_signal",
            self._handle_gesture
        )

        self.event_bus.subscribe(
            "face_signal",
            self._handle_face
        )

        self.event_bus.subscribe(
            "ui_signal",
            self._handle_ui
        )

    def stop(self):

        self.event_bus.unsubscribe(
            "keyboard_signal",
            self._handle_keyboard
        )

        self.event_bus.unsubscribe(
            "intent_detected",
            self._handle_voice
        )

        self.event_bus.unsubscribe(
            "gesture_signal",
            self._handle_gesture
        )

        self.event_bus.unsubscribe(
            "face_signal",
            self._handle_face
        )

        self.event_bus.unsubscribe(
            "ui_signal",
            self._handle_ui
        )

    def _load_mapping(self):

        try:

            data = load_mapping_config()

        except Exception:

            logger.exception(
                "Failed to load mapping.json — falling back to empty "
                "mappings"
            )

            data = {}

        self.keyboard_mapping = data.get(
            "keyboard",
            {}
        )

        self.voice_mapping = data.get(
            "voice",
            {}
        )

        self.gesture_mapping = data.get(
            "gesture",
            {}
        )

        self.face_mapping = data.get(
            "face",
            {}
        )

        self.ui_mapping = data.get(
            "ui",
            {}
        )

        self.valid_signals = data.get(
            "valid_signals",
            {}
        )

    def _handle_keyboard(self, event):

        data = event.get(
            "data",
            {}
        )

        signal = data.get(
            "signal"
        )

        if signal is None:
            return

        if signal not in self.valid_signals.get(
            "keyboard",
            []
        ):
            return

        mapped_signal = self.keyboard_mapping.get(
            signal
        )

        if mapped_signal is None:
            return

        self.event_bus.publish(

            "normalized_signal",

            {

                "source": "keyboard",

                "signal": mapped_signal,

                "confidence": 1.0,

                # "down" while the combo is held, "up" the instant it
                # breaks — MultimodalFusion uses this to keep a held combo
                # valid for as long as it is physically held, instead of
                # only at the moment of release.
                "event": data.get("event")

            }

        )

    def _handle_voice(self, event):

        data = event.get(
            "data",
            {}
        )

        signal = data.get(
            "command"
        )

        if signal is None:
            return

        if signal not in self.valid_signals.get(
            "voice",
            []
        ):
            return

        self.event_bus.publish(

            "normalized_signal",

            {

                "source": "voice",

                "signal": signal,

                "confidence": data.get(
                    "confidence",
                    1.0
                ),

                "tier": data.get(
                    "tier",
                    "exact"
                )

            }

        )

    def _handle_gesture(self, event):

        data = event.get(
            "data",
            {}
        )

        signal = data.get(
            "signal"
        )

        if signal is None:
            return

        if signal not in self.valid_signals.get(
            "gesture",
            []
        ):
            return

        mapped_signal = self.gesture_mapping.get(
            signal
        )

        if mapped_signal is None:
            return

        self.event_bus.publish(

            "normalized_signal",

            {

                "source": "gesture",

                "signal": mapped_signal,

                "confidence": data.get(
                    "confidence",
                    1.0
                )

            }

        )

    def _handle_face(self, event):

        data = event.get(
            "data",
            {}
        )

        signal = data.get(
            "signal"
        )

        if signal is None:
            return

        if signal not in self.valid_signals.get(
            "face",
            []
        ):
            return

        mapped_signal = self.face_mapping.get(
            signal
        )

        if mapped_signal is None:
            return

        self.event_bus.publish(

            "normalized_signal",

            {

                "source": "face",

                "signal": mapped_signal,

                "confidence": 1.0

            }

        )

    def _handle_ui(self, event):

        data = event.get(
            "data",
            {}
        )

        signal = data.get(
            "signal"
        )

        if signal is None:
            return

        if signal not in self.valid_signals.get(
            "ui",
            []
        ):
            return

        mapped_signal = self.ui_mapping.get(
            signal
        )

        if mapped_signal is None:
            return

        self.event_bus.publish(

            "normalized_signal",

            {

                "source": "ui",

                "signal": mapped_signal,

                "confidence": 1.0

            }

        )