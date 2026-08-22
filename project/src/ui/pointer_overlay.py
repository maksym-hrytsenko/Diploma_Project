"""Click-through laser-pointer overlay, active outside Cursor mode.

Two frameless, always-on-top, input-transparent QWidgets that each draw a
dot at the fingertip position published as pointer_position: one on
whichever screen isn't the presenter's primary display (the audience-facing
"big screen"), and — only when configured, see primary_preview below — a
second, smaller one pinned over wherever on the primary screen the
presentation software renders its own current-slide preview/thumbnail
(e.g. Keynote/PowerPoint Presenter Display), so the presenter sees the same
dot there too instead of only on the screen the audience watches.

By design, this is not scoped to Presentation mode specifically — it is
the default, mode-agnostic visual for wherever `Pointing_Up` is tracking,
including with no mode active at all. `Pointing_Up` always publishes
pointer_position (see GestureRecognizer._update_pointer); ActionExecutor.
_handle_pointer is what decides where that position goes — the real OS
cursor in Cursor mode, this overlay dot in every other case, no mode
included. So seeing the dot with no mode selected is expected, not a bug:
it is confirmation that a position is being tracked and is one hand-raise
away from being usable, in whichever mode gets entered next.

ActionExecutor never holds a reference to this class directly — it only
publishes pointer_overlay_update on the shared EventBus, keeping the
UI layer reachable exclusively through EventBus like every other module.
"""

from PyQt6.QtCore import (
    QObject,
    Qt,
    QRect,
    QTimer,
    pyqtSignal
)

from PyQt6.QtGui import (
    QGuiApplication,
    QPainter,
    QColor
)

from PyQt6.QtWidgets import QWidget

from ui.native_window import configure_overlay_window

from config.config_loader import load_system_config
from utils.logger import get_logger


logger = get_logger(__name__)


# One click-through, non-activating dot-drawing window. PointerOverlay owns
# one or two of these (see PointerOverlay.__init__) — this class knows
# nothing about screen selection or config, only how to sit at a fixed
# geometry and draw a dot at a fraction of its own width/height.
class _PointerDotWidget(QWidget):

    def __init__(self, dot_radius, dot_color, geometry):

        super().__init__()

        self.DOT_RADIUS = dot_radius
        self.DOT_COLOR = dot_color

        self.dot_x = None
        self.dot_y = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating
        )

        self.setGeometry(
            geometry
        )

        # Must run after every setWindowFlags/setAttribute/setGeometry call
        # above — Qt may rebuild the native NSWindow when those change,
        # silently discarding whatever collectionBehavior/level was set on
        # the old one. Without this, the overlay's window has no
        # CanJoinAllSpaces/FullScreenAuxiliary behavior, so showing it while
        # a presentation app is full-screen forces macOS to switch away
        # from the presentation's own Space to display it — surfacing as
        # the presentation losing focus the moment the pointer dot appears.
        configure_overlay_window(self)

    def set_dot_fraction(self, fraction_x, fraction_y):

        self.dot_x = int(
            fraction_x * self.width()
        )

        self.dot_y = int(
            fraction_y * self.height()
        )

        self.show()

        # WindowStaysOnTopHint alone does not always keep a frameless
        # window in front of everything else on macOS — raise_() forces
        # it to the front of the window stack.
        self.raise_()

        self.update()

    def paintEvent(self, event):

        if self.dot_x is None or self.dot_y is None:
            return

        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        painter.setBrush(
            self.DOT_COLOR
        )

        painter.setPen(
            Qt.PenStyle.NoPen
        )

        painter.drawEllipse(
            self.dot_x - self.DOT_RADIUS,
            self.dot_y - self.DOT_RADIUS,
            self.DOT_RADIUS * 2,
            self.DOT_RADIUS * 2
        )


