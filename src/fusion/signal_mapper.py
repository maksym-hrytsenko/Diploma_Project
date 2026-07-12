"""Decision-making stage of the fusion layer.

Reads fusion_signal (from MultimodalFusion) and config/fusion.json's rules,
mode_rules, modes and environments to decide whether a command should fire,
a mode should be entered/exited, or an environment should change — the only
module in the pipeline allowed to make that decision. Publishes command_event
and mode_changed.
"""

from core.event_bus import EventBus
from config.config_loader import load_fusion_config
from utils.logger import get_logger


logger = get_logger(__name__)


class SignalMapper:

    # How each (source, mapped signal) pair is actually recognized, for the
    # "[RESOLVED]" report in _report_resolution. "vector" = computed
    # directly from landmark geometry, never touching MediaPipe's own
    # classifier output. "model" = the value IS a MediaPipe ML classifier
    # category or blendshape regression score. Voice/keyboard aren't
    # listed: voice's tier already travels with the signal from IntentModel,
    # and a raw key combo has no recognition step at all.
    SIGNAL_METHOD = {

        ("gesture", "HAND_LEFT"): "vector",
        ("gesture", "HAND_RIGHT"): "vector",
        ("gesture", "HAND_UP"): "vector",
        ("gesture", "HAND_DOWN"): "vector",
        ("gesture", "HAND_SESSION_START"): "vector",
        ("gesture", "HAND_SESSION_END"): "vector",
        ("gesture", "PINCH"): "vector",
        ("gesture", "DOUBLE_PINCH"): "vector",
        ("gesture", "OK_SIGN"): "vector",

        ("gesture", "ONE_FINGER"): "vector",
        ("gesture", "TWO_FINGERS"): "vector",
        ("gesture", "THREE_FINGERS"): "vector",
        ("gesture", "FOUR_FINGERS"): "vector",

        ("face", "HEAD_TILT_LEFT"): "vector",
        ("face", "HEAD_TILT_RIGHT"): "vector",

        ("face", "MOUTH_OPEN"): "model",
        ("face", "DOUBLE_BLINK"): "model",
        ("face", "EYEBROWS_UP"): "model",
        ("face", "EYEBROWS_DOWN"): "model",
        ("face", "DOUBLE_EYEBROWS_UP"): "model",
        ("face", "CONFIRM"): "model"

    }

    VOICE_TIER_LABEL = {

        "exact": "voice exact match",
        "semantic": "voice semantic model",
        "llm": "voice LLM model"

    }

    def __init__(self, event_bus: EventBus):

        self.event_bus = event_bus

        self.settings = {}

        self.rules = []

        self.mode_rules = []

        self.modes = []

        self.environments = []

        self.current_mode = None

        self.current_environment = None

        # Main window's System ON/OFF hub button — while False, no mode
        # may be entered/exited and no command fires (see _handle_signal).
        self.system_enabled = True

        self._load_fusion()

    def start(self):

        self.event_bus.subscribe(
            "fusion_signal",
            self._handle_signal
        )

        self.event_bus.subscribe(
            "ui_system_toggle",
            self._handle_system_toggle
        )

    def stop(self):

        self.event_bus.unsubscribe(
            "fusion_signal",
            self._handle_signal
        )

        self.event_bus.unsubscribe(
            "ui_system_toggle",
            self._handle_system_toggle
        )

    def _handle_system_toggle(self, event):

        self.system_enabled = event.get(
            "data",
            {}
        ).get(
            "active",
            True
        )

    def _load_fusion(self):

        try:

            data = load_fusion_config(
                force_reload=True
            )

        except Exception:

            logger.exception(
                "Failed to load fusion.json — falling back to empty rules"
            )

            data = {}

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

    def _handle_signal(self, event):

        # System OFF — no mode changes, no commands, no quick_circle
        if not self.system_enabled:
            return

        data = event.get(
            "data",
            {}
        )

        signals = data.get(
            "signals",
            {}
        )

        triggering_source = data.get(
            "source"
        )

        if not signals:
            return

        # `signals` is the SAME dict TemporalSync stores internally, not a
        # copy — clearing it mid-way would delete entries out from under
        # the checks still to come in this pass, so nothing is cleared
        # until every check below has seen the complete signal set.
        mode_matched = self._update_mode(
            signals
        )

        environment_matched = self._update_environment(
            signals
        )

        rule_matched = self._check_rules(
            signals,
            triggering_source
        )

        if not rule_matched:

            rule_matched = self._check_mode_rules(
                signals,
                triggering_source
            )

        if mode_matched or environment_matched or rule_matched:

            self._maybe_clear_signals()

    # Modes are ephemeral gesture-scoping contexts — they decide what a
    # gesture MEANS right now, keeping the same physical gestures from
    # colliding across different uses (e.g. a swipe means "flip a page" in
    # Flip mode but "pick a quick command" in Quick Circle mode). They
    # carry no OS side effects of their own.
    def _update_mode(self, signals):

        voice = signals.get(
            "voice"
        )

        keyboard = signals.get(
            "keyboard"
        )

        gesture = signals.get(
            "gesture"
        )

        ui = signals.get(
            "ui"
        )

        # Four independent ways to back out of whichever mode is active.
        # Voice "exit mode", Esc and the UI's own active-mode-icon-clicked-
        # again all work identically from any mode at any time. Closing
        # the fist only backs out of Quick Circle specifically — every
        # other mode is voice/keyboard/UI-entered and persistent, so the
        # hand shape closing has no bearing on whether it should stay
        # active (e.g. closing the fist mid-swipe in Flip mode must not
        # exit Flip mode).
        exit_requested = (
            voice is not None
            and voice.get("signal") == "EXIT_MODE"
        ) or (
            keyboard is not None
            and keyboard.get("signal") == "ESCAPE_KEY"
        ) or (
            ui is not None
            and ui.get("signal") == "EXIT_MODE"
        ) or (
            gesture is not None
            and gesture.get("signal") == "HAND_SESSION_END"
            and self.current_mode == "quick_circle"
        )

        if exit_requested:

            if self.current_mode is not None:

                self._exit_current_mode()

                return True

            return False

        for mode in self.modes:

            if not self._mode_trigger_matches(
                mode,
                signals
            ):
                continue

            if mode["mode"] == self.current_mode:
                return False

            self._exit_current_mode()

            self._enter_mode(
                mode
            )

            return True

        return False

    def _mode_trigger_matches(self, mode, signals):

        for trigger in mode.get(
            "triggers",
            []
        ):

            source = trigger["source"]

            # A gesture-sourced trigger (only Quick Circle's Closed_Fist ->
            # Open_Palm uses one) only opens its mode from idle. That same
            # transition already means "start a new swipe/scroll session"
            # while Flip mode is active, so it must not be reinterpreted as
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

    def _enter_mode(self, mode):

        self.current_mode = mode["mode"]

        logger.info(
            "Mode -> %s",
            self.current_mode
        )

        self.event_bus.publish(
            "mode_changed",
            {"mode": self.current_mode}
        )

    def _exit_current_mode(self):

        if self.current_mode is None:
            return

        logger.info(
            "Mode -> None (exit %s)",
            self.current_mode
        )

        self.current_mode = None

        self.event_bus.publish(
            "mode_changed",
            {"mode": None}
        )

    # Environments are the longer-lived task backdrop — entering one runs a
    # real sequence of OS actions (opening apps, toggling Do Not Disturb,
    # music) and leaving it (by entering a different environment) undoes
    # them. Independent of which gesture mode is active at the same time.
    def _update_environment(self, signals):

        voice = signals.get(
            "voice"
        )

        if voice is None:
            return False

        signal = voice.get(
            "signal"
        )

        for environment in self.environments:

            if signal != environment["trigger"]:
                continue

            if environment["environment"] == self.current_environment:
                return False

            self._exit_current_environment()

            self._enter_environment(
                environment
            )

            return True

        return False

    def _enter_environment(self, environment):

        self.current_environment = environment["environment"]

        logger.info(
            "Environment -> %s",
            self.current_environment
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

        logger.info(
            "Environment -> None (exit %s)",
            self.current_environment
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

    # A rule only gets a chance to fire on the pass whose triggering source
    # is one of its own condition keys — i.e. it fires on the edge of ITS
    # OWN condition becoming satisfied, not on every unrelated signal that
    # arrives while a held keyboard combo (persistent, see MultimodalFusion)
    # keeps its share of the condition sitting in the buffer. Without this,
    # a rule keyed on a single held combo would refire on every unrelated
    # event for as long as the key stays down.
    def _check_rules(self, signals, triggering_source):

        for rule in self.rules:

            if triggering_source not in rule["conditions"]:
                continue

            if self._match_conditions(

                rule["conditions"],

                signals

            ):

                logger.info(
                    "Match -> %s",
                    rule['name']
                )

                self._report_resolution(
                    rule["conditions"],
                    signals,
                    action=rule["action"]
                )

                self._publish_command(
                    rule["action"]
                )

                return True

        return False

    def _check_mode_rules(self, signals, triggering_source):

        if self.current_mode is None:
            return False

        for rule in self.mode_rules:

            if rule["mode"] != self.current_mode:
                continue

            if triggering_source not in rule["conditions"]:
                continue

            if self._match_conditions(

                rule["conditions"],

                signals

            ):

                logger.info(
                    "Match -> %s",
                    rule['name']
                )

                # Quick Circle's four sides each select a different mode
                # directly — this is a mode transition, not a command, so
                # it swaps in the target mode instead of publishing one.
                target_mode_name = rule.get("enters_mode")

                if target_mode_name is not None:

                    self._report_resolution(
                        rule["conditions"],
                        signals,
                        enters_mode=target_mode_name
                    )

                    target_mode = self._find_mode(
                        target_mode_name
                    )

                    self._exit_current_mode()

                    if target_mode is not None:

                        self._enter_mode(
                            target_mode
                        )

                    return True

                self._report_resolution(
                    rule["conditions"],
                    signals,
                    action=rule["action"]
                )

                self._publish_command(
                    rule["action"]
                )

                # Quick Circle is a one-shot menu: picking one of its four
                # functions should close it again, not leave it hanging open.
                if rule.get("exits_mode", False):

                    self._exit_current_mode()

                return True

        return False

    # Prints, right after a rule/mode_rule matches, exactly which signal(s)
    # decided it and how each was recognized — voice tier, direct
    # vector/geometry, or an ML model — so a misfired command can be traced
    # back to its source instead of guessed at.
    def _report_resolution(
        self,
        conditions,
        signals,
        action=None,
        enters_mode=None
    ):

        descriptions = [
            self._describe_signal(
                source,
                signals.get(source, {})
            )
            for source in conditions
        ]

        outcome = (
            f"enters mode: {enters_mode}"
            if enters_mode is not None
            else action
        )

        logger.info(
            "[RESOLVED] %s <- %s",
            outcome,
            " + ".join(descriptions)
        )

    def _describe_signal(self, source, signal_data):

        signal_name = signal_data.get(
            "signal"
        )

        if source == "voice":

            tier = signal_data.get(
                "tier"
            ) or "exact"

            label = self.VOICE_TIER_LABEL.get(
                tier,
                "voice"
            )

            return f'voice:"{signal_name}" ({label})'

        if source == "keyboard":

            return f'keyboard:"{signal_name}" (direct)'

        method = self.SIGNAL_METHOD.get(
            (source, signal_name),
            "model"
        )

        label = (
            "vector/geometry"
            if method == "vector"
            else "ML model"
        )

        return f'{source}:"{signal_name}" ({label})'

    def _maybe_clear_signals(self):

        if self.settings.get(
            "clear_signals_after_match",
            True
        ):

            self.event_bus.publish(
                "clear_fusion_signals",
                {}
            )

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

    def _publish_command(
        self,
        command
    ):

        if not command:
            return

        logger.info(
            "Command -> %s",
            command
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

    def clear_mode(self):

        self._exit_current_mode()

    def clear_environment(self):

        self._exit_current_environment()

    def reload(self):

        self.settings = {}

        self.rules = []

        self.mode_rules = []

        self.modes = []

        self.environments = []

        self.current_mode = None

        self.current_environment = None

        self._load_fusion()
