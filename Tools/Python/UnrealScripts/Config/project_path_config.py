"""
Per-machine path config shared by all tools.

Values live only in a local json file under the UE project's Saved folder (never in source control),
so each PC can point to its own paths. Edit them with the Project Path Config tool.

    from Config import project_path_config
    exe = project_path_config.require_path("ff16_converter_exe")

A key requested by a tool but not yet configured is added to the local file with an empty value,
so it shows up in the config tool ready to be filled in.
"""
import json
import os

import path_util

PROJECT_PATH_CONFIG_FILE = os.path.join(path_util.tool_output_temp_folder(), "GlobalConfig/ProjectPaths.json")


def load_paths() -> dict:
    if not os.path.isfile(PROJECT_PATH_CONFIG_FILE):
        return {}
    try:
        with open(PROJECT_PATH_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_paths(values: dict):
    """Replace the whole config with values."""
    os.makedirs(os.path.dirname(PROJECT_PATH_CONFIG_FILE), exist_ok=True)
    with open(PROJECT_PATH_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(values, f, indent=4)


def get_path(key: str) -> str:
    """Configured value for key, or '' if not set (the key is then registered empty for the config tool)."""
    data = load_paths()
    if key not in data:
        data[key] = ""
        save_paths(data)
    return data[key]


def require_path(key: str) -> str:
    """Like get_path, but raises if the value is empty."""
    value = get_path(key)
    if not value:
        raise ValueError("Path '{}' is not configured. Set it in Project Path Config ({}).".format(
            key, PROJECT_PATH_CONFIG_FILE))
    return value
