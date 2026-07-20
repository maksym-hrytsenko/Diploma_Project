"""Settings window and Info window.

Two separate, independent top-level windows opened from MainWindow: the
header gear icon opens SettingsWindow (only configurable values, each with
an (i) button explaining what it changes, plus "Reset to defaults"); the
bottom-panel "Functions description" button opens InfoWindow (only
descriptions of every mode/gesture/voice command, no settings). They used
to be a single merged window — split apart per request, since "what can I
tune" and "what does this do" are different tasks for different moments.

Both are plain QWidget top-levels (not QDialog.exec()) constructed with no
parent, so macOS renders them as normal standalone app windows with their
own native title bar and close button, instead of a modal sheet attached
under MainWindow's title bar.

Built in the same light/rounded/purple-blue visual language as MainWindow,
anchored by one big rounded panel styled exactly like MainWindow's own
panels (panel_camera_preview / panel_status: white fill, thin purple-blue
border, soft glow) — see make_glass_panel. Deliberately self-contained (own
palette constants, own small widget helpers) rather than importing from
main_window.py, to avoid a circular import — MainWindow opens these on
demand.
"""

import json
import os
import subprocess
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLineEdit,
    QTextEdit,
    QSpinBox,
    QDoubleSpinBox,
    QGraphicsDropShadowEffect,
    QMessageBox
)

from config.config_loader import load_system_config

COLOR_BACKGROUND = "#F4F6FB"
COLOR_PANEL = "#FFFFFF"
COLOR_PANEL_ALT = "#F9FAFF"
COLOR_TEXT_DARK = "#172A5A"
COLOR_TEXT_SECONDARY = "#6D7285"
COLOR_ACCENT_PURPLE = "#8B3DFF"
COLOR_ACCENT_BLUE = "#4F7BFF"

SYSTEM_CONFIG_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "system.json")
)


def styled_window(window, title, width, height):

    window.setWindowTitle(title)
    window.setFixedSize(width, height)
    window.setStyleSheet(f"background-color: {COLOR_BACKGROUND};")


def make_action_button(parent, text, filled=True, width=None):
    """width defaults to None (Qt's own sizeHint from the text) — pass an
    explicit value for buttons sitting in the same row as others, since
    relying on sizeHint for several same-row QPushButtons has produced
    same-sized/overlapping buttons in practice (their hint isn't reliably
    settled before the fixed-size window's first paint).
    """

    button = QPushButton(text, parent)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFixedHeight(44)

    if width is not None:
        button.setFixedWidth(width)

    if filled:

        button.setStyleSheet(
            "QPushButton {"
            f" background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            f" stop:0 {COLOR_ACCENT_BLUE}, stop:1 {COLOR_ACCENT_PURPLE});"
            " color: #FFFFFF;"
            " border: none;"
            " border-radius: 20px;"
            " font-weight: 700;"
            "}"
            "QPushButton:hover { background-color: #6C4CC9; }"
        )

    else:

        button.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_PANEL}; color: {COLOR_TEXT_DARK};"
            f" border: 1.5px solid {COLOR_ACCENT_PURPLE}; border-radius: 20px; }}"
        )

    return button


def make_title_label(text, parent=None, size=20):

    label = QLabel(text, parent)

    font = QFont()
    font.setPixelSize(size)
    font.setBold(True)
    label.setFont(font)
    label.setStyleSheet(f"color: {COLOR_TEXT_DARK}; background: transparent; border: none;")

    return label


def make_glass_panel(parent, radius=32, bg=COLOR_PANEL):
    """The "same style rectangle as in the main interface" — matches
    MainWindow's panel_camera_preview / panel_status look: a light rounded
    panel with a thin purple-blue border and a soft violet glow, achieved
    the same way MainWindow's mode glow rings do (QGraphicsDropShadowEffect
    with no offset, just blur).
    """

    panel = QFrame(parent)
    panel.setStyleSheet(
        f"QFrame {{ background-color: {bg};"
        f" border: 1.5px solid rgba(139, 61, 255, 90);"
        f" border-radius: {radius}px; }}"
    )

    effect = QGraphicsDropShadowEffect(panel)
    effect.setBlurRadius(36)
    effect.setOffset(0, 4)
    effect.setColor(QColor(139, 61, 255, 55))
    panel.setGraphicsEffect(effect)

    return panel


def make_card():

    card = QFrame()
    card.setStyleSheet(
        f"QFrame {{ background-color: {COLOR_PANEL_ALT};"
        f" border: 1.5px solid rgba(139, 61, 255, 70); border-radius: 18px; }}"
    )

    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(18, 14, 18, 14)
    card_layout.setSpacing(6)

    return card, card_layout


def make_card_title(text, parent):

    title = QLabel(text, parent)
    title_font = QFont()
    title_font.setPixelSize(16)
    title_font.setBold(True)
    title.setFont(title_font)
    title.setStyleSheet(f"color: {COLOR_ACCENT_PURPLE}; background: transparent; border: none;")

    return title


