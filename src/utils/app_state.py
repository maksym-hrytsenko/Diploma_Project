"""Small persisted flags that outlive a single run of the app.

Currently just the first-run onboarding marker (see main.py/welcome_window.py).
Written next to the app itself, not inside PyInstaller's read-only bundled
resources — same _BASE_DIR convention utils/logger.py already uses for
logs/app.log, so this survives exactly the same way that already does in
both dev and packaged (.app) runs.
"""

import os
import sys


if getattr(sys, "frozen", False):

    _BASE_DIR = os.path.dirname(
        sys.executable
    )

else:

    _BASE_DIR = os.path.dirname(
        os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        )
    )

_ONBOARDING_MARKER_PATH = os.path.join(
    _BASE_DIR,
    "onboarding_shown"
)


def has_shown_onboarding() -> bool:

    return os.path.exists(
        _ONBOARDING_MARKER_PATH
    )


def mark_onboarding_shown() -> None:

    try:

        with open(
            _ONBOARDING_MARKER_PATH,
            "w",
            encoding="utf-8"
        ) as marker_file:

            marker_file.write(
                "Delete this file to see the welcome screen again "
                "next launch.\n"
            )

    except OSError:

        # Not worth failing startup over — worst case the welcome screen
        # shows again next launch.
        pass
