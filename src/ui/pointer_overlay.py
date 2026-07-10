from PyQt6.QtCore import (
    Qt,
    QTimer,
    pyqtSignal
)

from PyQt6.QtGui import (
    QGuiApplication,
    QPainter,
    QColor
)

from PyQt6.QtWidgets import QWidget


class PointerOverlay(QWidget):

    # Emitted from whichever thread calls
    # update_position() — typically the camera capture
    # thread, since EventBus.publish() dispatches
    # subscriber callbacks synchronously on the publishing
    # thread. Qt automatically queues delivery of a
    # connected slot onto the thread that owns this
    # QObject (the main/GUI thread), so this is the
    # cross-thread-safe way to reach a QWidget from here.
    position_updated = pyqtSignal(float, float)

    HIDE_AFTER_MS = 200

    DOT_RADIUS = 10

    DOT_COLOR = QColor(255, 0, 0, 220)

    # Camera frames are never flipped anywhere upstream, so
    # raw MediaPipe x=0 is the user's right side as seen
    # from behind the camera. Mirroring here makes the dot
    # move the same direction as the user's hand from the
    # user's own point of view. Verify this empirically
    # against a real camera and flip if the dot moves
    # backwards.
    MIRROR_X = True

    def __init__(self):

        super().__init__()

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
            self._select_presentation_screen().geometry()
        )

        self.dot_x = None
        self.dot_y = None

        self.position_updated.connect(
            self._on_position_updated
        )

        self.hide_timer = QTimer()

        self.hide_timer.setSingleShot(True)

        self.hide_timer.timeout.connect(
            self.hide
        )

    # ---------------------------------
    # Screen Selection
    # ---------------------------------

    # Presenting is normally done with a projector/external
    # display attached as a SECOND screen showing the actual
    # slides to the audience, while the primary screen (the
    # laptop's own) stays with the presenter's own view/notes.
    # The overlay is only useful pointing at whatever the
    # audience actually sees, so it targets the first
    # non-primary screen it finds rather than defaulting to
    # the primary one. Falls back to the primary screen when
    # only one is connected (e.g. testing without a projector
    # attached). Selected once, at construction — connect the
    # projector before starting the app; hot-plugging it in
    # mid-session needs a restart to be picked up.
    def _select_presentation_screen(self):

        primary_screen = QGuiApplication.primaryScreen()

        for screen in QGuiApplication.screens():

            if screen != primary_screen:
                return screen

        return primary_screen

    # ---------------------------------
    # Public API (safe to call from any thread)
    # ---------------------------------

    # Named update_position, not update, to avoid
    # colliding with QWidget's own built-in update()
    # repaint method.
    def update_position(self, normalized_x, normalized_y):

        self.position_updated.emit(
            normalized_x,
            normalized_y
        )

    # ---------------------------------
    # GUI-thread Slot
    # ---------------------------------

    def _on_position_updated(self, normalized_x, normalized_y):

        display_x = (
            (1.0 - normalized_x)
            if self.MIRROR_X
            else normalized_x
        )

        self.dot_x = int(
            display_x * self.width()
        )

        self.dot_y = int(
            normalized_y * self.height()
        )

        self.show()

        # WindowStaysOnTopHint alone does not always keep a
        # frameless window in front of everything else on
        # macOS — raise_() forces it to the front of the
        # window stack.
        self.raise_()

        self.update()

        # There is no explicit "pointer stopped" event —
        # pointer_position only fires while Pointing_Up is
        # confirmed. This watchdog hides the dot shortly
        # after updates stop arriving, standing in for that
        # missing signal.
        self.hide_timer.start(
            self.HIDE_AFTER_MS
        )

    # ---------------------------------
    # Paint
    # ---------------------------------

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
