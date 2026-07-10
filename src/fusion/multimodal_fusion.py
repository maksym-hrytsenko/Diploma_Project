import json
import os

from fusion.temporal_sync import TemporalSync


class MultimodalFusion:

    def __init__(self, event_bus):

        self.event_bus = event_bus

        signal_timeout = self._load_signal_timeout()

        self.sync = TemporalSync(
            timeout=signal_timeout
        )

    # ---------------------------------
    # Load fusion.json settings
    # ---------------------------------

    def _load_signal_timeout(self):

        try:

            base_dir = os.path.dirname(
                os.path.dirname(
                    os.path.abspath(__file__)
                )
            )

            config_path = os.path.join(
                base_dir,
                "config",
                "fusion.json"
            )

            with open(
                config_path,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

            return data.get(
                "settings",
                {}
            ).get(
                "signal_timeout",
                2.0
            )

        except Exception:

            return 2.0

    # ---------------------------------
    # Start / Stop
    # ---------------------------------

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

    # ---------------------------------
    # Handle Signal
    # ---------------------------------

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

            # The combo just broke — drop it immediately
            # rather than letting it linger until it times
            # out on its own.
            self.sync.clear_signal(source)

        else:

            # A keyboard combo is held for as long as the
            # physical keys are down, so it must not expire
            # on the fixed voice/gesture timeout — every
            # other source stays exactly as momentary as
            # before.
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
    # ---------------------------------
    # Clear Signals
    # ---------------------------------

    # Only clears momentary (voice/gesture) signals so they
    # cannot immediately re-match the rule that just fired.
    # A still-physically-held keyboard combo is left in
    # place, ready to combine with the next gesture/voice
    # signal that arrives while it is held.
    def _clear_signals(self, event):

        self.sync.clear_non_persistent()

    # ---------------------------------
    # Public API
    # ---------------------------------

    def get_active_signals(self):

        return self.sync.get_signals()

    def clear_signals(self):

        self.sync.clear_all()