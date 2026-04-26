import json
import os


class CommandInterpreter:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.mapping = self._load_mapping()

    def start(self):
        self.event_bus.subscribe("fusion_signal", self._handle_signal)

    def stop(self):
        self.event_bus.unsubscribe("fusion_signal", self._handle_signal)

    def _load_mapping(self):
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

            config_path = os.path.join(base_dir, "config", "mapping.json")

            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f).get("keyboard", {})

        except Exception as e:
            print("JSON ERROR:", e)
            return {}

    def _handle_signal(self, event):
        signal = event.get("data", {}).get("signal")

        if not signal:
            return

        command = self.mapping.get(signal)

        if not command:
            return

        self.event_bus.publish("command_event", {
            "command": command
        })