class PointerOverlay(QObject):

    # Emitted from whichever thread calls update_position() — typically
    # the camera capture thread, since EventBus.publish() dispatches
    # subscriber callbacks synchronously on the publishing thread. Qt
    # automatically queues delivery of a connected slot onto the thread
    # that owns this QObject (the main/GUI thread), so this is the
    # cross-thread-safe way to reach the QWidget dots from here.
    position_updated = pyqtSignal(float, float)

    def __init__(self, event_bus):

        super().__init__()

        self.event_bus = event_bus

        config = load_system_config().get(
            "ui",
            {}
        ).get(
            "pointer_overlay",
            {}
        )

        self.HIDE_AFTER_MS = config.get(
            "hide_after_ms",
            200
        )

        dot_radius = config.get(
            "dot_radius",
            10
        )

        dot_color = QColor(
            *config.get(
                "dot_color",
                [255, 0, 0, 220]
            )
        )

        # Camera frames are never flipped upstream, so raw MediaPipe x=0
        # is the user's right side as seen from behind the camera.
        # Mirroring here makes the dot move the same direction as the
        # user's hand from their own point of view.
        self.MIRROR_X = config.get(
            "mirror_x",
            True
        )

        self.presentation_dot = _PointerDotWidget(
            dot_radius,
            dot_color,
            self._select_presentation_screen().geometry()
        )

        # Mirrors the same dot onto a fixed rectangle of the PRIMARY screen
        # — meant to line up with wherever the presentation software (e.g.
        # Keynote/PowerPoint Presenter Display) draws its own current-slide
        # preview, so the presenter sees the pointer there too, not only on
        # the audience-facing screen above. There is no way to detect that
        # rectangle automatically — it depends entirely on which
        # presentation app is used and how its presenter view is laid out
        # — so it is off by default; set primary_preview.enabled plus its
        # x/y/width/height_fraction (0-1, relative to the primary screen's
        # own width/height) in config/system.json to match your own setup.
        # Fractions, not pixels, so the same config keeps lining up
        # regardless of the primary screen's resolution or Retina scale
        # factor.
        primary_preview_config = config.get(
            "primary_preview",
            {}
        )

        self.preview_dot = None

        if primary_preview_config.get(
            "enabled",
            False
        ):

            primary_geometry = QGuiApplication.primaryScreen().geometry()

            self.preview_dot = _PointerDotWidget(
                dot_radius,
                dot_color,
                QRect(
                    primary_geometry.x() + round(
                        primary_preview_config.get("x_fraction", 0.0)
                        * primary_geometry.width()
                    ),
                    primary_geometry.y() + round(
                        primary_preview_config.get("y_fraction", 0.0)
                        * primary_geometry.height()
                    ),
                    round(
                        primary_preview_config.get("width_fraction", 0.5)
                        * primary_geometry.width()
                    ),
                    round(
                        primary_preview_config.get("height_fraction", 0.5)
                        * primary_geometry.height()
                    )
                )
            )

        self.position_updated.connect(
            self._on_position_updated
        )

        # Whichever app was frontmost right before the dot(s) first appear
        # for a given pointing gesture — captured once per gesture (see
        # _on_position_updated) and re-activated once the dot(s) hide (see
        # _hide_dots). Even with every overlay window here already
        # non-activating and click-through, showing them still observably
        # drops the presentation app's own key/frontmost status on macOS;
        # this restores it explicitly instead of relying on AppKit to
        # leave it alone.
        self._app_to_restore = None

        self.hide_timer = QTimer()

        self.hide_timer.setSingleShot(True)

        self.hide_timer.timeout.connect(
            self._hide_dots
        )

    def start(self):

        self.event_bus.subscribe(
            "pointer_overlay_update",
            self._handle_update_event
        )

    def stop(self):

        self.event_bus.unsubscribe(
            "pointer_overlay_update",
            self._handle_update_event
        )

    def _handle_update_event(self, event):

        data = event.get(
            "data",
            {}
        )

        x = data.get("x")
        y = data.get("y")

        if x is None or y is None:
            return

        self.update_position(
            x,
            y
        )

    # Presenting is normally done with a projector/external display as a
    # SECOND screen showing the slides to the audience, while the primary
    # screen stays with the presenter's own view/notes. The overlay
    # targets the first non-primary screen it finds, falling back to the
    # primary when only one is connected. Selected once at construction —
    # hot-plugging a projector mid-session needs a restart to be picked up.
    def _select_presentation_screen(self):

        primary_screen = QGuiApplication.primaryScreen()

        for screen in QGuiApplication.screens():

            if screen != primary_screen:
                return screen

        return primary_screen

    # Named update_position, not update, to avoid colliding with
    # QWidget's own built-in update() repaint method. Safe to call from
    # any thread — only emits position_updated, see that signal's comment.
    def update_position(self, normalized_x, normalized_y):

        self.position_updated.emit(
            normalized_x,
            normalized_y
        )

    def _on_position_updated(self, normalized_x, normalized_y):

        # Only capture on the first update of a new gesture (dots were
        # hidden, i.e. nothing queued to restore yet) — later updates in
        # the same continuous point would otherwise overwrite the captured
        # app with whatever is frontmost by then, which may by now be this
        # process itself (exactly the bug being worked around here).
        if self._app_to_restore is None:
            self._app_to_restore = self._capture_frontmost_app()

        fraction_x = (
            (1.0 - normalized_x)
            if self.MIRROR_X
            else normalized_x
        )

        self.presentation_dot.set_dot_fraction(
            fraction_x,
            normalized_y
        )

        if self.preview_dot is not None:

            self.preview_dot.set_dot_fraction(
                fraction_x,
                normalized_y
            )

        # There is no explicit "pointer stopped" event — pointer_position
        # only fires while Pointing_Up is confirmed. This watchdog hides
        # the dot(s) shortly after updates stop arriving, standing in for
        # that missing signal.
        self.hide_timer.start(
            self.HIDE_AFTER_MS
        )

    def _hide_dots(self):

        self.presentation_dot.hide()

        if self.preview_dot is not None:
            self.preview_dot.hide()

        self._restore_frontmost_app()

    def _capture_frontmost_app(self):

        try:

            from AppKit import NSWorkspace

            return NSWorkspace.sharedWorkspace().frontmostApplication()

        except Exception:

            logger.exception(
                "Failed to capture frontmost app"
            )

            return None

    def _restore_frontmost_app(self):

        app = self._app_to_restore

        self._app_to_restore = None

        if app is None:
            return

        try:

            from AppKit import NSApplicationActivateIgnoringOtherApps

            app.activateWithOptions_(
                NSApplicationActivateIgnoringOtherApps
            )

        except Exception:

            logger.exception(
                "Failed to restore frontmost app"
            )
