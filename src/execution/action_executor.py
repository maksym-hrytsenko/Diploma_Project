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

        self.event_bus.subscribe(
            "pointer_position",
            self._handle_pointer
        )

    def stop(self):

        self.event_bus.unsubscribe(
            "command_event",
            self._handle_command
        )

        self.event_bus.unsubscribe(
            "pointer_position",
            self._handle_pointer
        )

    # ---------------------------------
    # Handle Commands
    # ---------------------------------

    def _handle_command(self, event):

        data = event.get("data", {})

        command = data.get("command")

        source = data.get("source")

        if not command:
            return

        print(
            f"[EXECUTION] "
            f"{command} "
            f"(source={source})"
        )

        self.event_bus.publish(
            "execution_event",
            {
                "command": command,
                "source": source
            }
        )

    # ---------------------------------
    # Handle Pointer Position
    # ---------------------------------

    def _handle_pointer(self, event):

        data = event.get("data", {})

        x = data.get("x")
        y = data.get("y")

        if x is None or y is None:
            return

        print(
            f"[POINTER] "
            f"x={x:.3f} "
            f"y={y:.3f}"
        )