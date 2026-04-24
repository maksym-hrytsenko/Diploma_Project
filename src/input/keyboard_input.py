from pynput import keyboard
import time


class KeyboardInput:
    def __init__(self, event_bus):
        # Store event bus
        self.event_bus = event_bus

        # Listener placeholder
        self.listener = None

    def start(self):
        # Start listener in background
        self.listener = keyboard.Listener(on_press=self._on_press)
        self.listener.start()

    def stop(self):
        # Stop listener safely
        if self.listener:
            self.listener.stop()
            self.listener = None

    def _on_press(self, key):
        try:
            # Get key value
            if hasattr(key, 'char') and key.char is not None:
                key_value = key.char
            else:
                key_value = str(key)

            # Create event
            event = {
                "type": "keyboard_event",
                "data": {
                    "key": key_value
                },
                "timestamp": time.time()
            }

            # Publish event
            self.event_bus.publish("keyboard_event", event)

        except Exception:
            # Prevent listener crash
            pass