from os_controller import OSController


class ActionExecutor:

    def __init__(self):

        self.os = OSController()

        self.actions = {

            # Mouse
            "CLICK":
                self.os.click,

            # Cursor
            "MOVE_CURSOR_LEFT":
                self.os.move_cursor_left,

            "MOVE_CURSOR_RIGHT":
                self.os.move_cursor_right,

            "MOVE_CURSOR_UP":
                self.os.move_cursor_up,

            "MOVE_CURSOR_DOWN":
                self.os.move_cursor_down,

            # Scroll
            "SCROLL_UP":
                self.os.scroll_up,

            "SCROLL_DOWN":
                self.os.scroll_down,

            # Window Management
            "MAXIMIZE_WINDOW":
                self.os.maximize_window,

            "MINIMIZE_WINDOW":
                self.os.minimize_window,

            "MOVE_WINDOW_LEFT":
                self.os.move_window_left,

            "MOVE_WINDOW_RIGHT":
                self.os.move_window_right,

            # Applications
            "OPEN_BROWSER":
                self.os.open_browser,

            "OPEN_CHATGPT":
                self.os.open_chatgpt,

            "OPEN_VSCODE":
                self.os.open_vscode,

            "OPEN_TERMINAL":
                self.os.open_terminal,

            # Keyboard Shortcuts
            "ALT_TAB":
                self.os.alt_tab,

            "CTRL_C":
                self.os.ctrl_c,

            "CTRL_V":
                self.os.ctrl_v,

            # Screenshot
            "SCREENSHOT":
                self.os.take_screenshot,
        }

    # ---------------------------------
    # Execute Command
    # ---------------------------------

    def execute(self, command):

        action = self.actions.get(command)

        if action is None:

            print(
                f"[UNKNOWN COMMAND] {command}"
            )

            return

        print(
            f"[EXECUTION] {command}"
        )

        try:

            result = action()

            if result:

                print(
                    f"[RESULT] {result}"
                )

        except Exception as e:

            print(
                f"[ERROR] {command}: {e}"
            )