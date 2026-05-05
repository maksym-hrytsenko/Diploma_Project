import json
import os


class CommandInterpreter:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.keyboard_mapping, self.voice_commands = self._load_mapping()

    def start(self):
        self.event_bus.subscribe("fusion_signal", self._handle_signal)

    def stop(self):
        self.event_bus.unsubscribe("fusion_signal", self._handle_signal)

    def _load_mapping(self):
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config", "mapping.json")

            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

                keyboard = data.get("keyboard", {})
                voice = data.get("voice", {})

                return keyboard, voice

        except Exception as e:
            print("JSON ERROR:", e)
            return {}, {}

    def _handle_signal(self, event):
        data = event.get("data", {})

        signal = data.get("signal")
        source = data.get("source")

        if not signal:
            return

        # 🔹 KEYBOARD LOGIC (unchanged behavior)
        if source == "keyboard":
            command = self.keyboard_mapping.get(signal)

            if not command:
                return

        # 🔹 VOICE LOGIC (NEW)
        elif source == "voice":
            # signal is already a command from intent_model
            if signal not in self.voice_commands:
                return

            command = signal

        else:
            return

        self.event_bus.publish("command_event", {
            "command": command,
            "source": source
        })