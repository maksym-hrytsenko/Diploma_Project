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

# Rounds the actual OS-level window shape to match the reference photo's
# own rounded border, instead of the frameless window staying a hard
# rectangle with the rounded photo floating inside it — see
# _apply_rounded_mask.
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
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._radius = height // 2
        self._knob_diameter = height - 6

        self.knob = QFrame(self)
        self.knob.setGeometry(3, 3, self._knob_diameter, self._knob_diameter)
        self.knob.setStyleSheet(
            f"background-color: #FFFFFF; border-radius: {self._knob_diameter // 2}px;"
        )

        self.toggled.connect(self._on_toggled)

        # setChecked comes AFTER connecting toggled, not before — a
        # QPushButton starts unchecked, so setChecked(True) here is itself
        # a real state change that fires toggled(True) same as a click
        # would. Doing this earlier (before self.knob existed and before
        # toggled was connected) silently dropped that first emission:
        # _apply_style() below still painted the "on" gradient track (it
        # reads isChecked() directly), but the knob itself never moved off
        # its construction default (left) — so a switch that starts
        # checked=True and is never actually clicked shows an "on" track
        # with the knob stuck on the wrong side, while one the user has
        # clicked at least once looks correct. Routing the initial state
        # through the same _on_toggled a real click uses fixes both to
        # agree from the start.
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

# The "ui" source's signal names — matching config/mapping.json's "ui"
# section and config/fusion.json's per-mode "ui" trigger — that make a
# mode-icon click a real trigger SignalMapper acts on, exactly like a
# voice phrase or keyboard combo would (see CommandInterpreter._handle_ui).
MODE_UI_SIGNALS = {
    "flip": "FLIP_MODE",
    "presentation": "PRESENTATION_MODE",
    "call": "CALL_MODE",
    "cursor": "CURSOR_MODE"
}

# Anchors text-patch labels resize around, calibrated against the
# approved reference photo (01_main_menu.png) — see the module docstring.
SYSTEM_STATE_CENTER_X = 1057
CURRENT_MODE_ANCHOR_X = 760

