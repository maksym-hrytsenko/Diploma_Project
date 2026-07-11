"""Main application window.

Renders the primary control panel (mode wheel, module toggles, system
power) on top of the approved reference photo (images/01_main_menu.png),
as specified in ui_documentation_final_without_functions_dialog.txt. It
only reflects state — mode changes are decided by SignalMapper and
reach this window exclusively through EventBus's "mode_changed" event;
user interaction here publishes UI intent events but never applies a
mode itself.
"""

import os
import sys
import time

from typing import Optional

import numpy as np

from PyQt6.QtCore import (
    Qt,
    pyqtSignal
)

from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QImage,
    QPainter,
    QPen,
    QPixmap
)

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QGraphicsDropShadowEffect
)

from core.event_bus import EventBus
from ui.dialogs import FunctionsDialog, SettingsDialog


# Palette (docs/ui: ui_documentation_final_without_functions_dialog.txt, section 1)

COLOR_BACKGROUND = "#F4F6FB"
COLOR_TEXT_DARK = "#172A5A"
COLOR_TEXT_SECONDARY = "#6D7285"
COLOR_ACCENT_PURPLE = "#8B3DFF"
COLOR_ACCENT_BLUE = "#4F7BFF"
COLOR_GLOW_VIOLET = "#B76CFF"
COLOR_DISABLED = "#B8BCCB"
COLOR_ERROR = "#FF5A7A"
COLOR_ACTIVE_DOT = "#34C778"

# Sampled from the approved reference photo (01_main_menu.png) — the
# near-white lavender fill used inside every card/chip/circle, so text
# patches painted on top of the photo blend in seamlessly.
COLOR_PATCH_BG = "#F2F1FA"

BACKGROUND_IMAGE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "images",
    "01_main_menu.png"
)

WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 900


def make_font(size, bold=False):

    font = QFont()
    font.setPixelSize(size)
    font.setBold(bold)

    return font


def text_advance(text, size, bold=False):

    return QFontMetrics(make_font(size, bold)).horizontalAdvance(text)


def make_label(
    parent,
    text,
    x,
    y,
    width,
    height,
    color,
    size=11,
    bold=False,
    align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    bg=None
):

    label = QLabel(text, parent)
    label.setGeometry(x, y, width, height)
    label.setAlignment(align)
    label.setTextFormat(Qt.TextFormat.RichText)

    # Set explicitly (not just via the stylesheet below) so
    # label.fontMetrics() — used by apply_fitted_text/apply_fitted_two_tone
    # to size patches to their actual runtime-rendered width — reflects
    # the real font this label paints with, on whatever platform/system
    # font is actually installed, rather than a width measured offline on
    # a different machine.
    label.setFont(make_font(size, bold))

    background = f"background-color: {bg};" if bg is not None else "background: transparent;"

    # border: none is explicit, not just a default — Qt style sheets
    # cascade unset properties from parent to child, so a label nested
    # inside a bordered patch (see make_patch_label) would otherwise pick
    # up that border for itself too.
    label.setStyleSheet(f"color: {color}; {background} border: none;")

    return label


