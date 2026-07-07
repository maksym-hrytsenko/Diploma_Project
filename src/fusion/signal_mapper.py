import json
import os


class SignalMapper:

    def __init__(self, event_bus):

        self.event_bus = event_bus

        self.settings = {}

        self.rules = []

        self.mode_rules = []

        self.modes = []

        self.environments = []

        self.current_mode = None

        self.current_environment = None

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

            self.environments = data.get(
                "environments",
                []
            )

        except Exception:

            self.settings = {}

            self.rules = []

            self.mode_rules = []

            self.modes = []

            self.environments = []

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

        self._update_environment(
            signals
        )

        matched = self._check_rules(
            signals
        )

        if not matched:

            self._check_mode_rules(
                signals
            )

    # ---------------------------------
    # Update Mode (Presentation / Flip /
    # Cursor / Quick Circle)
    # ---------------------------------

    # Modes are ephemeral gesture-scoping contexts —
    # they decide what a gesture MEANS right now, to keep
    # the same physical gestures from colliding across
    # different uses (e.g. a swipe means "flip a page" in
    # Flip mode but "pick a quick command" in Quick Circle
    # mode). They carry no OS side effects of their own.

    def _update_mode(self, signals):

        voice = signals.get(
            "voice"
        )

        if (
            voice is not None
            and voice.get("signal") == "EXIT_MODE"
        ):

            if self.current_mode is not None:

                self._exit_current_mode()

                self._maybe_clear_signals()

            return

        for mode in self.modes:

            if not self._mode_trigger_matches(
                mode,
                signals
            ):
                continue

            if mode["mode"] == self.current_mode:
                return

            self._exit_current_mode()

            self._enter_mode(
                mode
            )

            self._maybe_clear_signals()

            return

    def _mode_trigger_matches(self, mode, signals):

        for trigger in mode.get(
            "triggers",
            []
        ):

            source = trigger["source"]

            # A gesture-sourced trigger (only Quick
            # Circle's Closed_Fist -> Open_Palm uses one)
            # only opens its mode from idle. That same
            # transition already means "start a new
            # swipe/scroll session" while Flip mode is
            # active, so it must not be reinterpreted as
            # "enter Quick Circle" mid-session.
            if (
                source == "gesture"
                and self.current_mode is not None
            ):
                continue

            signal_data = signals.get(
                source
            )

            if signal_data is None:
                continue

            if signal_data.get("signal") == trigger["signal"]:
                return True

        return False

    # ---------------------------------
    # Enter / Exit Mode
    # ---------------------------------

    def _enter_mode(self, mode):

        self.current_mode = mode["mode"]

        print(
            f"[MAPPER] Mode -> {self.current_mode}"
        )

        self.event_bus.publish(
            "mode_changed",
            {"mode": self.current_mode}
        )

    def _exit_current_mode(self):

        if self.current_mode is None:
            return

        print(
            f"[MAPPER] Mode -> None (exit {self.current_mode})"
        )

        self.current_mode = None

        self.event_bus.publish(
            "mode_changed",
            {"mode": None}
        )

    # ---------------------------------
    # Update Environment (Work / Study /
    # Movie / News)
    # ---------------------------------

    # Environments are the longer-lived task backdrop —
    # entering one runs a real sequence of OS actions
    # (opening apps, toggling Do Not Disturb, music) and
    # leaving it (by entering a different environment)
    # undoes them. Independent of which gesture mode is
    # active at the same time.

    def _update_environment(self, signals):

        voice = signals.get(
            "voice"
        )

        if voice is None:
            return

        signal = voice.get(
            "signal"
        )

        for environment in self.environments:

            if signal != environment["trigger"]:
                continue

            if environment["environment"] == self.current_environment:
                return

            self._exit_current_environment()

            self._enter_environment(
                environment
            )

            self._maybe_clear_signals()

            return

    def _enter_environment(self, environment):

        self.current_environment = environment["environment"]

        print(
            f"[MAPPER] Environment -> {self.current_environment}"
        )

        for action in environment.get(
            "enter_actions",
            []
        ):

            self._publish_command(
                action
            )

    def _exit_current_environment(self):

        if self.current_environment is None:
            return

        previous_environment = self._find_environment(
            self.current_environment
        )

        if previous_environment is not None:

            for action in previous_environment.get(
                "exit_actions",
                []
            ):

                self._publish_command(
                    action
                )

        print(
            f"[MAPPER] Environment -> None (exit {self.current_environment})"
        )

        self.current_environment = None

    def _find_environment(self, environment_name):

        for environment in self.environments:

            if environment["environment"] == environment_name:
                return environment

        return None

    def _find_mode(self, mode_name):

        for mode in self.modes:

            if mode["mode"] == mode_name:
                return mode

        return None

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

                self._maybe_clear_signals()

                return True

        return False

    # ---------------------------------
    # Mode Rules
    # ---------------------------------

    def _check_mode_rules(self, signals):

        if self.current_mode is None:
            return False

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

                # Quick Circle is a one-shot menu: picking
                # one of its four functions should close it
                # again, not leave it hanging open.
                if rule.get("exits_mode", False):

                    self._exit_current_mode()

                self._maybe_clear_signals()

                return True

        return False

    # ---------------------------------
    # Clear Signals (respects settings)
    # ---------------------------------

    def _maybe_clear_signals(self):

        if self.settings.get(
            "clear_signals_after_match",
            True
        ):

            self.event_bus.publish(
                "clear_fusion_signals",
                {}
            )
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

                "mode": self.current_mode,

                "environment": self.current_environment

            }

        )

    # ---------------------------------
    # Clear Mode / Environment
    # ---------------------------------

    def clear_mode(self):

        self._exit_current_mode()

    def clear_environment(self):

        self._exit_current_environment()

    # ---------------------------------
    # Reload Configuration
    # ---------------------------------

    def reload(self):

        self.settings = {}

        self.rules = []

        self.mode_rules = []

        self.modes = []

        self.environments = []

        self.current_mode = None

        self.current_environment = None

        self._load_fusion()
