"""Functions Description and Settings dialogs.

Both are new, standalone windows (not yet covered by
ui_documentation_final_without_functions_dialog.txt, which explicitly
defers the Functions Description Dialog to a separate design pass) built
in the same light/rounded/purple-blue visual language as MainWindow, so
they don't look like a bolt-on. Deliberately self-contained (own palette
constants, own small widget helpers) rather than importing from
main_window.py, to avoid a circular import — MainWindow opens both of
these on demand.
"""

import json
import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
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


def styled_dialog(dialog, title, width, height):

    dialog.setWindowTitle(title)
    dialog.setFixedSize(width, height)
    dialog.setStyleSheet(f"QDialog {{ background-color: {COLOR_BACKGROUND}; }}")


def make_close_button(parent):

    button = QPushButton("Close", parent)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFixedHeight(44)

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

    return button


def make_title_label(text, parent=None):

    label = QLabel(text, parent)

    font = QFont()
    font.setPixelSize(20)
    font.setBold(True)
    label.setFont(font)
    label.setStyleSheet(f"color: {COLOR_TEXT_DARK}; background: transparent; border: none;")

    return label


# ---------------------------------
# Functions Description Dialog
# ---------------------------------

FUNCTION_SECTIONS = (
    (
        "Flip / Mode",
        "Gesture-based content flipping using open-palm swipes up, down, "
        "left or right. Built for feeds, photos, slides and pages."
    ),
    (
        "Presentation",
        "Slide control and pointer-style presentation actions — advance, "
        "go back, and point at content on screen."
    ),
    (
        "Call Mode",
        "Video-call gesture control: toggle camera, microphone and "
        "background blur without touching the keyboard."
    ),
    (
        "Cursor",
        "Direct cursor control — the hand drives the mouse pointer, with "
        "pinch gestures for click and drag."
    ),
    (
        "Camera / Microphone / Keyboard toggles",
        "The three switches on the main window's bottom panel start and "
        "stop each input source independently, regardless of which mode "
        "is active."
    ),
    (
        "Voice commands",
        "Say the wake word, then a command phrase from config/mapping.json "
        "— offline recognition only, no audio leaves this machine."
    )
)


class FunctionsDialog(QDialog):

    def __init__(self, parent=None):

        super().__init__(parent)

        styled_dialog(self, "Functions description", 640, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        layout.addWidget(make_title_label("Functions description", self))

        subtitle = QLabel(
            "What each mode and toggle does. This window's own design is "
            "still a draft — the content is final, the layout isn't.",
            self
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; background: transparent; border: none;")
        layout.addWidget(subtitle)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(12)

        for name, description in FUNCTION_SECTIONS:
            content_layout.addWidget(self._make_card(name, description))

        content_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        close_button = make_close_button(self)
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)

    def _make_card(self, name, description):

        card = QFrame(self)
        card.setStyleSheet(
            f"QFrame {{ background-color: {COLOR_PANEL}; border: 1.5px solid rgba(139, 61, 255, 90);"
            " border-radius: 18px; }"
        )

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 14, 18, 14)
        card_layout.setSpacing(4)

        title = QLabel(name, card)
        title_font = QFont()
        title_font.setPixelSize(15)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {COLOR_ACCENT_PURPLE}; background: transparent; border: none;")
        card_layout.addWidget(title)

        body = QLabel(description, card)
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {COLOR_TEXT_DARK}; background: transparent; border: none;")
        card_layout.addWidget(body)

        return card


# ---------------------------------
# Settings Dialog
# ---------------------------------

class SettingsDialog(QDialog):

    def __init__(self, parent=None):

        super().__init__(parent)

        styled_dialog(self, "Settings", 520, 460)

        config = load_system_config()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        layout.addWidget(make_title_label("Settings", self))

        note = QLabel(
            "Changes are written to config/system.json and take effect "
            "the next time the app starts.",
            self
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; background: transparent; border: none;")
        layout.addWidget(note)

        form = QFrame(self)
        form.setStyleSheet(
            f"QFrame {{ background-color: {COLOR_PANEL_ALT}; border: 1.5px solid rgba(139, 61, 255, 60);"
            " border-radius: 18px; }"
        )
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(20, 18, 20, 18)
        form_layout.setSpacing(14)

        self.wake_word_input = QLineEdit(config.get("wake_word", ""), form)
        form_layout.addLayout(
            self._make_row("Wake word", self.wake_word_input)
        )

        camera_config = config.get("camera", {})

        self.camera_index_input = QSpinBox(form)
        self.camera_index_input.setRange(0, 8)
        self.camera_index_input.setValue(camera_config.get("index", 0))
        form_layout.addLayout(
            self._make_row("Camera index", self.camera_index_input)
        )

        gesture_config = config.get("gesture", {})

        self.confidence_input = QDoubleSpinBox(form)
        self.confidence_input.setRange(0.0, 1.0)
        self.confidence_input.setSingleStep(0.05)
        self.confidence_input.setValue(gesture_config.get("confidence_threshold", 0.7))
        form_layout.addLayout(
            self._make_row("Gesture confidence threshold", self.confidence_input)
        )

        audio_config = config.get("audio", {})

        self.sample_rate_input = QSpinBox(form)
        self.sample_rate_input.setRange(8000, 48000)
        self.sample_rate_input.setSingleStep(1000)
        self.sample_rate_input.setValue(audio_config.get("sample_rate", 16000))
        form_layout.addLayout(
            self._make_row("Microphone sample rate", self.sample_rate_input)
        )

        layout.addWidget(form)
        layout.addStretch(1)

        buttons_row = QHBoxLayout()

        cancel_button = QPushButton("Cancel", self)
        cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_button.setFixedHeight(44)
        cancel_button.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_PANEL}; color: {COLOR_TEXT_DARK};"
            f" border: 1.5px solid {COLOR_ACCENT_PURPLE}; border-radius: 20px; }}"
        )
        cancel_button.clicked.connect(self.close)
        buttons_row.addWidget(cancel_button)

        save_button = make_close_button(self)
        save_button.setText("Save")
        save_button.clicked.connect(self._on_save_clicked)
        buttons_row.addWidget(save_button)

        layout.addLayout(buttons_row)

    def _make_row(self, label_text, field):

        row = QHBoxLayout()

        label = QLabel(label_text)
        label.setStyleSheet(f"color: {COLOR_TEXT_DARK}; background: transparent; border: none;")
        label.setMinimumWidth(220)

        field.setStyleSheet(
            f"background-color: {COLOR_PANEL}; color: {COLOR_TEXT_DARK};"
            f" border: 1px solid rgba(139, 61, 255, 90); border-radius: 8px; padding: 4px 8px;"
        )

        row.addWidget(label)
        row.addWidget(field, 1)

        return row

    def _on_save_clicked(self):

        try:

            with open(SYSTEM_CONFIG_PATH, "r", encoding="utf-8") as config_file:
                config = json.load(config_file)

            config["wake_word"] = self.wake_word_input.text()
            config.setdefault("camera", {})["index"] = self.camera_index_input.value()
            config.setdefault("gesture", {})["confidence_threshold"] = self.confidence_input.value()
            config.setdefault("audio", {})["sample_rate"] = self.sample_rate_input.value()

            with open(SYSTEM_CONFIG_PATH, "w", encoding="utf-8") as config_file:
                json.dump(config, config_file, indent=2)
                config_file.write("\n")

        except OSError as error:

            QMessageBox.warning(self, "Settings", f"Could not save settings: {error}")
            return

        QMessageBox.information(
            self, "Settings", "Saved. Restart the app for changes to take effect."
        )

        self.close()
