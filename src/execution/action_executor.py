class ActionExecutor:
    def __init__(self, event_bus):
        # Store event bus reference
        self.event_bus = event_bus
        self._is_running = False

    def start(self):
        # Subscribe to command events
        if not self._is_running:
            self.event_bus.subscribe("command_event", self.handle_command_event)
            self._is_running = True

    def stop(self):
        # Unsubscribe from command events
        if self._is_running:
            self.event_bus.unsubscribe("command_event", self.handle_command_event)
            self._is_running = False

    def handle_command_event(self, event):
        try:
            # Extract command
            command = event.get("data", {}).get("command")

            # Ignore invalid command
            if not command:
                return

            # Execute action
            if command == "MOVE_LEFT":
                print("Action: MOVE_LEFT")
            elif command == "MOVE_RIGHT":
                print("Action: MOVE_RIGHT")
            elif command == "MOVE_UP":
                print("Action: MOVE_UP")
            elif command == "MOVE_DOWN":
                print("Action: MOVE_DOWN")
            elif command == "STOP":
                print("Action: STOP")

        except Exception:
            # Prevent crash
            pass