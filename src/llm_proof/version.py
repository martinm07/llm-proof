"""Version resolution for llm-proof."""

import importlib
import importlib.metadata


def get_version() -> str:
    """Return the running version string.

    Frozen (PyInstaller) builds carry a generated `_version.py` written from
    the release tag at build time. Source and `uv tool` installs fall back to
    the installed package metadata; if that is unavailable too, a neutral
    placeholder is returned.
    """
    try:
        # `_version` is generated at build time and absent from source,
        # so it is imported dynamically and its absence is not an error.
        module = importlib.import_module("._version", package=__name__)
        return module.__version__
    except (ImportError, AttributeError):
        pass
    try:
        return importlib.metadata.version("llm-proof")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"
