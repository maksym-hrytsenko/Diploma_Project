"""First-run welcome screen.

Shown once automatically, right after MainWindow, the first time the app is
ever launched (see main.py + utils/app_state.py) — a short, plain-language
introduction and a nudge toward Try Mode, not the full reference (that's
InfoWindow, one click away via the button here or MainWindow's own
"Functions description" button at any later time).

Built from dialogs.py's own shared style helpers (styled_window,
make_title_label, make_glass_panel, make_action_button) rather than
reintroducing another palette/widget style, so it reads as part of the same
app as Settings/Info.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout
)

from ui.dialogs import (
    COLOR_TEXT_DARK,
    COLOR_TEXT_SECONDARY,
    COLOR_ACCENT_PURPLE,
    styled_window,
    make_title_label,
    make_glass_panel,
    make_action_button,
    InfoWindow
)

from utils.app_state import mark_onboarding_shown


WELCOME_POINTS = (
    "Control your computer with hand gestures, voice commands, or the "
    "keyboard — pick whichever fits the moment, and switch freely between "
    "them.",
    "Everything is organized into modes (Presentation, Flip, Cursor, "
    "Call...) — a mode decides what the same gesture currently means, so "
    "a swipe does something different in each one.",
    "The camera preview on the main window always shows what's currently "
    "being recognized, live.",
)


class WelcomeWindow(QWidget):
    """Plain top-level QWidget (no parent), same convention as
    SettingsWindow/InfoWindow — a normal standalone macOS window with its
    own title bar and close button.
    """

    def __init__(self):

        super().__init__()

        styled_window(self, "Welcome", 620, 600)

        self._info_window = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 24)
        layout.setSpacing(14)

        layout.addWidget(
            make_title_label("Welcome to Gesture & Voice Control", self, size=22)
        )

        subtitle = QLabel(
            "A quick look before you start — this only shows once.",
            self
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; background: transparent; border: none;"
        )
        layout.addWidget(subtitle)

        panel = make_glass_panel(self, radius=28)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(24, 20, 24, 20)
        panel_layout.setSpacing(12)

        for point in WELCOME_POINTS:

            point_label = QLabel(f"•  {point}", panel)
            point_label.setWordWrap(True)
            point_label.setStyleSheet(
                f"color: {COLOR_TEXT_DARK}; background: transparent; "
                "border: none; font-size: 13px;"
            )
            panel_layout.addWidget(point_label)

        try_mode_label = QLabel(
            "<b>Try it safely first:</b> turn on <b>Try Mode</b> (the "
            "switch next to the camera preview, or say \"try mode\") — "
            "look at yourself on screen, switch between modes, wave your "
            "hands around. Nothing you do will actually click, type, "
            "scroll, or open anything on your computer until you turn it "
            "back off.",
            panel
        )
        try_mode_label.setWordWrap(True)
        try_mode_label.setStyleSheet(
            f"color: {COLOR_ACCENT_PURPLE}; background: rgba(139, 61, 255, 20); "
            "border-radius: 12px; padding: 12px; font-size: 13px;"
        )
        panel_layout.addWidget(try_mode_label)

        panel_layout.addStretch(1)
        layout.addWidget(panel, 1)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(12)

        info_button = make_action_button(
            self, "View full functions & gestures guide", filled=False
        )
        info_button.clicked.connect(self._on_info_clicked)
        buttons_row.addWidget(info_button)

        buttons_row.addStretch(1)

        start_button = make_action_button(self, "Get started", filled=True, width=150)
        start_button.clicked.connect(self.close)
        buttons_row.addWidget(start_button)

        layout.addLayout(buttons_row)

    def _on_info_clicked(self):

        if self._info_window is None:
            self._info_window = InfoWindow()

        self._info_window.show()
        self._info_window.raise_()
        self._info_window.activateWindow()

    # Marks onboarding shown on ANY close (the header X, "Get started", or
    # Esc) — this screen has done its job the moment it's been seen once,
    # regardless of which way the user dismissed it.
    def closeEvent(self, event):

        mark_onboarding_shown()

        super().closeEvent(event)
