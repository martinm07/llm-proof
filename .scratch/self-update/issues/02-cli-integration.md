# 02 — CLI integration: update command, --version, auto-check

Status: done
Blocked by: 01

Implements spec §3.5, 8: wire the update engine into the CLI.

## Scope

- `src/llm_proof/cli.py`

## Steps

1. Add `--version` to the top-level parser (`action="version"`, `llm-proof <version>`).
2. Add the `update` subparser with a `--check` flag.
3. `update` path:
   - `--check`: fresh check (`force=True`); print `Update available: ...` (exact notice) or `Already up to date (<version>).`; if the latest version can't be determined at all, print an error to stderr and exit 1.
   - perform: `perform_update()`; print the result; `ValueError`/`Exception` → `Error: ...` on stderr, exit 1.
4. Auto-check: before dispatching `protect`/`password`, run `check_for_update(get_config_dir())` (TTL-cached). Capture the notice.
5. `protect` success path: after the existing result lines (and the optional generated URL), print the notice if present. `password` never prints it.
6. `update` does not run the auto-check (it performs its own lookups).

## Done when

- `llm-proof --version`, `llm-proof update --check`, `llm-proof update` behave per spec.
- `password` stdout is unchanged (password and nothing else).
- The notice appears only after a successful `protect`, and only when a newer stable release exists.

## Comments

- 2026-11-18: Done. `--version` flag, `update` subcommand with `--check`, auto-check before `protect`/`password` (notice printed only after a successful `protect`). Verified offline: `protect` output unchanged, `update --check` reports the offline error and exits 1.
