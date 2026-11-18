"""Tests for the self-update engine (src/llm_proof/update.py).

No live network: `_fetch_latest_release` is always mocked.
"""

import json
import time

import pytest

from llm_proof import update


def make_release(tag):
    return {
        "tag_name": tag,
        "assets": [
            {
                "name": "llm-proof-linux-x64",
                "browser_download_url": "https://example.com/llm-proof-linux-x64",
            }
        ],
    }


def seed_state(tmp_path, version, checked_at):
    (tmp_path / "update-state.json").write_text(
        json.dumps({"latest": version, "checked_at": checked_at})
    )


# --- parse_semver ---------------------------------------------------------


def test_parse_semver():
    assert update.parse_semver("1.2.3") == (1, 2, 3)
    assert update.parse_semver("v1.2.3") == (1, 2, 3)
    assert update.parse_semver("1.2") is None
    assert update.parse_semver("a.b.c") is None
    assert update.parse_semver("") is None
    assert update.parse_semver(None) is None


# --- notice_for -----------------------------------------------------------


def test_notice_for():
    assert (
        update.notice_for("0.2.0", "0.3.0")
        == "Update available: 0.3.0 (currently running version 0.2.0). "
        "Run 'llm-proof update' to update."
    )
    assert update.notice_for("0.3.0", "0.3.0") is None
    assert update.notice_for("0.4.0", "0.3.0") is None
    assert update.notice_for("0.2.0", "garbage") is None
    assert update.notice_for("garbage", "0.3.0") is None


# --- asset_name_for_platform ----------------------------------------------


def test_asset_name_for_platform(monkeypatch):
    import platform

    monkeypatch.setattr(platform, "system", lambda: "Linux")
    assert update.asset_name_for_platform() == "llm-proof-linux-x64"
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    assert update.asset_name_for_platform() == "llm-proof-windows-x64"
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    assert update.asset_name_for_platform() is None


# --- check_for_update -----------------------------------------------------


def test_check_uses_fresh_cache(tmp_path, monkeypatch):
    seed_state(tmp_path, "0.3.0", time.time())
    calls = []
    monkeypatch.setattr(
        update, "_fetch_latest_release", lambda *a, **k: calls.append(1) or None
    )
    notice, latest = update.check_for_update(str(tmp_path), current="0.2.0")
    assert calls == []  # fresh cache -> no network
    assert latest == "0.3.0"
    assert notice is not None and "0.3.0" in notice


def test_check_fresh_fetch_writes_state(tmp_path, monkeypatch):
    monkeypatch.setattr(
        update, "_fetch_latest_release", lambda *a, **k: make_release("v0.4.0")
    )
    notice, latest = update.check_for_update(str(tmp_path), current="0.2.0")
    assert latest == "0.4.0"
    assert notice is not None
    state = json.loads((tmp_path / "update-state.json").read_text())
    assert state["latest"] == "0.4.0"


def test_check_falls_back_to_stale_cache(tmp_path, monkeypatch):
    seed_state(tmp_path, "0.3.0", 0.0)  # stale
    monkeypatch.setattr(update, "_fetch_latest_release", lambda *a, **k: None)
    notice, latest = update.check_for_update(str(tmp_path), current="0.2.0")
    assert latest == "0.3.0"
    assert notice is not None


def test_check_no_cache_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(update, "_fetch_latest_release", lambda *a, **k: None)
    notice, latest = update.check_for_update(str(tmp_path), current="0.2.0")
    assert notice is None
    assert latest is None


def test_check_force_bypasses_fresh_cache(tmp_path, monkeypatch):
    seed_state(tmp_path, "0.2.0", time.time())  # fresh
    calls = []

    def fake(*a, **k):
        calls.append(1)
        return make_release("v0.5.0")

    monkeypatch.setattr(update, "_fetch_latest_release", fake)
    notice, latest = update.check_for_update(str(tmp_path), force=True, current="0.2.0")
    assert calls == [1]
    assert latest == "0.5.0"
    assert notice is not None


def test_check_no_notice_when_current_is_newer(tmp_path, monkeypatch):
    monkeypatch.setattr(
        update, "_fetch_latest_release", lambda *a, **k: make_release("v0.2.0")
    )
    notice, latest = update.check_for_update(str(tmp_path), current="0.3.0")
    assert latest == "0.2.0"
    assert notice is None


# --- perform_update -------------------------------------------------------


def test_perform_update_refuses_non_frozen(monkeypatch):
    monkeypatch.setattr(update, "is_frozen", lambda: False)
    with pytest.raises(ValueError, match="uv tool install --force"):
        update.perform_update()


def test_perform_update_no_asset_platform(monkeypatch):
    monkeypatch.setattr(update, "is_frozen", lambda: True)
    monkeypatch.setattr(update, "asset_name_for_platform", lambda: None)
    with pytest.raises(ValueError, match="No release asset"):
        update.perform_update()


def test_perform_update_already_current(monkeypatch):
    monkeypatch.setattr(update, "is_frozen", lambda: True)
    monkeypatch.setattr(
        update, "asset_name_for_platform", lambda: "llm-proof-linux-x64"
    )
    monkeypatch.setattr(update, "get_version", lambda: "0.5.0")
    monkeypatch.setattr(
        update, "_fetch_latest_release", lambda *a, **k: make_release("v0.4.0")
    )
    assert "Already up to date" in update.perform_update()


# --- state round-trip -----------------------------------------------------


def test_state_roundtrip(tmp_path):
    path = str(tmp_path / "s.json")
    update._write_state(path, "0.3.0", 123.0)
    assert update._read_state(path) == ("0.3.0", 123.0)


def test_read_state_corrupt(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("not json")
    assert update._read_state(str(path)) == (None, 0.0)


def test_read_state_missing(tmp_path):
    assert update._read_state(str(tmp_path / "absent.json")) == (None, 0.0)
