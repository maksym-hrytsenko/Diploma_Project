class ActionExecutor:
    def __init__(self, event_bus):
        self.event_bus = event_bus

    def start(self):
        self.event_bus.subscribe("command_event", self._handle_command)

    def stop(self):
        self.event_bus.unsubscribe("command_event", self._handle_command)

    def _handle_command(self, event):
        data = event.get("data", {})

        command = data.get("command")
        source = data.get("source")

        if not command:
            return

        # Pass-through (extended)
        self.event_bus.publish("execution_event", {
            "command": command,
            "source": source
        })