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

        # Debug SignalMapper
        self.event_bus.subscribe(
            "fusion_signal",
            self._debug_event
        )

        self.event_bus.subscribe(
            "command_event",
            self._debug_event
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

        self.event_bus.unsubscribe(
            "fusion_signal",
            self._debug_event
        )

        self.event_bus.unsubscribe(
            "command_event",
            self._debug_event
        )

    # ---------------------------------
    # Handle Commands
    # ---------------------------------

    def _handle_command(self, event):

        data = event.get(
            "data",
            {}
        )

        command = data.get(
            "command"
        )

        if command is None:
            return

        print(
            f"[EXECUTOR] {command}"
        )

    # ---------------------------------
    # Handle Pointer
    # ---------------------------------

    def _handle_pointer(self, event):

        data = event.get(
            "data",
            {}
        )

        x = data.get("x")
        y = data.get("y")

        if x is None or y is None:
            return

        print(
            f"[POINTER] x={x:.3f} y={y:.3f}"
        )

    # ---------------------------------
    # Debug SignalMapper
    # ---------------------------------

    def _debug_event(self, event):

        event_type = event.get(
            "type"
        )

        data = event.get(
            "data",
            {}
        )

        if event_type == "fusion_signal":

            print("\n========== SIGNAL MAPPER INPUT ==========")

            signals = data.get(
                "signals",
                {}
            )

            if not signals:

                print("No active signals")

            else:

                for source, value in signals.items():

                    print(
                        f"{source.upper():10} : {value['signal']}"
                    )

            print("=========================================")

        elif event_type == "command_event":

            print("========== SIGNAL MAPPER OUTPUT ==========")

            print(
                f"COMMAND    : {data.get('command')}"
            )

            print(
                f"SOURCE     : {data.get('source')}"
            )

            mode = data.get(
                "mode"
            )

            if mode:

                print(
                    f"MODE       : {mode}"
                )

            print("==========================================\n")