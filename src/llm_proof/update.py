"""Self-update engine for the llm-proof release build.

Discovers the latest GitHub release, checks for updates with a TTL cache, and
performs the download-and-swap. Integrity is TLS-only (see ADR-0007); the
auto-check contract is in ADR-0008.
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request

from .version import get_version

REPO = "martinm07/llm-proof"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
# How often (seconds) the latest version is re-fetched; the rest of the time
# the cached value is used (ADR-0008).
TTL = 3600
STATE_FILE = "update-state.json"


def parse_semver(tag: str | None) -> tuple[int, int, int] | None:
    """Parse a version tag (with or without a leading `v`) into an int tuple.

    Returns None when the tag is not a plain three-part semantic version.
    """
    parts = (tag or "").lstrip("v").split(".")
    if len(parts) != 3:
        return None
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


def asset_name_for_platform() -> str | None:
    """Return the release asset name for the running platform, else None."""
    system = platform.system()
    if system == "Linux":
        return "llm-proof-linux-x64"
    if system == "Windows":
        return "llm-proof-windows-x64"
    return None


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))


def _release_version(release: dict | None) -> str | None:
    """Extract the version (no leading `v`) from a release dict, else None."""
    if not release:
        return None
    tag = release.get("tag_name")
    if not tag:
        return None
    return tag.lstrip("v")


def _fetch_latest_release(timeout: float = 5) -> dict | None:
    """Fetch the latest release from the GitHub API; None on any error."""
    request = urllib.request.Request(
        LATEST_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "llm-proof"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return json.load(resp)
    except Exception:  # noqa: BLE001 -- any failure is treated as "no data"
        return None


def _read_state(path: str) -> tuple[str | None, float]:
    """Read the check cache; (None, 0.0) when missing or corrupt."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return (data.get("latest"), float(data.get("checked_at", 0)))
    except (OSError, ValueError):
        return (None, 0.0)


def _write_state(path: str, version: str, checked_at: float) -> None:
    """Persist the check cache; failures are harmless."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"latest": version, "checked_at": checked_at}, f)
    except OSError:
        pass


def notice_for(current: str, latest: str) -> str | None:
    """Return the update notice string, or None when `latest` is not newer."""
    cur = parse_semver(current)
    new = parse_semver(latest)
    if cur is None or new is None or new <= cur:
        return None
    return (
        f"Update available: {latest} (currently running version {current}). "
        "Run 'llm-proof update' to update."
    )


def check_for_update(
    config_dir: str,
    force: bool = False,
    timeout: float = 5,
    current: str | None = None,
) -> tuple[str | None, str | None]:
    """Check for a newer release and return `(notice, latest_version)`.

    Uses a TTL cache in `config_dir/update-state.json`. When the cache is
    fresh the network is not contacted. A failed fetch falls back to the
    cached version (even stale); with no cache at all, `(None, None)` is
    returned. `notice` is only non-None when `latest` is strictly newer than
    `current` (ADR-0008).
    """
    if current is None:
        current = get_version()
    state_path = os.path.join(config_dir, STATE_FILE)
    cached_version, checked_at = _read_state(state_path)

    version: str | None = None
    fresh = cached_version is not None and (time.time() - checked_at) < TTL
    if not force and fresh:
        version = cached_version
    else:
        release = _fetch_latest_release(timeout)
        version = _release_version(release)
        if version is not None:
            _write_state(state_path, version, time.time())
        else:
            version = cached_version  # fall back to stale cache

    if version is None:
        return (None, None)
    return (notice_for(current, version), version)


def _download(url: str, dest: str, timeout: float) -> None:
    """Stream `url` to `dest`, overwriting any partial file."""
    request = urllib.request.Request(url, headers={"User-Agent": "llm-proof"})
    with (
        urllib.request.urlopen(request, timeout=timeout) as resp,
        open(dest, "wb") as f,
    ):
        shutil.copyfileobj(resp, f)


def _swap(temp_path: str, exe_path: str) -> None:
    """Replace the running executable with `temp_path`."""
    if platform.system() == "Windows":
        # A running exe cannot be overwritten. Stage the new binary and let a
        # short-lived helper move it into place once this process has exited.
        helper = f'timeout /t 1 >nul & move /y "{temp_path}" "{exe_path}"'
        subprocess.Popen(
            ["cmd", "/c", helper],
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
    else:
        os.replace(temp_path, exe_path)
        os.chmod(exe_path, 0o755)


def perform_update(timeout: float = 30) -> str:
    """Download the latest release artifact and swap it into place.

    Raises ValueError for user-facing conditions (not a release build, no
    asset for the platform, missing asset in the release) and Exception for
    download/swap failures. A failed run never modifies the current binary.
    """
    if not is_frozen():
        raise ValueError(
            "This install was not built from a release. "
            "Update with 'uv tool install --force llm-proof' (or reinstall from source)."
        )
    asset = asset_name_for_platform()
    if asset is None:
        raise ValueError(f"No release asset for this platform ({platform.system()}).")

    current = get_version()
    release = _fetch_latest_release(timeout)
    if release is None:
        raise ValueError("Could not reach the GitHub releases API.")
    version = _release_version(release)
    if version is None:
        raise ValueError("Could not determine the latest release version.")
    cur = parse_semver(current)
    new = parse_semver(version)
    if cur is not None and new is not None and new <= cur:
        return f"Already up to date ({current})."

    url = None
    for a in release.get("assets", []):
        if a.get("name") == asset:
            url = a.get("browser_download_url")
            break
    if url is None:
        raise ValueError(f"Release {version} has no asset named '{asset}'.")

    exe_path = sys.executable
    temp_path = os.path.join(
        os.path.dirname(exe_path), os.path.basename(exe_path) + ".new"
    )
    try:
        _download(url, temp_path, timeout)
        _swap(temp_path, exe_path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
    return (
        f"Updated llm-proof {current} -> {version}. "
        "Restart llm-proof to use the new version."
    )
