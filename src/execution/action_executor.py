"""Final stage of the pipeline: turns decided commands into OS effects.

Subscribes to SignalMapper's command_event, plus the continuous
pointer/pinch streams that bypass fusion, and dispatches each to
OSController. Contains no decision logic of its own — every command
arrives already decided.

The one exception is Try Mode (see try_mode_active): a single dry-run gate
checked immediately before every OSController call, not a WHICH-command
decision — SignalMapper still decides and publishes command_event exactly
as normal while Try Mode is on, so mode switching and the on-screen
"Detected: ..." caption keep working; this module just stops the OS side
effect from actually happening.
"""

import pyautogui

from core.event_bus import EventBus
from execution.os_controller import OSController

from config.config_loader import load_system_config
from utils.logger import get_logger


logger = get_logger(__name__)


class ActionExecutor:

    def __init__(
        self,
        event_bus: EventBus,
        force_dry_run: bool = False
    ):

        self.event_bus = event_bus

        # Independent of try_mode_active below and never toggled after
        # construction — set only by main.py's --try-mode flag, for
        # benchmarks/run_stress_suite.py. try_mode_active mirrors
        # SignalMapper's Try Mode exactly, including its documented
        # behavior of turning itself off on "exit mode"/Esc/UI-exit (see
        # src/CLAUDE.md) — normal for a live demo, but wrong for an
        # unattended synthetic run, whose own command set naturally
        # exercises EXIT_MODE/HAND_SESSION_END and would otherwise let
        # real OS side effects start firing partway through. This flag is
        # the actual, unconditional safety guarantee; try_mode_active
        # alone is not.
        self.force_dry_run = force_dry_run

        execution_config = load_system_config().get(
            "execution",
            {}
        )

        self.os_controller = OSController()

        self.command_table = self._build_command_table()

        # Mirrored from SignalMapper's "mode_changed" event, used only to
        # route the continuous, fusion-bypassing streams below (pointer
        # position, pinch-drag, pinch-zoom); discrete commands already
        # arrive fully decided via command_event.
        self.active_mode = None

        # Mirrored from SignalMapper's "try_mode_changed" event. While True,
        # every real OS side effect below is skipped (see _handle_command,
        # _handle_pointer, _handle_pinch_drag, _handle_pinch_zoom) — the
        # rest of the pipeline (mode switching, gesture recognition, the
        # camera preview's "Detected: ..." caption) keeps running exactly
        # as normal, so a demo can show the system deciding what it WOULD
        # do without it actually touching the computer.
        self.try_mode_active = False

        # Accumulates raw pinch-distance deltas and only fires a zoom
        # hotkey once zoom_step_threshold is crossed — firing on every
        # frame's tiny delta would spam keystrokes faster than any app's
        # zoom animation can follow.
        self.zoom_accumulator = 0.0

        self.zoom_step_threshold = execution_config.get(
            "zoom_step_threshold",
            0.05
        )

        # Mirrors PointerOverlay's own MIRROR_X convention, so the real
        # cursor sits on the same side as the user's hand from their own
        # point of view.
        self.mirror_cursor_x = execution_config.get(
            "mirror_cursor_x",
            True
        )

    # A static lookup from command string to an OSController method, not
    # decision logic — the decision already happened in SignalMapper.
    def _build_command_table(self):

        controller = self.os_controller

        return {

            "CLICK": controller.click,
            "RIGHT_CLICK": controller.right_click,

            "SCROLL_UP": controller.scroll_up,
            "SCROLL_DOWN": controller.scroll_down,

            "FLIP_NEXT": controller.flip_next,
            "FLIP_PREVIOUS": controller.flip_previous,

            "NEXT_SLIDE": controller.next_slide,
            "PREVIOUS_SLIDE": controller.previous_slide,
            "START_SLIDESHOW": controller.start_slideshow,

            "OPEN_BROWSER": controller.open_browser,
            "OPEN_CHATGPT": controller.open_chatgpt,
            "OPEN_GITHUB": controller.open_github,
            "OPEN_VSCODE": controller.open_vscode,
            "OPEN_TERMINAL": controller.open_terminal,
            "OPEN_SAFARI": controller.open_safari,
            "OPEN_CHROME": controller.open_chrome,
            "OPEN_SPOTIFY": controller.open_spotify,
            "OPEN_SLACK": controller.open_slack,
            "OPEN_DISCORD": controller.open_discord,
            "OPEN_MAIL": controller.open_mail,
            "OPEN_CALENDAR": controller.open_calendar,
            "OPEN_NOTES": controller.open_notes,
            "OPEN_TELEGRAM": controller.open_telegram,
            "OPEN_FINDER": controller.open_finder,
            "OPEN_NOTION": controller.open_notion,
            "OPEN_PHOTOS": controller.open_photos,
            "OPEN_PREVIEW": controller.open_preview,
            "OPEN_SETTINGS": controller.open_settings,
            "OPEN_TV": controller.open_tv,
            "OPEN_NEWS": controller.open_news,
            "OPEN_NETFLIX": controller.open_netflix,

            "OPEN_JOB_SEARCH_WINDOWS": controller.open_job_search_windows,
            "OPEN_STUDY_WINDOWS": controller.open_study_windows,
            "OPEN_NEWS_TABS": controller.open_news_tabs,

            "RUN_CINEMA_MODE": controller.run_cinema_mode,

            "TOGGLE_MIC": controller.toggle_mic,
            "TOGGLE_CAMERA": controller.toggle_camera,
            "TOGGLE_CALL_AUDIO": controller.toggle_call_audio,
            "TOGGLE_BACKGROUND_BLUR": controller.toggle_background_blur,

            "NEXT_TRACK": controller.next_track,
            "PREVIOUS_TRACK": controller.previous_track,

            "VOLUME_UP": controller.volume_up,
            "VOLUME_DOWN": controller.volume_down,

            "ENABLE_DO_NOT_DISTURB": controller.enable_do_not_disturb,
            "DISABLE_DO_NOT_DISTURB": controller.disable_do_not_disturb,

            "PREVENT_DISPLAY_SLEEP": controller.prevent_display_sleep,
            "ALLOW_DISPLAY_SLEEP": controller.allow_display_sleep,

            "PLAY_FOCUS_MUSIC": controller.play_focus_music,
            "PAUSE_FOCUS_MUSIC": controller.pause_focus_music,

            "MEDIA_PLAY_PAUSE": controller.media_play_pause
        }

    def start(self):

        self.event_bus.subscribe(
            "command_event",
            self._handle_command
        )

        self.event_bus.subscribe(
            "pointer_position",
            self._handle_pointer
        )

        self.event_bus.subscribe(
            "pinch_drag",
            self._handle_pinch_drag
        )

        self.event_bus.subscribe(
            "pinch_zoom",
            self._handle_pinch_zoom
        )

        self.event_bus.subscribe(
            "mode_changed",
            self._handle_mode_changed
        )

        self.event_bus.subscribe(
            "try_mode_changed",
            self._handle_try_mode_changed
        )

        self.event_bus.subscribe(
            "fusion_signal",
            self._debug_event
        )

        self.event_bus.subscribe(
            "command_event",
            self._debug_event
        )

    def stop(self):

        self.event_bus.unsubscribe(
            "command_event",
            self._handle_command
        )

        self.event_bus.unsubscribe(
            "pointer_position",
            self._handle_pointer
        )

        self.event_bus.unsubscribe(
            "pinch_drag",
            self._handle_pinch_drag
        )

        self.event_bus.unsubscribe(
            "pinch_zoom",
            self._handle_pinch_zoom
        )

        self.event_bus.unsubscribe(
            "mode_changed",
            self._handle_mode_changed
        )

        self.event_bus.unsubscribe(
            "try_mode_changed",
            self._handle_try_mode_changed
        )

        self.event_bus.unsubscribe(
            "fusion_signal",
            self._debug_event
        )

        self.event_bus.unsubscribe(
            "command_event",
            self._debug_event
        )

    def _handle_command(self, event):

        data = event.get(
            "data",
            {}
        )

        command = data.get(
            "command"
        )

        if command is None:
            return

        handler = self.command_table.get(
            command
        )

        if handler is None:

            logger.warning(
                "Unknown command: %s",
                command
            )

            return

        if self._is_dry_run():

            logger.info(
                "[TRY MODE] would execute: %s",
                command
            )

            self.event_bus.publish(
                "try_mode_action",
                {"command": command}
            )

            return

        logger.info(
            "%s",
            command
        )

        handler()

    def _handle_mode_changed(self, event):

        data = event.get(
            "data",
            {}
        )

        self.active_mode = data.get(
            "mode"
        )

    def _handle_try_mode_changed(self, event):

        data = event.get(
            "data",
            {}
        )

        self.try_mode_active = data.get(
            "active",
            False
        )

    # Every OSController-call site below checks this instead of
    # try_mode_active directly, so force_dry_run (permanent, set only at
    # construction) keeps gating the OS side effect even after
    # try_mode_active itself flips back to False mid-run.
    def _is_dry_run(self):

        return (
            self.try_mode_active
            or self.force_dry_run
        )

    def _handle_pointer(self, event):

        data = event.get(
            "data",
            {}
        )

        x = data.get("x")
        y = data.get("y")

        if x is None or y is None:
            return

        if self.active_mode == "cursor":

            # Try Mode: no real cursor movement (see try_mode_active
            # above) AND no laser-dot substitute either — PointerOverlay
            # draws on the PRIMARY screen whenever there's no second
            # display connected (its own fallback, see
            # _select_presentation_screen), i.e. the same screen the real
            # cursor already lives on. A same-color, same-position moving
            # dot there reads as "the cursor is moving" even though it
            # isn't — precisely the confusion Try Mode must not cause.
            # The camera preview's "Detected: Cursor control" caption is
            # the only Try Mode feedback for this gesture, on purpose.
            if not self._is_dry_run():

                self._move_real_cursor_to(
                    x,
                    y
                )

        elif (
            self.active_mode is None
            or self.active_mode == "presentation"
        ):

            # Laser-pointer dot: standby (no mode) or Presentation (its
            # own pointer math already computed upstream in
            # GestureRecognizer, still ends up as a dot here). Every other
            # mode — Flip, Call — has no pointer behavior of its own, so
            # the position is simply dropped.
            self.event_bus.publish(
                "pointer_overlay_update",
                {
                    "x": x,
                    "y": y
                }
            )

    def _move_real_cursor_to(self, normalized_x, normalized_y):

        screen_width, screen_height = pyautogui.size()

        # Mirrors PointerOverlay's convention, so the cursor sits on the
        # same side the user's hand is on from their own point of view.
        display_x = (
            (1.0 - normalized_x)
            if self.mirror_cursor_x
            else normalized_x
        )

        pixel_x = int(display_x * screen_width)
        pixel_y = int(normalized_y * screen_height)

        self.os_controller.move_cursor_to(
            pixel_x,
            pixel_y
        )

    def _handle_pinch_drag(self, event):

        if self.active_mode != "cursor":
            return

        if self._is_dry_run():
            return

        data = event.get(
            "data",
            {}
        )

        delta_x = data.get("delta_x")
        delta_y = data.get("delta_y")

        if delta_x is None or delta_y is None:
            return

        screen_width, screen_height = pyautogui.size()

        # Natural/drag scrolling: content moves WITH the hand, as if
        # physically grabbed — dragging up pulls later content into view
        # (same direction as OSController.scroll_down), dragging down
        # reveals earlier content (same as scroll_up), and the same logic
        # applies horizontally. Converted to real screen pixels so content
        # moves roughly the same distance the hand moved.
        pixel_amount_x = int(
            delta_x * screen_width
        )

        pixel_amount_y = int(
            delta_y * screen_height
        )

        self.os_controller.scroll_by(
            pixel_amount_x,
            pixel_amount_y
        )

    def _handle_pinch_zoom(self, event):

        if self.active_mode != "cursor":
            return

        if self._is_dry_run():
            return

        data = event.get(
            "data",
            {}
        )

        delta_distance = data.get("delta_distance")

        if delta_distance is None:
            return

        self.zoom_accumulator += delta_distance

        while self.zoom_accumulator >= self.zoom_step_threshold:

            self.os_controller.zoom_in()

            self.zoom_accumulator -= self.zoom_step_threshold

        while self.zoom_accumulator <= -self.zoom_step_threshold:

            self.os_controller.zoom_out()

            self.zoom_accumulator += self.zoom_step_threshold

    def _debug_event(self, event):

        event_type = event.get(
            "type"
        )

        data = event.get(
            "data",
            {}
        )

        if event_type == "fusion_signal":

            lines = ["========== SIGNAL MAPPER INPUT =========="]

            signals = data.get(
                "signals",
                {}
            )

            if not signals:

                lines.append("No active signals")

            else:

                for source, value in signals.items():

                    lines.append(
                        f"{source.upper():10} : {value['signal']}"
                    )

            lines.append("=========================================")

            logger.debug(
                "\n".join(lines)
            )

        elif event_type == "command_event":

            lines = ["========== SIGNAL MAPPER OUTPUT =========="]

            lines.append(
                f"COMMAND    : {data.get('command')}"
            )

            lines.append(
                f"SOURCE     : {data.get('source')}"
            )

            mode = data.get(
                "mode"
            )

            if mode:

                lines.append(
                    f"MODE       : {mode}"
                )

            environment = data.get(
                "environment"
            )

            if environment:

                lines.append(
                    f"ENVIRONMENT: {environment}"
                )

            lines.append("==========================================")

            logger.debug(
                "\n".join(lines)
            )
