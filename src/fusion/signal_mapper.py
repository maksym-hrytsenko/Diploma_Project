import json
import os


class SignalMapper:

    def __init__(self, event_bus):

        self.event_bus = event_bus

        self.settings = {}

        self.rules = []

        self.mode_rules = []

        self.modes = []

        self.current_mode = None

        self._load_fusion()

    # ---------------------------------
    # Start / Stop
    # ---------------------------------

    def start(self):

        self.event_bus.subscribe(
            "fusion_signal",
            self._handle_signal
        )

    def stop(self):

        self.event_bus.unsubscribe(
            "fusion_signal",
            self._handle_signal
        )

    # ---------------------------------
    # Load fusion.json
    # ---------------------------------

    def _load_fusion(self):

        try:

            base_dir = os.path.dirname(
                os.path.dirname(
                    os.path.abspath(__file__)
                )
            )

            config_path = os.path.join(
                base_dir,
                "config",
                "fusion.json"
            )

            with open(
                config_path,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

            self.settings = data.get(
                "settings",
                {}
            )

            self.rules = data.get(
                "rules",
                []
            )

            self.mode_rules = data.get(
                "mode_rules",
                []
            )

            self.modes = data.get(
                "modes",
                []
            )

        except Exception:

            self.settings = {}

            self.rules = []

            self.mode_rules = []

            self.modes = []

    # ---------------------------------
    # Fusion Signal
    # ---------------------------------

    def _handle_signal(self, event):

        data = event.get(
            "data",
            {}
        )

        signals = data.get(
            "signals",
            {}
        )

        if not signals:
            return

        self._update_mode(
            signals
        )

        self._check_rules(
            signals
        )

        self._check_mode_rules(
            signals
        )
    # ---------------------------------
    # Update Mode
    # ---------------------------------

    def _update_mode(self, signals):

        voice = signals.get(
            "voice"
        )

        if voice is None:
            return

        signal = voice.get(
            "signal"
        )

        for mode in self.modes:

            if signal != mode["trigger"]:
                continue

            self.current_mode = mode["mode"]

            print(
                f"[MAPPER] Mode -> {self.current_mode}"
            )

            return

    # ---------------------------------
    # Standard Rules
    # ---------------------------------

    def _check_rules(self, signals):

        for rule in self.rules:

            if self._match_conditions(

                rule["conditions"],

                signals

            ):

                print(
                    f"[MAPPER] Match -> {rule['name']}"
                )

                self._publish_command(
                    rule["action"]
                )

                self.event_bus.publish(
                    "clear_fusion_signals",
                    {}
                )

                return

    # ---------------------------------
    # Mode Rules
    # ---------------------------------

    def _check_mode_rules(self, signals):

        if self.current_mode is None:
            return

        for rule in self.mode_rules:

            if rule["mode"] != self.current_mode:
                continue

            if self._match_conditions(

                rule["conditions"],

                signals

            ):

                print(
                    f"[MAPPER] Match -> {rule['name']}"
                )

                self._publish_command(
                    rule["action"]
                )

                self.event_bus.publish(
                    "clear_fusion_signals",
                    {}
                )

                return
    # ---------------------------------
    # Match Conditions
    # ---------------------------------
    def _match_conditions(
        self,
        conditions,
        signals
    ):

        for source, expected_signal in conditions.items():

            signal_data = signals.get(
                source
            )

            if signal_data is None:
                return False

            current_signal = signal_data.get(
                "signal"
            )

            if current_signal != expected_signal:
                return False

        return True

    # ---------------------------------
    # Publish Command
    # ---------------------------------

    def _publish_command(
        self,
        command
    ):

        if not command:
            return

        print(
            f"[MAPPER] Command -> {command}"
        )

        self.event_bus.publish(

            "command_event",

            {

                "command": command,

                "source": "fusion",

                "mode": self.current_mode

            }

        )

    # ---------------------------------
    # Clear Mode
    # ---------------------------------

    def clear_mode(self):

        self.current_mode = None

    # ---------------------------------
    # Reload Configuration
    # ---------------------------------

    def reload(self):

        self.settings = {}

        self.rules = []

        self.mode_rules = []

        self.modes = []

        self.current_mode = None

        self._load_fusion()