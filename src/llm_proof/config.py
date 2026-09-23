"""Salt and marker loading from config file, environment, and CLI flag."""

import os
import platform
import tomllib

from .seed import MARKER_DEFAULT, validate_marker


def get_config_dir():
    """Get the platform-specific config directory."""
    system = platform.system()

    if system == "Linux":
        xdg = os.environ.get("XDG_CONFIG_HOME")
        if xdg:
            return os.path.join(xdg, "llm-proof")
        return os.path.expanduser("~/.config/llm-proof")
    elif system == "Darwin":
        return os.path.expanduser("~/Library/Application Support/llm-proof")
    elif system == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return os.path.join(appdata, "llm-proof")
        return os.path.expanduser("~/AppData/Roaming/llm-proof")

    # Fallback
    return os.path.expanduser("~/.config/llm-proof")


def get_salt(salt_value: str | None = None) -> str | None:
    """Resolve the salt from flag, environment, or config file.

    Priority: explicit salt_value > LLM_PROOF_SALT env > config file.
    Returns None if no salt found.
    """
    # Check explicit value (e.g. --salt flag)
    if salt_value:
        return salt_value

    # Check environment
    env_salt = os.environ.get("LLM_PROOF_SALT")
    if env_salt:
        return env_salt

    # Check config file
    config_dir = get_config_dir()
    config_file = os.path.join(config_dir, "config.toml")
    return load_config(config_file).get("salt")


def load_config(path: str) -> dict:
    """Load a TOML config file, returning {} when missing or unparseable."""
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return {}


def get_marker(flag_value: str | None = None) -> str:
    """Resolve the marker from flag, config file, or default.

    Priority: explicit flag_value > marker key in config file > MARKER_DEFAULT.
    The resolved value is validated, so a bad config-file marker fails too.
    """
    marker = flag_value
    if marker is None:
        marker = load_config(os.path.join(get_config_dir(), "config.toml")).get(
            "marker"
        )
    if marker is None:
        marker = MARKER_DEFAULT
    validate_marker(marker)
    return marker


def get_url_template(flag_value: str | None = None) -> str | None:
    if flag_value:
        return flag_value

    url_template = load_config(os.path.join(get_config_dir(), "config.toml")).get(
        "url_template"
    )

    return url_template
