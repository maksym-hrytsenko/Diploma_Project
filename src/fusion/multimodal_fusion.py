from fusion.temporal_sync import TemporalSync


class MultimodalFusion:

    def __init__(self, event_bus):

        self.event_bus = event_bus

        self.sync = TemporalSync()

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

        if source is None:
            return

        if signal is None:
            return

        self.sync.store_signal(

            source=source,

            signal=signal,

            confidence=confidence

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

    def _clear_signals(self, event):

        self.sync.clear_all()

    # ---------------------------------
    # Public API
    # ---------------------------------

    def get_active_signals(self):

        return self.sync.get_signals()

    def clear_signals(self):

        self.sync.clear_all()