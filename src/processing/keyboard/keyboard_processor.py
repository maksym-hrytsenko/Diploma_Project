class KeyboardProcessor:
    def __init__(self, event_bus):
        self.event_bus = event_bus

        # Currently pressed keys
        self.current_keys = set()

        # Keys collected during one "session"
        self.session_keys = set()

        # Are we currently recording a session
        self.is_recording = False

    def start(self):
        self.event_bus.subscribe("keyboard_raw", self._handle_raw)

    def stop(self):
        self.event_bus.unsubscribe("keyboard_raw", self._handle_raw)

    def _handle_raw(self, event):
        key = event.get("data", {}).get("key")
        action = event.get("data", {}).get("event")

        if not key:
            return

        # --- PRESS ---
        if action == "press":
            self.current_keys.add(key)

            # Start session on first press
            if not self.is_recording:
                self.is_recording = True
                self.session_keys.clear()

            # Add key to session
            self.session_keys.add(key)

        # --- RELEASE ---
        elif action == "release":
            self.current_keys.discard(key)

            # If ALL keys released → finalize session
            if not self.current_keys and self.is_recording:
                combo = self._build_combo(self.session_keys)

                if combo:
                    self.event_bus.publish("keyboard_signal", {
                        "signal": combo
                    })

                # Reset session
                self.session_keys.clear()
                self.is_recording = False

    def _build_combo(self, keys):
        if not keys:
            return None

        return "+".join(sorted(keys))