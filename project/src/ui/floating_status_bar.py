"""Floating status bar (minimized view).

Shown after "Minimize to bar" in MainWindow; hidden again once its own
expand button is clicked. Renders the approved reference photo
(images/02_floating_status_bar.png) as-is — camera/microphone/keyboard
icons, then the four wheel-mode icons, then the expand arrow, exactly as
laid out in that photo — and overlays only these kinds of things on top of
it:

- A translucent grey "dim" chip (the same rgba(180, 182, 200, 130) treatment
  MainWindow's own bottom-panel toggle cards use — see make_dim_overlay in
  main_window.py) over camera/microphone/keyboard whenever that input isn't
  currently active — so the bar reads its true state from EventBus instead
  of the photo's static all-active look. Also dims the three mode icons
  that are NOT the active one, but only while some mode IS active — with
  no active mode, none of the four get dimmed either, since there is
  nothing to contrast them against.
- A yellow ring around whichever mode icon IS the active mode — the only
  marker used for "this one is active"; with no active mode, no icon gets
  a ring. Only the mode icons ever get a ring; module icons only ever get
  dimmed, never ringed, since being "on" is their default/expected state
  rather than something to call out.
- The single expand button already drawn into the photo. This is
  deliberately the bar's only interactive control — closing the app is
  only reachable through MainWindow's own header close button once
  expanded back, not from here.

Both chip kinds are purely informative — none of them are clickable.

Icon centers below were measured directly from the source PNG (column/row
ink-density analysis, since the AI-generated photo's actual icon spacing
doesn't match the idealized coordinate table in
docs/UI_SPEC.txt section 6) and then
scaled into this widget's render size.

The source PNG (images/02_floating_status_bar.png) was replaced with a
version cropped tight to the pill's own edges — no whitespace margin
around it any more, unlike the original (see BAR_WIDTH/BAR_HEIGHT below,
sized to the new image's own aspect ratio so it isn't stretched/squashed).
"""

import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QPixmap
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QFrame,
    QPushButton,
    QGraphicsDropShadowEffect
)

from ui.native_window import configure_overlay_window

BAR_IMAGE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "images",
    "02_floating_status_bar.png"
)

# The source PNG is 2287x249 (aspect ratio ~9.18:1), cropped tight to the
# pill with no padding. BAR_WIDTH/BAR_HEIGHT is that aspect ratio at half
# the previous on-screen size (was 588x64) — per request, everything below
# (ICON_CENTERS, chip sizes, expand button geometry) is that same previous
# layout scaled by exactly 1/2, so nothing drifts out of alignment with
# the image. If the source image is replaced again, recompute BAR_WIDTH =
# round(BAR_HEIGHT * new_width / new_height) and rescale everything below
# from fresh ink-density measurements (see floating_status_bar's own
# measurement notes in past commits), not by scaling old numbers again.
BAR_HEIGHT = 32
BAR_WIDTH = 294

WINDOW_WIDTH = BAR_WIDTH
WINDOW_HEIGHT = BAR_HEIGHT

# Screen position: top-right corner, matching the approved doc's
# "screen_width - 460, 32" — comfortably clear of the macOS menu bar
# (top-left is where the Apple menu / app menu live, so a top-left overlay
# would sit awkwardly under them) and, combined with native_window.py's
# CanJoinAllSpaces + NSScreenSaverWindowLevel configuration below, this
# keeps the bar visible above every app and every Space while it's shown.
SCREEN_MARGIN_RIGHT = 40
SCREEN_MARGIN_TOP = 32

# (center_x, center_y) of each icon's ink, in this widget's BAR_WIDTH x
# BAR_HEIGHT space — half of the previous (588x64-space) centers, measured
# off the current 2287x249 source PNG. To move a single icon's dim/
# highlight treatment, edit its (x, y) pair here — everything below reads
# from this dict, nothing else needs to change.
ICON_CENTERS = {
    "camera": (24, 16),
    "microphone": (55, 16),
    "keyboard": (87, 16),
    "flip": (129, 16),
    "presentation": (162, 16),
    "call": (198, 16),
    "cursor": (232, 16)
}

