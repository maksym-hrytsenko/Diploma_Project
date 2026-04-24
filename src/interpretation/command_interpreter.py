class CommandInterpreter:
    def __init__(self, event_bus):
        # Store event bus reference
        self.event_bus = event_bus

        # Map keys to commands
        self.key_map = {
            "a": "MOVE_LEFT",
            "d": "MOVE_RIGHT",
            "w": "MOVE_UP",
            "s": "MOVE_DOWN",
            "esc": "STOP"
        }

    def start(self):
        # Subscribe to keyboard events
        self.event_bus.subscribe("keyboard_event", self.handle_keyboard_event)

    def stop(self):
        # Unsubscribe from keyboard events
        self.event_bus.unsubscribe("keyboard_event", self.handle_keyboard_event)

    def handle_keyboard_event(self, event):
        try:
            # Extract key
            key = event.get("data", {}).get("key")

            # Get command
            command = self.key_map.get(key)

            # Ignore unsupported keys
            if not command:
                return

            # Publish command event
            self.event_bus.publish("command_event", {
                "command": command
            })

        except Exception:
            # Prevent crash on any error
            pass