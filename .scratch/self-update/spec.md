# Spec: self-update for the llm-proof release build

Status: done
Design: agreed 2026-11-18 — see ADR-0007 (accepted), ADR-0008 (accepted)

## 1. Goal

The single-file release executable updates itself from the project's GitHub Releases: it discovers the latest release, downloads the matching platform artifact, and swaps itself into place. A one-line notice surfaces in `protect` output when a newer release exists.

User story:

```bash
llm-proof protect report.pdf
# ... later, when 0.3.0 is out:
# Update available: 0.3.0 (currently running version 0.2.0). Run 'llm-proof update' to update.
llm-proof update            # Updated llm-proof 0.2.0 -> 0.3.0. Restart to use it.
llm-proof update --check    # report-only
llm-proof --version         # llm-proof 0.3.0
```

Acceptance:

- `update` downloads the correct `llm-proof-{os}-{arch}` asset and swaps it in; a failed or interrupted download never touches the current binary.
- `update` on a non-frozen install (source / `uv tool`) refuses with a pointer to `uv tool install --force llm-proof`.
- `update --check` and `--version` work without downloading.
- The notice appears only in `protect`, only on success, only when the latest stable release is strictly newer than the running version.
- Offline / rate-limited / API errors never delay, fail, or add output to any command.

## 2. Current state (what you are changing)

- `src/llm_proof/cli.py` — argparse; `protect` and `password` subcommands; top-level catch-all per command. Gains an `update` subcommand, a `--version` flag, and the auto-check + notice wiring.
- `src/llm_proof/config.py` — `get_config_dir()` (platform config dir). Unchanged; the check cache lives beside `config.toml` here.
- `pyproject.toml` — version `0.2.0` → `0.3.0` (first pipeline release). No new dependencies.
- `.github/workflows/python-app.yml` — `workflow_dispatch`-only PyInstaller build via a third-party action; **replaced** by a tag-triggered release pipeline.
- Releases today: `v0.1.0`, `v0.2.0` with zip-wrapped assets `llm-proof-{os}.zip`. New releases use bare executables `llm-proof-{os}-x64`.

## 3. Design decisions (agreed — do not revisit)

1. **Channel**: frozen single-file build only; TLS-only integrity (ADR-0007).
2. **Artifacts**: `llm-proof-linux-x64`, `llm-proof-windows-x64` (bare executables, no archive). No asset for another platform → clear error.
3. **Discovery**: `GET /repos/martinm07/llm-proof/releases/latest` (unauthenticated GitHub API).
4. **Check**: before `protect`/`password`; TTL 1 h cache in `config_dir/update-state.json`; 5 s timeout; silent on any failure, falling back to a stale cached version when one exists.
5. **Notice**: `protect` only, stdout, after a successful run: `Update available: {latest} (currently running version {current}). Run 'llm-proof update' to update.`
6. **Version**: `_version.py` generated from the tag at build time; source installs fall back to package metadata. Exposed as `llm-proof --version`.
7. **Swap**: Linux `os.replace` (atomic, in-process); Windows stages to `<exe>.new` and a delayed `move` helper swaps it in after the process exits.
8. **Commands**: `update` (perform) and `update --check` (report-only).
9. **Pipeline**: `v*` tag push → build linux + windows (uv, PyInstaller 6.20.0, `_version.py` injected from the tag) → create release (`softprops/action-gh-release`) → upload both assets. First release `v0.3.0`.
10. **CA store**: TLS verification is pinned to `certifi` (data-only runtime dependency, added in 0.3.1) because some Python builds — uv-managed interpreters, PyInstaller bundles — cannot locate the system CA store. See ADR-0007.

## 4. Files

- `src/llm_proof/version.py` (new) — version resolution.
- `src/llm_proof/_version.py` (generated at build time; gitignored).
- `src/llm_proof/update.py` (new) — discovery, check + TTL cache, notice, download + swap.
- `src/llm_proof/cli.py` — `update` subcommand, `--version`, auto-check + notice.
- `.github/workflows/release.yml` (new; replaces `python-app.yml`).
- `tests/test_update.py` (new).
- `README.md`, `pyproject.toml`, `.gitignore`.
