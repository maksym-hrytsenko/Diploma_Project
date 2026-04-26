class MultimodalFusion:
    def __init__(self, event_bus):
        self.event_bus = event_bus

    def start(self):
        self.event_bus.subscribe("keyboard_signal", self._handle_keyboard)

    def stop(self):
        self.event_bus.unsubscribe("keyboard_signal", self._handle_keyboard)

    def _handle_keyboard(self, event):
        signal = event.get("data", {}).get("signal")

        if not signal:
            return

        # Pass-through
        self.event_bus.publish("fusion_signal", {
            "signal": signal,
            "source": "keyboard"
        })