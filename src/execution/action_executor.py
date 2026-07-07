import pyautogui

from execution.os_controller import OSController
from ui.pointer_overlay import PointerOverlay


class ActionExecutor:

    def __init__(self, event_bus):

        self.event_bus = event_bus

        self.os_controller = OSController()

        self.pointer_overlay = PointerOverlay()

        self.command_table = self._build_command_table()

        # Which gesture mode is currently active, mirrored
        # from SignalMapper's "mode_changed" event. Needed
        # only to route the two continuous, fusion-bypassing
        # streams below (pointer position, pinch-drag) to
        # the right place — every discrete command still
        # arrives fully decided via command_event, with no
        # branching here.
        self.active_mode = None

    # ---------------------------------
    # Command Table
    # ---------------------------------

    # A static lookup from command string to an OSController
    # method — not decision logic. The decision (which
    # command to fire, for which signals) already happened
    # in SignalMapper; this table only knows how to carry
    # a decided command out.
    def _build_command_table(self):

        controller = self.os_controller

        return {

            "CLICK": controller.click,

            "SCROLL_UP": controller.scroll_up,
            "SCROLL_DOWN": controller.scroll_down,

            "FLIP_NEXT": controller.flip_next,
            "FLIP_PREVIOUS": controller.flip_previous,

            "NEXT_SLIDE": controller.next_slide,
            "PREVIOUS_SLIDE": controller.previous_slide,

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
            "OPEN_ZOOM": controller.open_zoom,
            "OPEN_MAIL": controller.open_mail,
            "OPEN_CALENDAR": controller.open_calendar,
            "OPEN_NOTES": controller.open_notes,
            "OPEN_MESSAGES": controller.open_messages,
            "OPEN_WHATSAPP": controller.open_whatsapp,
            "OPEN_TELEGRAM": controller.open_telegram,
            "OPEN_FINDER": controller.open_finder,
            "OPEN_NOTION": controller.open_notion,
            "OPEN_FIGMA": controller.open_figma,
            "OPEN_PHOTOS": controller.open_photos,
            "OPEN_MUSIC": controller.open_music,
            "OPEN_PREVIEW": controller.open_preview,
            "OPEN_SETTINGS": controller.open_settings,
            "OPEN_TV": controller.open_tv,
            "OPEN_NEWS": controller.open_news,

            "OPEN_ADMIN_TERMINAL": controller.open_admin_terminal,
            "FORCE_QUIT_APP": controller.force_quit_frontmost_app,
            "LOCK_SCREEN": controller.lock_screen,

            "ENABLE_DO_NOT_DISTURB": controller.enable_do_not_disturb,
            "DISABLE_DO_NOT_DISTURB": controller.disable_do_not_disturb,
            "TOGGLE_DO_NOT_DISTURB": controller.toggle_do_not_disturb,

            "PREVENT_DISPLAY_SLEEP": controller.prevent_display_sleep,
            "ALLOW_DISPLAY_SLEEP": controller.allow_display_sleep,

            "PLAY_FOCUS_MUSIC": controller.play_focus_music,
            "PAUSE_FOCUS_MUSIC": controller.pause_focus_music,

            "MEDIA_PLAY_PAUSE": controller.media_play_pause
        }

    # ---------------------------------
    # Start / Stop
    # ---------------------------------

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
            "mode_changed",
            self._handle_mode_changed
        )

        # Debug SignalMapper
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
            "mode_changed",
            self._handle_mode_changed
        )

        self.event_bus.unsubscribe(
            "fusion_signal",
            self._debug_event
        )

        self.event_bus.unsubscribe(
            "command_event",
            self._debug_event
        )

    # ---------------------------------
    # Handle Commands
    # ---------------------------------

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

            print(
                f"[EXECUTOR] Unknown command: {command}"
            )

            return

        print(
            f"[EXECUTOR] {command}"
        )

        handler()

    # ---------------------------------
    # Track Active Mode
    # ---------------------------------

    def _handle_mode_changed(self, event):

        data = event.get(
            "data",
            {}
        )

        self.active_mode = data.get(
            "mode"
        )

    # ---------------------------------
    # Handle Pointer (Cursor Mode vs.
    # laser pointer overlay)
    # ---------------------------------

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

            self._move_real_cursor(
                x,
                y
            )

        else:

            self.pointer_overlay.update_position(
                x,
                y
            )

    def _move_real_cursor(self, normalized_x, normalized_y):

        screen_width, screen_height = pyautogui.size()

        # Mirrors PointerOverlay's convention, so the
        # cursor moves the same direction as the user's
        # hand from their own point of view.
        display_x = 1.0 - normalized_x

        pixel_x = int(display_x * screen_width)
        pixel_y = int(normalized_y * screen_height)

        self.os_controller.move_cursor_to(
            pixel_x,
            pixel_y
        )

    # ---------------------------------
    # Handle Pinch-Drag (Cursor Mode scroll)
    # ---------------------------------

    def _handle_pinch_drag(self, event):

        if self.active_mode != "cursor":
            return

        data = event.get(
            "data",
            {}
        )

        delta_y = data.get("delta_y")

        if delta_y is None:
            return

        self.os_controller.scroll_by(
            delta_y
        )

    # ---------------------------------
    # Debug SignalMapper
    # ---------------------------------

    def _debug_event(self, event):

        event_type = event.get(
            "type"
        )

        data = event.get(
            "data",
            {}
        )

        if event_type == "fusion_signal":

            print("\n========== SIGNAL MAPPER INPUT ==========")

            signals = data.get(
                "signals",
                {}
            )

            if not signals:

                print("No active signals")

            else:

                for source, value in signals.items():

                    print(
                        f"{source.upper():10} : {value['signal']}"
                    )

            print("=========================================")

        elif event_type == "command_event":

            print("========== SIGNAL MAPPER OUTPUT ==========")

            print(
                f"COMMAND    : {data.get('command')}"
            )

            print(
                f"SOURCE     : {data.get('source')}"
            )

            mode = data.get(
                "mode"
            )

            if mode:

                print(
                    f"MODE       : {mode}"
                )

            environment = data.get(
                "environment"
            )

            if environment:

                print(
                    f"ENVIRONMENT: {environment}"
                )

            print("==========================================\n")
