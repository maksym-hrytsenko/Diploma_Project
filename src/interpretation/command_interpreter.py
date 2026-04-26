class CommandInterpreter:
    def __init__(self, event_bus):
        # Store event bus
        self.event_bus = event_bus

        # Key to command mapping
        self.key_map = {
            "a": "MOVE_LEFT",
            "d": "MOVE_RIGHT",
            "w": "MOVE_UP",
            "s": "MOVE_DOWN",
            "Key.esc": "STOP"
        }

    def start(self):
        # Subscribe to keyboard events
        self.event_bus.subscribe("keyboard_event", self._handle_keyboard)

    def stop(self):
        # Unsubscribe
        self.event_bus.unsubscribe("keyboard_event", self._handle_keyboard)

    def _handle_keyboard(self, event):
        try:
            key = event.get("data", {}).get("key")

            # Debug input
            print(f"[Interpreter] Received key: {key}")

            command = self.key_map.get(key)

            if not command:
                return

            # Debug command
            print(f"[Interpreter] Command: {command}")

            # Send command дальше
            self.event_bus.publish("command_event", {
                "command": command
            })

        except Exception as e:
            print(f"[Interpreter ERROR] {e}")