def make_section_label(text, parent):

    label = QLabel(text, parent)

    font = QFont()
    font.setPixelSize(11)
    font.setBold(True)
    label.setFont(font)
    label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; background: transparent; border: none;")

    return label


def show_message(parent, title, text, warning=False):
    """A QMessageBox with its colors pinned explicitly, instead of the
    plain QMessageBox.information()/.warning() convenience functions.

    Those convenience functions build a QMessageBox parented to `parent`,
    and Qt's stylesheet cascade follows that parent chain — so on a window
    styled via styled_window() (a bare "background-color: ..." rule, no
    widget-type selector), the message box silently inherits that light
    background while its text label keeps whatever color the system/OS
    theme defaults to (white, under macOS dark mode). Light background +
    white text is unreadable. Setting both explicitly here, on every
    message box this app shows, sidesteps the cascade instead of relying
    on it to happen to produce a readable pair.
    """

    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Icon.Warning if warning else QMessageBox.Icon.Information)

    box.setStyleSheet(
        f"QMessageBox {{ background-color: {COLOR_PANEL}; }}"
        f"QMessageBox QLabel {{ color: {COLOR_TEXT_DARK}; background: transparent; }}"
        "QMessageBox QPushButton {"
        f" background-color: {COLOR_PANEL}; color: {COLOR_TEXT_DARK};"
        f" border: 1.5px solid {COLOR_ACCENT_PURPLE}; border-radius: 8px;"
        " padding: 4px 16px; min-width: 60px;"
        "}"
        "QMessageBox QPushButton:hover {"
        " background-color: rgba(139, 61, 255, 30);"
        "}"
    )

    box.exec()


def make_info_button(parent, title, description):
    """The (i) next to a setting — opens a small popup explaining exactly
    what that value controls, instead of leaving the user to guess from
    the label alone.
    """

    button = QPushButton("i", parent)
    button.setFixedSize(22, 22)
    button.setCursor(Qt.CursorShape.PointingHandCursor)

    font = QFont()
    font.setPixelSize(12)
    font.setItalic(True)
    font.setBold(True)
    button.setFont(font)

    button.setStyleSheet(
        "QPushButton {"
        f" color: {COLOR_ACCENT_PURPLE};"
        " background-color: rgba(139, 61, 255, 25);"
        f" border: 1.5px solid {COLOR_ACCENT_PURPLE};"
        " border-radius: 11px;"
        "}"
        "QPushButton:hover { background-color: rgba(139, 61, 255, 55); }"
    )

    button.clicked.connect(
        lambda: show_message(button.window(), title, description)
    )

    return button


def make_number_field(parent, value, minimum, maximum, step, decimals=None):

    if decimals is None:

        field = QSpinBox(parent)
        field.setRange(int(minimum), int(maximum))
        field.setSingleStep(int(step))
        field.setValue(int(value))

    else:

        field = QDoubleSpinBox(parent)
        field.setDecimals(decimals)
        field.setRange(minimum, maximum)
        field.setSingleStep(step)
        field.setValue(float(value))

    field.setStyleSheet(
        f"background-color: {COLOR_PANEL}; color: {COLOR_TEXT_DARK};"
        f" border: 1px solid rgba(139, 61, 255, 90); border-radius: 8px; padding: 4px 8px;"
    )

    return field


def get_nested(config, path, default=None):

    node = config

    for key in path:

        if not isinstance(node, dict) or key not in node:
            return default

        node = node[key]

    return node


def set_nested(config, path, value):

    node = config

    for key in path[:-1]:
        node = node.setdefault(key, {})

    node[path[-1]] = value


# ---------------------------------
# Content: modes, gestures, settings fields
#
# Sourced from config/fusion.json (mode_rules / triggers), config/
# mapping.json (voice/keyboard phrases) and processing/gesture/
# gesture_recognizer.py (which config/system.json "gesture" key each
# setting reads, which mode it actually affects, and the literal default
# it falls back to — see that file's own comments for confidence_threshold,
# presentation_fist, pinch_distance_threshold, call_toggle_hold_seconds,
# etc.). The "default" value in every SETTING_GROUPS field below matches
# that Python-side fallback literal exactly, so "Reset to defaults" always
# reverts to the value the app would use if the key were simply absent
# from system.json.
# ---------------------------------

