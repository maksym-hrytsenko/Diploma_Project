import os

from PyQt6.QtCore import (
    Qt,
    pyqtSignal
)

from PyQt6.QtGui import (
    QGuiApplication,
    QPainter,
    QPixmap
)

from PyQt6.QtWidgets import QWidget

from ui.native_window import configure_overlay_window

from config.config_loader import load_system_config


class QuickCommandOverlay(QWidget):

    # Designed asset covering the whole quick-circle graphic
    # (ring + per-mode badges + center hub icon). Mode-to-
    # position mapping mirrors the four quick_circle mode_rules
    # in fusion.json (src/config/fusion.json) — baked into the
    # image itself, the actual gesture -> mode wiring lives
    # entirely in fusion.json / SignalMapper.
    #
    # Resolved relative to this file (not the process cwd) so
    # it loads correctly regardless of where main.py is launched
    # from.
    IMAGE_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "images",
        "quick_circle.png"
    )

    mode_changed_signal = pyqtSignal(object)

    def __init__(self, event_bus):

        super().__init__()

        self.event_bus = event_bus

        # Matches the diameter the previous drawEllipse-based
        # circle used (RADIUS 140 * 2). The source image is
        # scaled down to fit within this box, aspect ratio
        # preserved, so nothing is cropped — only shrunk.
        self.DISPLAY_SIZE = load_system_config().get(
            "ui",
            {}
        ).get(
            "quick_circle",
            {}
        ).get(
            "display_size",
            280
        )

        self.circle_pixmap = QPixmap(
            self.IMAGE_PATH
        )

        if not self.circle_pixmap.isNull():

            self.circle_pixmap = self.circle_pixmap.scaled(
                self.DISPLAY_SIZE,
                self.DISPLAY_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

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

        if self.circle_pixmap.isNull():
            return

        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        center_x = self.width() // 2
        center_y = self.height() // 2

        pixmap_width = self.circle_pixmap.width()

        pixmap_height = self.circle_pixmap.height()

        draw_x = center_x - pixmap_width // 2

        draw_y = center_y - pixmap_height // 2

        painter.drawPixmap(
            draw_x,
            draw_y,
            self.circle_pixmap
        )