def apply_fitted_text(
    patch,
    label,
    text,
    color,
    base_size,
    bold,
    anchor_x,
    center=False,
    padding=20,
    min_width=40,
    max_width=None,
    min_size=8
):
    """Set a patch/label pair's text, sizing the box to the text's actual
    runtime width instead of a width guessed offline — the root cause of
    text overflowing its frame on a machine with different font metrics.
    """

    size = base_size

    while True:

        width = max(text_advance(text, size, bold) + padding, min_width)

        if max_width is None or width <= max_width or size <= min_size:
            break

        size -= 1

    if max_width is not None:
        width = min(width, max_width)

    x = (anchor_x - width // 2) if center else anchor_x

    patch.setGeometry(x, patch.y(), width, patch.height())
    label.setGeometry(0, 0, width, label.height())
    label.setFont(make_font(size, bold))
    label.setText(text)
    label.setStyleSheet(f"color: {color}; background: transparent; border: none;")


def apply_fitted_two_tone(
    patch,
    label,
    prefix_text,
    value_text,
    prefix_color,
    value_color,
    base_size,
    anchor_x,
    center=False,
    padding=20,
    min_width=40,
    max_width=None,
    min_size=8
):

    size = base_size

    while True:

        content_width = (
            text_advance(prefix_text, size, False)
            + text_advance(value_text, size, True)
        )

        width = max(content_width + padding, min_width)

        if max_width is None or width <= max_width or size <= min_size:
            break

        size -= 1

    if max_width is not None:
        width = min(width, max_width)

    x = (anchor_x - width // 2) if center else anchor_x

    patch.setGeometry(x, patch.y(), width, patch.height())
    label.setGeometry(0, 0, width, label.height())
    label.setFont(make_font(size, False))

    label.setText(
        f'<span style="color:{prefix_color};">{prefix_text}</span>'
        f'<span style="color:{value_color}; font-weight:700;">{value_text}</span>'
    )


def make_patch_label(parent, x, y, width, height, radius=8, border=None):

    label = make_label(parent, "", x, y, width, height, COLOR_TEXT_DARK, bg=COLOR_PATCH_BG)

    border_style = f" border: 1.5px solid {border};" if border is not None else ""

    label.setStyleSheet(label.styleSheet() + f" border-radius: {radius}px;{border_style}")

    return label


def make_transparent_button(parent, object_name, x, y, width, height, radius):

    button = QPushButton(parent)
    button.setObjectName(object_name)
    button.setGeometry(x, y, width, height)
    button.setCursor(Qt.CursorShape.PointingHandCursor)

    button.setStyleSheet(
        f"QPushButton#{object_name} {{"
        " background: transparent;"
        " border: none;"
        f" border-radius: {radius}px;"
        "}"
        f"QPushButton#{object_name}:hover {{"
        f" background-color: rgba(139, 61, 255, 28);"
        "}"
        f"QPushButton#{object_name}:pressed {{"
        f" background-color: rgba(139, 61, 255, 45);"
        "}"
    )

    return button


def make_glow_ring(parent, x, y, width, height, color=COLOR_GLOW_VIOLET):

    ring = QFrame(parent)
    ring.setGeometry(x, y, width, height)

    ring.setStyleSheet(
        f"background-color: rgba(183, 108, 255, 35);"
        f" border: 2.5px solid {color};"
        f" border-radius: {width // 2}px;"
    )

    effect = QGraphicsDropShadowEffect(ring)
    effect.setBlurRadius(50)
    effect.setOffset(0, 0)
    effect.setColor(QColor(color))
    ring.setGraphicsEffect(effect)

    ring.hide()

    return ring


def make_dim_overlay(parent, x, y, width, height, radius):

    overlay = QFrame(parent)
    overlay.setGeometry(x, y, width, height)

    overlay.setStyleSheet(
        "background-color: rgba(180, 182, 200, 130);"
        f" border-radius: {radius}px;"
    )

    overlay.hide()

    return overlay


def render_camera_icon(color, size):
    """The one baked-in icon the reference photo no longer draws — its
    camera-preview placeholder area was cleared out to make room for the
    live feed built in _build_camera_preview, so this is drawn instead of
    patched, matching the approved line-art style (large, simple, no
    small details).
    """

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 100.0, size / 100.0)

    pen = QPen(QColor(color))
    pen.setWidthF(8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(12, 32, 76, 48, 14.0, 14.0)
    painter.drawRoundedRect(38, 20, 24, 14, 5.0, 5.0)
    painter.drawEllipse(34, 40, 32, 32)

    painter.end()

    return pixmap


def render_hand_icon(color, size):

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 100.0, size / 100.0)

    pen = QPen(QColor(color))
    pen.setWidthF(8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(30, 48, 40, 40, 14.0, 14.0)
    painter.drawLine(38, 48, 38, 14)
    painter.drawLine(50, 48, 50, 8)
    painter.drawLine(62, 48, 62, 16)
    painter.drawLine(28, 55, 14, 40)

    painter.end()

    return pixmap


CORNER_BORDER_SIDES = {
    "top-left": ("border-top", "border-left"),
    "top-right": ("border-top", "border-right"),
    "bottom-left": ("border-bottom", "border-left"),
    "bottom-right": ("border-bottom", "border-right")
}


def make_corner_marker(parent, x, y, size, corner):

    sides = CORNER_BORDER_SIDES[corner]

    style = "; ".join(f"{side}: 2.5px solid {COLOR_ACCENT_PURPLE}" for side in sides)

    marker = QFrame(parent)
    marker.setGeometry(x, y, size, size)
    marker.setStyleSheet(f"background: transparent; {style};")

    return marker


class DraggableFrame(QFrame):

    def __init__(self, parent=None):

        super().__init__(parent)

        self._drag_offset = None

        self.setStyleSheet("background: transparent; border: none;")

    def mousePressEvent(self, event):

        if event.button() == Qt.MouseButton.LeftButton:

            self._drag_offset = (
                event.globalPosition().toPoint()
                - self.window().frameGeometry().topLeft()
            )

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):

        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:

            self.window().move(
                event.globalPosition().toPoint() - self._drag_offset
            )

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):

        self._drag_offset = None

        super().mouseReleaseEvent(event)


