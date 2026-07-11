"""Standalone manual test script, no imports from src/.

Reproduces exactly the two pieces of native window setup that
src/ui/native_window.py applies to the quick_circle overlay (per-window
collectionBehavior/level, and the app-wide activation policy), so the fix
for the "circle spawns its own empty Space" bug can be checked by hand
without running the full pipeline (camera/mic/gestures).

Manual verification steps:
    1. Run this script.
    2. Open a couple of full-screen apps / extra Desktops in Mission
       Control so there is more than one Space to be on.
    3. Switch between Spaces and full-screen apps freely — the red circle
       should already be sitting on top of whichever one you land on, with
       no new empty Space ever appearing and no focus jump.
    4. Ctrl+C in the terminal to quit.
"""

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication, QPainter, QColor
from PyQt6.QtWidgets import QWidget

from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowCollectionBehaviorIgnoresCycle,
    NSScreenSaverWindowLevel
)

import objc


class TestCircle(QWidget):

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

        screen = QGuiApplication.primaryScreen()

        self.setGeometry(
            screen.geometry()
        )

        self._configure_native_window()

    def _configure_native_window(self):

        native_view = objc.objc_object(
            c_void_p=int(self.winId())
        )

        native_window = native_view.window()

        native_window.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorIgnoresCycle
        )

        native_window.setLevel_(
            NSScreenSaverWindowLevel
        )

        native_window.setHidesOnDeactivate_(
            False
        )

    def paintEvent(self, event):

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
            QColor(200, 0, 0, 160)
        )

        painter.drawEllipse(
            center_x - 140,
            center_y - 140,
            280,
            280
        )


def main():

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # This is the actual fix under test — comment it out to
    # reproduce the "spawns its own empty Space" bug and
    # confirm the difference for yourself.
    NSApplication.sharedApplication().setActivationPolicy_(
        NSApplicationActivationPolicyAccessory
    )

    circle = TestCircle()

    circle.show()

    circle.raise_()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
