"""JSON config loading shared by every pipeline module.

Loads and caches system.json, mapping.json and fusion.json — the files
that back OSController hotkeys/apps/URLs, the voice/gesture command
mapping, and the multimodal fusion rules respectively.
"""

import json
import os


# Resolved from this file's own location, not the process cwd, so every
# caller gets the same path regardless of where the app was launched from.
_CONFIG_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

_cache = {}


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
