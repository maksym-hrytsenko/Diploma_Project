import os
import subprocess
import webbrowser
from datetime import datetime

import pyautogui
import pyperclip


class OSController:

    CURSOR_STEP = 50
    SCROLL_STEP = 300

    def __init__(self):

        pyautogui.FAILSAFE = True

    # ---------------------------------
    # Mouse
    # ---------------------------------

    def click(self):

        pyautogui.click()

    def move_cursor_left(self):

        pyautogui.moveRel(
            -self.CURSOR_STEP,
            0,
            duration=0.1
        )

    def move_cursor_right(self):

        pyautogui.moveRel(
            self.CURSOR_STEP,
            0,
            duration=0.1
        )

    def move_cursor_up(self):

        pyautogui.moveRel(
            0,
            -self.CURSOR_STEP,
            duration=0.1
        )

    def move_cursor_down(self):

        pyautogui.moveRel(
            0,
            self.CURSOR_STEP,
            duration=0.1
        )

    # ---------------------------------
    # Scroll
    # ---------------------------------

    def scroll_up(self):

        pyautogui.scroll(
            self.SCROLL_STEP
        )

    def scroll_down(self):

        pyautogui.scroll(
            -self.SCROLL_STEP
        )

    # ---------------------------------
    # Keyboard Shortcuts
    # ---------------------------------

    def shortcut(self, *keys):

        pyautogui.hotkey(*keys)

    def alt_tab(self):

        pyautogui.hotkey(
            "alt",
            "tab"
        )

    def ctrl_c(self):

        pyautogui.hotkey(
            "ctrl",
            "c"
        )

    def ctrl_v(self):

        pyautogui.hotkey(
            "ctrl",
            "v"
        )

    # ---------------------------------
    # Clipboard
    # ---------------------------------

    def clipboard_copy(self, text):

        pyperclip.copy(text)

    def clipboard_paste(self):

        return pyperclip.paste()

    # ---------------------------------
    # Window Management
    # ---------------------------------

    def maximize_window(self):

        pyautogui.hotkey(
            "win",
            "up"
        )

    def minimize_window(self):

        pyautogui.hotkey(
            "win",
            "down"
        )

    def move_window_left(self):

        pyautogui.hotkey(
            "win",
            "left"
        )

    def move_window_right(self):

        pyautogui.hotkey(
            "win",
            "right"
        )

    # ---------------------------------
    # Applications
    # ---------------------------------

    def open_application(self, command):

        try:

            subprocess.Popen(command)

        except Exception as e:

            print(
                f"[APPLICATION ERROR] {e}"
            )

    def open_vscode(self):

        try:

            subprocess.Popen(
                ["code"]
            )

        except Exception as e:

            print(
                f"[VSCODE ERROR] {e}"
            )

    def open_terminal(self):

        try:

            subprocess.Popen(
                ["cmd.exe"]
            )

        except Exception as e:

            print(
                f"[TERMINAL ERROR] {e}"
            )

    # ---------------------------------
    # Websites
    # ---------------------------------

    def open_website(self, url):

        webbrowser.open(url)

    def open_browser(self):

        webbrowser.open(
            "https://google.com"
        )

    def open_chatgpt(self):

        webbrowser.open(
            "https://chatgpt.com"
        )

    # ---------------------------------
    # Screenshot
    # ---------------------------------

    def take_screenshot(self):

        os.makedirs(
            "screenshots",
            exist_ok=True
        )

        filename = (
            datetime.now()
            .strftime(
                "%Y%m%d_%H%M%S"
            )
            + ".png"
        )

        path = os.path.join(
            "screenshots",
            filename
        )

        screenshot = pyautogui.screenshot()

        screenshot.save(path)

        return path