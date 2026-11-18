# 01 — Version resolution and update core module

Status: done
Blocked by: (none)

Implements spec §3.1–7: version resolution and the self-update engine (discovery, check + TTL cache, notice, download + swap).

## Scope

- `src/llm_proof/version.py` (new)
- `src/llm_proof/update.py` (new)
- `src/llm_proof/_version.py` (generated at build time only — gitignored, never committed)

## Steps

1. `version.py::get_version()`: try `from . import _version` (frozen builds carry a generated `_version.py` from the tag); fall back to `importlib.metadata.version("llm-proof")`; fall back to `"0.0.0"`.
2. `update.py`:
   - `REPO = "martinm07/llm-proof"`, `LATEST_URL` = the `releases/latest` endpoint, `TTL = 3600`.
   - `parse_semver(tag)` — strip `v`, require 3 dot-separated ints, else `None`.
   - `_fetch_latest_release(timeout=5)` — unauthenticated GitHub API; return the release dict or `None` on any error.
   - `asset_name_for_platform()` — `llm-proof-linux-x64` / `llm-proof-windows-x64` / `None`.
   - `check_for_update(config_dir, force=False, timeout=5, current=None)` — TTL cache in `config_dir/update-state.json` (`{"latest", "checked_at"}`); fresh fetch when stale/forced; on fetch failure fall back to the cached value (even stale); return `(notice, latest_version)` where `notice` is the exact string only when latest > current.
   - `notice_for(current, latest)` — the exact notice string or `None`.
   - `perform_update(timeout=30)` — refuse when not frozen (pointer to `uv tool install --force llm-proof`); select asset by platform; fresh fetch; "Already up to date" when latest <= current; download to `<exe>.new`; swap: Linux `os.replace` + `chmod 0o755`, Windows delayed `move` helper after exit; remove the temp file on failure; return the result message.
3. Add `src/llm_proof/_version.py` to `.gitignore`.

## Done when

- `get_version()` returns the package version in a source install.
- `check_for_update`/`perform_update` pass the unit tests in ticket 04 (no live network in tests).

## Comments

- 2026-11-18: Done. `version.py::get_version()` (dynamic `_version` import → metadata → `0.0.0`) and `update.py` (parse_semver, asset_name_for_platform, is_frozen, check_for_update with TTL cache + stale fallback, notice_for, perform_update with Linux `os.replace` / Windows delayed-move swap). `_version.py` gitignored.
