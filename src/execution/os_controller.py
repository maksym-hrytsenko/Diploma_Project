import subprocess
import time
import webbrowser

import pyautogui


class OSController:

    SCROLL_STEP = 300

    # A single swipe should feel like a smooth scroll, not
    # one abrupt jump — broken into a short burst of small
    # ticks with tiny pauses between them.
    SCROLL_BURST_TICKS = 6
    SCROLL_BURST_DELAY = 0.012

    # Scales a pinch-drag's per-frame normalized Y movement
    # into pyautogui scroll units.
    DRAG_SCROLL_SENSITIVITY = 4000

    # Frontmost apps that actually respond to arrow-key
    # "next/previous" navigation (photo viewers, browsers,
    # video players). Everywhere else, Flip mode falls back
    # to switching macOS Spaces instead — there is no
    # generic macOS API to ask an arbitrary app "is there
    # more content in this direction".
    FLIPPABLE_APPS = {
        "Preview",
        "Photos",
        "Safari",
        "Google Chrome",
        "QuickTime Player"
    }

    def __init__(self):

        pyautogui.FAILSAFE = True

        # Tracks the caffeinate subprocess started by
        # prevent_display_sleep, so allow_display_sleep can
        # stop the right one.
        self.caffeinate_process = None

    # ---------------------------------
    # Mouse (Cursor Mode)
    # ---------------------------------

    def click(self):

        pyautogui.click()

    def move_cursor_to(self, x_pixels, y_pixels):

        try:

            pyautogui.moveTo(
                x_pixels,
                y_pixels,
                duration=0
            )

        except Exception as e:

            print(
                f"[CURSOR ERROR] {e}"
            )

    def scroll_by(self, delta_y):

        # Dragging down (delta_y > 0 in normalized image
        # coordinates) reveals content below, matching
        # natural/trackpad-style scrolling.
        amount = int(
            -delta_y * self.DRAG_SCROLL_SENSITIVITY
        )

        if amount == 0:
            return

        try:

            pyautogui.scroll(amount)

        except Exception as e:

            print(
                f"[SCROLL ERROR] {e}"
            )

    # ---------------------------------
    # Scroll (Flip Mode)
    # ---------------------------------

    def scroll_up(self):

        self._smooth_scroll(
            self.SCROLL_STEP
        )

    def scroll_down(self):

        self._smooth_scroll(
            -self.SCROLL_STEP
        )

    def _smooth_scroll(self, total_amount):

        tick_amount = total_amount // self.SCROLL_BURST_TICKS

        if tick_amount == 0:
            tick_amount = total_amount

        for _ in range(self.SCROLL_BURST_TICKS):

            pyautogui.scroll(tick_amount)

            time.sleep(self.SCROLL_BURST_DELAY)

    # ---------------------------------
    # Flip Next / Previous (Flip Mode)
    # ---------------------------------

    def flip_next(self):

        if self._frontmost_app_is_flippable():

            pyautogui.press("right")

        else:

            pyautogui.hotkey("ctrl", "right")

    def flip_previous(self):

        if self._frontmost_app_is_flippable():

            pyautogui.press("left")

        else:

            pyautogui.hotkey("ctrl", "left")

    def _frontmost_app_is_flippable(self):

        app_name = self._run_applescript(
            'tell application "System Events" to get name of '
            'first process whose frontmost is true'
        )

        return app_name in self.FLIPPABLE_APPS

    # ---------------------------------
    # AppleScript Helper
    # ---------------------------------

    def _run_applescript(self, script):

        try:

            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                check=True
            )

            return result.stdout.strip()

        except Exception as e:

            print(
                f"[APPLESCRIPT ERROR] {e} "
                f"(Accessibility permission granted?)"
            )

            return None

    # ---------------------------------
    # Applications
    # ---------------------------------

    def _open_mac_app(self, app_name):

        try:

            subprocess.Popen(
                ["open", "-a", app_name]
            )

        except Exception as e:

            print(
                f"[APPLICATION ERROR] {app_name}: {e}"
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

        self._open_mac_app("Terminal")

    def open_admin_terminal(self):

        # macOS has no direct "Run as Administrator"
        # equivalent — the realistic version is opening
        # Terminal and immediately prompting for the
        # user's password via sudo.
        try:

            subprocess.Popen(
                [
                    "osascript",
                    "-e",
                    'tell application "Terminal" to do script "sudo -s"'
                ]
            )

            subprocess.Popen(
                [
                    "osascript",
                    "-e",
                    'tell application "Terminal" to activate'
                ]
            )

        except Exception as e:

            print(
                f"[ADMIN TERMINAL ERROR] {e}"
            )

    def open_safari(self):

        self._open_mac_app("Safari")

    def open_chrome(self):

        self._open_mac_app("Google Chrome")

    def open_spotify(self):

        self._open_mac_app("Spotify")

    def open_slack(self):

        self._open_mac_app("Slack")

    def open_discord(self):

        self._open_mac_app("Discord")

    def open_zoom(self):

        self._open_mac_app("zoom.us")

    def open_mail(self):

        self._open_mac_app("Mail")

    def open_calendar(self):

        self._open_mac_app("Calendar")

    def open_notes(self):

        self._open_mac_app("Notes")

    def open_messages(self):

        self._open_mac_app("Messages")

    def open_whatsapp(self):

        self._open_mac_app("WhatsApp")

    def open_telegram(self):

        self._open_mac_app("Telegram")

    def open_finder(self):

        self._open_mac_app("Finder")

    def open_notion(self):

        self._open_mac_app("Notion")

    def open_figma(self):

        self._open_mac_app("Figma")

    def open_photos(self):

        self._open_mac_app("Photos")

    def open_music(self):

        self._open_mac_app("Music")

    def open_preview(self):

        self._open_mac_app("Preview")

    def open_settings(self):

        self._open_mac_app("System Settings")

    def open_tv(self):

        self._open_mac_app("TV")

    def open_news(self):

        self._open_mac_app("News")

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

    def open_github(self):

        webbrowser.open(
            "https://github.com"
        )

    # ---------------------------------
    # Focus Music (Study Environment)
    # ---------------------------------

    def play_focus_music(self):

        try:

            subprocess.Popen(
                [
                    "osascript",
                    "-e",
                    'tell application "Spotify" to play'
                ]
            )

        except Exception as e:

            print(
                f"[MUSIC ERROR] {e}"
            )

    def pause_focus_music(self):

        try:

            subprocess.Popen(
                [
                    "osascript",
                    "-e",
                    'tell application "Spotify" to pause'
                ]
            )

        except Exception as e:

            print(
                f"[MUSIC ERROR] {e}"
            )

    # ---------------------------------
    # Media Play / Pause (Global)
    # ---------------------------------

    # Works with whichever player currently owns "now
    # playing" (Spotify, Music, a browser tab, QuickTime,
    # ...) by posting the real macOS system Play/Pause
    # media key, the same event a physical keyboard's media
    # key sends — not an app-specific AppleScript call.
    #
    # This is inherently a single toggle key, not separate
    # absolute play/pause keys, so "start" and "stop" both
    # send the identical event: saying "stop" while already
    # paused resumes playback. See docs/SYSTEM_FUNCTIONS.md
    # for this accepted limitation.
    def media_play_pause(self):

        try:

            from AppKit import NSEvent
            import Quartz

            nx_keytype_play = 16

            def post(key_down):

                flags = 0xa00 if key_down else 0xb00

                data1 = (
                    (nx_keytype_play << 16)
                    | ((0xa if key_down else 0xb) << 8)
                )

                event = (
                    NSEvent
                    .otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
                        Quartz.NSSystemDefined,
                        (0, 0),
                        flags,
                        0,
                        0,
                        0,
                        8,
                        data1,
                        -1
                    )
                )

                Quartz.CGEventPost(
                    Quartz.kCGHIDEventTap,
                    event.CGEvent()
                )

            post(True)
            post(False)

        except Exception as e:

            print(
                f"[MEDIA ERROR] {e}"
            )

    # ---------------------------------
    # Do Not Disturb
    # ---------------------------------

    # Raw `defaults write` + `killall NotificationCenter`
    # toggling is version-fragile and deprecated on modern
    # macOS. The supported approach is running a Focus
    # toggle through the Shortcuts app — this requires the
    # user to author "Enable Do Not Disturb", "Disable Do
    # Not Disturb" and "Toggle Do Not Disturb" Shortcuts
    # once (see docs/SYSTEM_FUNCTIONS.md setup section).

    def enable_do_not_disturb(self):

        try:

            subprocess.Popen(
                ["shortcuts", "run", "Enable Do Not Disturb"]
            )

        except Exception as e:

            print(
                f"[DND ERROR] {e}"
            )

    def disable_do_not_disturb(self):

        try:

            subprocess.Popen(
                ["shortcuts", "run", "Disable Do Not Disturb"]
            )

        except Exception as e:

            print(
                f"[DND ERROR] {e}"
            )

    def toggle_do_not_disturb(self):

        try:

            subprocess.Popen(
                ["shortcuts", "run", "Toggle Do Not Disturb"]
            )

        except Exception as e:

            print(
                f"[DND ERROR] {e}"
            )

    # ---------------------------------
    # Display Sleep (Movie / Presentation)
    # ---------------------------------

    def prevent_display_sleep(self):

        try:

            self.caffeinate_process = subprocess.Popen(
                ["caffeinate", "-d"]
            )

        except Exception as e:

            print(
                f"[CAFFEINATE ERROR] {e}"
            )

    def allow_display_sleep(self):

        if self.caffeinate_process is None:
            return

        try:

            self.caffeinate_process.terminate()

        except Exception as e:

            print(
                f"[CAFFEINATE ERROR] {e}"
            )

        self.caffeinate_process = None

    # ---------------------------------
    # Slides (Presentation Mode)
    # ---------------------------------

    def next_slide(self):

        pyautogui.press("right")

    def previous_slide(self):

        pyautogui.press("left")

    # ---------------------------------
    # Quick Command Circle
    # ---------------------------------

    def lock_screen(self):

        try:

            subprocess.Popen(
                ["pmset", "displaysleepnow"]
            )

        except Exception as e:

            print(
                f"[LOCK ERROR] {e}"
            )

    def force_quit_frontmost_app(self):

        app_name = self._run_applescript(
            'tell application "System Events" to get name of '
            'first process whose frontmost is true'
        )

        if not app_name:
            return

        try:

            subprocess.Popen(
                ["killall", app_name]
            )

        except Exception as e:

            print(
                f"[FORCE QUIT ERROR] {e}"
            )
