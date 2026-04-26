from pynput import keyboard
import time


class KeyboardInput:
    def __init__(self, event_bus):
        # Store event bus reference
        self.event_bus = event_bus

        # Listener instance
        self.listener = None

    def start(self):
        # Start listener in background thread
        self.listener = keyboard.Listener(on_press=self._on_press)
        self.listener.start()

    def stop(self):
        # Stop listener safely
        if self.listener:
            self.listener.stop()
            self.listener = None

    def _on_press(self, key):
        try:
            # Extract key value
            if hasattr(key, 'char') and key.char is not None:
                key_value = key.char
            else:
                key_value = str(key)

            # Debug output
            print(f"[Keyboard] Key pressed: {key_value}")

            # Send only data to event bus
            self.event_bus.publish("keyboard_event", {
                "key": key_value
            })

        except Exception as e:
            # Prevent crash and show error
            print(f"[Keyboard ERROR] {e}")