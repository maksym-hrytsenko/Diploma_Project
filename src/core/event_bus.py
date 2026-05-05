import time


class EventBus:
    def __init__(self):
        # {event_type: [callbacks]}
        self._subscribers = {}

    def subscribe(self, event_type, callback):
        # Add subscriber
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type, callback):
        # Remove subscriber
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
            for callback in list(self._subscribers[event_type]):  # FIX
                try:
                    callback(event)
                except Exception as e:
                    print(f"[EventBus ERROR] {e}")