class ToggleSwitch(QPushButton):

    def __init__(self, parent, object_name, x, y, width, height, checked):

        super().__init__(parent)

        self.setObjectName(object_name)
        self.setGeometry(x, y, width, height)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._radius = height // 2
        self._knob_diameter = height - 6

        self.knob = QFrame(self)
        self.knob.setGeometry(3, 3, self._knob_diameter, self._knob_diameter)
        self.knob.setStyleSheet(
            f"background-color: #FFFFFF; border-radius: {self._knob_diameter // 2}px;"
        )

        self.toggled.connect(self._on_toggled)

        self._apply_style()

    def _on_toggled(self, checked):

        knob_x = self.width() - self._knob_diameter - 3 if checked else 3

        self.knob.move(knob_x, 3)

        self._apply_style()

    def _apply_style(self):

        if self.isChecked():

            background = (
                "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                f"stop:0 {COLOR_ACCENT_BLUE}, stop:1 {COLOR_ACCENT_PURPLE})"
            )

        else:

            background = COLOR_DISABLED

        self.setStyleSheet(
            "QPushButton {"
            f" background: {background};"
            f" border-radius: {self._radius}px;"
            " border: none;"
            "}"
        )


MODE_DISPLAY_NAMES = {
    "flip": "Flip / Mode",
    "presentation": "Presentation",
    "call": "Call Mode",
    "cursor": "Cursor"
}

# Anchors text-patch labels resize around, calibrated against the
# approved reference photo (01_main_menu.png) — see the module docstring.
CAMERA_CHIP_ANCHOR_X = 86
SYSTEM_STATE_CENTER_X = 1057
CURRENT_MODE_ANCHOR_X = 760
ACTIVE_MODULES_ANCHOR_X = 760
ACTIVE_MODULES_MAX_WIDTH = 250
CARD_STATE_ANCHORS = {
    "camera": (140, 224),
    "microphone": (430, 507),
    "keyboard": (710, 785)
}