MODULE_NAMES = ("camera", "microphone", "keyboard")
MODE_NAMES = ("flip", "presentation", "call", "cursor")

# The three tiers of the hybrid voice recognizer (see the matching
# SPEECH_TIERS_REQUIRED comment in main_window.py) — the microphone icon
# only sheds its dim chip once every one of these has reported ready via
# "speech_model_ready" events, even if the mic toggle itself is on.
SPEECH_TIERS_REQUIRED = frozenset(("exact", "semantic", "llm"))

# DIM CHIP — the grey "not active/not working" wash (see _build_dim_chips
# and _refresh_state). SIZE is the square box's side length in px;
# RADIUS is edited to match SIZE // 2 so it renders as a full circle,
# same shape language as the yellow highlight ring below (rather than the
# rounded-square look this used to have, which visually clashed with the
# ring). To change how big or round this looks: SIZE controls how much of
# the icon it covers, RADIUS controls corner roundness (RADIUS == SIZE//2
# is a circle; smaller RADIUS is a rounded square).
DIM_CHIP_SIZE = 19
DIM_CHIP_RADIUS = DIM_CHIP_SIZE // 2

# HIGHLIGHT RING — the yellow "this mode is active" ring (see
# _build_highlight_chips and _refresh_state). SIZE/RADIUS follow the same
# rule as DIM_CHIP above (RADIUS == SIZE // 2 for a full circle). COLOR is
# the ring's stroke/glow color — change it here to recolor every active-
# mode ring at once.
HIGHLIGHT_CHIP_SIZE = 24
HIGHLIGHT_CHIP_RADIUS = HIGHLIGHT_CHIP_SIZE // 2
HIGHLIGHT_COLOR = "#FFC93C"


