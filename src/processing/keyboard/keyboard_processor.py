class KeyboardProcessor:

    def __init__(self, event_bus):

        self.event_bus = event_bus

        # Keys physically held down right now
        self.current_keys = set()

        # The combo string last announced as "down", so a
        # change in current_keys can be compared against
        # it — None means nothing is currently held.
        self.currently_held_combo = None

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

    # Press and release are tracked as two separate moments
    # rather than waiting for a full press-then-release
    # cycle to complete before publishing anything. This
    # means a combo is announced ("down") the instant it is
    # fully held, and announced again ("up") the instant it
    # breaks — so a still-held combo stays valid the whole
    # time a key is down, not just at the moment it is
    # released, letting another gesture/voice action fire
    # alongside it mid-hold.
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

        key = key.lower()

        if action == "press":

            self.current_keys.add(key)

        elif action == "release":

            self.current_keys.discard(key)

        else:

            return

        self._update_combo()

    # ---------------------------------
    # Announce Combo Transitions
    # ---------------------------------

    def _update_combo(self):

        new_combo = self._build_combo(
            self.current_keys
        )

        if new_combo == self.currently_held_combo:
            return

        if self.currently_held_combo is not None:

            self.event_bus.publish(
                "keyboard_signal",
                {
                    "signal": self.currently_held_combo,
                    "event": "up"
                }
            )

        self.currently_held_combo = new_combo

        if self.currently_held_combo is not None:

            self.event_bus.publish(
                "keyboard_signal",
                {
                    "signal": self.currently_held_combo,
                    "event": "down"
                }
            )

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
