"""Main application window.

Renders the control panel on top of images/01_main_menu.png. Reflects
state only — SignalMapper decides modes, this window just displays
"mode_changed" events and publishes UI intent (see docs/ARCHITECTURE.md).
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
    QPainterPath,
    QPen,
    QPixmap,
    QRegion
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
from ui.dialogs import SettingsWindow, InfoWindow
from utils.logger import get_logger


logger = get_logger(__name__)


# Palette — see docs/UI_SPEC.txt §1

COLOR_BACKGROUND = "#F4F6FB"
COLOR_TEXT_DARK = "#172A5A"
COLOR_TEXT_SECONDARY = "#6D7285"
COLOR_ACCENT_PURPLE = "#8B3DFF"
COLOR_ACCENT_BLUE = "#4F7BFF"
COLOR_GLOW_VIOLET = "#B76CFF"
COLOR_DISABLED = "#B8BCCB"
COLOR_ERROR = "#FF5A7A"
COLOR_ACTIVE_DOT = "#34C778"

# Patch fill matching the photo's own panel color
COLOR_PATCH_BG = "#F2F1FA"

BACKGROUND_IMAGE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "images",
    "01_main_menu.png"
)

WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 900

# Real OS-level window rounding, see _apply_rounded_mask
WINDOW_CORNER_RADIUS = 35


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

    # Real rendered font, for fitted-width calculations below
    label.setFont(make_font(size, bold))

    background = f"background-color: {bg};" if bg is not None else "background: transparent;"

    # Explicit border:none — stylesheets cascade to children otherwise
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
    # Sizes the patch to the text's real rendered width, shrinking font
    # down to min_size if max_width would otherwise be exceeded.

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
    # Drawn, not photo-baked — the placeholder area was cleared for the
    # live feed (see _build_camera_preview).

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
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._radius = height // 2
        self._knob_diameter = height - 6

        self.knob = QFrame(self)
        self.knob.setGeometry(3, 3, self._knob_diameter, self._knob_diameter)
        self.knob.setStyleSheet(
            f"background-color: #FFFFFF; border-radius: {self._knob_diameter // 2}px;"
        )

        self.toggled.connect(self._on_toggled)

        # Must connect before setChecked, so an initial checked=True
        # routes through _on_toggled (moves the knob) instead of only
        # updating the track color.
        self.setChecked(checked)

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

# Momentary gesture_signal names (swipe direction / fist-swipe / pinch)
# have no held pose of their own to read a live state from — shown for
# this long after gesture_debug's "last_signal_time", via "last_signal",
# instead of nothing. Longer than GestureRecognizer's own visual anchor
# freeze (freeze_duration, default 0.3s) so the caption stays legible
# even though it isn't tied to that same timer.
GESTURE_SIGNAL_FLASH_SECONDS = 0.6

# HAND_LEFT/RIGHT/UP/DOWN mean different things in each mode that reads
# them — matched against gesture_debug's "last_signal", not "gesture_name"
# (a swipe direction is never a MediaPipe category).
FLIP_MODE_SIGNAL_CAPTIONS = {
    "HAND_UP": "Scroll down",
    "HAND_DOWN": "Scroll up",
    "HAND_RIGHT": "Flip previous",
    "HAND_LEFT": "Flip next"
}

PRESENTATION_MODE_SIGNAL_CAPTIONS = {
    "HAND_RIGHT": "Next slide",
    "HAND_LEFT": "Previous slide"
}

PINCH_SIGNAL_CAPTIONS = {
    "PINCH": "Click",
    "DOUBLE_PINCH": "Right-click"
}

# Call mode's finger-count toggles have no MediaPipe gesture category of
# their own (see GestureRecognizer.FINGER_COUNT_GESTURES) — matched here
# against gesture_debug's "active_gesture_signal", not "gesture_name".
CALL_MODE_GESTURE_CAPTIONS = {
    "ONE_FINGER": "Toggle microphone",
    "TWO_FINGERS": "Toggle camera",
    "THREE_FINGERS": "Toggle call audio",
    "FOUR_FINGERS": "Toggle background blur"
}

# UI-triggered signal per mode, matching config/mapping.json's "ui" section
MODE_UI_SIGNALS = {
    "flip": "FLIP_MODE",
    "presentation": "PRESENTATION_MODE",
    "call": "CALL_MODE",
    "cursor": "CURSOR_MODE"
}

# "SYSTEM ON/OFF" label center — keep equal to btn_system_power's own
# center (x + width/2, currently 993 + 158/2 = 1072) or it drifts off
# the hub's actual center.
SYSTEM_STATE_CENTER_X = 1072

# "Current mode: …" label left edge — not centered on purpose so far;
# edit this one number to reposition it (apply_fitted_two_tone grows the
# patch rightward from here as the text changes).
CURRENT_MODE_ANCHOR_X = 760

# Toggle-card "Active"/"Disabled" label: (left edge, right edge) per card
CARD_STATE_ANCHORS = {
    "camera": (165, 260),
    "microphone": (455, 545),
    "keyboard": (735, 825)
}


class MainWindow(QWidget):
    """Main control panel — draws over images/01_main_menu.png."""

    mode_changed_signal = pyqtSignal(object)
    try_mode_changed_signal = pyqtSignal(bool)
    gesture_debug_signal = pyqtSignal(object)
    face_debug_signal = pyqtSignal(object)

    # gesture_debug fires up to ~30fps; repainting every one is wasted work
    VIDEO_MIN_INTERVAL_SECONDS = 1.0 / 24.0

    def __init__(self, event_bus: Optional[EventBus] = None):

        super().__init__()

        self.event_bus = event_bus

        self.system_on = True
        self.active_mode = None
        self.try_mode_active = False
        self.camera_active = True
        self.microphone_active = True
        self.keyboard_active = True

        # Reused so a second click on gear/Functions-description raises
        # the existing window instead of opening a duplicate.
        self._settings_window = None
        self._info_window = None

        self.setObjectName("main_window")
        self.setWindowTitle("Gesture & Voice Control")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(f"#main_window {{ background-color: {COLOR_BACKGROUND}; }}")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        # Needed for _apply_rounded_mask to actually look rounded
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._apply_rounded_mask()

        self.mode_changed_signal.connect(self._on_mode_changed_from_bus)
        self.try_mode_changed_signal.connect(self._on_try_mode_changed_from_bus)
        self.gesture_debug_signal.connect(self._on_gesture_debug)
        self.face_debug_signal.connect(self._on_face_debug)

        # Press D to toggle labeled outlines over every registered
        # button/icon/glow ring — see _build_debug_overlay/keyPressEvent.
        self._debug_elements = []
        self._debug_overlay_widgets = []
        self._debug_overlay_visible = False

        self._build_background()
        self._build_header()
        self._build_camera_preview()
        self._build_try_mode_toggle()
        self._build_control_wheel()
        self._build_bottom_status()

        self._refresh_system_power()
        self._refresh_mode_buttons()
        self._refresh_try_mode_state()
        self._refresh_toggle_states()

        self._build_debug_overlay()

    # ---------------------------------
    # Start / Stop — read-only subscriptions, SignalMapper decides modes
    # ---------------------------------

    def start(self):

        if self.event_bus is not None:

            self.event_bus.subscribe("mode_changed", self._handle_mode_changed)
            self.event_bus.subscribe("try_mode_changed", self._handle_try_mode_changed)
            self.event_bus.subscribe("ui_expand_requested", self._handle_expand_requested)

            # Same events the --debug-gesture/--debug-face cv2 windows use
            self.event_bus.subscribe("gesture_debug", self._handle_gesture_debug)
            self.event_bus.subscribe("face_debug", self._handle_face_debug)

    def stop(self):

        if self.event_bus is not None:

            self.event_bus.unsubscribe("mode_changed", self._handle_mode_changed)
            self.event_bus.unsubscribe("try_mode_changed", self._handle_try_mode_changed)
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

        # FaceRecognizer only publishes face_debug while idle (suppressed
        # the instant a mode becomes active — see its active_mode guard in
        # _handle_frame), so on EITHER transition — entering a mode, or
        # returning to idle — the last-known dots/pitch it last delivered
        # would otherwise hang on screen until fresh data arrives. Idle ->
        # mode: no more face_debug events will come until the mode ends,
        # so nothing would ever clear this on its own. Mode -> idle:
        # FaceRecognizer does resume publishing, but only once a face is
        # next confidently detected — if the face isn't in frame at that
        # exact moment, the stale mode-entry-time dots would otherwise
        # keep showing indefinitely instead of a fresh "no face" reading.
        self._latest_face_pitch = None
        self._latest_face_landmarks = None

        if self.camera_active and self.video_label.isVisible():
            self._refresh_face_status()

        self._refresh_mode_buttons()

    def _handle_try_mode_changed(self, event):

        active = event.get("data", {}).get("active", False)

        self.try_mode_changed_signal.emit(active)

    def _on_try_mode_changed_from_bus(self, active):

        self.try_mode_active = active

        # Reconciles the switch's knob with SignalMapper's own decision —
        # voice/keyboard can flip Try Mode independently of this window,
        # and the system-off/turn-back-on detour in _on_try_mode_toggled
        # means a click doesn't always land where the knob first jumped to.
        # blockSignals so setChecked doesn't itself re-trigger the click
        # handler and publish a second, unwanted toggle.
        self.switch_try_mode.blockSignals(True)
        self.switch_try_mode.setChecked(active)
        self.switch_try_mode.blockSignals(False)

        self._refresh_try_mode_state()

    # ---------------------------------
    # Live camera preview — events arrive off the Qt thread, marshaled
    # via signal/slot before touching any widget.
    # ---------------------------------

    def _handle_gesture_debug(self, event):

        data = event.get("data", {})

        # The frame-rate throttle below exists purely to cap repaint work,
        # not to decide WHAT gets shown — but applied blindly, it could
        # swallow the one event that matters most: the very frame the
        # hand disappears on. hand_landmarks is only ever non-empty while
        # a hand is actually tracked (see GestureRecognizer._handle_frame/
        # _handle_hand_lost) — if the PREVIOUS frame painted had a hand
        # and this one doesn't, that transition always gets through
        # immediately, so the landmark dots clear the instant the hand
        # leaves frame instead of potentially waiting up to one throttle
        # window (worse under a mode's heavier per-frame processing —
        # Cursor mode's off-hand model, zoom/precision math — which
        # already eats into how much of that window is headroom).
        hand_lost_transition = (
            not data.get("hand_landmarks")
            and self._hand_landmarks_present
        )

        if (
            not hand_lost_transition
            and time.time() - self._last_video_update < self.VIDEO_MIN_INTERVAL_SECONDS
        ):
            return

        self.gesture_debug_signal.emit(data)

    def _handle_face_debug(self, event):

        self.face_debug_signal.emit(event.get("data", {}))

    def _on_face_debug(self, data):

        self._latest_face_pitch = data.get("pitch")
        self._latest_face_landmarks = data.get("face_landmarks")

        if self.camera_active and self.video_label.isVisible():
            self._refresh_face_status()

    def _on_gesture_debug(self, data):

        frame = data.get("frame")

        if frame is None or not self.camera_active:
            return

        self._last_video_update = time.time()

        self._hand_landmarks_present = bool(data.get("hand_landmarks"))

        pixmap = self._build_video_frame_pixmap(frame, data)

        self.video_label.setPixmap(pixmap)

        if not self.video_label.isVisible():

            self.video_label.show()
            self.icon_camera_placeholder.hide()
            self.label_camera_placeholder_title.hide()
            self.label_camera_placeholder_hint.hide()

        self._refresh_face_status()

    # One clipped QPainter session so the rounded-corner clip applies to
    # the frame, landmark points and caption alike.
    def _build_video_frame_pixmap(self, frame, data):

        width, height = self.video_area[2], self.video_area[3]
        source_height, source_width = frame.shape[:2]
        source_size = (source_width, source_height)

        crop_box = self._crop_box(source_width, source_height, width, height)

        cropped = self._frame_to_rect_pixmap(frame, crop_box, width, height)

        canvas = QPixmap(width, height)
        canvas.fill(Qt.GlobalColor.transparent)

        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        clip_path = QPainterPath()
        clip_path.addRoundedRect(
            0.0, 0.0, float(width), float(height),
            self.video_radius - 2, self.video_radius - 2
        )
        painter.setClipPath(clip_path)

        painter.drawPixmap(0, 0, cropped)

        self._paint_hand_landmarks(painter, width, height, data, crop_box, source_size)
        self._paint_face_landmarks(painter, width, height, crop_box, source_size)
        self._paint_gesture_caption(painter, width, height, data)

        painter.end()

        return canvas

    # Crop box (x, y, w, h) in SOURCE pixel space matching the target
    # aspect ratio — shared by the frame crop below and by
    # _map_normalized_point, so a landmark point and the pixel it should
    # sit on top of go through the exact same transform.
    def _crop_box(self, source_width, source_height, target_width, target_height):

        target_aspect = target_width / target_height
        source_aspect = source_width / source_height

        if source_aspect > target_aspect:

            crop_height = source_height
            crop_width = round(source_height * target_aspect)

        else:

            crop_width = source_width
            crop_height = round(source_width / target_aspect)

        crop_x = (source_width - crop_width) // 2
        crop_y = (source_height - crop_height) // 2

        return crop_x, crop_y, crop_width, crop_height

    def _frame_to_rect_pixmap(self, frame, crop_box, target_width, target_height):

        frame = np.ascontiguousarray(frame)
        source_height, source_width = frame.shape[:2]

        image = QImage(
            frame.data, source_width, source_height, source_width * 3,
            QImage.Format.Format_BGR888
        ).copy()

        crop_x, crop_y, crop_width, crop_height = crop_box

        cropped_image = image.copy(crop_x, crop_y, crop_width, crop_height)

        return QPixmap.fromImage(cropped_image).scaled(
            target_width, target_height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

    # Maps a normalized (0-1, relative to the FULL camera frame) point
    # onto the cropped+scaled preview canvas. Landmarks are normalized to
    # the original frame, not the cropped preview — skipping this step
    # (drawing at int(x*width)) is what made hand/face points drift out
    # of place whenever the crop trims any edge, which it almost always
    # does (camera aspect ratio != preview panel aspect ratio). Returns
    # None if the point falls outside the visible crop.
    def _map_normalized_point(
        self,
        x,
        y,
        source_width,
        source_height,
        crop_box,
        target_width,
        target_height
    ):

        crop_x, crop_y, crop_width, crop_height = crop_box

        cropped_x = x * source_width - crop_x
        cropped_y = y * source_height - crop_y

        if cropped_x < 0 or cropped_x > crop_width:
            return None

        if cropped_y < 0 or cropped_y > crop_height:
            return None

        point_x = int(cropped_x * target_width / crop_width)
        point_y = int(cropped_y * target_height / crop_height)

        return point_x, point_y

    # Every MediaPipe hand landmark (see gesture_recognizer.py's
    # _publish_debug "hand_landmarks").
    def _paint_hand_landmarks(self, painter, width, height, data, crop_box, source_size):

        hand_landmarks = data.get("hand_landmarks")

        if not hand_landmarks:
            return

        source_width, source_height = source_size

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLOR_ACCENT_BLUE))

        radius = 3

        for x, y in hand_landmarks:

            mapped = self._map_normalized_point(
                x, y, source_width, source_height, crop_box, width, height
            )

            if mapped is None:
                continue

            point_x, point_y = mapped

            painter.drawEllipse(
                point_x - radius, point_y - radius, radius * 2, radius * 2
            )

    # Every MediaPipe face landmark (see face_recognizer.py's
    # _publish_debug "face_landmarks"). Reads self._latest_face_landmarks
    # rather than "data" since face_debug/gesture_debug are independent
    # events — the latest face reading is drawn on whichever frame
    # gesture_debug is currently painting.
    def _paint_face_landmarks(self, painter, width, height, crop_box, source_size):

        if not self._latest_face_landmarks:
            return

        source_width, source_height = source_size

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLOR_GLOW_VIOLET))

        radius = 1

        for x, y in self._latest_face_landmarks:

            mapped = self._map_normalized_point(
                x, y, source_width, source_height, crop_box, width, height
            )

            if mapped is None:
                continue

            point_x, point_y = mapped

            painter.drawEllipse(
                point_x - radius, point_y - radius, radius * 2, radius * 2
            )

    # Mode-aware, human-readable description of what the camera currently
    # sees, for the "Detected: ..." caption below — e.g. Cursor mode's
    # Pointing_Up reads as "Cursor control", a held pinch as "Click",
    # rather than the raw MediaPipe category name a viewer would otherwise
    # have to already know the meaning of. Falls back to the raw
    # gesture_name (Call mode excepted — see below) for poses the active
    # mode gives no specific meaning to.
    #
    # Returns (text, show_confidence) — show_confidence is False for
    # readings not directly tied to gesture_debug's own "confidence"
    # value (pinch/drag, Call mode's finger count — neither has a
    # MediaPipe classifier score of its own, see GestureRecognizer's
    # active_gesture_signal/is_pinching/is_dragging), so an unrelated
    # percentage is never shown next to them.
    def _describe_gesture(self, data):

        gesture_name = data.get("gesture_name")
        tracking_active = data.get("tracking_active", False)
        active_gesture_signal = data.get("active_gesture_signal")
        is_pinching = data.get("is_pinching", False)
        is_dragging = data.get("is_dragging", False)
        off_hand_pinching = data.get("off_hand_pinching", False)

        mode = self.active_mode

        # A swipe/fist-swipe/pinch is a one-frame event with no held pose
        # to read a live state from (unlike is_pinching/is_dragging/
        # tracking_active, which stay true for as long as the pose is
        # held) — shown for GESTURE_SIGNAL_FLASH_SECONDS after it fires
        # instead of never at all. None outside that window, so it falls
        # through to whatever live state applies below.
        recent_signal = None

        last_signal = data.get("last_signal")
        last_signal_time = data.get("last_signal_time")

        if (
            last_signal is not None
            and last_signal_time is not None
            and time.time() - last_signal_time < GESTURE_SIGNAL_FLASH_SECONDS
        ):
            recent_signal = last_signal

        if mode == "cursor":

            if recent_signal in PINCH_SIGNAL_CAPTIONS:
                return PINCH_SIGNAL_CAPTIONS[recent_signal], False

            if off_hand_pinching:
                return "Zoom", False

            if is_dragging:
                return "Scroll", False

            if is_pinching:
                return "Click", False

            if gesture_name == "Pointing_Up":
                return "Cursor control", True

        elif mode == "flip":

            if recent_signal in FLIP_MODE_SIGNAL_CAPTIONS:
                return FLIP_MODE_SIGNAL_CAPTIONS[recent_signal], False

            if tracking_active:
                return "Swipe to scroll or flip", False

            if gesture_name == "Closed_Fist":
                return "Ready to swipe", True

        elif mode == "presentation":

            if recent_signal in PRESENTATION_MODE_SIGNAL_CAPTIONS:
                return PRESENTATION_MODE_SIGNAL_CAPTIONS[recent_signal], False

            if gesture_name == "Pointing_Up":
                return "Laser pointer", True

            if gesture_name == "Closed_Fist":
                return "Ready to change slide", True

        elif mode == "call":

            call_caption = CALL_MODE_GESTURE_CAPTIONS.get(
                active_gesture_signal
            )

            if call_caption:
                return call_caption, False

            return "Hold 1-4 fingers up to toggle mic/camera/audio/blur", False

        elif mode == "quick_circle":

            if gesture_name == "Closed_Fist":
                return "Close menu", True

            return "Swipe to pick a mode", False

        elif mode is None:

            if gesture_name == "Pointing_Up":
                return "Laser pointer", True

            if tracking_active:
                return "Quick menu — swipe to select", False

            if gesture_name == "Closed_Fist":
                return "Ready to open quick menu", True

        if gesture_name:
            return gesture_name.replace("_", " "), True

        return None, False

    # Detected-command caption, painted directly on the frame
    def _paint_gesture_caption(self, painter, width, height, data):

        description, show_confidence = self._describe_gesture(data)

        confidence = data.get("confidence") if show_confidence else None

        if description:

            confidence_text = (
                f" · {confidence * 100:.0f}%" if confidence is not None else ""
            )
            caption_text = f"Detected: {description}{confidence_text}"

        else:

            caption_text = "Detected: —"

        caption_height = 36

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(23, 42, 90, 165))
        painter.drawRect(0, height - caption_height, width, caption_height)

        font = make_font(11, bold=True)
        painter.setFont(font)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(
            0, height - caption_height, width, caption_height,
            Qt.AlignmentFlag.AlignCenter, caption_text
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

        self._latest_face_pitch = None
        self._latest_face_landmarks = None
        self._hand_landmarks_present = False

    def _publish_ui_event(self, event_type, data):

        if self.event_bus is not None:
            self.event_bus.publish(event_type, data)

    # Real OS-level rounded window shape (hard clip), not just painted
    # rounded corners on a square window.
    def _apply_rounded_mask(self):

        path = QPainterPath()
        path.addRoundedRect(
            0.0, 0.0, float(WINDOW_WIDTH), float(WINDOW_HEIGHT),
            WINDOW_CORNER_RADIUS, WINDOW_CORNER_RADIUS
        )

        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    # ---------------------------------
    # Live layout debug overlay (press D to toggle)
    # ---------------------------------

    def _register_debug_element(self, name, widget):
        # Bookkeeping only — _build_debug_overlay reads this list once
        # every element for this window exists.

        self._debug_elements.append((name, widget))

    def _build_debug_overlay(self):
        # One hidden labeled outline per registered element, exact same
        # geometry. WA_TransparentForMouseEvents so it never blocks
        # clicks — purely visual/printed.

        for name, widget in self._debug_elements:

            geometry = widget.geometry()

            outline = QFrame(self)
            outline.setGeometry(geometry)
            outline.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            outline.setStyleSheet(
                "background-color: rgba(255, 45, 85, 40);"
                " border: 1.5px solid rgba(255, 45, 85, 235);"
            )
            outline.hide()

            label_text = f"{name} {geometry.x()},{geometry.y()},{geometry.width()}x{geometry.height()}"

            label = QLabel(label_text, self)
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            label.setStyleSheet(
                "color: #FFFFFF; background-color: rgba(23, 42, 90, 220);"
                " border: none; padding: 1px 4px; font-size: 10px;"
            )
            label.adjustSize()

            # Sits above the outline, or just inside it near the top edge
            label_y = geometry.y() - label.height() - 1

            if label_y < 0:
                label_y = geometry.y() + 1

            label.move(geometry.x(), label_y)
            label.hide()

            self._debug_overlay_widgets.append(outline)
            self._debug_overlay_widgets.append(label)

    def _toggle_debug_overlay(self):

        self._debug_overlay_visible = not self._debug_overlay_visible

        for widget in self._debug_overlay_widgets:

            widget.setVisible(self._debug_overlay_visible)

            if self._debug_overlay_visible:
                widget.raise_()

        state = "ON" if self._debug_overlay_visible else "off"

        logger.debug(
            "[layout-debug] overlay %s — %d elements",
            state,
            len(self._debug_elements)
        )

        if self._debug_overlay_visible:

            for name, widget in self._debug_elements:

                geometry = widget.geometry()

                logger.debug(
                    "  %s: x=%d y=%d w=%d h=%d",
                    name,
                    geometry.x(),
                    geometry.y(),
                    geometry.width(),
                    geometry.height()
                )

    def keyPressEvent(self, event):

        if event.key() == Qt.Key.Key_D:

            self._toggle_debug_overlay()
            return

        super().keyPressEvent(event)

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

        # Window minimize
        self.btn_window_minimize = make_transparent_button(
            self, "btn_window_minimize", 1198, 39, 52, 47, 13
        )
        self.btn_window_minimize.clicked.connect(self.showMinimized)
        self._register_debug_element("btn_window_minimize", self.btn_window_minimize)

        # Opens SettingsWindow
        self.btn_window_settings = make_transparent_button(
            self, "btn_window_settings", 1268, 39, 52, 47, 13
        )
        self.btn_window_settings.clicked.connect(self._on_settings_clicked)
        self._register_debug_element("btn_window_settings", self.btn_window_settings)

        # Quits the app
        self.btn_window_close = make_transparent_button(
            self, "btn_window_close", 1337, 39, 53, 47, 13
        )
        self.btn_window_close.clicked.connect(self._on_close_clicked)
        self._register_debug_element("btn_window_close", self.btn_window_close)

    # ---------------------------------
    # Camera preview
    # ---------------------------------

    def _build_camera_preview(self):
        # Fills panel_camera_preview; the photo's own placeholder content
        # here was cleared for the live feed.

        rect_x, rect_y = 24, 132
        rect_width, rect_height = 679, 500

        self.video_area = (rect_x, rect_y, rect_width, rect_height)
        self.video_radius = 35

        self.video_frame_bg = make_patch_label(
            self, rect_x, rect_y, rect_width, rect_height,
            radius=self.video_radius, border=COLOR_ACCENT_PURPLE
        )

        self.video_label = QLabel(self)
        self.video_label.setGeometry(*self.video_area)
        self.video_label.setStyleSheet("background: transparent;")
        self.video_label.hide()

        icon_size = 92

        # Vertically centers the icon/title/hint block
        block_y = rect_y + (rect_height - 156) // 2

        self.icon_camera_placeholder = QLabel(self)
        self.icon_camera_placeholder.setGeometry(
            rect_x + (rect_width - icon_size) // 2, block_y, icon_size, icon_size
        )
        self.icon_camera_placeholder.setPixmap(
            render_camera_icon(COLOR_ACCENT_BLUE, icon_size)
        )
        self.icon_camera_placeholder.setStyleSheet("background: transparent;")

        self.label_camera_placeholder_title = make_label(
            self, "Camera preview", rect_x, block_y + icon_size + 8, rect_width, 26,
            COLOR_TEXT_DARK, size=15, bold=True, align=Qt.AlignmentFlag.AlignCenter
        )

        self.label_camera_placeholder_hint = make_label(
            self, "Waiting for video input", rect_x, block_y + icon_size + 42, rect_width, 22,
            COLOR_TEXT_SECONDARY, size=11, align=Qt.AlignmentFlag.AlignCenter
        )

        self.face_status_patch = make_patch_label(self.video_label, 10, 10, 130, 26, radius=12)
        self.face_status_patch.hide()

        self.label_face_status = make_label(
            self.face_status_patch, "", 0, 0, 130, 26, COLOR_TEXT_SECONDARY,
            size=10, bold=True, align=Qt.AlignmentFlag.AlignCenter
        )

        self._latest_face_pitch = None
        self._latest_face_landmarks = None
        self._last_video_update = 0.0

        # Whether the most recently PAINTED frame had a tracked hand — see
        # _handle_gesture_debug's hand_lost_transition check, which uses
        # this (not the throttled video_label state) to let a hand's
        # disappearance always bypass the repaint throttle.
        self._hand_landmarks_present = False

    # ---------------------------------
    # Try Mode — top-left corner of panel_control_wheel (the white square
    # the mode wheel sits on: x=800,y=128 per
    # docs/UI_SPEC.txt §"panel_control_
    # wheel" — empty space there, well clear of glow_mode_flip at
    # x=1014,y=128). Independent of camera_active/microphone_active/
    # keyboard_active (those gate which INPUTS are read) and of
    # active_mode (which of the four exclusive modes is on) — this one
    # gates whether ActionExecutor is allowed to touch the OS at all, see
    # action_executor.py's try_mode_active.
    # ---------------------------------

    def _build_try_mode_toggle(self):

        panel_x, panel_y = 760, 128

        inset = 14

        switch_width, switch_height = 52, 28

        switch_x = panel_x + inset
        switch_y = panel_y + inset

        self.switch_try_mode = ToggleSwitch(
            self, "switch_try_mode", switch_x, switch_y,
            switch_width, switch_height, False
        )
        self.switch_try_mode.toggled.connect(self._on_try_mode_toggled)
        self._register_debug_element("switch_try_mode", self.switch_try_mode)

        label_width = 110
        label_x = switch_x + switch_width + 8

        self.try_mode_patch = make_patch_label(
            self, label_x, switch_y - 1, label_width, switch_height + 2, radius=10
        )
        self.label_try_mode = make_label(
            self.try_mode_patch, "", 0, 0, label_width, switch_height + 2,
            COLOR_TEXT_SECONDARY, size=11, bold=True, align=Qt.AlignmentFlag.AlignCenter
        )

    def _on_try_mode_toggled(self, checked):

        if not self.system_on:

            # Same detour as _on_mode_clicked: clicking while the hub
            # shows OFF turns it back on first (published, so
            # SignalMapper's gate lifts before the TRY_MODE signal below
            # reaches it), instead of the click silently doing nothing.
            self.system_on = True

            self._refresh_system_power()

            self._publish_ui_event("ui_system_toggle", {"active": True})

        if self.event_bus is None:

            # Standalone hot-reload preview only (no SignalMapper running)
            # — simulate locally, same fallback as _on_mode_clicked.
            self.try_mode_active = checked

            self._refresh_try_mode_state()
            return

        # Not applied locally here — SignalMapper decides (it's also
        # reachable by voice/keyboard, and needs to agree with whatever
        # they last set); the switch's knob and label only become final
        # once _on_try_mode_changed_from_bus echoes the real state back.
        self._publish_ui_event("ui_signal", {"signal": "TRY_MODE"})

    def _refresh_try_mode_state(self):

        color = COLOR_ACCENT_PURPLE if self.try_mode_active else COLOR_TEXT_SECONDARY
        text = "● Try Mode ON" if self.try_mode_active else "Try mode"

        self.label_try_mode.setText(text)
        self.label_try_mode.setStyleSheet(
            f"color: {color}; background: transparent; border: none;"
        )

    # ---------------------------------
    # Circular control wheel
    # ---------------------------------

    def _build_control_wheel(self):

        # Glow rings: shown behind a mode icon when it's active (see
        # _refresh_mode_buttons/mode_glow_rings). Keep width==height and
        # centered on the matching wheel button below.
        self.glow_mode_flip = make_glow_ring(self, 1014, 128, 116, 116)
        self.glow_presentation = make_glow_ring(self, 817, 321, 116, 116)
        self.glow_call_mode = make_glow_ring(self, 1210, 320, 116, 116)
        self.glow_cursor = make_glow_ring(self, 1014, 511, 116, 116)

        self._register_debug_element("glow_mode_flip", self.glow_mode_flip)
        self._register_debug_element("glow_presentation", self.glow_presentation)
        self._register_debug_element("glow_call_mode", self.glow_call_mode)
        self._register_debug_element("glow_cursor", self.glow_cursor)

        self.mode_glow_rings = {
            "flip": self.glow_mode_flip,
            "presentation": self.glow_presentation,
            "call": self.glow_call_mode,
            "cursor": self.glow_cursor
        }

        # Grey "system off" circle — keep x/y/w/h identical to
        # btn_system_power below (same circle), or it drifts off-center.
        self.system_dim_overlay = make_dim_overlay(self, 993, 298, 158, 160, 79)
        self._register_debug_element("system_dim_overlay", self.system_dim_overlay)

        # System ON/OFF hub button
        self.btn_system_power = make_transparent_button(
            self, "btn_system_power", 993, 298, 158, 160, 79
        )
        self.btn_system_power.clicked.connect(self._on_system_power_clicked)
        self._register_debug_element("btn_system_power", self.btn_system_power)

        self.system_state_patch = make_patch_label(self, 1005, 417, 105, 22, radius=10)

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

        # Icon graphic is baked into the photo; width/height/radius here
        # only control the click/highlight circle around it. Widen the
        # matching glow ring above by the same amount if you resize one.

        # Flip/Mode (top icon)
        self.btn_mode_flip = make_transparent_button(
            self, "btn_mode_flip", 1022, 138, 98, 98, 49
        )
        self.btn_mode_flip.clicked.connect(lambda: self._on_mode_clicked("flip"))
        self._register_debug_element("btn_mode_flip", self.btn_mode_flip)

        # Presentation (left icon)
        self.btn_presentation = make_transparent_button(
            self, "btn_presentation", 827, 329, 98, 98, 49
        )
        self.btn_presentation.clicked.connect(lambda: self._on_mode_clicked("presentation"))
        self._register_debug_element("btn_presentation", self.btn_presentation)

        # Call Mode (right icon)
        self.btn_call_mode = make_transparent_button(
            self, "btn_call_mode", 1220, 329, 98, 98, 49
        )
        self.btn_call_mode.clicked.connect(lambda: self._on_mode_clicked("call"))
        self._register_debug_element("btn_call_mode", self.btn_call_mode)

        # Cursor (bottom icon)
        self.btn_cursor_mode = make_transparent_button(
            self, "btn_cursor_mode", 1022, 521, 98, 98, 49
        )
        self.btn_cursor_mode.clicked.connect(lambda: self._on_mode_clicked("cursor"))
        self._register_debug_element("btn_cursor_mode", self.btn_cursor_mode)

        self.mode_buttons = {
            "flip": self.btn_mode_flip,
            "presentation": self.btn_presentation,
            "call": self.btn_call_mode,
            "cursor": self.btn_cursor_mode
        }

        # "Current mode: …" — see CURRENT_MODE_ANCHOR_X above to reposition
        self.current_mode_patch = make_patch_label(self, 760, 574, 320, 20)
        self.label_current_mode = make_label(
            self.current_mode_patch, "", 0, 0, 320, 20, COLOR_TEXT_DARK, size=13
        )

    # ---------------------------------
    # Bottom status panel
    # ---------------------------------

    def _build_bottom_status(self):

        self.dim_toggle_camera = make_dim_overlay(self, 53, 678, 265, 153, 25)
        self.dim_toggle_microphone = make_dim_overlay(self, 344, 678, 255, 153, 25)
        self.dim_toggle_keyboard = make_dim_overlay(self, 624, 678, 250, 153, 25)

        # "● Active"/"● Disabled" per card — position via CARD_STATE_ANCHORS
        # above (x) and y below (not touched by apply_fitted_text).
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

        # Camera toggle switch
        self.switch_camera = ToggleSwitch(
            self, "switch_camera", 230, 775, 52, 28, self.camera_active
        )
        self.switch_camera.toggled.connect(self._on_camera_toggled)
        self._register_debug_element("switch_camera", self.switch_camera)

        # Microphone toggle switch
        self.switch_microphone = ToggleSwitch(
            self, "switch_microphone", 513, 775, 52, 28, self.microphone_active
        )
        self.switch_microphone.toggled.connect(self._on_microphone_toggled)
        self._register_debug_element("switch_microphone", self.switch_microphone)

        # Keyboard toggle switch
        self.switch_keyboard = ToggleSwitch(
            self, "switch_keyboard", 791, 775, 52, 28, self.keyboard_active
        )
        self.switch_keyboard.toggled.connect(self._on_keyboard_toggled)
        self._register_debug_element("switch_keyboard", self.switch_keyboard)

        # Opens InfoWindow
        self.btn_functions = make_transparent_button(
            self, "btn_functions", 902, 716, 234, 73, 18
        )
        self.btn_functions.clicked.connect(self._on_functions_clicked)
        self._register_debug_element("btn_functions", self.btn_functions)

        # Hides MainWindow, shows FloatingStatusBar
        self.btn_minimize_to_bar = make_transparent_button(
            self, "btn_minimize_to_bar", 1158, 715, 232, 75, 18
        )
        self.btn_minimize_to_bar.clicked.connect(self._on_minimize_to_bar_clicked)
        self._register_debug_element("btn_minimize_to_bar", self.btn_minimize_to_bar)

    # ---------------------------------
    # System power
    # ---------------------------------

    def _on_system_power_clicked(self):

        turning_off = self.system_on

        if turning_off and self.active_mode is not None:

            # Exit the active mode BEFORE the system actually goes off —
            # SignalMapper's system-off gate blocks everything, including
            # an EXIT_MODE request, once ui_system_toggle(False) below
            # has been processed, so this has to go out first.
            if self.event_bus is None:

                self.active_mode = None
                self._refresh_mode_buttons()

            else:

                self._publish_ui_event("ui_signal", {"signal": "EXIT_MODE"})

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

    # Asks via the real pipeline (CommandInterpreter -> MultimodalFusion
    # -> SignalMapper) instead of setting active_mode directly —
    # SignalMapper alone decides (docs/ARCHITECTURE.md). Visible effect only happens
    # once mode_changed comes back, see _on_mode_changed_from_bus.
    def _on_mode_clicked(self, mode_name):

        if not self.system_on:

            # Clicking a mode while the hub shows OFF turns it back on
            # first (published, so SignalMapper's gate lifts before the
            # mode request below reaches it), instead of the click just
            # silently doing nothing — keeps the hub and the wheel from
            # ever disagreeing (a mode active while the hub still shows
            # OFF).
            self.system_on = True

            self._refresh_system_power()

            self._publish_ui_event("ui_system_toggle", {"active": True})

        if self.active_mode == mode_name:

            signal = "EXIT_MODE"

        else:

            signal = MODE_UI_SIGNALS[mode_name]

        if self.event_bus is None:

            # Standalone hot-reload preview only (no SignalMapper running)
            # — simulate locally so glow rings are visible while checking
            # layout. See _on_mode_changed_from_bus for the real path.
            self.active_mode = None if signal == "EXIT_MODE" else mode_name

            self._refresh_mode_buttons()
            return

        self._publish_ui_event("ui_signal", {"signal": signal})

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

    # ---------------------------------
    # Module toggles
    # ---------------------------------

    def _on_camera_toggled(self, active):

        self.camera_active = active

        if not active:
            self._reset_camera_preview()

        self._refresh_toggle_states()

        self._publish_ui_event("ui_camera_toggle", {"active": active})

    def _on_microphone_toggled(self, active):

        self.microphone_active = active

        self._refresh_toggle_states()

        self._publish_ui_event("ui_microphone_toggle", {"active": active})

    def _on_keyboard_toggled(self, active):

        self.keyboard_active = active

        self._refresh_toggle_states()

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

    # ---------------------------------
    # Functions description / minimize / settings
    #
    # btn_functions opens InfoWindow, btn_window_settings opens
    # SettingsWindow — separate standalone (non-modal, no parent) windows,
    # reused rather than reopened on repeat clicks.
    # ---------------------------------

    def _on_functions_clicked(self):

        self._publish_ui_event("ui_open_functions_description", {})

        if self._info_window is None:
            self._info_window = InfoWindow()

        self._info_window.show()
        self._info_window.raise_()
        self._info_window.activateWindow()

    def _on_minimize_to_bar_clicked(self):

        self._publish_ui_event("ui_minimize_to_bar_requested", {})

        self.hide()

    def _on_settings_clicked(self):

        if self._settings_window is None:
            self._settings_window = SettingsWindow(self.event_bus)

        self._settings_window.show()
        self._settings_window.raise_()
        self._settings_window.activateWindow()

    # Full app quit, not just hiding — same event FloatingStatusBar's
    # close button publishes; main.py stops every backend module on it.
    def _on_close_clicked(self):

        self._publish_ui_event("ui_quit_requested", {})

        self.close()


if __name__ == "__main__":

    # Hot-reload dev preview (`python ui/main_window.py` only — never
    # runs when main.py imports MainWindow normally). Edit + save this
    # file: polls mtime, re-execs from disk, rebuilds the window at the
    # same screen position.
    import importlib.util

    from PyQt6.QtCore import QTimer

    THIS_FILE = os.path.abspath(__file__)

    RELOAD_POLL_MS = 400

    app = QApplication(sys.argv)

    state = {
        "window": None,
        "mtime": os.path.getmtime(THIS_FILE)
    }

    def _load_main_window_class():
        # Re-reads the file fresh by path — it's loaded as "__main__"
        # right now, so there's no normal module to importlib.reload.

        spec = importlib.util.spec_from_file_location(
            "main_window_live_reload",
            THIS_FILE
        )

        module = importlib.util.module_from_spec(spec)

        spec.loader.exec_module(module)

        return module.MainWindow

    def _rebuild_window():

        previous_position = (
            state["window"].pos() if state["window"] is not None else None
        )

        try:

            window_class = _load_main_window_class()

        except Exception as error:

            # Syntax error mid-edit — keep the last good window
            logger.warning(
                "[hot-reload] edit not applied yet, still showing "
                "the last good window: %s",
                error
            )

            return

        if state["window"] is not None:

            state["window"].close()

        new_window = window_class()

        if previous_position is not None:

            new_window.move(previous_position)

        new_window.show()

        state["window"] = new_window

        logger.info(
            "[hot-reload] window rebuilt — click a wheel icon to "
            "preview its glow ring, press D to toggle the layout "
            "debug overlay"
        )

    def _check_for_edits():

        mtime = os.path.getmtime(THIS_FILE)

        if mtime == state["mtime"]:
            return

        state["mtime"] = mtime

        _rebuild_window()

    _rebuild_window()

    reload_timer = QTimer()
    reload_timer.timeout.connect(_check_for_edits)
    reload_timer.start(RELOAD_POLL_MS)

    sys.exit(app.exec())