MODE_INFO = (
    {
        "name": "Flip / Mode",
        "entry": 'Voice "flip mode" · Keyboard Ctrl+Shift+F · Wheel icon',
        "description": (
            "Gesture-based content flipping using open-palm swipes. Built "
            "for feeds, photos, slides and pages."
        ),
        "gestures": (
            ("Open-palm swipe up", "Scroll down"),
            ("Open-palm swipe down", "Scroll up"),
            ("Open-palm swipe right", "Flip to previous"),
            ("Open-palm swipe left", "Flip to next")
        )
    },
    {
        "name": "Presentation",
        "entry": 'Voice "presentation mode" · Keyboard Ctrl+Shift+P · Wheel icon',
        "description": (
            "Slide control and pointer-style presentation actions — advance, "
            "go back, and point at content on screen."
        ),
        "gestures": (
            ("Closed-fist swipe right", "Next slide"),
            ("Closed-fist swipe left", "Previous slide"),
            ('Voice "next slide"', "Next slide"),
            ('Voice "previous slide"', "Previous slide"),
            ('Voice "start presentation"', "Start slideshow (F5)")
        )
    },
    {
        "name": "Call Mode",
        "entry": 'Voice "call mode" · Keyboard Ctrl+Shift+W · Wheel icon',
        "description": (
            "Video-call gesture control: toggle camera, microphone, call "
            "audio and background blur without touching the keyboard."
        ),
        "gestures": (
            ("Hold 1 finger up", "Toggle microphone"),
            ("Hold 2 fingers up", "Toggle camera"),
            ("Hold 3 fingers up", "Toggle call audio"),
            ("Hold 4 fingers up", "Toggle background blur")
        )
    },
    {
        "name": "Cursor",
        "entry": 'Voice "cursor mode" · Keyboard Ctrl+Shift+C · Wheel icon',
        "description": (
            "Direct cursor control — the hand drives the mouse pointer, with "
            "pinch gestures for click and drag."
        ),
        "gestures": (
            ("Hand movement", "Moves the cursor"),
            ("Pinch (thumb + index)", "Click"),
            ("Double pinch", "Right-click"),
            ("Off-hand pinch + move", "Precision mode (slower cursor)")
        )
    },
    {
        "name": "Quick Command Circle",
        "entry": "Raise an open palm and hold",
        "description": (
            "A radial mode picker that opens right over your hand — swipe "
            "in a direction to jump straight into another mode instead of "
            "saying its name or reaching for the keyboard."
        ),
        "gestures": (
            ("Swipe left", "Enter Presentation mode"),
            ("Swipe right", "Enter Call mode"),
            ("Swipe up", "Enter Flip mode"),
            ("Swipe down", "Enter Cursor mode"),
            ("Close the fist", "Cancel and close the circle")
        )
    },
    {
        "name": "Try Mode",
        "entry": 'Voice "try mode" · Keyboard Ctrl+Shift+T · Switch next to the camera preview',
        "description": (
            "Not a mode like the others — an independent on/off switch that "
            "can be active at the same time as any of them, so you can "
            "safely see how the system works. While it's on, nothing above "
            "ever touches the real computer: no key presses, clicks, cursor "
            "movement, or app launches. Mode switching, gesture/voice/"
            "keyboard recognition and the camera preview's live "
            "\"Detected: ...\" caption all keep working exactly as normal."
        ),
        "gestures": (
            ('Say "try mode" / Ctrl+Shift+T / click the switch again', "Turn Try Mode off"),
            ('Say "exit mode" or press Esc', "Turn Try Mode off too, on top of leaving whichever mode is active")
        )
    }
)

# Environments are independent of modes (you can be in an environment and a
# mode at the same time) and, unlike modes, have no Esc/"exit mode"/wheel-
# icon exit of their own — see ENVIRONMENT_EXIT_NOTE below.
ENVIRONMENT_INFO = (
    {
        "name": "Job Search",
        "entry": 'Voice "job search mode"',
        "description": (
            "Sets up a job-hunting session: enables Do Not Disturb and opens "
            "the browser windows/tabs configured for it in Settings."
        ),
        "effects": (
            ("On enter", "Enable Do Not Disturb · open Job Search browser windows"),
            ("On exit", "Disable Do Not Disturb")
        )
    },
    {
        "name": "Study",
        "entry": 'Voice "study mode"',
        "description": (
            "Sets up a study session: enables Do Not Disturb and opens the "
            "browser windows/tabs configured for it in Settings."
        ),
        "effects": (
            ("On enter", "Enable Do Not Disturb · open Study browser windows"),
            ("On exit", "Disable Do Not Disturb")
        )
    },
    {
        "name": "Movie",
        "entry": 'Voice "movie mode"',
        "description": (
            "Sets up a movie night: enables Do Not Disturb, keeps the "
            "display awake, opens the TV app and Netflix, and runs the "
            "\"cinema mode\" Shortcuts automation (e.g. dimming smart lights, "
            "if one is set up)."
        ),
        "effects": (
            (
                "On enter",
                "Enable Do Not Disturb · prevent display sleep · open TV app "
                "+ Netflix · run cinema-mode Shortcut"
            ),
            ("On exit", "Disable Do Not Disturb · allow display sleep again")
        )
    },
    {
        "name": "News",
        "entry": 'Voice "news mode"',
        "description": (
            "Opens the browser tabs configured for it in Settings — no Do "
            "Not Disturb, no other side effects."
        ),
        "effects": (
            ("On enter", "Open News browser tabs"),
            ("On exit", "— (nothing to undo)")
        )
    }
)

ENVIRONMENT_EXIT_NOTE = (
    "Environments don't have their own exit phrase — saying an environment's "
    "own name again does nothing once it's already active. The only way to "
    "leave one is to say a different environment's name, which undoes the "
    "current one's \"On exit\" effects first."
)

GENERAL_EXIT = 'Say "exit mode", or click the active mode\'s icon again.'

