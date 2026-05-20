class KeyboardProcessor:

    def __init__(self, event_bus):

        self.event_bus = event_bus

        # Currently pressed keys
        self.current_keys = set()

        # Keys collected during session
        self.session_keys = set()

        # Recording state
        self.is_recording = False

        # Modifier priority
        self.modifier_order = [
            "ctrl",
            "alt",
            "shift",
            "capslock"
        ]

    # ---------------------------------
    # Start / Stop
    # ---------------------------------

    def start(self):

        self.event_bus.subscribe(
            "keyboard_raw",
            self._handle_raw
        )

    def stop(self):

        self.event_bus.unsubscribe(
            "keyboard_raw",
            self._handle_raw
        )

    # ---------------------------------
    # Handle Raw Keyboard Events
    # ---------------------------------

    def _handle_raw(self, event):

        key = (
            event.get("data", {})
            .get("key")
        )

        action = (
            event.get("data", {})
            .get("event")
        )

        if not key:
            return

        # Normalize key
        key = key.lower()

        # ---------------------------------
        # PRESS
        # ---------------------------------

        if action == "press":

            self.current_keys.add(key)

            # Start session
            if not self.is_recording:

                self.is_recording = True

                self.session_keys.clear()

            # Save key
            self.session_keys.add(key)

        # ---------------------------------
        # RELEASE
        # ---------------------------------

        elif action == "release":

            self.current_keys.discard(key)

            # ---------------------------------
            # Modifier-only combo
            # ---------------------------------

            if (
                self.is_recording
                and not self.current_keys
                and self.session_keys
            ):

                combo = self._build_combo(
                    self.session_keys
                )

                if combo:

                    #print(
                     #   f"[KEYBOARD] "
                      #  f"{combo}"
                    #)

                    self.event_bus.publish(
                        "keyboard_signal",
                        {
                            "signal": combo
                        }
                    )

                # Reset session
                self.session_keys.clear()

                self.is_recording = False

            # ---------------------------------
            # Normal combo
            # ---------------------------------

            elif (
                self.is_recording
                and key not in self.modifier_order
            ):

                combo = self._build_combo(
                    self.session_keys
                )

                if combo:

                    #print(
                     #   f"[KEYBOARD] "
                      #  f"{combo}"
                    #)

                    self.event_bus.publish(
                        "keyboard_signal",
                        {
                            "signal": combo
                        }
                    )

                # Reset session
                self.session_keys.clear()

                self.current_keys.clear()

                self.is_recording = False

    # ---------------------------------
    # Build Combination
    # ---------------------------------

    def _build_combo(self, keys):

        if not keys:
            return None

        keys = list(keys)

        # Sort modifiers first
        keys.sort(
            key=self._sort_key
        )

        return "+".join(keys)

    # ---------------------------------
    # Sort Priority
    # ---------------------------------

    def _sort_key(self, key):

        if key in self.modifier_order:

            return (
                0,
                self.modifier_order.index(key)
            )

        return (1, key)