import json
import os


# All config JSON files live alongside this module, in
# src/config/ — resolved from this file's own location so
# every caller gets the same path regardless of the process's
# current working directory.
_CONFIG_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

_cache = {}


def load_config(filename, force_reload=False):

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


def load_system_config(force_reload=False):

    return load_config(
        "system.json",
        force_reload=force_reload
    )


def load_mapping_config(force_reload=False):

    return load_config(
        "mapping.json",
        force_reload=force_reload
    )


def load_fusion_config(force_reload=False):

    return load_config(
        "fusion.json",
        force_reload=force_reload
    )