GENERAL_MODE_SWITCHING = (
    "Every mode below can be entered the same three ways: say its name "
    "(after the wake word), use its keyboard shortcut, or click its wheel "
    "icon on the main window — see each mode's own \"Enter\" line for its "
    "exact phrase and shortcut. Raising an open palm and holding it "
    "(Quick Circle, below) is a fourth, gesture-only way to jump into "
    "Flip, Cursor, Presentation or Call Mode without saying anything or "
    "touching the keyboard."
)

GENERAL_WAKE_WORD_NOTE = (
    "Every voice command on this screen — and everywhere else in the app "
    "— must be preceded by the wake word, by default \"jack\" (e.g. "
    "\"jack flip mode\", \"jack open browser\"). Configurable in Settings "
    "under General → Wake word."
)

GENERAL_GESTURES = (
    (
        "Raise an open palm and hold (Quick Circle)",
        "Opens a quick mode picker — swipe up/down/left/right to jump "
        "straight into Flip, Cursor, Presentation or Call Mode."
    ),
    ("Alt + head tilt right / left", "Next / previous track"),
    ("Alt + mouth open", "Play / pause"),
    ("Alt + eyebrows up", "Volume up"),
    ("Ctrl + eyebrows up", "Volume down")
)

GENERAL_VOICE_COMMANDS = (
    "Apps & sites: \"open browser / chatgpt / github / terminal / safari / "
    "chrome / spotify / discord / mail / calendar / notes / telegram / "
    "finder / notion / photos / preview / settings\".",
    "Media: \"start\", \"stop\", \"pause\", \"reset\", \"next track\", "
    "\"previous track\"."
)

# Every setting field: (label, path, kind, default, extra...)
# kind "text" -> extra: (description,)
# kind "int"/"float" -> extra: (minimum, maximum, step, decimals, description)
# decimals is None for "int".

