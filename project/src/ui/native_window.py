"""macOS-specific window behavior for overlay widgets (PointerOverlay,
QuickCommandOverlay) and the app's own Dock/activation policy.
"""

from utils.logger import get_logger


logger = get_logger(__name__)


# Qt's WindowStaysOnTopHint/Tool flags only control ordering within the
# Space a window was created on; they say nothing to AppKit about which
# Spaces it belongs to. CanJoinAllSpaces + FullScreenAuxiliary make the
# overlay live on every Space (and over full-screen apps) at once, so
# there is no Space to switch to or from. An earlier version instead used
# a single-Space window plus forced app activation to make macOS switch to
# it and back; that added real complexity (capturing/restoring the
# previous frontmost app) without reliably landing on the right Space, so
# it was dropped for this simpler design.
#
# NSWindowCollectionBehaviorStationary is deliberately NOT included —
# Apple's documentation states it cannot be combined with
# CanJoinAllSpaces, and an earlier version mixed the two, which is
# undefined/conflicting behavior, not a supported combination.
def configure_overlay_window(widget):

    try:

        import objc

        from AppKit import (
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
            NSWindowCollectionBehaviorIgnoresCycle,
            NSScreenSaverWindowLevel
        )

        # winId() forces Qt to create the native NSView/NSWindow
        # immediately rather than lazily on first show() — safe to call
        # here in __init__ before the widget is ever shown.
        native_view = objc.objc_object(
            c_void_p=int(widget.winId())
        )

        native_window = native_view.window()

        if native_window is None:
            return

        collection_behavior = (
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorIgnoresCycle
        )

        native_window.setCollectionBehavior_(
            collection_behavior
        )

        # NSStatusWindowLevel (25, the menu-bar-extras level) measured as
        # still losing to some regular app windows in practice.
        # NSScreenSaverWindowLevel (1000) is the level notification-
        # banner-style HUD overlays need — comfortably above any ordinary
        # or "floating" app window. Safe to go this high specifically
        # because the overlay is click-through (WindowTransparentForInput).
        native_window.setLevel_(
            NSScreenSaverWindowLevel
        )

        # Root cause of the overlay "not appearing" at all, confirmed via
        # CGWindowListCopyWindowInfo: Qt.WindowType.Tool backs onto an
        # NSPanel, and NSPanel defaults hidesOnDeactivate to YES — AppKit
        # removes the window from the screen the instant this app stops
        # being frontmost. Since this app is a background daemon the user
        # is essentially never focused on, that default made the overlay
        # invisible in every real-world case even with a correct
        # collectionBehavior/level.
        native_window.setHidesOnDeactivate_(
            False
        )

        # Root cause of a presentation losing keyboard focus (and its
        # slide-switching hotkeys going nowhere) the moment Cursor mode's
        # real, hand-driven pointer clicks anywhere near one of these
        # overlays — FloatingStatusBar sits pinned to a fixed corner of the
        # primary screen and stays on top of every Space, including a
        # full-screen presentation app's own Space, by design (see the
        # collectionBehavior above). Without this, a single AppKit click on
        # its expand button makes this window key and activates this
        # process, which un-frontmosts the presentation app; the reported
        # symptom ("need one click back on the presentation to restore
        # slide-switching") is exactly that recovery step. With
        # becomesKeyOnlyIfNeeded, an ordinary button click is still
        # delivered to the view without the window ever claiming key
        # status, so this app never activates and the presentation stays
        # frontmost throughout.
        native_window.setBecomesKeyOnlyIfNeeded_(
            True
        )

    except Exception:

        logger.exception(
            "Native window configuration failed"
        )


# Root cause of the quick-circle overlay spawning on its own empty Space
# with no auto-switch, confirmed against AppKit's WindowServer behavior for
# an un-bundled `python3` process: with no Info.plist, NSApplication
# defaults to NSApplicationActivationPolicyRegular, and AppKit assigns a
# *regular* app's first on-screen window a dedicated home Space the moment
# it appears — independently of NSWindowCollectionBehavior, which only
# controls which Spaces a window is visible on once it already has a home.
# CanJoinAllSpaces alone was necessary but not sufficient.
#
# NSApplicationActivationPolicyAccessory is the runtime equivalent of
# LSUIElement in a signed .app's Info.plist: it drops the Dock icon/
# Cmd-Tab entry and tells AppKit this is a background utility.
# Accessory-policy apps aren't given a dedicated Space for their windows,
# so a CanJoinAllSpaces window from one simply renders on whatever Space
# is already active.
#
# Must run exactly once, on the main thread, immediately after
# QApplication is constructed and before any widget is shown — changing
# policy after a window already has a Space assigned doesn't move it.
def configure_accessory_app():

    try:

        from AppKit import (
            NSApplication,
            NSApplicationActivationPolicyAccessory
        )

        NSApplication.sharedApplication().setActivationPolicy_(
            NSApplicationActivationPolicyAccessory
        )

    except Exception:

        logger.exception(
            "Native window configuration failed"
        )
