from pynput import keyboard
import time


class KeyboardInput:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.listener = None

    def start(self):
        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self.listener.start()
        print("[KeyboardInput] Started")

    def stop(self):
        if self.listener:
            self.listener.stop()
            self.listener = None
            print("[KeyboardInput] Stopped")

    def _on_press(self, key):
        key_name = self._get_key_name(key)

        if key_name:
            self.event_bus.publish("keyboard_raw", {
                "event": "press",
                "key": key_name,
                "timestamp": time.time()
            })

    def _on_release(self, key):
        key_name = self._get_key_name(key)

        if key_name:
            self.event_bus.publish("keyboard_raw", {
                "event": "release",
                "key": key_name,
                "timestamp": time.time()
            })

    def _get_key_name(self, key):
        try:
            # Special keys
            if isinstance(key, keyboard.Key):
                name = str(key).replace("Key.", "")

                if name in ["ctrl_l", "ctrl_r"]:
                    return "ctrl"
                if name in ["shift_l", "shift_r"]:
                    return "shift"
                if name in ["alt_l", "alt_r"]:
                    return "alt"

                return name

            # Normal keys
            if hasattr(key, 'char') and key.char:
                char = key.char

                # 🔥 FIX: convert control chars back to letters
                if ord(char) < 32:
                    # Ctrl+A → chr(1+96) = 'a'
                    return chr(ord(char) + 96)

                return char.lower()

        except Exception:
            pass

        return None