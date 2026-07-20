"""JSON config loading shared by every pipeline module.

Loads and caches system.json, mapping.json and fusion.json — the files
that back OSController hotkeys/apps/URLs, the voice/gesture command
mapping, and the multimodal fusion rules respectively.
"""

import json
import os
import sys


# Resolved from this file's own location, not the process cwd, so every
# caller gets the same path regardless of where the app was launched from.
_CONFIG_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

# Repo root when running "python src/main.py" (dev mode) — src/config ->
# src -> repo root.
_DEV_REPO_ROOT = os.path.dirname(
    os.path.dirname(_CONFIG_DIR)
)

_cache = {}


def _resource_base_dir() -> str:
    """Base directory model/data paths (e.g. "models/...") resolve against.

    sys._MEIPASS is PyInstaller's own bundled-resource root, set in both
    --onedir and --onefile builds; the repo root otherwise. Never the
    process cwd, which is not guaranteed to be the app's own directory once
    launched from Finder/LaunchServices instead of a terminal.
    """

    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS

    return _DEV_REPO_ROOT


def resolve_model_path(relative_path: str) -> str:
    """Resolve a "models/..." style config path against _resource_base_dir().

    Args:
        relative_path: Path from config/defaults, e.g. "models/foo.task".
            Passed through unchanged if already absolute.

    Returns:
        An absolute path valid both when run from a terminal and when
        frozen inside a packaged app.
    """

    if os.path.isabs(relative_path):
        return relative_path

    return os.path.join(
        _resource_base_dir(),
        relative_path
    )


def load_config(filename: str, force_reload: bool = False) -> dict:
    """Load a JSON config file from src/config/, caching by filename.

    Args:
        filename: Name of the JSON file inside src/config/.
        force_reload: Bypass the cache and re-read from disk.

    Returns:
        The parsed JSON content.
    """

    if not force_reload and filename in _cache:
        return _cache[filename]

    config_path = os.path.join(
        _CONFIG_DIR,
        filename
    )

    with open(
        config_path,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    _cache[filename] = data

    return data


def load_system_config(force_reload: bool = False) -> dict:

    return load_config(
        "system.json",
        force_reload=force_reload
    )


def load_mapping_config(force_reload: bool = False) -> dict:

    return load_config(
        "mapping.json",
        force_reload=force_reload
    )


def load_fusion_config(force_reload: bool = False) -> dict:

    return load_config(
        "fusion.json",
        force_reload=force_reload
    )