class FloatingStatusBar(QWidget):

    mode_changed_signal = pyqtSignal(object)
    try_mode_changed_signal = pyqtSignal(bool)
    camera_toggle_signal = pyqtSignal(bool)
    microphone_toggle_signal = pyqtSignal(bool)
    keyboard_toggle_signal = pyqtSignal(bool)
    speech_model_ready_signal = pyqtSignal(str)

    def __init__(self, event_bus=None):

        super().__init__()

        self.event_bus = event_bus

        # Mirrors MainWindow's own initial module state (camera/microphone/
        # keyboard start active) so the bar agrees with the main window
        # the moment both exist, before any toggle has fired.
        self.camera_active = True
        self.microphone_active = True
        self.keyboard_active = True
        self.active_mode = None
        self.try_mode_active = False

        # Mirrors MainWindow's own speech_ready_tiers — see this module's
        # SPEECH_TIERS_REQUIRED comment.
        self.speech_ready_tiers = set()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Showing/raising this bar must never activate this app — it stays
        # on top of a full-screen presentation by design (see
        # configure_overlay_window below), and activating on show would
        # un-frontmost that presentation the same way an activating click
        # would (see setBecomesKeyOnlyIfNeeded_ in native_window.py).
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)

        self.mode_changed_signal.connect(self._on_mode_changed_from_bus)
        self.try_mode_changed_signal.connect(self._on_try_mode_changed_from_bus)
        self.camera_toggle_signal.connect(self._on_camera_toggled_from_bus)
        self.microphone_toggle_signal.connect(self._on_microphone_toggled_from_bus)
        self.keyboard_toggle_signal.connect(self._on_keyboard_toggled_from_bus)
        self.speech_model_ready_signal.connect(self._on_speech_model_ready_from_bus)

        self._build_background()
        self._build_dim_chips()
        self._build_highlight_chips()
        self._build_expand_button()

        self._refresh_state()

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

            # Read-only, same pattern as MainWindow's own mode_changed/
            # toggle subscriptions: this bar only ever reflects state that
            # SignalMapper (mode) or MainWindow's toggle switches (module
            # on/off intent) already decided — it never decides anything
            # itself.
            self.event_bus.subscribe("mode_changed", self._handle_mode_changed)
            self.event_bus.subscribe("try_mode_changed", self._handle_try_mode_changed)
            self.event_bus.subscribe("ui_camera_toggle", self._handle_camera_toggle)
            self.event_bus.subscribe("ui_microphone_toggle", self._handle_microphone_toggle)
            self.event_bus.subscribe("ui_keyboard_toggle", self._handle_keyboard_toggle)

            # Same per-tier readiness events MainWindow listens for — see
            # this module's SPEECH_TIERS_REQUIRED comment.
            self.event_bus.subscribe("speech_model_ready", self._handle_speech_model_ready)

    def stop(self):

        if self.event_bus is not None:

            self.event_bus.unsubscribe(
                "ui_minimize_to_bar_requested",
                self._handle_minimize_requested
            )

            self.event_bus.unsubscribe("mode_changed", self._handle_mode_changed)
            self.event_bus.unsubscribe("try_mode_changed", self._handle_try_mode_changed)
            self.event_bus.unsubscribe("ui_camera_toggle", self._handle_camera_toggle)
            self.event_bus.unsubscribe("ui_microphone_toggle", self._handle_microphone_toggle)
            self.event_bus.unsubscribe("ui_keyboard_toggle", self._handle_keyboard_toggle)
            self.event_bus.unsubscribe("speech_model_ready", self._handle_speech_model_ready)

    def _handle_minimize_requested(self, event):

        self._reposition()
        self.show()
        self.raise_()

    # ---------------------------------
    # State (marshaled onto the Qt main thread, same pattern as
    # MainWindow.mode_changed_signal — EventBus callbacks may arrive on a
    # non-Qt thread, e.g. mode_changed from SignalMapper).
    # ---------------------------------

    def _handle_mode_changed(self, event):

        self.mode_changed_signal.emit(event.get("data", {}).get("mode"))

    def _handle_camera_toggle(self, event):

        self.camera_toggle_signal.emit(bool(event.get("data", {}).get("active", True)))

    def _handle_microphone_toggle(self, event):

        self.microphone_toggle_signal.emit(bool(event.get("data", {}).get("active", True)))

    def _handle_keyboard_toggle(self, event):

        self.keyboard_toggle_signal.emit(bool(event.get("data", {}).get("active", True)))

    def _handle_try_mode_changed(self, event):

        self.try_mode_changed_signal.emit(bool(event.get("data", {}).get("active", False)))

    def _on_mode_changed_from_bus(self, mode):

        self.active_mode = mode
        self._refresh_state()

    def _on_try_mode_changed_from_bus(self, active):

        self.try_mode_active = active
        self._refresh_state()

    def _on_camera_toggled_from_bus(self, active):

        self.camera_active = active
        self._refresh_state()

    def _on_microphone_toggled_from_bus(self, active):

        self.microphone_active = active
        self._refresh_state()

    def _on_keyboard_toggled_from_bus(self, active):

        self.keyboard_active = active
        self._refresh_state()

    def _handle_speech_model_ready(self, event):

        tier = event.get("data", {}).get("tier")

        if tier:
            self.speech_model_ready_signal.emit(tier)

    def _on_speech_model_ready_from_bus(self, tier):

        self.speech_ready_tiers.add(tier)
        self._refresh_state()

    def _refresh_state(self):

        # Same gate as MainWindow's microphone card — "on" per the user's
        # own toggle isn't enough, every recognition tier must also have
        # reported ready (see SPEECH_TIERS_REQUIRED).
        microphone_ready = (
            self.microphone_active
            and SPEECH_TIERS_REQUIRED <= self.speech_ready_tiers
        )

        self.dim_chips["camera"].setVisible(not self.camera_active)
        self.dim_chips["microphone"].setVisible(not microphone_ready)
        self.dim_chips["keyboard"].setVisible(not self.keyboard_active)

        for mode_name in MODE_NAMES:

            is_active = mode_name == self.active_mode

            # No mode active at all -> nothing marked on any of the four
            # (no dim, no ring). A mode active -> yellow ring on that one,
            # dim on the other three for contrast.
            self.dim_chips[mode_name].setVisible(
                self.active_mode is not None and not is_active
            )
            self.highlight_chips[mode_name].setVisible(is_active)

        mode_label = self.active_mode.title() if self.active_mode else "Standby"

        active_inputs = [
            name
            for name, active in (
                ("Camera", self.camera_active),
                ("Microphone", microphone_ready),
                ("Keyboard", self.keyboard_active)
            )
            if active
        ]
        inputs_label = ", ".join(active_inputs) if active_inputs else "None"

        # No spare pixel-measured icon slot to safely add a new chip to
        # (see this file's own docstring on how fragile ICON_CENTERS is
        # without being able to render and re-measure it) — the tooltip
        # is the low-risk way to still surface Try Mode's state here.
        try_mode_label = "\nTry Mode: ON" if self.try_mode_active else ""

        self.setToolTip(
            f"Active input: {inputs_label}\nMode: {mode_label}{try_mode_label}"
        )

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

    def _build_dim_chips(self):

        self.dim_chips = {}

        for name, (center_x, center_y) in ICON_CENTERS.items():

            chip = QFrame(self)
            chip.setGeometry(
                center_x - DIM_CHIP_SIZE // 2,
                center_y - DIM_CHIP_SIZE // 2,
                DIM_CHIP_SIZE,
                DIM_CHIP_SIZE
            )
            chip.setStyleSheet(
                "background-color: rgba(180, 182, 200, 145);"
                f" border-radius: {DIM_CHIP_RADIUS}px;"
            )
            chip.hide()

            self.dim_chips[name] = chip

    def _build_highlight_chips(self):

        self.highlight_chips = {}

        for name in MODE_NAMES:

            center_x, center_y = ICON_CENTERS[name]

            chip = QFrame(self)
            chip.setGeometry(
                center_x - HIGHLIGHT_CHIP_SIZE // 2,
                center_y - HIGHLIGHT_CHIP_SIZE // 2,
                HIGHLIGHT_CHIP_SIZE,
                HIGHLIGHT_CHIP_SIZE
            )
            chip.setStyleSheet(
                "background-color: transparent;"
                f" border: 2.5px solid {HIGHLIGHT_COLOR};"
                f" border-radius: {HIGHLIGHT_CHIP_RADIUS}px;"
            )

            effect = QGraphicsDropShadowEffect(chip)
            effect.setBlurRadius(14)
            effect.setOffset(0, 0)
            effect.setColor(QColor(HIGHLIGHT_COLOR))
            chip.setGraphicsEffect(effect)

            chip.hide()

            self.highlight_chips[name] = chip

    def _build_expand_button(self):

        self.btn_expand = QPushButton(self)
        self.btn_expand.setObjectName("floating_btn_expand")
        self.btn_expand.setGeometry(268, 4, 25, 25)
        self.btn_expand.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_expand.setToolTip("Open main window")

        self.btn_expand.setStyleSheet(
            "QPushButton#floating_btn_expand {"
            " background: transparent;"
            " border: none;"
            " border-radius: 12px;"
            "}"
            "QPushButton#floating_btn_expand:hover {"
            " background-color: rgba(139, 61, 255, 35);"
            "}"
        )
        self.btn_expand.clicked.connect(self._on_expand_clicked)

    def _reposition(self):

        screen = QGuiApplication.primaryScreen()

        if screen is None:
            return

        screen_geometry = screen.geometry()

        self.move(
            screen_geometry.width() - WINDOW_WIDTH - SCREEN_MARGIN_RIGHT,
            SCREEN_MARGIN_TOP
        )

    # ---------------------------------
    # Actions
    # ---------------------------------

    def _on_expand_clicked(self):

        self.hide()

        if self.event_bus is not None:
            self.event_bus.publish("ui_expand_requested", {})