SETTING_GROUPS = (
    (
        "General",
        (
            (
                "Wake word", ("wake_word",), "text", "jack",
                "The word you say before every voice command to wake up "
                'speech recognition (e.g. "jack, open browser").'
            ),
            (
                "Camera index", ("camera", "index"), "int", 0,
                0, 8, 1, None,
                "Which camera device to capture from, if more than one is "
                "connected. 0 is usually the built-in camera."
            ),
            (
                "Microphone sample rate (Hz)", ("audio", "sample_rate"), "int", 16000,
                8000, 48000, 1000, None,
                "Microphone recording rate in Hz. Must match what the "
                "offline Vosk speech model expects — changing this can "
                "break voice recognition."
            ),
            (
                "Gesture confidence threshold",
                ("gesture", "confidence_threshold"), "float", 0.7,
                0.0, 1.0, 0.05, 2,
                "Minimum confidence MediaPipe's gesture classifier must "
                "report before a gesture is accepted. Higher means fewer "
                "false positives, but real gestures may be missed."
            ),
            (
                "Confirm frames", ("gesture", "confirm_frames"), "int", 4,
                1, 20, 1, None,
                "How many consecutive camera frames must show the same "
                "gesture before it's trusted — filters out single-frame "
                "misreads."
            ),
            (
                "Hand-lost frames", ("gesture", "hand_lost_frames"), "int", 5,
                1, 30, 1, None,
                "How many consecutive frames the hand may be briefly "
                "undetected (motion blur, fast movement) before its "
                "tracking session is considered ended."
            ),
            (
                "Freeze duration (s)", ("gesture", "freeze_duration"), "float", 0.3,
                0.0, 2.0, 0.05, 2,
                "Seconds the on-screen tracking anchor freezes in place "
                "right after a swipe fires, before resuming live tracking."
            ),
            (
                "Same-hand distance", ("gesture", "same_hand_distance"), "float", 0.15,
                0.0, 1.0, 0.01, 2,
                "How close two detected hands must be (normalized 0-1 "
                "distance) before the second one is treated as a duplicate "
                "reading of the same hand, not a real second hand."
            ),
            (
                "Finger extension margin",
                ("gesture", "finger_extension_margin"), "float", 1.05,
                1.0, 2.0, 0.01, 2,
                "How much farther a fingertip must sit from the wrist than "
                "its middle joint to count as \"extended\" — keeps "
                "near-straight fingers from flickering extended/folded."
            )
        )
    ),
    (
        "Flip / Mode",
        (
            (
                "Swipe velocity threshold",
                ("gesture", "velocity_threshold"), "float", 1.8,
                0.0, 5.0, 0.1, 2,
                "How fast the hand must move (normalized units/second) for "
                "a Flip-mode swipe to register."
            ),
            (
                "Minimum frame distance",
                ("gesture", "min_frame_distance"), "float", 0.015,
                0.0, 0.1, 0.001, 3,
                "Minimum frame-to-frame movement distance before a swipe "
                "direction is even considered — filters out hand jitter."
            ),
            (
                "Vertical cone (degrees)",
                ("gesture", "vertical_cone_degrees"), "float", 25.0,
                0.0, 90.0, 1.0, 0,
                "How many degrees off pure up/down/left/right a swipe's "
                "direction may deviate and still count as that direction."
            ),
            (
                "Motion cooldown (s)", ("gesture", "motion_cooldown"), "float", 0.5,
                0.0, 2.0, 0.05, 2,
                "Minimum seconds between two consecutive swipe detections, "
                "so one long motion doesn't fire multiple flips."
            )
        )
    ),
    (
        "Presentation",
        (
            (
                "Swipe velocity threshold",
                ("gesture", "presentation_fist", "velocity_threshold"), "float", 0.5,
                0.0, 5.0, 0.05, 2,
                "Same idea as Flip mode's swipe speed threshold, tuned "
                "separately for Presentation mode's closed-fist swipe — a "
                "fist naturally moves slower than an open-palm swipe."
            ),
            (
                "Minimum frame distance",
                ("gesture", "presentation_fist", "min_frame_distance"), "float", 0.0075,
                0.0, 0.1, 0.0005, 4,
                "Minimum frame-to-frame movement before a fist swipe's "
                "direction is considered — filters out jitter."
            ),
            (
                "Vertical cone (degrees)",
                ("gesture", "presentation_fist", "vertical_cone_degrees"), "float", 25.0,
                0.0, 90.0, 1.0, 0,
                "How many degrees off pure left/right a fist swipe may "
                "deviate and still count as next/previous slide."
            ),
            (
                "Motion cooldown (s)",
                ("gesture", "presentation_fist", "motion_cooldown"), "float", 0.5,
                0.0, 2.0, 0.05, 2,
                "Minimum seconds between two consecutive fist-swipe slide "
                "changes."
            ),
            (
                "Pointer box size (hand-widths)",
                ("gesture", "presentation_pointer_box_hands"), "float", 4.0,
                1.0, 10.0, 0.5, 1,
                "Size of the on-screen area the presentation pointer can "
                "reach, measured in multiples of your own hand's width, "
                "centered on wherever pointing started."
            )
        )
    ),
    (
        "Call Mode",
        (
            (
                "Toggle hold time (s)",
                ("gesture", "call_toggle_hold_seconds"), "float", 1.5,
                0.0, 5.0, 0.1, 2,
                "How many seconds you must hold up 1/2/3/4 fingers before "
                "the corresponding toggle (mic/camera/call audio/blur) "
                "actually fires — prevents accidental toggles while just "
                "passing through that finger count."
            ),
        )
    ),
    (
        "Cursor",
        (
            (
                "Pinch distance threshold",
                ("gesture", "pinch_distance_threshold"), "float", 0.06,
                0.0, 0.3, 0.01, 2,
                "How close together the thumb and index finger must be "
                "(normalized distance) to register as a pinch/click."
            ),
            (
                "Drag activation time (s)",
                ("gesture", "drag_activation_seconds"), "float", 0.15,
                0.0, 1.0, 0.01, 2,
                "How long a pinch must be held before it turns into a drag "
                "instead of a click."
            ),
            (
                "Drag activation distance",
                ("gesture", "drag_activation_distance"), "float", 0.03,
                0.0, 0.2, 0.005, 3,
                "How far the hand must move while pinching before a drag "
                "starts, instead of a click."
            ),
            (
                "Double-pinch window (s)",
                ("gesture", "double_pinch_window"), "float", 0.3,
                0.0, 1.0, 0.05, 2,
                "Maximum seconds between two pinches for them to count as "
                "a double-pinch (right-click) instead of two separate "
                "clicks."
            ),
            (
                "Precision-mode scale",
                ("gesture", "precision_scale"), "float", 0.5,
                0.0, 1.0, 0.05, 2,
                "Cursor speed while precision mode is active (holding a "
                "pinch with the off-hand), as a fraction of normal speed — "
                "like a DPI switch on a physical mouse."
            ),
            (
                "Active zone margin",
                ("gesture", "active_zone_margin"), "float", 0.1,
                0.0, 0.4, 0.01, 2,
                "Fraction of the camera frame's edges trimmed away before "
                "mapping the fingertip to the screen, so you don't have to "
                "reach the true edge of the camera view to reach the edge "
                "of the screen."
            )
        )
    ),
    (
        "Apps",
        (
            (
                "Terminal", ("os_controller", "apps", "terminal"), "text", "Terminal",
                'App name opened by "open terminal".'
            ),
            (
                "Safari", ("os_controller", "apps", "safari"), "text", "Safari",
                'App name opened by "open safari".'
            ),
            (
                "Chrome", ("os_controller", "apps", "chrome"), "text", "Google Chrome",
                'App name opened by "open chrome", and used for every Work '
                "Environment's browser windows/tabs below."
            ),
            (
                "Spotify", ("os_controller", "apps", "spotify"), "text", "Spotify",
                'App name opened by "open spotify", and used by the '
                "focus-music play/pause actions."
            ),
            (
                "Slack", ("os_controller", "apps", "slack"), "text", "Slack",
                'App name opened by "open slack".'
            ),
            (
                "Discord", ("os_controller", "apps", "discord"), "text", "Discord",
                'App name opened by "open discord".'
            ),
            (
                "Mail", ("os_controller", "apps", "mail"), "text", "Mail",
                'App name opened by "open mail".'
            ),
            (
                "Calendar", ("os_controller", "apps", "calendar"), "text", "Calendar",
                'App name opened by "open calendar".'
            ),
            (
                "Notes", ("os_controller", "apps", "notes"), "text", "Notes",
                'App name opened by "open notes".'
            ),
            (
                "Telegram", ("os_controller", "apps", "telegram"), "text", "Telegram",
                'App name opened by "open telegram".'
            ),
            (
                "Finder", ("os_controller", "apps", "finder"), "text", "Finder",
                'App name opened by "open finder".'
            ),
            (
                "Notion", ("os_controller", "apps", "notion"), "text", "Notion",
                'App name opened by "open notion".'
            ),
            (
                "Photos", ("os_controller", "apps", "photos"), "text", "Photos",
                'App name opened by "open photos".'
            ),
            (
                "Preview", ("os_controller", "apps", "preview"), "text", "Preview",
                'App name opened by "open preview".'
            ),
            (
                "System Settings", ("os_controller", "apps", "settings"), "text", "System Settings",
                'App name opened by "open settings".'
            ),
            (
                "TV", ("os_controller", "apps", "tv"), "text", "TV",
                'App name opened when entering the Movie environment '
                '("movie mode").'
            ),
            (
                "News app", ("os_controller", "apps", "news"), "text", "News",
                'App name for the "open news app" action — not currently '
                "reachable by any voice/gesture command. Not the same as "
                "the News environment's browser tabs below."
            )
        )
    )
)

