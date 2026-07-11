"""Floating status bar.

Shown after "Minimize to bar" in MainWindow; hidden again once its own
expand button is clicked. Renders the approved reference photo
(images/02_floating_status_bar.png) as-is and overlays only the two
things that need to be clickable: the expand button already drawn into
that photo, and a small close button next to it (added because closing
from here — not just hiding the main window — is expected to shut the
whole application down, per the approved bottom-panel wiring in
MainWindow that stops every backend module through EventBus).
"""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication, QPixmap
from PyQt6.QtWidgets import QWidget, QLabel, QPushButton

from ui.native_window import configure_overlay_window

BAR_IMAGE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "images",
    "02_floating_status_bar.png"
)

BAR_WIDTH = 420
BAR_HEIGHT = 64

WINDOW_WIDTH = 462
WINDOW_HEIGHT = 64

COLOR_TEXT_DARK = "#172A5A"
COLOR_ERROR = "#FF5A7A"


class FloatingStatusBar(QWidget):

    def __init__(self, event_bus=None):

        super().__init__()

        self.event_bus = event_bus

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)

        self._build_background()
        self._build_expand_button()
        self._build_close_button()

        # Must run after the flags/attributes above — Qt may rebuild the
        # native NSWindow when those change (see native_window.py).
        configure_overlay_window(self)

    # ---------------------------------
    # Start / Stop
    # ---------------------------------

    def start(self):

        if self.event_bus is not None:
            self.event_bus.subscribe(
                "ui_minimize_to_bar_requested",
                self._handle_minimize_requested
            )

    def stop(self):

        if self.event_bus is not None:
            self.event_bus.unsubscribe(
                "ui_minimize_to_bar_requested",
                self._handle_minimize_requested
            )

    def _handle_minimize_requested(self, event):

        self._reposition()
        self.show()
        self.raise_()

    # ---------------------------------
    # Layout
    # ---------------------------------

    def _build_background(self):

        pixmap = QPixmap(BAR_IMAGE_PATH)

        if not pixmap.isNull():

            pixmap = pixmap.scaled(
                BAR_WIDTH,
                BAR_HEIGHT,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

        self.background_label = QLabel(self)
        self.background_label.setGeometry(0, 0, BAR_WIDTH, BAR_HEIGHT)
        self.background_label.setPixmap(pixmap)

    def _build_expand_button(self):

        self.btn_expand = QPushButton(self)
        self.btn_expand.setObjectName("floating_btn_expand")
        self.btn_expand.setGeometry(322, 14, 36, 36)
        self.btn_expand.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_expand.setToolTip("Open main window")

        self.btn_expand.setStyleSheet(
            "QPushButton#floating_btn_expand {"
            " background: transparent;"
            " border: none;"
            " border-radius: 18px;"
            "}"
            "QPushButton#floating_btn_expand:hover {"
            " background-color: rgba(139, 61, 255, 35);"
            "}"
        )
        self.btn_expand.clicked.connect(self._on_expand_clicked)

    def _build_close_button(self):

        self.btn_close = QPushButton("✕", self)
        self.btn_close.setObjectName("floating_btn_close")
        self.btn_close.setGeometry(WINDOW_WIDTH - 34, 16, 32, 32)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setToolTip("Quit")

        self.btn_close.setStyleSheet(
            "QPushButton#floating_btn_close {"
            f" color: {COLOR_TEXT_DARK};"
            " background-color: rgba(255, 255, 255, 210);"
            " border: 1.5px solid rgba(139, 61, 255, 90);"
            " border-radius: 16px;"
            " font-size: 13px;"
            " font-weight: 700;"
            "}"
            "QPushButton#floating_btn_close:hover {"
            f" color: #FFFFFF;"
            f" background-color: {COLOR_ERROR};"
            f" border: 1.5px solid {COLOR_ERROR};"
            "}"
        )
        self.btn_close.clicked.connect(self._on_close_clicked)

    def _reposition(self):

        screen = QGuiApplication.primaryScreen()

        if screen is None:
            return

        screen_geometry = screen.geometry()

        self.move(
            screen_geometry.width() - WINDOW_WIDTH - 40,
            32
        )

    # ---------------------------------
    # Actions
    # ---------------------------------

    def _on_expand_clicked(self):

        self.hide()

        if self.event_bus is not None:
            self.event_bus.publish("ui_expand_requested", {})

    def _on_close_clicked(self):

        if self.event_bus is not None:
            self.event_bus.publish("ui_quit_requested", {})
