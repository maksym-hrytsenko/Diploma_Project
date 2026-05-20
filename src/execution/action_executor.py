class ActionExecutor:

    def __init__(self, event_bus):

        self.event_bus = event_bus

    # ---------------------------------
    # Start / Stop
    # ---------------------------------

    def start(self):

        self.event_bus.subscribe(
            "command_event",
            self._handle_command
        )

    def stop(self):

        self.event_bus.unsubscribe(
            "command_event",
            self._handle_command
        )

    # ---------------------------------
    # Handle Command
    # ---------------------------------

    def _handle_command(self, event):

        data = event.get("data", {})

        command = data.get("command")

        source = data.get("source")

        if not command:
            return

        # ---------------------------------
        # Terminal Output
        # ---------------------------------

        print(
            f"[EXECUTION] "
            f"{command} "
            f"(source={source})"
        )

        # ---------------------------------
        # Publish Execution Event
        # ---------------------------------

        self.event_bus.publish(
            "execution_event",
            {
                "command": command,
                "source": source
            }
        )