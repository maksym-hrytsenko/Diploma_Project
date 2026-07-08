import subprocess
import time
import webbrowser

import pyautogui


class OSController:

    # Total on-screen distance (real pixels) a single Flip
    # Mode swipe scrolls, spread across many small ticks
    # with a short pause between each so it reads as a
    # smooth glide rather than one abrupt jump.
    FLIP_SCROLL_PIXELS = 90
    FLIP_SCROLL_TICKS = 18
    FLIP_SCROLL_TICK_DELAY = 0.014

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

        # This app moves the cursor continuously and on
        # purpose (Cursor mode follows the fingertip every
        # frame) — the corner-abort safety net is meant for
        # runaway scripts, not a live, hand-driven pointer,
        # and a fingertip position that happens to map to a
        # screen corner would otherwise silently cancel that
        # frame's move.
        pyautogui.FAILSAFE = False

        self._warn_if_not_trusted()

        # Tracks the caffeinate subprocess started by
        # prevent_display_sleep, so allow_display_sleep can
        # stop the right one.
        self.caffeinate_process = None

    # ---------------------------------
    # Accessibility Permission Check
    # ---------------------------------

    # Every OS-level action in this class (cursor, scroll,
    # window/app control) is a synthetic input event, which
    # macOS silently drops — no exception, nothing — unless
    # Accessibility permission is granted to whatever process
    # is actually running python. This is the single most
    # common reason "nothing happens" with no visible error,
    # so it's checked once, loudly, at startup instead of
    # leaving it to be discovered the hard way.
    def _warn_if_not_trusted(self):

        try:

            from ApplicationServices import AXIsProcessTrusted

            if not AXIsProcessTrusted():

                print(
                    "\n"
                    "==================================================\n"
                    "[ACCESSIBILITY WARNING] This process is NOT trusted "
                    "for Accessibility.\n"
                    "Cursor movement, clicks, scrolling and window "
                    "control will silently do nothing until you grant "
                    "it.\n"
                    "Fix: System Settings -> Privacy & Security -> "
                    "Accessibility -> enable the app/terminal running "
                    "this program.\n"
                    "==================================================\n"
                )

        except Exception as e:

            print(
                f"[ACCESSIBILITY CHECK ERROR] {e}"
            )

    # ---------------------------------
    # Mouse (Cursor Mode)
    # ---------------------------------

    def click(self):

        pyautogui.click()

    # Absolute move — the cursor jumps straight to the given
    # screen position, mirroring wherever the fingertip
    # currently is within the camera's view (converted to
    # screen pixels by the caller).
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

    def scroll_by(self, pixel_amount):

        self._post_pixel_scroll(pixel_amount)

    # ---------------------------------
    # Scroll (Flip Mode)
    # ---------------------------------

    def scroll_up(self):

        self._smooth_scroll(
            self.FLIP_SCROLL_PIXELS
        )

    def scroll_down(self):

        self._smooth_scroll(
            -self.FLIP_SCROLL_PIXELS
        )

    def _smooth_scroll(self, total_pixels):

        tick_pixels = total_pixels // self.FLIP_SCROLL_TICKS

        if tick_pixels == 0:
            tick_pixels = total_pixels

        for _ in range(self.FLIP_SCROLL_TICKS):

            self._post_pixel_scroll(tick_pixels)

            time.sleep(self.FLIP_SCROLL_TICK_DELAY)

    # ---------------------------------
    # Pixel-Precise Scroll (shared helper)
    # ---------------------------------

    # Uses a real, hardware-accurate pixel-unit scroll event
    # (via Quartz) instead of pyautogui's coarser "line/click"
    # scroll units — this is what makes both the Flip Mode
    # glide and the Cursor Mode drag-to-scroll move the
    # content by an actual, predictable number of pixels.
    def _post_pixel_scroll(self, pixel_amount):

        if pixel_amount == 0:
            return

        try:

            import Quartz

            event = Quartz.CGEventCreateScrollWheelEvent(
                None,
                Quartz.kCGScrollEventUnitPixel,
                1,
                pixel_amount
            )

            Quartz.CGEventPost(
                Quartz.kCGHIDEventTap,
                event
            )

        except Exception as e:

            print(
                f"[SCROLL ERROR] {e}"
            )

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
    # user to author "Enable Do Not Disturb" and "Disable
    # Do Not Disturb" Shortcuts once (see
    # docs/SYSTEM_FUNCTIONS.md setup section).

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
    # Window Management (Window Management Mode)
    # ---------------------------------

    def _get_screen_size(self):

        output = self._run_applescript(
            'tell application "Finder" to get bounds of window of desktop'
        )

        if output is None:
            return None

        parts = [
            int(value.strip())
            for value in output.split(",")
        ]

        return parts[2], parts[3]

    def _set_frontmost_window_bounds(
        self,
        x,
        y,
        width,
        height
    ):

        script = (
            'tell application "System Events"\n'
            'set frontApp to first process whose frontmost is true\n'
            'tell (first window of frontApp)\n'
            f'set position to {{{x}, {y}}}\n'
            f'set size to {{{width}, {height}}}\n'
            'end tell\n'
            'end tell'
        )

        self._run_applescript(script)

    def maximize_window(self):

        screen_size = self._get_screen_size()

        if screen_size is None:
            return

        width, height = screen_size

        self._set_frontmost_window_bounds(
            0,
            0,
            width,
            height
        )

    def minimize_window(self):

        # True AppleScript minimize-to-Dock is unreliable
        # across apps; hiding the frontmost app achieves
        # the same practical "get it out of the way" result.
        self._run_applescript(
            'tell application "System Events" to set visible of '
            '(first process whose frontmost is true) to false'
        )

    def move_window_left(self):

        screen_size = self._get_screen_size()

        if screen_size is None:
            return

        width, height = screen_size

        self._set_frontmost_window_bounds(
            0,
            0,
            width // 2,
            height
        )

    def move_window_right(self):

        screen_size = self._get_screen_size()

        if screen_size is None:
            return

        width, height = screen_size

        self._set_frontmost_window_bounds(
            width // 2,
            0,
            width // 2,
            height
        )
