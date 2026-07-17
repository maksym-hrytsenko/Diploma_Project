"""macOS Accessibility permission pre-flight, run once at startup.

Accessibility is what lets OSController's synthetic input (pyautogui/Quartz)
actually move the cursor or send clicks/keystrokes — without it, those calls
succeed but have no visible effect anywhere on screen. Checking this before
any pipeline object is constructed means the user sees one clear prompt up
front instead of a silently inert app.
"""

from utils.logger import get_logger


logger = get_logger(__name__)


# kAXTrustedCheckOptionPrompt=True both checks trust status AND, if not yet
# trusted, adds the app to System Settings -> Privacy & Security ->
# Accessibility (unchecked) and shows the system's own prompt to open that
# pane — the same mechanism AXIsProcessTrusted() alone (used by
# OSController._warn_if_not_trusted as a second, deeper check) does not
# trigger on its own.
def ensure_macos_permissions() -> None:

    try:

        from ApplicationServices import (
            AXIsProcessTrustedWithOptions
        )

        from CoreFoundation import (
            CFDictionaryCreate,
            kCFTypeDictionaryKeyCallBacks,
            kCFTypeDictionaryValueCallBacks
        )

        prompt_key = "AXTrustedCheckOptionPrompt"

        options = CFDictionaryCreate(
            None,
            [prompt_key],
            [True],
            1,
            kCFTypeDictionaryKeyCallBacks,
            kCFTypeDictionaryValueCallBacks
        )

        trusted = AXIsProcessTrustedWithOptions(
            options
        )

        if not trusted:

            logger.warning(
                "Accessibility permission not yet granted. Cursor "
                "movement, clicks, scrolling and window control will do "
                "nothing until it is. Fix: System Settings -> Privacy & "
                "Security -> Accessibility -> enable this app."
            )

        # Input Monitoring (keyboard listening via pynput) has no public
        # "ask now" API — macOS only prompts for it the first time a
        # CGEventTap/pynput listener is actually created, with no way for
        # app code to trigger that check ahead of time. If keyboard-driven
        # commands don't register, point the user at System Settings ->
        # Privacy & Security -> Input Monitoring.

    except Exception:

        logger.exception(
            "Accessibility permission pre-flight failed"
        )
