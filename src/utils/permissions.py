"""macOS permission pre-flight helpers.

Accessibility is what lets OSController's synthetic input (pyautogui/Quartz)
actually move the cursor or send clicks/keystrokes — without it, those calls
succeed but have no visible effect anywhere on screen. Checking this before
any pipeline object is constructed means the user sees one clear prompt up
front instead of a silently inert app.

Camera access fails in a sharper way than merely doing nothing: opening a
cv2.VideoCapture before the user has answered the system's camera prompt
leaves that particular AVFoundation capture session permanently silent (no
frames ever arrive) even after they click Allow — recovering needs a brand
new VideoCapture instance. ensure_camera_permission() waits for the
decision before CameraInput ever opens the device, so that broken session
never gets created in the first place. See CameraInput._run.
"""

import threading

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


# AVAuthorizationStatus (AVFoundation) values — pyobjc doesn't expose these
# as named constants, so they're mirrored here from Apple's enum.
_AV_AUTHORIZATION_NOT_DETERMINED = 0
_AV_AUTHORIZATION_AUTHORIZED = 3

# How long to wait for the user to answer the system's camera prompt
# before giving up and letting CameraInput try to open the device anyway.
# Generous on purpose: this runs on CameraInput's own background thread
# (see CameraInput._run), never blocking the UI, so there is little cost
# to waiting out even a slow response.
CAMERA_AUTHORIZATION_TIMEOUT_SECONDS = 120.0


# Call from CameraInput's capture thread, before the first cv2.VideoCapture
# of the process is opened — see the module docstring for why a capture
# session opened ahead of this decision can never recover on its own.
def ensure_camera_permission() -> None:

    try:

        from AVFoundation import (
            AVCaptureDevice,
            AVMediaTypeVideo
        )

    except Exception:

        logger.exception(
            "Camera permission pre-flight failed"
        )

        return

    status = AVCaptureDevice.authorizationStatusForMediaType_(
        AVMediaTypeVideo
    )

    # Already decided (Allow or Deny, this run or a previous one) — the
    # capture device below can be opened right away either way; if it was
    # denied, cv2.VideoCapture will simply fail to open.
    if status != _AV_AUTHORIZATION_NOT_DETERMINED:

        if status != _AV_AUTHORIZATION_AUTHORIZED:

            logger.warning(
                "Camera permission not granted. Fix: System Settings -> "
                "Privacy & Security -> Camera -> enable this app."
            )

        return

    # Not yet asked — trigger the system prompt and block THIS thread
    # (not the Qt main thread) until the user answers, so the capture
    # device is only ever opened once the decision has actually landed.
    decided = threading.Event()

    def _on_decided(granted):

        decided.set()

    AVCaptureDevice.requestAccessForMediaType_completionHandler_(
        AVMediaTypeVideo,
        _on_decided
    )

    if not decided.wait(timeout=CAMERA_AUTHORIZATION_TIMEOUT_SECONDS):

        logger.warning(
            "Camera permission prompt not answered within %.0fs, "
            "continuing anyway",
            CAMERA_AUTHORIZATION_TIMEOUT_SECONDS
        )
