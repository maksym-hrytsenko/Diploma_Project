class ActionExecutor:
    def __init__(self, event_bus):
        self.event_bus = event_bus

    def start(self):
        self.event_bus.subscribe("command_event", self._handle_command)

    def stop(self):
        self.event_bus.unsubscribe("command_event", self._handle_command)

    def _handle_command(self, event):
        command = event.get("data", {}).get("command")

        if not command:
            return

        # For now: just pass through
        self.event_bus.publish("execution_event", {
            "command": command
        })