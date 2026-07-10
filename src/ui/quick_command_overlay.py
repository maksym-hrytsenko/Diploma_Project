from PyQt6.QtCore import (
    Qt,
    pyqtSignal
)

from PyQt6.QtGui import (
    QGuiApplication,
    QPainter,
    QColor,
    QFont
)

from PyQt6.QtWidgets import QWidget

from ui.native_window import configure_overlay_window


class QuickCommandOverlay(QWidget):

    # Mirrors the four quick_circle mode_rules in
    # fusion.json (src/config/fusion.json) — kept here only
    # as display labels, the actual gesture -> mode wiring
    # lives entirely in fusion.json / SignalMapper.
    LABELS = {
        "up": "Flip",
        "down": "Cursor",
        "left": "Presentation",
        "right": "Call Mode"
    }

    RADIUS = 140

    mode_changed_signal = pyqtSignal(object)

    def __init__(self, event_bus):

        super().__init__()

        self.event_bus = event_bus

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

        screen = QGuiApplication.primaryScreen()

        self.setGeometry(
            screen.geometry()
        )

        # Must run after every setWindowFlags/setAttribute
        # call above — Qt may rebuild the native NSWindow
        # when those change, silently discarding whatever
        # collectionBehavior/level was set on the old one.
        configure_overlay_window(
            self
        )

        self.circle_visible = False

        self.mode_changed_signal.connect(
            self._on_mode_changed
        )

    # ---------------------------------
    # Start / Stop
    # ---------------------------------

    def start(self):

        self.event_bus.subscribe(
            "mode_changed",
            self._handle_mode_changed
        )

    def stop(self):

        self.event_bus.unsubscribe(
            "mode_changed",
            self._handle_mode_changed
        )

        self.hide()

    # ---------------------------------
    # Mode Changed (arrives on whichever
    # thread SignalMapper published from)
    # ---------------------------------

    def _handle_mode_changed(self, event):

        mode = event.get(
            "data",
            {}
        ).get("mode")

        self.mode_changed_signal.emit(
            mode
        )

    def _on_mode_changed(self, mode):

        self.circle_visible = (
            mode == "quick_circle"
        )

        if self.circle_visible:

            print(
                "[QUICK CIRCLE] showing overlay"
            )

            self.show()

            # WindowStaysOnTopHint alone does not always put
            # a freshly-shown frameless window in front of
            # everything else on macOS — raise_() forces it
            # to the front of the window stack.
            self.raise_()

        else:

            self.hide()

        self.update()

    # ---------------------------------
    # Paint
    # ---------------------------------

    def paintEvent(self, event):

        if not self.circle_visible:
            return

        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        center_x = self.width() // 2
        center_y = self.height() // 2

        painter.setPen(
            QColor(255, 255, 255, 200)
        )

        painter.setBrush(
            QColor(20, 20, 20, 160)
        )

        painter.drawEllipse(
            center_x - self.RADIUS,
            center_y - self.RADIUS,
            self.RADIUS * 2,
            self.RADIUS * 2
        )

        font = QFont()

        font.setPointSize(13)

        painter.setFont(font)

        painter.setPen(
            QColor(255, 255, 255, 230)
        )

        self._draw_label(painter, "up", center_x, center_y - self.RADIUS + 34)
        self._draw_label(painter, "down", center_x, center_y + self.RADIUS - 24)
        self._draw_label(painter, "left", center_x - self.RADIUS + 70, center_y)
        self._draw_label(painter, "right", center_x + self.RADIUS - 70, center_y)

    def _draw_label(self, painter, direction, x, y):

        painter.drawText(
            x - 70,
            y - 12,
            140,
            24,
            Qt.AlignmentFlag.AlignCenter,
            self.LABELS[direction]
        )