# anchor_x/max_right_x per card for apply_fitted_text in
# _refresh_toggle_states — the "● Active"/"● Disabled" label under each
# toggle card's title (state_patch_camera/microphone/keyboard, built in
# _build_bottom_status below; y=745 there). anchor_x is the label's left
# edge, max_right_x the right edge it must not cross (apply_fitted_text
# shrinks the font to fit within that span). Moved right from their
# original position per request — to push these further right, raise
# both numbers in a pair together (so the available width, and therefore
# the font size apply_fitted_text picks, doesn't shrink); each card's own
# right edge is a safe upper bound (camera ends ~318, microphone ~599,
# keyboard ~874 — see dim_toggle_camera/microphone/keyboard below).
CARD_STATE_ANCHORS = {
    "camera": (165, 260),
    "microphone": (455, 545),
    "keyboard": (735, 825)
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

        # Kept as instance attributes (rather than a fresh instance per
        # click) so a second click on the gear/Functions-description
        # button raises the existing standalone window instead of opening
        # a duplicate — needed now that SettingsWindow/InfoWindow are
        # plain non-modal top-levels instead of a modal .exec() dialog.
        self._settings_window = None
        self._info_window = None

        self.setObjectName("main_window")
        self.setWindowTitle("Gesture & Voice Control")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(f"#main_window {{ background-color: {COLOR_BACKGROUND}; }}")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        # Lets the reference photo's own transparent rounded corners (it's
        # an RGBA PNG that already fades to alpha 0 right at its corners)
        # show real desktop through them instead of being flattened to a
        # solid COLOR_BACKGROUND square — required for _apply_rounded_mask
        # right below to actually look rounded rather than just clipping a
        # square-cornered image to a round window.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._apply_rounded_mask()

        self.mode_changed_signal.connect(self._on_mode_changed_from_bus)
        self.gesture_debug_signal.connect(self._on_gesture_debug)
        self.face_debug_signal.connect(self._on_face_debug)

        # LIVE LAYOUT DEBUG OVERLAY — press D (while this window has focus)
        # to toggle labeled outlines over every registered button/icon/glow
        # ring, so their real on-screen position/size can be checked
        # against the reference photo at a glance instead of guessing from
        # numbers alone. _register_debug_element calls are sprinkled right
        # after each element's construction below; see _build_debug_overlay
        # and keyPressEvent. Works both under main.py's real app and the
        # standalone hot-reload preview at the bottom of this file — press
        # D again after every hot-reload to bring the overlay back.
        self._debug_elements = []
        self._debug_overlay_widgets = []
        self._debug_overlay_visible = False

        self._build_background()
        self._build_header()
        self._build_camera_preview()
        self._build_control_wheel()
        self._build_bottom_status()

        self._refresh_system_power()
        self._refresh_mode_buttons()
        self._refresh_toggle_states()

        self._build_debug_overlay()

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
        self._latest_face_landmarks = data.get("face_landmarks")

        if self.camera_active and self.video_label.isVisible():
            self._refresh_face_status()

    def _on_gesture_debug(self, data):

        frame = data.get("frame")

        if frame is None or not self.camera_active:
            return

        self._last_video_update = time.time()

        pixmap = self._build_video_frame_pixmap(frame, data)

        self.video_label.setPixmap(pixmap)

        if not self.video_label.isVisible():

            self.video_label.show()
            self.icon_camera_placeholder.hide()
            self.label_camera_placeholder_title.hide()
            self.label_camera_placeholder_hint.hide()

        self._refresh_face_status()

    # A single clipped QPainter session — the frame, the tracking overlay
    # and the detected-command caption are all painted together so the
    # rounded-square clip applies to every one of them alike. Painting
    # the overlay/caption in a later, separate QPainter pass (no clip set)
    # would let them draw straight through the transparent rounded
    # corners this same clip leaves in the base frame.
    def _build_video_frame_pixmap(self, frame, data):

        width, height = self.video_area[2], self.video_area[3]

        cropped = self._frame_to_rect_pixmap(frame, width, height)

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

        self._paint_hand_landmarks(painter, width, height, data)
        self._paint_face_landmarks(painter, width, height)
        self._paint_gesture_caption(painter, width, height, data)

        painter.end()

        return canvas

    def _frame_to_rect_pixmap(self, frame, target_width, target_height):

        frame = np.ascontiguousarray(frame)
        source_height, source_width = frame.shape[:2]

        image = QImage(
            frame.data, source_width, source_height, source_width * 3,
            QImage.Format.Format_BGR888
        ).copy()

        # Crop to the target aspect ratio out of the SOURCE resolution
        # first (integer math on the real width/height, so it lands
        # exactly on a whole pixel every time), then scale that already-
        # matching-aspect crop up/down to exactly target_width x
        # target_height. Scaling first and cropping the scaled result
        # could round the scaled size to one pixel short of the target,
        # making the crop offset negative and leaving a sliver of the
        # frame unpainted — cropping first, on exact source pixels,
        # can't do that.
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

        cropped_image = image.copy(crop_x, crop_y, crop_width, crop_height)

        return QPixmap.fromImage(cropped_image).scaled(
            target_width, target_height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

    # Every MediaPipe hand landmark point (not just the single tracked
    # fingertip the old finger/anchor/velocity-vector overlay drew) — the
    # full set GestureRecognizer already reads off its model result and
    # now publishes verbatim in "hand_landmarks" (see gesture_recognizer.
    # py's _publish_debug). None whenever no hand is currently tracked.
    def _paint_hand_landmarks(self, painter, width, height, data):

        hand_landmarks = data.get("hand_landmarks")

        if not hand_landmarks:
            return

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLOR_ACCENT_BLUE))

        radius = 3

        for x, y in hand_landmarks:

            point_x = int(x * width)
            point_y = int(y * height)

            painter.drawEllipse(
                point_x - radius, point_y - radius, radius * 2, radius * 2
            )

    # Every MediaPipe face landmark point, the same idea as
    # _paint_hand_landmarks but for FaceRecognizer's "face_landmarks" (see
    # face_recognizer.py's _publish_debug) and in a different color so the
    # two point clouds stay visually distinct on the same frame. Reads
    # self._latest_face_landmarks rather than a "data" param, since
    # face_debug and gesture_debug are two independent events arriving at
    # their own pace — the most recently received face reading is drawn
    # on top of whichever camera frame gesture_debug is currently
    # painting, same pattern _refresh_face_status already uses for
    # self._latest_face_pitch.
    def _paint_face_landmarks(self, painter, width, height):

        if not self._latest_face_landmarks:
            return

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLOR_GLOW_VIOLET))

        radius = 1

        for x, y in self._latest_face_landmarks:

            point_x = int(x * width)
            point_y = int(y * height)

            painter.drawEllipse(
                point_x - radius, point_y - radius, radius * 2, radius * 2
            )

    # The command the system might capture, labeled directly on the
    # frame rather than in a separate box below it.
    def _paint_gesture_caption(self, painter, width, height, data):

        gesture_name = data.get("gesture_name")
        confidence = data.get("confidence")

        if gesture_name:

            confidence_text = (
                f" · {confidence * 100:.0f}%" if confidence is not None else ""
            )
            caption_text = f"Detected: {gesture_name}{confidence_text}"

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

    def _publish_ui_event(self, event_type, data):

        if self.event_bus is not None:
            self.event_bus.publish(event_type, data)

    # Gives the frameless window itself a rounded OS-level shape (a hard
    # clip via setMask, not just painted rounded corners) — otherwise a
    # frameless QWidget stays a plain rectangle no matter how rounded its
    # painted content looks, and the reference photo's own rounded border
    # would just float inside a square window. WINDOW_WIDTH/HEIGHT are
    # fixed (see setFixedSize above), so this only needs to run once.
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
        """Called right after building any button/toggle/glow ring that
        has an on-screen position worth checking against the reference
        photo. Purely bookkeeping — appends to a list _build_debug_overlay
        reads once, after every element for this window exists.
        """

        self._debug_elements.append((name, widget))

    def _build_debug_overlay(self):
        """Builds (hidden) one labeled outline per registered element,
        exactly on top of that element's own geometry — see
        _register_debug_element call sites throughout _build_header/
        _build_control_wheel/_build_bottom_status for what gets covered.
        Toggled on/off as a whole by keyPressEvent (key "D"). Every piece
        here is WA_TransparentForMouseEvents so the overlay never blocks
        the real button underneath — it is purely a visual/printed aid.
        """

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

            # Sits just above the outline, unless that would run off the
            # window's top edge — drop it just inside the box instead.
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

        print(f"[layout-debug] overlay {state} — {len(self._debug_elements)} elements")

        if self._debug_overlay_visible:

            for name, widget in self._debug_elements:

                geometry = widget.geometry()

                print(
                    f"  {name}: x={geometry.x()} y={geometry.y()} "
                    f"w={geometry.width()} h={geometry.height()}"
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

        # BUTTON: header minimize (window) — args after object_name are
        # x, y, width, height, radius. Edit those 5 numbers to reposition/
        # resize this button.
        self.btn_window_minimize = make_transparent_button(
            self, "btn_window_minimize", 1198, 39, 52, 47, 13
        )
        self.btn_window_minimize.clicked.connect(self.showMinimized)
        self._register_debug_element("btn_window_minimize", self.btn_window_minimize)

        # BUTTON: header settings (opens Settings dialog) — x, y, width,
        # height, radius.
        self.btn_window_settings = make_transparent_button(
            self, "btn_window_settings", 1268, 39, 52, 47, 13
        )
        self.btn_window_settings.clicked.connect(self._on_settings_clicked)
        self._register_debug_element("btn_window_settings", self.btn_window_settings)

        # BUTTON: header close (quits the whole app) — x, y, width,
        # height, radius.
        self.btn_window_close = make_transparent_button(
            self, "btn_window_close", 1337, 39, 53, 47, 13
        )
        self.btn_window_close.clicked.connect(self._on_close_clicked)
        self._register_debug_element("btn_window_close", self.btn_window_close)

    # ---------------------------------
    # Camera preview
    # ---------------------------------

    def _build_camera_preview(self):

        # Fills the entire panel_camera_preview rounded rectangle (inset
        # by a few px so this border sits just inside the reference
        # photo's own matching border instead of doubling up on top of
        # it) — the photo's own placeholder content in this area was
        # cleared out to make room for this (see render_camera_icon's
        # docstring). The detected-command caption paints directly onto
        # the live frame itself (see _build_video_frame_pixmap). No
        # separate "Camera: Active/Disabled" chip here any more — that
        # state is already shown on the Camera toggle card below.
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

        # Vertically centers the icon/title/hint block (92 + 8 + 26 + 8
        # + 22 = 156px tall) within rect_height.
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

    # ---------------------------------
    # Circular control wheel
    # ---------------------------------

    def _build_control_wheel(self):

        # GLOW RINGS: the visual indicator that a mode is currently
        # active — a soft violet ring drawn behind/around that mode's
        # icon (see make_glow_ring above; hidden by default, shown by
        # _refresh_mode_buttons for whichever name matches self.active_mode
        # via mode_glow_rings below). Args are x, y, width, height —
        # keep width == height so it stays a circle, and each one should
        # stay centered on its matching wheel button
        # (btn_mode_flip/btn_presentation/btn_call_mode/btn_cursor_mode,
        # built further down) — i.e. same center point, this ring just a
        # few px larger all around than that button's own 96x96.
        # TODO: reposition/resize here if a ring stops lining up with its
        # icon.
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

        # SYSTEM-OFF GREY CIRCLE: shown over the hub instead of the glow
        # when system_on is False (see _refresh_system_power). Its x/y/w/h
        # must match btn_system_power's own 4 numbers right below exactly
        # (same circle, same center) — they drifted apart in an earlier
        # edit (978,305,158,158 vs the button's 993,298,158,160), which is
        # why the grey circle looked off-center from the actual hub. Edit
        # both together from now on: whatever you set btn_system_power's
        # x/y/w/h to, copy the same 4 numbers here.
        self.system_dim_overlay = make_dim_overlay(self, 993, 298, 158, 160, 79)
        self._register_debug_element("system_dim_overlay", self.system_dim_overlay)

        # BUTTON: central System ON/OFF (control wheel hub) — x, y, width,
        # height, radius. Keep width == height so it stays a circle, and
        # radius == width / 2. See system_dim_overlay right above — keep
        # its x/y/w/h identical to this button's.
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

        # ICON SIZE, all four wheel-mode buttons below: the icon graphic
        # itself is baked into the reference photo's pixels (there is no
        # code-side icon image to resize) — what you CAN resize here is
        # the circular click-region/highlight-boundary drawn around it,
        # which is what visually reads as "how big the icon is". For each
        # button below, the 3rd/4th numbers (currently 98, 98) are that
        # circle's width/height — keep them equal so it stays a circle,
        # and the 5th number (radius, currently 49) equal to half of
        # them. The matching glow ring in mode_glow_rings above (e.g.
        # glow_mode_flip for btn_mode_flip) is a SEPARATE element sized
        # independently — if you resize a button here, widen its glow
        # ring by roughly the same amount so the glow still reads as a
        # ring around the (new) button size instead of matching the old
        # one.
        #
        # BUTTON: wheel mode — Flip/Mode (top icon) — x, y, width, height,
        # radius.
        self.btn_mode_flip = make_transparent_button(
            self, "btn_mode_flip", 1022, 138, 98, 98, 49
        )
        self.btn_mode_flip.clicked.connect(lambda: self._on_mode_clicked("flip"))
        self._register_debug_element("btn_mode_flip", self.btn_mode_flip)

        # BUTTON: wheel mode — Presentation (left icon) — x, y, width,
        # height, radius.
        self.btn_presentation = make_transparent_button(
            self, "btn_presentation", 827, 329, 98, 98, 49
        )
        self.btn_presentation.clicked.connect(lambda: self._on_mode_clicked("presentation"))
        self._register_debug_element("btn_presentation", self.btn_presentation)

        # BUTTON: wheel mode — Call Mode (right icon) — x, y, width,
        # height, radius.
        self.btn_call_mode = make_transparent_button(
            self, "btn_call_mode", 1220, 329, 98, 98, 49
        )
        self.btn_call_mode.clicked.connect(lambda: self._on_mode_clicked("call"))
        self._register_debug_element("btn_call_mode", self.btn_call_mode)

        # BUTTON: wheel mode — Cursor (bottom icon) — x, y, width, height,
        # radius.
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

        # The wheel's four icon labels ("Mode" / "Presentation" /
        # "Call Mode" / "Cursor") used to be covered with blank patches
        # here, because the reference photo baked in stale draft text
        # ("Gesture" / "Voice" / "Control") at those spots. The current
        # photo (images/01_main_menu.png) no longer has any text there at
        # all, so nothing needs covering any more — those patches were
        # removed rather than left in as now-pointless blank rectangles.
        # MODE_DISPLAY_NAMES is still the single source of truth for a
        # mode's display name, used by the "Current mode: …" line below
        # and by InfoWindow.

        self.current_mode_patch = make_patch_label(self, 760, 574, 320, 20)
        self.label_current_mode = make_label(
            self.current_mode_patch, "", 0, 0, 320, 20, COLOR_TEXT_DARK, size=13
        )

        # Blank cover only, per request — the reference photo bakes in an
        # "Active modules: …" line right under the current-mode text (with
        # the old draft module names "Gesture"/"Voice"), and removing the
        # patch entirely would leave that stale photo text exposed instead
        # of actually removing it. No label is attached here on purpose:
        # nothing is drawn back on top.
        make_patch_label(self, 760, 597, 285, 18)

    # ---------------------------------
    # Bottom status panel
    # ---------------------------------

    def _build_bottom_status(self):

        self.dim_toggle_camera = make_dim_overlay(self, 53, 678, 265, 153, 25)
        self.dim_toggle_microphone = make_dim_overlay(self, 344, 678, 255, 153, 25)
        self.dim_toggle_keyboard = make_dim_overlay(self, 624, 678, 250, 153, 25)

        # These three patch/label pairs are the "● Active" / "● Disabled"
        # text under each toggle card's title. The x/width given here only
        # matter before the very first _refresh_toggle_states() call at
        # the end of __init__ — every refresh after that (including the
        # first one) repositions/resizes the patch via apply_fitted_text
        # using CARD_STATE_ANCHORS above, so CARD_STATE_ANCHORS is the
        # actual place to edit left/right position. The y below (745) is
        # the one thing apply_fitted_text does NOT touch — move it here if
        # the label needs to shift up/down instead of left/right.
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

        # BUTTON: Camera toggle switch (bottom-left card) — x, y, width,
        # height (ToggleSwitch has no separate radius arg — it is always
        # a full pill, i.e. radius = height / 2).
        self.switch_camera = ToggleSwitch(
            self, "switch_camera", 230, 775, 52, 28, self.camera_active
        )
        self.switch_camera.toggled.connect(self._on_camera_toggled)
        self._register_debug_element("switch_camera", self.switch_camera)

        # BUTTON: Microphone toggle switch (bottom-middle card) — x, y,
        # width, height.
        self.switch_microphone = ToggleSwitch(
            self, "switch_microphone", 513, 775, 52, 28, self.microphone_active
        )
        self.switch_microphone.toggled.connect(self._on_microphone_toggled)
        self._register_debug_element("switch_microphone", self.switch_microphone)

        # BUTTON: Keyboard toggle switch (bottom-right card) — x, y,
        # width, height.
        self.switch_keyboard = ToggleSwitch(
            self, "switch_keyboard", 791, 775, 52, 28, self.keyboard_active
        )
        self.switch_keyboard.toggled.connect(self._on_keyboard_toggled)
        self._register_debug_element("switch_keyboard", self.switch_keyboard)

        # BUTTON: "Functions description" (opens Functions dialog) —
        # x, y, width, height, radius.
        self.btn_functions = make_transparent_button(
            self, "btn_functions", 902, 716, 234, 73, 18
        )
        self.btn_functions.clicked.connect(self._on_functions_clicked)
        self._register_debug_element("btn_functions", self.btn_functions)

        # BUTTON: "Minimize to bar" (hides MainWindow, shows the floating
        # status bar) — x, y, width, height, radius.
        self.btn_minimize_to_bar = make_transparent_button(
            self, "btn_minimize_to_bar", 1158, 715, 232, 75, 18
        )
        self.btn_minimize_to_bar.clicked.connect(self._on_minimize_to_bar_clicked)
        self._register_debug_element("btn_minimize_to_bar", self.btn_minimize_to_bar)

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

    # Sends a real request through the same pipeline a voice phrase or
    # keyboard combo would use (CommandInterpreter -> MultimodalFusion ->
    # SignalMapper) rather than switching self.active_mode directly —
    # SignalMapper is still the only module that decides the mode
    # (CLAUDE.md); this only asks. The click's visible effect (glow ring,
    # current-mode label, QuickCommandOverlay, etc.) only happens once
    # the resulting mode_changed event comes back — see
    # _on_mode_changed_from_bus.
    def _on_mode_clicked(self, mode_name):

        if self.active_mode == mode_name:

            signal = "EXIT_MODE"

        else:

            signal = MODE_UI_SIGNALS[mode_name]

        if self.event_bus is None:

            # No backend to round-trip through — this only happens in the
            # standalone hot-reload preview at the bottom of this file
            # (constructed with no event_bus), where SignalMapper never
            # runs and _on_mode_changed_from_bus would otherwise never
            # fire. Simulate the same end state locally purely so glow
            # rings / "Current mode" are actually visible while checking
            # wheel-button layout live — see _on_mode_changed_from_bus for
            # the real (event_bus-driven) path this mirrors.
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
    # The bottom-panel "Functions description" button opens InfoWindow
    # (descriptions only) and the header gear icon opens SettingsWindow
    # (configurable values only) — two separate standalone windows, not
    # one merged dialog (see ui/dialogs.py's module docstring). Both are
    # plain non-modal top-levels with no parent, so each gets its own
    # native macOS title bar and close button instead of appearing as a
    # sheet attached to this window; a single instance is kept and raised
    # rather than reopened, so repeat clicks don't spawn duplicates.
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
            self._settings_window = SettingsWindow()

        self._settings_window.show()
        self._settings_window.raise_()
        self._settings_window.activateWindow()

    # Closing the main window is a full quit, not just hiding this
    # widget — "ui_quit_requested" is the same event FloatingStatusBar's
    # own close (X) button publishes, and main.py's loop reacts to it by
    # stopping every backend module (see main.py's shutdown_requested).
    def _on_close_clicked(self):

        self._publish_ui_event("ui_quit_requested", {})

        self.close()


if __name__ == "__main__":

    # Hot-reload dev preview — only runs when this file is executed
    # directly (`python ui/main_window.py`), never when main.py imports
    # MainWindow normally. Leave the file running, edit any BUTTON
    # comment's numbers (or anything else in this file), hit save: this
    # polls the file's mtime, re-execs it fresh from disk, swaps in the
    # rebuilt MainWindow class, and reopens the window at the same
    # screen position — no manual restart, no retyping the run command.
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

        # spec_from_file_location + exec_module re-reads and re-runs the
        # file straight from disk by path, rather than relying on
        # importlib.reload(sys.modules[...]) — this file is loaded as
        # "__main__" right now, not under its normal "ui.main_window"
        # name, so there is no regular module object to reload here.
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

            # A syntax error or typo mid-edit should not kill the dev
            # preview — keep showing the last good window and try again
            # on the next save.
            print(
                f"[hot-reload] edit not applied yet, still showing the last good window: {error}"
            )

            return

        if state["window"] is not None:

            state["window"].close()

        new_window = window_class()

        if previous_position is not None:

            new_window.move(previous_position)

        new_window.show()

        state["window"] = new_window

        print("[hot-reload] window rebuilt — click a wheel icon to preview its glow "
              "ring, press D to toggle the layout debug overlay")

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
