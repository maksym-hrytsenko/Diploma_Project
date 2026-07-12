"""Synchronization stage of the fusion layer.

Receives normalized_signal from CommandInterpreter, buffers each source's
signal in a TemporalSync window (so voice/gesture/keyboard/face signals
arriving within a short span can combine), and republishes the active set
as fusion_signal for SignalMapper to decide on. Never decides an action itself.
"""

from core.event_bus import EventBus
from fusion.temporal_sync import TemporalSync
from config.config_loader import load_fusion_config
from utils.logger import get_logger


logger = get_logger(__name__)


class MultimodalFusion:

    def __init__(self, event_bus: EventBus):

        self.event_bus = event_bus

        signal_timeout = self._load_signal_timeout()

        self.sync = TemporalSync(
            timeout=signal_timeout
        )

    def _load_signal_timeout(self):

        try:

            data = load_fusion_config()

        except Exception:

            logger.exception(
                "Failed to load fusion.json — falling back to a "
                "2.0s signal timeout"
            )

            return 2.0

        return data.get(
            "settings",
            {}
        ).get(
            "signal_timeout",
            2.0
        )

    def start(self):

        self.event_bus.subscribe(
            "normalized_signal",
            self._handle_signal
        )

        self.event_bus.subscribe(
            "clear_fusion_signals",
            self._clear_signals
        )

    def stop(self):

        self.event_bus.unsubscribe(
            "normalized_signal",
            self._handle_signal
        )

        self.event_bus.unsubscribe(
            "clear_fusion_signals",
            self._clear_signals
        )

    def _handle_signal(self, event):

        data = event.get(
            "data",
            {}
        )

        source = data.get(
            "source"
        )

        signal = data.get(
            "signal"
        )

        confidence = data.get(
            "confidence",
            1.0
        )

        tier = data.get(
            "tier"
        )

        keyboard_event = data.get(
            "event"
        )

        if source is None:
            return

        if signal is None:
            return

        if source == "keyboard" and keyboard_event == "up":

            # The combo just broke — drop it immediately rather than
            # letting it linger until it times out on its own.
            self.sync.clear_signal(source)

        else:

            # A keyboard combo is held for as long as the physical keys
            # are down, so it must not expire on the fixed voice/gesture
            # timeout — every other source stays as momentary as before.
            self.sync.store_signal(

                source=source,

                signal=signal,

                confidence=confidence,

                persistent=(source == "keyboard"),

                tier=tier

            )

        self.event_bus.publish(

            "fusion_signal",

            {

                "source": source,

                "signal": signal,

                "signals": self.sync.get_signals()

            }

        )

    # Only clears momentary (voice/gesture) signals so they cannot
    # immediately re-match the rule that just fired. A still-physically-held
    # keyboard combo is left in place, ready to combine with the next
    # gesture/voice signal that arrives while it is held.
    def _clear_signals(self, event):

        self.sync.clear_non_persistent()

    def get_active_signals(self):

        return self.sync.get_signals()

    def clear_signals(self):

        self.sync.clear_all()