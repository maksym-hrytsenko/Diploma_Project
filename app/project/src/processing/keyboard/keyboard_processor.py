"""Keyboard signal normalization.

Tracks which keys are physically held from keyboard_raw events and publishes
keyboard_signal "down"/"up" transitions for the current combo. Sits in the
Processing layer — CommandInterpreter validates/normalizes these further
downstream.
"""


class KeyboardProcessor:

    def __init__(self, event_bus):

        self.event_bus = event_bus

        self.current_keys = set()

        # The combo string last announced as "down", so a change in
        # current_keys can be compared against it — None means nothing is
        # currently held.
        self.currently_held_combo = None

        # Keys that must be recognized on their own, no matter what else is
        # physically held, and are therefore never folded into the combo
        # string above. Esc is meant to back out of anything at any time
        # (see SignalMapper._update_mode); if it were joined into
        # current_keys like every other key, pressing it while e.g. Alt is
        # still held for the face layer (§9.1) would produce "alt+esc" —
        # a combo nothing in mapping.json recognizes — so it would be
        # silently dropped instead of exiting the mode.
        self.priority_keys = {
            "esc"
        }

        self.modifier_order = [
            "ctrl",
            "alt",
            "shift",
            "capslock"
        ]

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

    # Press and release are tracked as two separate moments rather than
    # waiting for a full press-then-release cycle before publishing
    # anything, so a still-held combo stays valid the whole time a key is
    # down (not just at release), letting another gesture/voice action
    # fire alongside it mid-hold.
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

        if key in self.priority_keys:

            self._handle_priority_key(
                key,
                action
            )

            return

        if action == "press":

            self.current_keys.add(key)

        elif action == "release":

            self.current_keys.discard(key)

        else:

            return

        self._update_combo()

    # Published straight from the raw press/release, ahead of and
    # independent from combo tracking, so a priority key's signal can never
    # be swallowed by whatever unrelated keys happen to already be down.
    def _handle_priority_key(self, key, action):

        if action == "press":

            self.event_bus.publish(
                "keyboard_signal",
                {
                    "signal": key,
                    "event": "down"
                }
            )

        elif action == "release":

            self.event_bus.publish(
                "keyboard_signal",
                {
                    "signal": key,
                    "event": "up"
                }
            )

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

    def _build_combo(self, keys):

        if not keys:
            return None

        keys = list(keys)

        keys.sort(
            key=self._sort_key
        )

        return "+".join(keys)

    def _sort_key(self, key):

        if key in self.modifier_order:

            return (
                0,
                self.modifier_order.index(key)
            )

        return (1, key)
