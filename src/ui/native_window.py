# ---------------------------------
# macOS Overlay Window Setup
# ---------------------------------

# Qt's own WindowStaysOnTopHint/Tool flags only control
# ordering within the Space the window was created on — they
# say nothing to AppKit about which Spaces the window should
# belong to. CanJoinAllSpaces + FullScreenAuxiliary make the
# overlay simply live on every Space (and over full-screen
# apps) at once, so there is nothing to navigate to and
# nothing to hunt for — no Space switch, no "previous app"
# bookkeeping, no activation dance. An earlier version of this
# file tried the opposite approach (a single-Space window plus
# forcing app activation to make macOS switch to it and back)
# to avoid this file also needing FullScreenAuxiliary; that
# added real complexity (capturing/restoring the previous
# frontmost app) without ever reliably landing on the right
# Space, so it was dropped in favor of this simpler design,
# which mirrors how Flip mode's own Space switching
# (OSController.flip_next/flip_previous) stays simple by
# leaning on a single well-tested OS mechanism instead of
# fighting AppKit internals.
#
# NSWindowCollectionBehaviorStationary is deliberately NOT
# included here — Apple's own documentation states it cannot
# be combined with CanJoinAllSpaces, and an earlier version of
# this file mixed the two, which is undefined/conflicting
# behavior, not a supported combination.

def configure_overlay_window(widget):

    try:

        import objc

        from AppKit import (
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
            NSWindowCollectionBehaviorIgnoresCycle,
            NSScreenSaverWindowLevel
        )

        # winId() forces Qt to create the native NSView/
        # NSWindow immediately rather than lazily on first
        # show() — safe to call here in __init__ before the
        # widget is ever shown.
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

        # NSStatusWindowLevel (25, the menu-bar-extras level)
        # measured as still losing to some regular app
        # windows in practice. NSScreenSaverWindowLevel
        # (1000) is the level notification-banner-style HUD
        # overlays actually need — comfortably above any
        # ordinary or "floating" app window, short of
        # genuinely system-critical UI like the lock screen
        # (CGShieldingWindowLevel, far higher still). Safe to
        # go this high specifically because the overlay is
        # click-through (WindowTransparentForInput) — it can
        # never steal input from whatever it's drawn over.
        native_window.setLevel_(
            NSScreenSaverWindowLevel
        )

        # The actual root cause of the overlay "not
        # appearing" at all, confirmed empirically (checked
        # the live on-screen window list via
        # CGWindowListCopyWindowInfo): Qt.WindowType.Tool
        # backs onto an NSPanel, and NSPanel defaults
        # hidesOnDeactivate to YES — meaning AppKit removes
        # the window from the screen entirely the instant
        # this app stops being the frontmost/active
        # application. Since this app is a background daemon
        # the user is essentially never focused on (they're
        # always using whatever app they're gesturing over),
        # that default made the overlay invisible in every
        # real-world case, even though collectionBehavior/
        # level were already correct. Level/collectionBehavior
        # alone were never going to be enough.
        native_window.setHidesOnDeactivate_(
            False
        )

    except Exception as e:

        print(
            f"[NATIVE WINDOW ERROR] {e}"
        )


# ---------------------------------
# App-wide Activation Policy
# ---------------------------------

# The actual root cause of the circle spawning on its own
# empty Space, with no auto-switch to it — confirmed against
# AppKit's WindowServer behavior for an un-bundled `python3`
# process: with no Info.plist, NSApplication defaults to
# NSApplicationActivationPolicyRegular, i.e. a normal
# foreground app with a Dock icon. AppKit assigns a *regular*
# app's first on-screen window a dedicated home Space of its
# own the moment that window appears, and this happens
# independently of NSWindowCollectionBehavior — collection
# behavior (CanJoinAllSpaces etc., see configure_overlay_window
# above) only controls which Spaces a window is VISIBLE on
# once it already has a home; it does not stop AppKit from
# creating that home Space for a regular app in the first
# place. That is what both earlier approaches (single-Space +
# forced activation, then CanJoinAllSpaces alone) were still
# missing — CanJoinAllSpaces was necessary but not sufficient.
#
# NSApplicationActivationPolicyAccessory is the runtime
# equivalent of setting LSUIElement in a signed .app's
# Info.plist: it drops the Dock icon/Cmd-Tab entry and tells
# AppKit this process is a background utility. Accessory-policy
# apps are not given a dedicated Space for their windows, so a
# CanJoinAllSpaces window from an accessory app simply renders
# on whatever Space is already active — no Space to create, no
# Space to switch to or back from.
#
# Must run exactly once, on the main thread, immediately after
# QApplication is constructed and before any widget is ever
# shown — changing policy after a window already has a Space
# assigned does not retroactively move it.
def configure_accessory_app():

    try:

        from AppKit import (
            NSApplication,
            NSApplicationActivationPolicyAccessory
        )

        NSApplication.sharedApplication().setActivationPolicy_(
            NSApplicationActivationPolicyAccessory
        )

    except Exception as e:

        print(
            f"[NATIVE WINDOW ERROR] {e}"
        )