class MainWindow(QWidget):
    """Main control panel window.

    Uses the approved reference photo (01_main_menu.png) directly as the
    visual surface — every panel, icon and glow is already baked into it —
    and overlays only what needs to move or change: transparent click
    regions, toggle switches, glow highlights and a handful of text
    patches for values that must update live or that the photo still
    shows from an older draft (superseded by
    ui_documentation_final_without_functions_dialog.txt section 10).
    """

    mode_changed_signal = pyqtSignal(object)
    gesture_debug_signal = pyqtSignal(object)
    face_debug_signal = pyqtSignal(object)

    # Caps how often a camera_frame-driven gesture_debug event repaints
    # video_label — gesture_debug fires once per processed camera frame
    # (up to CameraInput's own ~30fps), well past what this preview
    # needs, and scaling+painting every single one would just burn Qt
    # main-thread time the rest of the UI also needs.
    VIDEO_MIN_INTERVAL_SECONDS = 1.0 / 24.0

    def __init__(self, event_bus: Optional[EventBus] = None):

        super().__init__()

        self.event_bus = event_bus

        self.system_on = True
        self.active_mode = None
        self.camera_active = True
        self.microphone_active = True
        self.keyboard_active = True

        self.setObjectName("main_window")
        self.setWindowTitle("Gesture & Voice Control")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(f"#main_window {{ background-color: {COLOR_BACKGROUND}; }}")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        self.mode_changed_signal.connect(self._on_mode_changed_from_bus)
        self.gesture_debug_signal.connect(self._on_gesture_debug)
        self.face_debug_signal.connect(self._on_face_debug)

        self._build_background()
        self._build_header()
        self._build_camera_preview()
        self._build_control_wheel()
        self._build_bottom_status()

        self._refresh_system_power()
        self._refresh_mode_buttons()
        self._update_camera_status_chip()
        self._refresh_toggle_states()

    # ---------------------------------
    # Start / Stop
    #
    # Mirrors QuickCommandOverlay's pattern: a read-only
    # subscription to the real mode_changed event so the wheel
    # reflects whatever SignalMapper actually decided, without the
    # UI ever deciding a mode itself (SignalMapper is the only
    # module allowed to do that — see CLAUDE.md).
    # ---------------------------------

    def start(self):

        if self.event_bus is not None:

            self.event_bus.subscribe("mode_changed", self._handle_mode_changed)
            self.event_bus.subscribe("ui_expand_requested", self._handle_expand_requested)

            # Read-only, same as mode_changed above: GestureRecognizer and
            # FaceRecognizer already publish these every processed camera
            # frame (see gesture_debug_view.py / face_debug_view.py, which
            # read the exact same events for the --debug-gesture/--debug-
            # face cv2 windows) — this window just draws them instead of
            # opening a second, redundant subscription path.
            self.event_bus.subscribe("gesture_debug", self._handle_gesture_debug)
            self.event_bus.subscribe("face_debug", self._handle_face_debug)

    def stop(self):

        if self.event_bus is not None:

            self.event_bus.unsubscribe("mode_changed", self._handle_mode_changed)
            self.event_bus.unsubscribe("ui_expand_requested", self._handle_expand_requested)
            self.event_bus.unsubscribe("gesture_debug", self._handle_gesture_debug)
            self.event_bus.unsubscribe("face_debug", self._handle_face_debug)

    def _handle_expand_requested(self, event):

        self.show()
        self.raise_()

    def _handle_mode_changed(self, event):

        mode = event.get("data", {}).get("mode")

        self.mode_changed_signal.emit(mode)

    def _on_mode_changed_from_bus(self, mode):

        self.active_mode = mode

        self._refresh_mode_buttons()

    # ---------------------------------
    # Live camera preview
    #
    # gesture_debug/face_debug arrive on CameraInput's capture thread —
    # marshaled onto the Qt main thread via a signal/slot (same pattern
    # QuickCommandOverlay uses for mode_changed) before touching any
    # widget, since Qt widgets may only be touched from their own thread.
    # ---------------------------------

    def _handle_gesture_debug(self, event):

        if time.time() - self._last_video_update < self.VIDEO_MIN_INTERVAL_SECONDS:
            return

        self.gesture_debug_signal.emit(event.get("data", {}))

    def _handle_face_debug(self, event):

        self.face_debug_signal.emit(event.get("data", {}))

    def _on_face_debug(self, data):

        self._latest_face_pitch = data.get("pitch")

        if self.camera_active and self.video_label.isVisible():
            self._refresh_face_status()

    def _on_gesture_debug(self, data):

        frame = data.get("frame")

        if frame is None or not self.camera_active:
            return

        self._last_video_update = time.time()

        pixmap = self._frame_to_pixmap(frame)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        self._paint_hand_overlay(painter, pixmap, data)

        painter.end()

        self.video_label.setPixmap(pixmap)

        if not self.video_label.isVisible():

            self.video_label.show()
            self.icon_camera_placeholder.hide()
            self.label_camera_placeholder_title.hide()
            self.label_camera_placeholder_hint.hide()

        gesture_name = data.get("gesture_name") or "—"
        confidence = data.get("confidence")
        confidence_text = f"{confidence * 100:.0f}%" if confidence is not None else "—"

        self.value_detected_gesture.setText(gesture_name)
        self.value_confidence.setText(confidence_text)

        self._refresh_face_status()

    def _frame_to_pixmap(self, frame):

        frame = np.ascontiguousarray(frame)
        height, width = frame.shape[:2]

        image = QImage(
            frame.data, width, height, width * 3, QImage.Format.Format_BGR888
        ).copy()

        video_width, video_height = self.video_area[2], self.video_area[3]

        return QPixmap.fromImage(image).scaled(
            video_width,
            video_height,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )

    def _paint_hand_overlay(self, painter, pixmap, data):

        width = pixmap.width()
        height = pixmap.height()

        finger = data.get("finger")
        anchor = data.get("anchor")

        pen = QPen(QColor(COLOR_ACCENT_PURPLE))
        pen.setWidthF(3)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        anchor_point = None

        if anchor is not None:

            anchor_point = (int(anchor[0] * width), int(anchor[1] * height))

            painter.drawEllipse(anchor_point[0] - 26, anchor_point[1] - 26, 52, 52)

        if finger is not None:

            finger_point = (int(finger[0] * width), int(finger[1] * height))

            painter.setBrush(QColor(COLOR_ACCENT_BLUE))
            painter.drawEllipse(finger_point[0] - 8, finger_point[1] - 8, 16, 16)

            if anchor_point is not None:

                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawLine(
                    anchor_point[0], anchor_point[1], finger_point[0], finger_point[1]
                )

    def _refresh_face_status(self):

        tracked = self._latest_face_pitch is not None

        apply_fitted_text(
            self.face_status_patch,
            self.label_face_status,
            "● Face tracked" if tracked else "● No face",
            COLOR_ACTIVE_DOT if tracked else COLOR_TEXT_SECONDARY,
            base_size=10,
            bold=True,
            anchor_x=10,
            max_width=160
        )

        self.face_status_patch.show()

    def _reset_camera_preview(self):

        self.video_label.hide()
        self.video_label.clear()
        self.face_status_patch.hide()

        self.icon_camera_placeholder.show()
        self.label_camera_placeholder_title.show()
        self.label_camera_placeholder_hint.show()

        self.value_detected_gesture.setText("—")
        self.value_confidence.setText("—")

        self._latest_face_pitch = None

    def _publish_ui_event(self, event_type, data):

        if self.event_bus is not None:
            self.event_bus.publish(event_type, data)

    # ---------------------------------
    # Background photo
    # ---------------------------------

    def _build_background(self):

        pixmap = QPixmap(BACKGROUND_IMAGE_PATH)

        if not pixmap.isNull():

            pixmap = pixmap.scaled(
                WINDOW_WIDTH,
                WINDOW_HEIGHT,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

        self.background_label = QLabel(self)
        self.background_label.setGeometry(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
        self.background_label.setPixmap(pixmap)

    # ---------------------------------
    # Header
    # ---------------------------------

    def _build_header(self):

        self.header_drag_area = DraggableFrame(self)
        self.header_drag_area.setGeometry(24, 18, 1090, 78)

        self.btn_window_minimize = make_transparent_button(
            self, "btn_window_minimize", 1200, 39, 48, 48, 18
        )
        self.btn_window_minimize.clicked.connect(self.showMinimized)

        self.btn_window_settings = make_transparent_button(
            self, "btn_window_settings", 1269, 39, 48, 48, 18
        )
        self.btn_window_settings.clicked.connect(self._on_settings_clicked)

        self.btn_window_close = make_transparent_button(
            self, "btn_window_close", 1338, 39, 48, 48, 18
        )
        self.btn_window_close.clicked.connect(self.close)

    # ---------------------------------
    # Camera preview
    # ---------------------------------

    def _build_camera_preview(self):

        self.camera_status_patch = make_patch_label(
            self, 86, 163, 140, 32, radius=16, border=COLOR_ACCENT_PURPLE
        )

        self.label_camera_status = make_label(
            self.camera_status_patch,
            "",
            0,
            0,
            140,
            32,
            COLOR_ACCENT_PURPLE,
            size=12,
            bold=True,
            align=Qt.AlignmentFlag.AlignCenter
        )

        # The reference photo's camera-preview placeholder and detected-
        # gesture bar were cleared out in the approved photo to leave room
        # for the live feed below — see render_camera_icon's docstring.
        self.video_area = (48, 210, 606, 260)

        self.video_label = QLabel(self)
        self.video_label.setGeometry(*self.video_area)
        self.video_label.setStyleSheet("background: transparent;")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.hide()

        self.icon_camera_placeholder = QLabel(self)
        self.icon_camera_placeholder.setGeometry(292, 260, 92, 92)
        self.icon_camera_placeholder.setPixmap(
            render_camera_icon(COLOR_ACCENT_BLUE, 92)
        )
        self.icon_camera_placeholder.setStyleSheet("background: transparent;")

        self.label_camera_placeholder_title = make_label(
            self, "Camera preview", 248, 364, 180, 26, COLOR_TEXT_DARK,
            size=15, bold=True, align=Qt.AlignmentFlag.AlignCenter
        )

        self.label_camera_placeholder_hint = make_label(
            self, "Waiting for video input", 218, 396, 240, 22, COLOR_TEXT_SECONDARY,
            size=11, align=Qt.AlignmentFlag.AlignCenter
        )

        for corner_x, corner_y, corner in (
            (self.video_area[0] + 8, self.video_area[1] + 8, "top-left"),
            (self.video_area[0] + self.video_area[2] - 36, self.video_area[1] + 8, "top-right"),
            (self.video_area[0] + 8, self.video_area[1] + self.video_area[3] - 36, "bottom-left"),
            (
                self.video_area[0] + self.video_area[2] - 36,
                self.video_area[1] + self.video_area[3] - 36,
                "bottom-right"
            )
        ):
            make_corner_marker(self, corner_x, corner_y, 28, corner)

        self.gesture_info_patch = make_patch_label(
            self, 72, 502, 558, 62, radius=22, border=COLOR_ACCENT_PURPLE
        )

        self.icon_detected_gesture = QLabel(self.gesture_info_patch)
        self.icon_detected_gesture.setGeometry(20, 15, 32, 32)
        self.icon_detected_gesture.setPixmap(render_hand_icon(COLOR_ACCENT_PURPLE, 32))
        self.icon_detected_gesture.setStyleSheet("background: transparent;")

        make_label(
            self.gesture_info_patch, "Detected gesture:", 66, 10, 180, 18,
            COLOR_TEXT_SECONDARY, size=9
        )

        self.value_detected_gesture = make_label(
            self.gesture_info_patch, "—", 66, 30, 200, 22, COLOR_TEXT_DARK,
            size=12, bold=True
        )

        make_label(
            self.gesture_info_patch, "Confidence:", 340, 10, 130, 18,
            COLOR_TEXT_SECONDARY, size=9
        )

        self.value_confidence = make_label(
            self.gesture_info_patch, "—", 340, 30, 100, 22, COLOR_TEXT_DARK,
            size=12, bold=True
        )

        self.face_status_patch = make_patch_label(self, 0, 0, 10, 10, radius=12)
        self.face_status_patch.setParent(self.video_label)
        self.face_status_patch.setGeometry(10, 10, 130, 26)
        self.face_status_patch.hide()

        self.label_face_status = make_label(
            self.face_status_patch, "", 0, 0, 130, 26, COLOR_TEXT_SECONDARY,
            size=10, bold=True, align=Qt.AlignmentFlag.AlignCenter
        )

        self._latest_face_pitch = None
        self._last_video_update = 0.0

    # ---------------------------------
    # Circular control wheel
    # ---------------------------------

    def _build_control_wheel(self):

        self.glow_mode_flip = make_glow_ring(self, 999, 130, 116, 116)
        self.glow_presentation = make_glow_ring(self, 799, 318, 116, 116)
        self.glow_call_mode = make_glow_ring(self, 1195, 318, 116, 116)
        self.glow_cursor = make_glow_ring(self, 998, 495, 116, 116)

        self.mode_glow_rings = {
            "flip": self.glow_mode_flip,
            "presentation": self.glow_presentation,
            "call": self.glow_call_mode,
            "cursor": self.glow_cursor
        }

        self.system_dim_overlay = make_dim_overlay(self, 978, 305, 158, 158, 79)

        self.btn_system_power = make_transparent_button(
            self, "btn_system_power", 978, 305, 158, 158, 79
        )
        self.btn_system_power.clicked.connect(self._on_system_power_clicked)

        self.system_state_patch = make_patch_label(self, 1005, 410, 105, 22, radius=10)

        self.label_system_state = make_label(
            self.system_state_patch,
            "",
            0,
            0,
            105,
            22,
            COLOR_ACCENT_PURPLE,
            size=11,
            bold=True,
            align=Qt.AlignmentFlag.AlignCenter
        )

        self.btn_mode_flip = make_transparent_button(
            self, "btn_mode_flip", 1009, 140, 96, 96, 48
        )
        self.btn_mode_flip.clicked.connect(lambda: self._on_mode_clicked("flip"))

        self.btn_presentation = make_transparent_button(
            self, "btn_presentation", 809, 328, 96, 96, 48
        )
        self.btn_presentation.clicked.connect(lambda: self._on_mode_clicked("presentation"))

        self.btn_call_mode = make_transparent_button(
            self, "btn_call_mode", 1205, 328, 96, 96, 48
        )
        self.btn_call_mode.clicked.connect(lambda: self._on_mode_clicked("call"))

        self.btn_cursor_mode = make_transparent_button(
            self, "btn_cursor_mode", 1008, 505, 96, 96, 48
        )
        self.btn_cursor_mode.clicked.connect(lambda: self._on_mode_clicked("cursor"))

        self.mode_buttons = {
            "flip": self.btn_mode_flip,
            "presentation": self.btn_presentation,
            "call": self.btn_call_mode,
            "cursor": self.btn_cursor_mode
        }

        # The reference photo still shows the deprecated labels
        # "Gesture" / "Voice" / "Control" (an earlier draft) — patched
        # here to the approved names from section 10 of the
        # documentation. The top label ("Mode") already matches an
        # approved alternative name, so it is left untouched.
        make_patch_label(self, 787, 428, 140, 24)
        make_label(
            self, "Presentation", 787, 428, 140, 24, COLOR_TEXT_DARK,
            size=14, bold=True, align=Qt.AlignmentFlag.AlignCenter
        )

        make_patch_label(self, 1198, 428, 110, 24)
        make_label(
            self, "Call Mode", 1198, 428, 110, 24, COLOR_TEXT_DARK,
            size=14, bold=True, align=Qt.AlignmentFlag.AlignCenter
        )

        make_patch_label(self, 1016, 606, 80, 24)
        make_label(
            self, "Cursor", 1016, 606, 80, 24, COLOR_TEXT_DARK,
            size=14, bold=True, align=Qt.AlignmentFlag.AlignCenter
        )

        self.current_mode_patch = make_patch_label(self, 760, 574, 320, 20)
        self.label_current_mode = make_label(
            self.current_mode_patch, "", 0, 0, 320, 20, COLOR_TEXT_DARK, size=13
        )

        self.active_modules_patch = make_patch_label(self, 760, 597, 285, 18)
        self.label_active_modules = make_label(
            self.active_modules_patch, "", 0, 0, 285, 18, COLOR_TEXT_DARK, size=10
        )

    # ---------------------------------
    # Bottom status panel
    # ---------------------------------

    def _build_bottom_status(self):

        self.dim_toggle_camera = make_dim_overlay(self, 53, 678, 265, 120, 28)
        self.dim_toggle_microphone = make_dim_overlay(self, 344, 678, 265, 120, 28)
        self.dim_toggle_keyboard = make_dim_overlay(self, 624, 678, 265, 120, 28)

        self.state_patch_camera = make_patch_label(self, 140, 745, 100, 22, radius=8)
        self.label_state_camera = make_label(
            self.state_patch_camera, "", 0, 0, 100, 22, COLOR_ACTIVE_DOT, size=12, bold=True
        )

        self.state_patch_microphone = make_patch_label(self, 430, 745, 100, 22, radius=8)
        self.label_state_microphone = make_label(
            self.state_patch_microphone, "", 0, 0, 100, 22, COLOR_ACTIVE_DOT, size=12, bold=True
        )

        self.state_patch_keyboard = make_patch_label(self, 710, 745, 100, 22, radius=8)
        self.label_state_keyboard = make_label(
            self.state_patch_keyboard, "", 0, 0, 100, 22, COLOR_ACTIVE_DOT, size=12, bold=True
        )

        self.switch_camera = ToggleSwitch(
            self, "switch_camera", 230, 775, 52, 28, self.camera_active
        )
        self.switch_camera.toggled.connect(self._on_camera_toggled)

        self.switch_microphone = ToggleSwitch(
            self, "switch_microphone", 513, 775, 52, 28, self.microphone_active
        )
        self.switch_microphone.toggled.connect(self._on_microphone_toggled)

        self.switch_keyboard = ToggleSwitch(
            self, "switch_keyboard", 791, 775, 52, 28, self.keyboard_active
        )
        self.switch_keyboard.toggled.connect(self._on_keyboard_toggled)

        self.btn_functions = make_transparent_button(
            self, "btn_functions", 902, 706, 235, 65, 24
        )
        self.btn_functions.clicked.connect(self._on_functions_clicked)

        self.btn_minimize_to_bar = make_transparent_button(
            self, "btn_minimize_to_bar", 1158, 704, 235, 68, 24
        )
        self.btn_minimize_to_bar.clicked.connect(self._on_minimize_to_bar_clicked)

    # ---------------------------------
    # System power
    # ---------------------------------

    def _on_system_power_clicked(self):

        self.system_on = not self.system_on

        self._refresh_system_power()

        self._publish_ui_event("ui_system_toggle", {"active": self.system_on})

    def _refresh_system_power(self):

        color = COLOR_ACCENT_PURPLE if self.system_on else COLOR_DISABLED
        state_text = "● SYSTEM ON" if self.system_on else "● SYSTEM OFF"

        apply_fitted_text(
            self.system_state_patch,
            self.label_system_state,
            state_text,
            color,
            base_size=11,
            bold=True,
            anchor_x=SYSTEM_STATE_CENTER_X,
            center=True,
            max_width=150
        )

        self.system_dim_overlay.setVisible(not self.system_on)

    # ---------------------------------
    # Modes (only one active at a time)
    # ---------------------------------

    def _on_mode_clicked(self, mode_name):

        self.active_mode = None if self.active_mode == mode_name else mode_name

        self._refresh_mode_buttons()

        self._publish_ui_event("ui_mode_selected", {"mode": self.active_mode})

    def _refresh_mode_buttons(self):

        for mode_name, ring in self.mode_glow_rings.items():

            ring.setVisible(mode_name == self.active_mode)

        display_name = MODE_DISPLAY_NAMES.get(self.active_mode)

        if display_name is None:
            display_name = "Standby" if self.active_mode is None else self.active_mode.title()

        apply_fitted_two_tone(
            self.current_mode_patch,
            self.label_current_mode,
            "Current mode: ",
            display_name,
            COLOR_TEXT_DARK,
            COLOR_ACCENT_PURPLE,
            base_size=13,
            anchor_x=CURRENT_MODE_ANCHOR_X,
            max_width=320
        )

        self._refresh_active_modules_label()

    def _refresh_active_modules_label(self):

        active_modules = []

        if self.camera_active:
            active_modules.append("Camera")

        if self.microphone_active:
            active_modules.append("Microphone")

        if self.keyboard_active:
            active_modules.append("Keyboard")

        modules_text = ", ".join(active_modules) if active_modules else "None"

        apply_fitted_two_tone(
            self.active_modules_patch,
            self.label_active_modules,
            "Active modules: ",
            modules_text,
            COLOR_TEXT_DARK,
            COLOR_ACCENT_PURPLE,
            base_size=10,
            anchor_x=ACTIVE_MODULES_ANCHOR_X,
            max_width=ACTIVE_MODULES_MAX_WIDTH,
            min_size=7
        )

    # ---------------------------------
    # Module toggles
    # ---------------------------------

    def _on_camera_toggled(self, active):

        self.camera_active = active

        if not active:
            self._reset_camera_preview()

        self._update_camera_status_chip()
        self._refresh_toggle_states()
        self._refresh_active_modules_label()

        self._publish_ui_event("ui_camera_toggle", {"active": active})

    def _on_microphone_toggled(self, active):

        self.microphone_active = active

        self._refresh_toggle_states()
        self._refresh_active_modules_label()

        self._publish_ui_event("ui_microphone_toggle", {"active": active})

    def _on_keyboard_toggled(self, active):

        self.keyboard_active = active

        self._refresh_toggle_states()
        self._refresh_active_modules_label()

        self._publish_ui_event("ui_keyboard_toggle", {"active": active})

    def _refresh_toggle_states(self):

        cards = (
            (
                "camera",
                self.camera_active,
                self.dim_toggle_camera,
                self.state_patch_camera,
                self.label_state_camera
            ),
            (
                "microphone",
                self.microphone_active,
                self.dim_toggle_microphone,
                self.state_patch_microphone,
                self.label_state_microphone
            ),
            (
                "keyboard",
                self.keyboard_active,
                self.dim_toggle_keyboard,
                self.state_patch_keyboard,
                self.label_state_keyboard
            )
        )

        for name, active, dim_overlay, state_patch, state_label in cards:

            dim_overlay.setVisible(not active)

            anchor_x, max_right_x = CARD_STATE_ANCHORS[name]
            color = COLOR_ACTIVE_DOT if active else COLOR_DISABLED
            text = "● Active" if active else "● Disabled"

            apply_fitted_text(
                state_patch,
                state_label,
                text,
                color,
                base_size=12,
                bold=True,
                anchor_x=anchor_x,
                max_width=max_right_x - anchor_x
            )

    def _update_camera_status_chip(self):

        state_text = "Active" if self.camera_active else "Disabled"
        color = COLOR_ACCENT_PURPLE if self.camera_active else COLOR_DISABLED

        apply_fitted_text(
            self.camera_status_patch,
            self.label_camera_status,
            f"● Camera: {state_text}",
            color,
            base_size=12,
            bold=True,
            anchor_x=CAMERA_CHIP_ANCHOR_X,
            max_width=200
        )

    # ---------------------------------
    # Functions description / minimize / settings
    #
    # Both dialogs' own designs are still drafts — see ui/dialogs.py's
    # module docstring — only their content is meant to be final here.
    # ---------------------------------

    def _on_functions_clicked(self):

        self._publish_ui_event("ui_open_functions_description", {})

        dialog = FunctionsDialog(self)
        dialog.exec()

    def _on_minimize_to_bar_clicked(self):

        self._publish_ui_event("ui_minimize_to_bar_requested", {})

        self.hide()

    def _on_settings_clicked(self):

        dialog = SettingsDialog(self)
        dialog.exec()


if __name__ == "__main__":

    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
