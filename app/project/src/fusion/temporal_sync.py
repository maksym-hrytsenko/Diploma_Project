"""Time-windowed buffer of the latest signal per source.

Backs MultimodalFusion: holds each source's most recent signal until it
either expires after `timeout` or is explicitly cleared, so signals from
different modalities that arrive within a short span of each other can
still be seen as simultaneous.
"""

import time


class TemporalSync:

    def __init__(self, timeout: float = 2.0):

        self.timeout = timeout

        self.signals = {}

    def store_signal(
        self,
        source,
        signal,
        confidence=1.0,
        persistent=False,
        tier=None
    ):

        self.signals[source] = {

            "signal": signal,

            "confidence": confidence,

            "timestamp": time.time(),

            # A persistent signal (a physically held keyboard combo) stays
            # valid until explicitly cleared rather than expiring after
            # `timeout`, since it shouldn't drop out of the buffer while
            # still physically pressed.
            "persistent": persistent,

            # Voice-only: "exact"/"semantic"/"llm", which tier of
            # IntentModel resolved this signal. None for every other source.
            "tier": tier
        }

        self.cleanup()

    def get_signal(
        self,
        source
    ):

        self.cleanup()

        return self.signals.get(source)

    def get_signals(self):

        self.cleanup()

        return self.signals

    def clear_signal(
        self,
        source
    ):

        if source in self.signals:

            del self.signals[source]

    def clear_all(self):

        self.signals.clear()

    # Used after a rule fires: momentary voice/gesture signals should be
    # consumed so they cannot immediately re-match, but a still-held
    # keyboard combo remains available for the next signal that arrives
    # while it is held.
    def clear_non_persistent(self):

        to_remove = [
            source
            for source, data in self.signals.items()
            if not data.get("persistent", False)
        ]

        for source in to_remove:

            del self.signals[source]

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
