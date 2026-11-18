# 04 — Unit tests for the update engine

Status: done
Blocked by: 01

Implements spec §4: `tests/test_update.py`. No live network — `_fetch_latest_release` is always mocked.

## Scope

- `tests/test_update.py` (new)

## Steps

1. `parse_semver`: valid `1.2.3`, `v1.2.3` prefix, malformed (`1.2`, `a.b.c`, empty) → `None`.
2. `notice_for`: newer → exact string; equal → `None`; older → `None`; malformed → `None`.
3. `asset_name_for_platform`: monkeypatched `platform.system` → linux/windows/`None` (Darwin).
4. `check_for_update`:
   - fresh cache hit (seeded `update-state.json` within TTL) → no fetch call, returns cached notice.
   - stale/missing cache → fetch called, state written, notice from fresh version.
   - fetch failure + stale cache → falls back to cached version.
   - fetch failure + no cache → `(None, None)`.
   - `force=True` bypasses a fresh cache.
5. `perform_update`:
   - not frozen → `ValueError` mentioning `uv tool install --force`.
   - frozen + unsupported platform → `ValueError`.
   - frozen + latest <= current → "Already up to date".
6. State round-trip: `_write_state`/`_read_state` (including a corrupt file → `(None, 0.0)`).

## Done when

- `uv run pytest tests/test_update.py -v` — all green, offline.

## Comments

- 2026-11-18: Done. `tests/test_update.py` — 15 tests, all offline (`_fetch_latest_release` mocked). Full suite 30/30 green.
