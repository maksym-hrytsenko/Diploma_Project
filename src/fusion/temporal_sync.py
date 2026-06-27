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
        confidence=1.0
    ):

        self.signals[source] = {

            "signal": signal,

            "confidence": confidence,

            "timestamp": time.time()
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
    # Cleanup expired signals
    # ---------------------------------

    def cleanup(self):

        now = time.time()

        expired = []

        for source, data in self.signals.items():

            if now - data["timestamp"] > self.timeout:

                expired.append(source)

        for source in expired:

            del self.signals[source]