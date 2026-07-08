import time


class TemporalSync:

    def __init__(self, timeout=2.0):

        self.timeout = timeout

        self.signals = {}

    # ---------------------------------
    # Store signal
    # ---------------------------------

    def store_signal(
        self,
        source,
        signal,
        confidence=1.0,
        persistent=False
    ):

        self.signals[source] = {

            "signal": signal,

            "confidence": confidence,

            "timestamp": time.time(),

            # A persistent signal (a physically held
            # keyboard combo) stays valid until explicitly
            # cleared rather than expiring after `timeout`
            # — a key held longer than the timeout should
            # not silently drop out of the buffer while
            # still physically pressed.
            "persistent": persistent
        }

        self.cleanup()

    # ---------------------------------
    # Get signal
    # ---------------------------------

    def get_signal(
        self,
        source
    ):

        self.cleanup()

        return self.signals.get(source)

    # ---------------------------------
    # Get all signals
    # ---------------------------------

    def get_signals(self):

        self.cleanup()

        return self.signals

    # ---------------------------------
    # Clear source
    # ---------------------------------

    def clear_signal(
        self,
        source
    ):

        if source in self.signals:

            del self.signals[source]

    # ---------------------------------
    # Clear all
    # ---------------------------------

    def clear_all(self):

        self.signals.clear()

    # ---------------------------------
    # Clear only non-persistent signals
    # ---------------------------------

    # Used after a rule fires: momentary voice/gesture
    # signals should be consumed so they cannot immediately
    # re-match, but a still-held keyboard combo should
    # remain available for the next gesture/voice signal
    # that arrives while it is held.
    def clear_non_persistent(self):

        to_remove = [
            source
            for source, data in self.signals.items()
            if not data.get("persistent", False)
        ]

        for source in to_remove:

            del self.signals[source]

    # ---------------------------------
    # Cleanup expired signals
    # ---------------------------------

    def cleanup(self):

        now = time.time()

        expired = []

        for source, data in self.signals.items():

            if data.get("persistent", False):
                continue

            if now - data["timestamp"] > self.timeout:

                expired.append(source)

        for source in expired:

            del self.signals[source]
