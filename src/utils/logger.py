"""Shared logging setup for every pipeline module.

Provides get_logger(name), which returns a logger writing to both the
console and a rotating logs/app.log file, so a failed demo run can be
diagnosed from the log file afterward instead of only from whatever
scrolled past in the terminal.
"""

import logging
import os
import sys

from logging.handlers import RotatingFileHandler


# Anchored to the running executable when frozen (PyInstaller/.exe build)
# or to this file's own location otherwise — never to the process cwd, so
# every caller writes to the same logs/ directory regardless of where the
# app was launched from.
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

_LOG_DIR = os.path.join(
    _BASE_DIR,
    "logs"
)

_LOG_FILE = os.path.join(
    _LOG_DIR,
    "app.log"
)

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

_ROOT_LOGGER_NAME = "gvcontrol"

_configured = False


def _configure_root_logger():

    global _configured

    if _configured:
        return

    os.makedirs(
        _LOG_DIR,
        exist_ok=True
    )

    formatter = logging.Formatter(
        _LOG_FORMAT
    )

    console_handler = logging.StreamHandler()

    console_handler.setFormatter(
        formatter
    )

    file_handler = RotatingFileHandler(
        _LOG_FILE,
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )

    file_handler.setFormatter(
        formatter
    )

    root_logger = logging.getLogger(
        _ROOT_LOGGER_NAME
    )

    root_logger.setLevel(
        logging.INFO
    )

    root_logger.addHandler(
        console_handler
    )

    root_logger.addHandler(
        file_handler
    )

    root_logger.propagate = False

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger under the shared "gvcontrol" root.

    Args:
        name: Usually __name__ of the calling module.

    Returns:
        A configured logging.Logger writing to console + logs/app.log.
    """

    _configure_root_logger()

    return logging.getLogger(
        f"{_ROOT_LOGGER_NAME}.{name}"
    )