# (config key, card label) for os_controller.window_groups — each one a
# list of browser-window tab-groups, edited as plain text in SettingsWindow
# rather than through the generic SETTING_GROUPS scalar-field mechanism
# above, since a tab-group list doesn't fit a single (path, value) pair.
WINDOW_GROUP_LABELS = (
    ("job_search", "Job Search"),
    ("study", "Study"),
    ("news", "News")
)


# Relaunches the app so a just-saved config/system.json actually takes
# effect, without the user having to quit and reopen it by hand — the app
# only ever reads its config files once, at startup (see config_loader.py
# and every module that calls load_system_config() in __init__).
def restart_application():

    if getattr(sys, "frozen", False):

        # sys.executable is .../GestureVoiceControl.app/Contents/MacOS/
        # GestureVoiceControl — walk back up to the .app bundle itself so
        # this goes through LaunchServices like a normal Finder double-
        # click, instead of exec'ing the raw Mach-O binary directly.
        app_bundle = os.path.abspath(
            os.path.join(os.path.dirname(sys.executable), "..", "..")
        )

        subprocess.Popen(["open", "-n", app_bundle])

    else:

        subprocess.Popen([sys.executable] + sys.argv)


# ---------------------------------
# Settings Window
# ---------------------------------

class SettingsWindow(QWidget):
    """Only what can actually be configured — no descriptions, no gesture
    lists (see InfoWindow for those). Every field has an (i) button
    explaining what it does, and "Reset to defaults" reverts every field
    on screen to gesture_recognizer.py's own fallback values (still
    requires Save to persist, same as any other unsaved change).

    Built with no parent and no custom window flags — a plain top-level
    QWidget on macOS already gets a normal native title bar with a working
    close button, which is what turns this into a standalone app window
    instead of a modal sheet glued under MainWindow's own title bar.
    """

    def __init__(self, event_bus=None):

        super().__init__()

        styled_window(self, "Settings", 640, 720)

        self.event_bus = event_bus

        self._fields = []
        self._window_group_fields = {}

        config = load_system_config()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        layout.addWidget(make_title_label("Settings", self))

        subtitle = QLabel(
            "Every tunable value behind gesture recognition and input, plus "
            "every app and Work Environment — tap the (i) next to a field "
            'to see what it controls. "Save && Restart" writes '
            "config/system.json and relaunches the app so the change "
            "actually takes effect.",
            self
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; background: transparent; border: none;"
        )
        layout.addWidget(subtitle)

        panel = make_glass_panel(self, radius=32)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(4, 4, 4, 4)

        scroll = QScrollArea(panel)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(18, 18, 18, 12)
        content_layout.setSpacing(14)

        for group_name, fields in SETTING_GROUPS:
            content_layout.addWidget(self._make_settings_card(group_name, fields, config))

        content_layout.addWidget(self._make_window_groups_card(config))

        content_layout.addStretch(1)
        scroll.setWidget(content)
        panel_layout.addWidget(scroll)

        layout.addWidget(panel, 1)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(12)

        reset_button = make_action_button(self, "Reset to defaults", filled=False, width=170)
        reset_button.clicked.connect(self._on_reset_clicked)
        buttons_row.addWidget(reset_button)

        buttons_row.addStretch(1)

        cancel_button = make_action_button(self, "Cancel", filled=False, width=110)
        cancel_button.clicked.connect(self.close)
        buttons_row.addWidget(cancel_button)

        save_button = make_action_button(self, "Save && Restart", filled=True, width=160)
        save_button.clicked.connect(self._on_save_clicked)
        buttons_row.addWidget(save_button)

        layout.addLayout(buttons_row)

    def _make_settings_card(self, group_name, fields, config):

        card, card_layout = make_card()
        card_layout.addWidget(make_card_title(group_name, card))

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        for row, spec in enumerate(fields):

            label_text, path, kind = spec[0], spec[1], spec[2]

            label = QLabel(label_text, card)
            label.setStyleSheet(
                f"color: {COLOR_TEXT_DARK}; background: transparent; border: none; font-size: 12px;"
            )

            if kind == "text":

                default_value, description = spec[3], spec[4]

                field = QLineEdit(str(get_nested(config, path, default_value)), card)
                field.setStyleSheet(
                    f"background-color: {COLOR_PANEL}; color: {COLOR_TEXT_DARK};"
                    f" border: 1px solid rgba(139, 61, 255, 90); border-radius: 8px; padding: 4px 8px;"
                )

            else:

                default_value, minimum, maximum, step, decimals, description = spec[3:]

                value = get_nested(config, path, default_value)
                field = make_number_field(card, value, minimum, maximum, step, decimals)

            self._fields.append((path, field, default_value))

            info_button = make_info_button(card, label_text, description)

            grid.addWidget(label, row, 0)
            grid.addWidget(field, row, 1)
            grid.addWidget(info_button, row, 2)

        card_layout.addLayout(grid)

        return card

    # Each window group is a list of browser-window tab-groups: the first
    # URL of every line-group opens a new window, the rest join it as
    # tabs (see OSController.open_window_group). Edited as plain text —
    # one URL per line, a blank line starts a new window — rather than a
    # dynamic add/remove-row UI, since this is config only the developer
    # (not an end user) is expected to edit.
    def _make_window_groups_card(self, config):

        card, card_layout = make_card()
        card_layout.addWidget(make_card_title("Work Environments", card))

        description = QLabel(
            "One browser tab URL per line. A blank line starts a new "
            "browser window — its first URL opens the window, the rest "
            'join it as tabs. Opened by voice ("job search mode" / "study '
            'mode" / "news mode").',
            card
        )
        description.setWordWrap(True)
        description.setStyleSheet(f"color: {COLOR_TEXT_DARK}; background: transparent; border: none;")
        card_layout.addWidget(description)

        window_groups = get_nested(config, ("os_controller", "window_groups"), {})

        for group_key, group_label in WINDOW_GROUP_LABELS:

            card_layout.addWidget(make_section_label(group_label.upper(), card))

            text_edit = QTextEdit(card)
            text_edit.setPlainText(
                self._window_group_to_text(window_groups.get(group_key, []))
            )
            text_edit.setFixedHeight(90)
            text_edit.setStyleSheet(
                f"background-color: {COLOR_PANEL}; color: {COLOR_TEXT_DARK};"
                f" border: 1px solid rgba(139, 61, 255, 90); border-radius: 8px; padding: 4px 8px;"
            )
            card_layout.addWidget(text_edit)

            self._window_group_fields[group_key] = text_edit

        return card

    def _window_group_to_text(self, tab_groups):

        return "\n\n".join(
            "\n".join(urls) for urls in tab_groups
        )

    def _text_to_window_group(self, text):

        tab_groups = []

        for block in text.strip().split("\n\n"):

            urls = [line.strip() for line in block.splitlines() if line.strip()]

            if urls:
                tab_groups.append(urls)

        return tab_groups

    def _on_reset_clicked(self):

        for _, field, default_value in self._fields:

            if isinstance(field, QLineEdit):
                field.setText(str(default_value))

            else:
                field.setValue(default_value)

    def _on_save_clicked(self):

        try:

            with open(SYSTEM_CONFIG_PATH, "r", encoding="utf-8") as config_file:
                config = json.load(config_file)

            for path, field, _ in self._fields:

                if isinstance(field, QLineEdit):
                    value = field.text()

                else:
                    value = field.value()

                set_nested(config, path, value)

            for group_key, text_edit in self._window_group_fields.items():

                set_nested(
                    config,
                    ("os_controller", "window_groups", group_key),
                    self._text_to_window_group(text_edit.toPlainText())
                )

            with open(SYSTEM_CONFIG_PATH, "w", encoding="utf-8") as config_file:
                json.dump(config, config_file, indent=2)
                config_file.write("\n")

        except OSError as error:

            show_message(self, "Settings", f"Could not save settings: {error}", warning=True)
            return

        self.close()

        restart_application()

        # Mirrors the normal window-close quit path (MainWindow's header X
        # button) so the pipeline shuts down cleanly — camera/mic released,
        # etc. — instead of the process being killed mid-restart.
        if self.event_bus is not None:
            self.event_bus.publish("ui_quit_requested", {})


