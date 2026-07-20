"""Publish/subscribe hub that every pipeline module communicates through.

All input, processing, interpretation, fusion, execution and UI modules
talk exclusively via EventBus.publish/subscribe/unsubscribe — never through
direct calls to one another.
"""

import time

from utils.logger import get_logger


logger = get_logger(__name__)


class EventBus:
    def __init__(self):
        self._subscribers = {}

    def subscribe(self, event_type, callback):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type, callback):
        if event_type in self._subscribers:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)

    def publish(self, event_type, data):
        event = {
            "type": event_type,
            "data": data,
            "timestamp": time.time()
        }

        if event_type in self._subscribers:
            # Copy the list before iterating: a callback may itself
            # subscribe/unsubscribe, which would otherwise mutate this
            # list mid-loop.
            for callback in list(self._subscribers[event_type]):
                try:
                    callback(event)
                except Exception:
                    logger.exception(
                        "Subscriber callback failed for event '%s'",
                        event_type
                    )
