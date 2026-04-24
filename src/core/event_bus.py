import time
import logging
from typing import Callable, Dict, List, Any

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        # {event_type: [callbacks]}
        self._subscribers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}

    def subscribe(self, event_type: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        # prevent duplicate subscriptions
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        callbacks = self._subscribers.get(event_type)
        if not callbacks:
            return

        try:
            callbacks.remove(callback)
        except ValueError:
            pass  # callback not found

        # cleanup empty lists
        if not callbacks:
            del self._subscribers[event_type]

    def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        event = {
            "type": event_type,
            "data": data,
            "timestamp": time.time(),
        }

        callbacks = self._subscribers.get(event_type, [])
        if not callbacks:
            return

        # iterate over copy to avoid mutation issues
        for callback in list(callbacks):
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in callback for '{event_type}': {e}", exc_info=True)

    def get_subscribers(self, event_type: str) -> List[Callable[[Dict[str, Any]], None]]:
        # return copy to prevent external mutation
        return list(self._subscribers.get(event_type, []))