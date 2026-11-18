# 05 — Docs, version bump, gitignore

Status: done
Blocked by: 02

Implements spec §4: user-facing docs and housekeeping.

## Scope

- `README.md`
- `pyproject.toml`
- `.gitignore`

## Steps

1. `pyproject.toml`: `version = "0.3.0"` (first pipeline release).
2. `.gitignore`: add `src/llm_proof/_version.py` (build-generated).
3. `README.md`:
   - Installation: note the single-file release executables as an install option (GitHub Releases).
   - New "Updating" section: `llm-proof update`, `update --check`, the `protect` notice line, the 1-hour/offline-silent behaviour, and the pointer for source / `uv tool` installs (`uv tool install --force llm-proof`).

## Done when

- README documents the feature accurately and matches the implemented behaviour.

## Comments

- 2026-11-18: Done. `pyproject.toml` → 0.3.0, `uv.lock` regenerated, `_version.py` gitignored, README gained the release-binary install note and an "Updating" section.
