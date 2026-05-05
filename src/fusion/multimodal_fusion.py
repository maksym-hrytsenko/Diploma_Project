class MultimodalFusion:
    def __init__(self, event_bus):
        self.event_bus = event_bus

    def start(self):
        self.event_bus.subscribe("keyboard_signal", self._handle_keyboard)
        self.event_bus.subscribe("intent_detected", self._handle_voice)  # NEW

    def stop(self):
        self.event_bus.unsubscribe("keyboard_signal", self._handle_keyboard)
        self.event_bus.unsubscribe("intent_detected", self._handle_voice)  # NEW

    def _handle_keyboard(self, event):
        signal = event.get("data", {}).get("signal")

        if not signal:
            return

        # Pass-through
        self.event_bus.publish("fusion_signal", {
            "signal": signal,
            "source": "keyboard"
        })

    def _handle_voice(self, event):  # NEW
        intent = event.get("data")

        if not intent:
            return

        command = intent.get("command")

        if not command:
            return

        # Pass-through
        self.event_bus.publish("fusion_signal", {
            "signal": command,
            "source": "voice",
            "confidence": intent.get("confidence", 1.0)
        })