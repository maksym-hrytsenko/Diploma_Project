"""macOS system-action backend.

Translates high-level commands from ActionExecutor into concrete OS effects:
synthetic input (pyautogui/Quartz), app/URL launches, and Shortcuts/AppleScript
calls. Contains no decision logic — it only executes what it is told.
"""

import subprocess
import time
import webbrowser

import pyautogui

from config.config_loader import load_system_config


class OSController:

    # NSSystemDefined event data1 high byte — the codes a physical keyboard's
    # media keys send. Used for volume only; play/pause/next/previous use
    # MediaRemote instead (see MEDIA_REMOTE_BUNDLE_PATH below).
    NX_KEYTYPE_SOUND_UP = 0
    NX_KEYTYPE_SOUND_DOWN = 1

    # MediaRemote.framework is private but is the same command path macOS
    # uses for Control Center's Now Playing widget and AVRCP headphone
    # buttons. Used instead of NX_KEYTYPE HID media-key events because the
    # HID path silently reached no app on at least one dev machine — see
    # tests/mediaremote_standalone_test.py.
    MEDIA_REMOTE_BUNDLE_PATH = (
        "/System/Library/PrivateFrameworks/MediaRemote.framework"
    )

    MR_COMMAND_TOGGLE_PLAY_PAUSE = 2
    MR_COMMAND_NEXT_TRACK = 4
    MR_COMMAND_PREVIOUS_TRACK = 5

    def __init__(self):

        config = load_system_config().get(
            "os_controller",
            {}
        )

        flip_scroll_config = config.get(
            "flip_scroll",
            {}
        )

        # Total on-screen distance (pixels) a single Flip Mode swipe scrolls,
        # spread across many small ticks with a pause between each so it
        # reads as a smooth glide rather than one abrupt jump.
        self.FLIP_SCROLL_PIXELS = flip_scroll_config.get(
            "pixels",
            500
        )

        self.FLIP_SCROLL_TICKS = flip_scroll_config.get(
            "ticks",
            18
        )

        self.FLIP_SCROLL_TICK_DELAY = flip_scroll_config.get(
            "tick_delay",
            0.014
        )

        # Hotkeys, app names/URLs and Shortcuts names are user-tunable via
        # the "os_controller" section of config/system.json; each getter
        # below falls back to a hardcoded default if unset.
        self.hotkeys = config.get(
            "hotkeys",
            {}
        )

        self.urls = config.get(
            "urls",
            {}
        )

        self.apps = config.get(
            "apps",
            {}
        )

        self.shortcuts = config.get(
            "shortcuts",
            {}
        )

        # Each entry is a list of tab-groups: one new Chrome window per inner
        # list, first URL opening the window and the rest joining as tabs.
        self.window_groups = config.get(
            "window_groups",
            {}
        )

        # Cursor mode moves the pointer continuously on purpose; the
        # corner-abort safety net is meant for runaway scripts, not a live,
        # hand-driven pointer that may legitimately pass through a corner.
        pyautogui.FAILSAFE = False

        # pyautogui's default 0.1s PAUSE after every call would cap Cursor
        # mode's per-frame moveTo() to ~10fps.
        pyautogui.PAUSE = 0

        self._warn_if_not_trusted()

        self.caffeinate_process = None

        # Cached MRMediaRemoteSendCommand pointer; loading the private
        # framework bundle is only needed once.
        self.media_remote_send_command = None

    # Every OS-level action in this class is a synthetic input event, which
    # macOS silently drops unless Accessibility permission is granted to the
    # process running python — this is the most common cause of "nothing
    # happens" with no error, so it's surfaced loudly at startup.
    def _warn_if_not_trusted(self) -> None:

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

    # Hotkeys are stored as a list of key names, even for a single key like
    # "f5", so pyautogui.hotkey(*keys) can handle every combo uniformly.
    def _send_hotkey(self, name: str, default: list[str]) -> None:

        keys = self.hotkeys.get(
            name,
            default
        )

        pyautogui.hotkey(*keys)

    def _app_name(self, name: str, default: str) -> str:

        return self.apps.get(
            name,
            default
        )

    def click(self) -> None:

        pyautogui.click()

    def right_click(self) -> None:

        pyautogui.rightClick()

    def move_cursor_to(self, x_pixels: int, y_pixels: int) -> None:

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

    def scroll_by(self, pixel_amount_x: int, pixel_amount_y: int) -> None:

        self._post_pixel_scroll(
            pixel_amount_y,
            pixel_amount_x
        )

    # Cmd+"="/Cmd+"-" is the standard zoom shortcut across Safari, Preview,
    # Photos and most macOS apps; there is no system-wide "zoom the
    # frontmost app's content" API to call instead.
    def zoom_in(self) -> None:

        self._send_hotkey(
            "zoom_in",
            ["command", "="]
        )

    def zoom_out(self) -> None:

        self._send_hotkey(
            "zoom_out",
            ["command", "-"]
        )

    def scroll_up(self) -> None:

        self._smooth_scroll(
            self.FLIP_SCROLL_PIXELS
        )

    def scroll_down(self) -> None:

        self._smooth_scroll(
            -self.FLIP_SCROLL_PIXELS
        )

    def _smooth_scroll(self, total_pixels: int) -> None:

        tick_pixels = total_pixels // self.FLIP_SCROLL_TICKS

        if tick_pixels == 0:
            tick_pixels = total_pixels

        for _ in range(self.FLIP_SCROLL_TICKS):

            self._post_pixel_scroll(tick_pixels)

            time.sleep(self.FLIP_SCROLL_TICK_DELAY)

    # Uses a hardware-accurate pixel-unit scroll event (via Quartz) instead
    # of pyautogui's coarser line/click units, so both Flip Mode's glide and
    # Cursor Mode's drag-to-scroll move content by a predictable pixel amount.
    def _post_pixel_scroll(self, pixel_amount_y: int, pixel_amount_x: int = 0) -> None:

        if pixel_amount_y == 0 and pixel_amount_x == 0:
            return

        try:

            import Quartz

            # wheelCount=2 makes Quartz read a second (horizontal) wheel
            # delta alongside the vertical one.
            event = Quartz.CGEventCreateScrollWheelEvent(
                None,
                Quartz.kCGScrollEventUnitPixel,
                2,
                pixel_amount_y,
                pixel_amount_x
            )

            Quartz.CGEventPost(
                Quartz.kCGHIDEventTap,
                event
            )

        except Exception as e:

            print(
                f"[SCROLL ERROR] {e}"
            )

    # Always switches macOS Spaces rather than guessing whether the
    # frontmost app has its own next/previous navigation — a prior per-app
    # heuristic was removed so Flip Mode swipes behave the same way in
    # every app.
    def flip_next(self) -> None:

        self._send_hotkey(
            "flip_next",
            ["ctrl", "right"]
        )

    def flip_previous(self) -> None:

        self._send_hotkey(
            "flip_previous",
            ["ctrl", "left"]
        )

    def _open_mac_app(self, app_name: str) -> None:

        try:

            subprocess.Popen(
                ["open", "-a", app_name]
            )

        except Exception as e:

            print(
                f"[APPLICATION ERROR] {app_name}: {e}"
            )

    def open_vscode(self) -> None:

        try:

            subprocess.Popen(
                ["code"]
            )

        except Exception as e:

            print(
                f"[VSCODE ERROR] {e}"
            )

    def open_terminal(self) -> None:

        self._open_mac_app(
            self._app_name("terminal", "Terminal")
        )

    def open_safari(self) -> None:

        self._open_mac_app(
            self._app_name("safari", "Safari")
        )

    def open_chrome(self) -> None:

        self._open_mac_app(
            self._app_name("chrome", "Google Chrome")
        )

    def open_spotify(self) -> None:

        self._open_mac_app(
            self._app_name("spotify", "Spotify")
        )

    def open_slack(self) -> None:

        self._open_mac_app(
            self._app_name("slack", "Slack")
        )

    def open_discord(self) -> None:

        self._open_mac_app(
            self._app_name("discord", "Discord")
        )

    def open_mail(self) -> None:

        self._open_mac_app(
            self._app_name("mail", "Mail")
        )

    def open_calendar(self) -> None:

        self._open_mac_app(
            self._app_name("calendar", "Calendar")
        )

    def open_notes(self) -> None:

        self._open_mac_app(
            self._app_name("notes", "Notes")
        )

    def open_telegram(self) -> None:

        self._open_mac_app(
            self._app_name("telegram", "Telegram")
        )

    def open_finder(self) -> None:

        self._open_mac_app(
            self._app_name("finder", "Finder")
        )

    def open_notion(self) -> None:

        self._open_mac_app(
            self._app_name("notion", "Notion")
        )

    def open_photos(self) -> None:

        self._open_mac_app(
            self._app_name("photos", "Photos")
        )

    def open_preview(self) -> None:

        self._open_mac_app(
            self._app_name("preview", "Preview")
        )

    def open_settings(self) -> None:

        self._open_mac_app(
            self._app_name("settings", "System Settings")
        )

    def open_tv(self) -> None:

        self._open_mac_app(
            self._app_name("tv", "TV")
        )

    def open_news(self) -> None:

        self._open_mac_app(
            self._app_name("news", "News")
        )

    def open_website(self, url: str) -> None:

        webbrowser.open(url)

    def open_browser(self) -> None:

        webbrowser.open(
            self.urls.get(
                "browser",
                "https://google.com"
            )
        )

    def open_chatgpt(self) -> None:

        webbrowser.open(
            self.urls.get(
                "chatgpt",
                "https://chatgpt.com"
            )
        )

    def open_github(self) -> None:

        webbrowser.open(
            self.urls.get(
                "github",
                "https://github.com"
            )
        )

    def open_netflix(self) -> None:

        webbrowser.open(
            self.urls.get(
                "netflix",
                "https://www.netflix.com"
            )
        )

    # A window group is a list of tab-groups: each inner list becomes one
    # Chrome window, its first URL opening the window and the rest joining
    # it as tabs.
    def open_window_group(self, group_name: str) -> None:

        for tab_urls in self.window_groups.get(
            group_name,
            []
        ):

            if not tab_urls:
                continue

            self._open_chrome_new_window(
                tab_urls[0]
            )

            time.sleep(1)

            for url in tab_urls[1:]:
                self._open_chrome_tab(url)

    def _open_chrome_new_window(self, url: str) -> None:

        try:

            subprocess.Popen(
                [
                    "open", "-na",
                    self._app_name("chrome", "Google Chrome"),
                    "--args", "--new-window", url
                ]
            )

        except Exception as e:

            print(
                f"[CHROME WINDOW ERROR] {url}: {e}"
            )

    def _open_chrome_tab(self, url: str) -> None:

        try:

            subprocess.Popen(
                [
                    "open", "-a",
                    self._app_name("chrome", "Google Chrome"),
                    url
                ]
            )

        except Exception as e:

            print(
                f"[CHROME TAB ERROR] {url}: {e}"
            )

    def open_job_search_windows(self) -> None:

        self.open_window_group(
            "job_search"
        )

    def open_study_windows(self) -> None:

        self.open_window_group(
            "study"
        )

    def open_news_tabs(self) -> None:

        self.open_window_group(
            "news"
        )

    def play_focus_music(self) -> None:

        try:

            app_name = self._app_name(
                "spotify",
                "Spotify"
            )

            subprocess.Popen(
                [
                    "osascript",
                    "-e",
                    f'tell application "{app_name}" to play'
                ]
            )

        except Exception as e:

            print(
                f"[MUSIC ERROR] {e}"
            )

    def pause_focus_music(self) -> None:

        try:

            app_name = self._app_name(
                "spotify",
                "Spotify"
            )

            subprocess.Popen(
                [
                    "osascript",
                    "-e",
                    f'tell application "{app_name}" to pause'
                ]
            )

        except Exception as e:

            print(
                f"[MUSIC ERROR] {e}"
            )

    # This is a single toggle command, not separate play/pause commands —
    # sending it while already paused resumes playback. Accepted limitation,
    # see docs/SYSTEM_FUNCTIONS.md.
    def media_play_pause(self) -> None:

        self._post_media_remote_command(
            self.MR_COMMAND_TOGGLE_PLAY_PAUSE
        )

    def next_track(self) -> None:

        self._post_media_remote_command(
            self.MR_COMMAND_NEXT_TRACK
        )

    def previous_track(self) -> None:

        self._post_media_remote_command(
            self.MR_COMMAND_PREVIOUS_TRACK
        )

    # Unlike the MediaRemote calls above, volume is handled directly by
    # CoreAudio and doesn't depend on any app owning "Now Playing". Each
    # call is one hardware "tick" (~6.25% of full range), matching a single
    # gesture to a single discrete step rather than a continuous ramp.
    def volume_up(self) -> None:

        self._post_system_media_key(
            self.NX_KEYTYPE_SOUND_UP
        )

    def volume_down(self) -> None:

        self._post_system_media_key(
            self.NX_KEYTYPE_SOUND_DOWN
        )

    def _post_system_media_key(self, nx_keytype: int) -> None:

        try:

            from AppKit import NSEvent
            import Quartz

            def post(key_down: bool) -> None:

                flags = 0xa00 if key_down else 0xb00

                data1 = (
                    (nx_keytype << 16)
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

    def _post_media_remote_command(self, command: int) -> None:

        try:

            send_command = self._load_media_remote_send_command()

            send_command(
                command,
                None
            )

        except Exception as e:

            print(
                f"[MEDIA ERROR] {e}"
            )

    def _load_media_remote_send_command(self):

        if self.media_remote_send_command is not None:
            return self.media_remote_send_command

        import objc
        from Foundation import NSBundle

        bundle = NSBundle.bundleWithPath_(
            self.MEDIA_REMOTE_BUNDLE_PATH
        )

        namespace = {}

        objc.loadBundleFunctions(
            bundle,
            namespace,
            [
                ("MRMediaRemoteSendCommand", b"Bi@")
            ]
        )

        self.media_remote_send_command = namespace[
            "MRMediaRemoteSendCommand"
        ]

        return self.media_remote_send_command

    # Raw `defaults write` + `killall NotificationCenter` toggling is
    # version-fragile and deprecated; the supported approach is running a
    # Focus toggle through the Shortcuts app (user must author the two
    # Shortcuts once — see docs/SYSTEM_FUNCTIONS.md setup section).
    def enable_do_not_disturb(self) -> None:

        try:

            shortcut_name = self.shortcuts.get(
                "enable_dnd",
                "Enable Do Not Disturb"
            )

            subprocess.Popen(
                ["shortcuts", "run", shortcut_name]
            )

        except Exception as e:

            print(
                f"[DND ERROR] {e}"
            )

    def disable_do_not_disturb(self) -> None:

        try:

            shortcut_name = self.shortcuts.get(
                "disable_dnd",
                "Disable Do Not Disturb"
            )

            subprocess.Popen(
                ["shortcuts", "run", shortcut_name]
            )

        except Exception as e:

            print(
                f"[DND ERROR] {e}"
            )

    # Runs a user-authored Shortcuts automation that controls the Magic
    # Home smart lights; there is no direct Magic Home API call here.
    def run_cinema_mode(self) -> None:

        try:

            shortcut_name = self.shortcuts.get(
                "cinema_mode",
                "Turn on cinema mode"
            )

            subprocess.Popen(
                ["shortcuts", "run", shortcut_name]
            )

        except Exception as e:

            print(
                f"[CINEMA MODE ERROR] {e}"
            )

    def prevent_display_sleep(self) -> None:

        try:

            self.caffeinate_process = subprocess.Popen(
                ["caffeinate", "-d"]
            )

        except Exception as e:

            print(
                f"[CAFFEINATE ERROR] {e}"
            )

    def allow_display_sleep(self) -> None:

        if self.caffeinate_process is None:
            return

        try:

            self.caffeinate_process.terminate()

        except Exception as e:

            print(
                f"[CAFFEINATE ERROR] {e}"
            )

        self.caffeinate_process = None

    # F5 is PowerPoint/Keynote's own "start from the beginning" shortcut;
    # entering Presentation mode only arms next/previous-slide mapping,
    # it does not start the slideshow itself.
    def start_slideshow(self) -> None:

        self._send_hotkey(
            "start_slideshow",
            ["f5"]
        )

    def next_slide(self) -> None:

        self._send_hotkey(
            "next_slide",
            ["right"]
        )

    def previous_slide(self) -> None:

        self._send_hotkey(
            "previous_slide",
            ["left"]
        )

    # Teams for Mac's own meeting-control shortcuts, sent as real
    # keystrokes; there is no app-agnostic "mute the current call" API.
    # Microsoft has changed these bindings before — re-verify against
    # Teams' Settings -> Keyboard shortcuts if they stop firing. Each is a
    # single toggle: firing it while already in the target state flips it
    # back rather than no-op'ing (see GestureRecognizer.locked_toggle_gestures
    # for how a gesture is kept from firing twice in a row).
    def toggle_mic(self) -> None:

        self._send_hotkey(
            "toggle_mic",
            ["command", "shift", "m"]
        )

    def toggle_camera(self) -> None:

        self._send_hotkey(
            "toggle_camera",
            ["command", "shift", "o"]
        )

    # Teams exposes no shortcut for muting the call's own incoming audio,
    # so this toggles the Mac's system-wide output mute instead, silencing
    # everything, not just the call.
    def toggle_call_audio(self) -> None:

        try:

            subprocess.run(
                [
                    "osascript",
                    "-e",
                    "set volume output muted "
                    "(not (output muted of (get volume settings)))"
                ],
                check=True
            )

        except Exception as e:

            print(
                f"[CALL AUDIO ERROR] {e}"
            )

    def toggle_background_blur(self) -> None:

        self._send_hotkey(
            "toggle_background_blur",
            ["command", "shift", "p"]
        )

    # macOS's built-in full-screen capture shortcut, not the interactive
    # region-select (Cmd+Shift+4), so it needs no follow-up mouse drag.
    def take_screenshot(self) -> None:

        self._send_hotkey(
            "take_screenshot",
            ["command", "shift", "3"]
        )