# ---------------------------------
# Info Window
# ---------------------------------

class InfoWindow(QWidget):
    """Only descriptions — what every mode and gesture does, and how to
    trigger it. No settings, no editable fields (see SettingsWindow for
    those).
    """

    def __init__(self):

        super().__init__()

        styled_window(self, "Info", 640, 720)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        layout.addWidget(make_title_label("Functions & Gestures", self))

        subtitle = QLabel(
            "Every mode and environment, its gestures, and every voice/"
            "keyboard way to switch into it — grouped together.",
            self
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; background: transparent; border: none;"
        )
        layout.addWidget(subtitle)

        panel = make_glass_panel(self, radius=32)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(4, 4, 4, 4)

        scroll = QScrollArea(panel)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(18, 18, 18, 12)
        content_layout.setSpacing(14)

        content_layout.addWidget(self._make_general_card())

        content_layout.addWidget(make_section_label("MODES", content))

        for section in MODE_INFO:
            content_layout.addWidget(self._make_mode_card(section))

        content_layout.addWidget(make_section_label("ENVIRONMENTS", content))

        environments_note = QLabel(ENVIRONMENT_EXIT_NOTE, content)
        environments_note.setWordWrap(True)
        environments_note.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; background: transparent; border: none; font-size: 11px;"
        )
        content_layout.addWidget(environments_note)

        for section in ENVIRONMENT_INFO:
            content_layout.addWidget(self._make_environment_card(section))

        content_layout.addStretch(1)
        scroll.setWidget(content)
        panel_layout.addWidget(scroll)

        layout.addWidget(panel, 1)

        close_button = make_action_button(self, "Close", filled=True)
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)

    def _make_gesture_row(self, trigger_text, action_text, parent):

        row = QLabel(
            f'<span style="color:{COLOR_TEXT_DARK};">{trigger_text}</span>'
            f'<span style="color:{COLOR_TEXT_SECONDARY};"> &rarr; </span>'
            f'<span style="color:{COLOR_ACCENT_PURPLE}; font-weight:600;">{action_text}</span>',
            parent
        )
        row.setWordWrap(True)
        row.setStyleSheet("background: transparent; border: none; font-size: 12px;")

        return row

    def _make_mode_card(self, section):

        card, card_layout = make_card()
        card_layout.addWidget(make_card_title(section["name"], card))

        entry = QLabel(f"Enter: {section['entry']}", card)
        entry.setWordWrap(True)
        entry.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; background: transparent; border: none; font-size: 11px;"
        )
        card_layout.addWidget(entry)

        description = QLabel(section["description"], card)
        description.setWordWrap(True)
        description.setStyleSheet(f"color: {COLOR_TEXT_DARK}; background: transparent; border: none;")
        card_layout.addWidget(description)

        card_layout.addWidget(make_section_label("GESTURES", card))

        for trigger_text, action_text in section["gestures"]:
            card_layout.addWidget(self._make_gesture_row(trigger_text, action_text, card))

        return card

    def _make_environment_card(self, section):

        card, card_layout = make_card()
        card_layout.addWidget(make_card_title(section["name"], card))

        entry = QLabel(f"Enter: {section['entry']}", card)
        entry.setWordWrap(True)
        entry.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; background: transparent; border: none; font-size: 11px;"
        )
        card_layout.addWidget(entry)

        description = QLabel(section["description"], card)
        description.setWordWrap(True)
        description.setStyleSheet(f"color: {COLOR_TEXT_DARK}; background: transparent; border: none;")
        card_layout.addWidget(description)

        for label_text, value_text in section["effects"]:
            card_layout.addWidget(self._make_gesture_row(label_text, value_text, card))

        return card

    def _make_general_card(self):

        card, card_layout = make_card()
        card_layout.addWidget(make_card_title("General", card))

        description = QLabel(
            "Applies across every mode: the three input toggles on the main "
            f"window's bottom panel, and how to leave whichever mode is "
            f"active ({GENERAL_EXIT}).",
            card
        )
        description.setWordWrap(True)
        description.setStyleSheet(f"color: {COLOR_TEXT_DARK}; background: transparent; border: none;")
        card_layout.addWidget(description)

        card_layout.addWidget(make_section_label("SWITCHING MODES", card))

        switching = QLabel(GENERAL_MODE_SWITCHING, card)
        switching.setWordWrap(True)
        switching.setStyleSheet(
            f"color: {COLOR_TEXT_DARK}; background: transparent; border: none; font-size: 12px;"
        )
        card_layout.addWidget(switching)

        card_layout.addWidget(make_section_label("ALWAYS-ON GESTURES", card))

        for trigger_text, action_text in GENERAL_GESTURES:
            card_layout.addWidget(self._make_gesture_row(trigger_text, action_text, card))

        card_layout.addWidget(make_section_label("VOICE COMMANDS", card))

        wake_word = QLabel(GENERAL_WAKE_WORD_NOTE, card)
        wake_word.setWordWrap(True)
        wake_word.setStyleSheet(
            f"color: {COLOR_TEXT_DARK}; background: transparent; border: none; "
            "font-size: 12px; font-weight: 600;"
        )
        card_layout.addWidget(wake_word)

        for line in GENERAL_VOICE_COMMANDS:

            label = QLabel(line, card)
            label.setWordWrap(True)
            label.setStyleSheet(
                f"color: {COLOR_TEXT_DARK}; background: transparent; border: none; font-size: 12px;"
            )
            card_layout.addWidget(label)

        return card
