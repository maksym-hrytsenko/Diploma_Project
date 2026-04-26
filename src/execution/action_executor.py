class ActionExecutor:
    def __init__(self, event_bus):
        # Store event bus
        self.event_bus = event_bus

    def start(self):
        # Subscribe to command events
        self.event_bus.subscribe("command_event", self._handle_command)

    def stop(self):
        # Unsubscribe
        self.event_bus.unsubscribe("command_event", self._handle_command)

    def _handle_command(self, event):
        try:
            command = event.get("data", {}).get("command")

            # Debug input
            print(f"[Executor] Received command: {command}")

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

        except Exception as e:
            print(f"[Executor ERROR] {e}")