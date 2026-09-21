# 03 — Password command from the protected file

Status: done
Blocked by: 01

Implements spec §5 (`password_cmd.py` + `cli.py` password side) and decisions 7–9.

## Scope

- `src/llm_proof/password_cmd.py` (rewritten)
- `src/llm_proof/cli.py` — `password` subparser and its dispatch branch only (the `protect` region belongs to ticket 02; the shared marker-resolution block, if ticket 02 already added it, is reused, not duplicated)

## Steps

1. Rewrite `get_password(input_path: str, salt: str, marker: str = MARKER_DEFAULT) -> str` exactly per spec §5:
   - open without a password; `needs_pass` falsy → `ValueError("not a password-protected PDF")`
   - `xref_get_key(-1, "ID")` → `parse_seed(id_value, marker)`
   - `None` → `ValueError` with the marker-aware two-cause message from spec §5 (interpolate the marker looked for)
   - else `return derive_password(salt, seed)`
   - close the document in a `finally`
   - **No** `authenticate()` call, **no** canary logic, **no** `canaries_file` parameter.
2. `cli.py`:
   - `password` subparser: **remove** `--canaries`, **add** `--marker` (same help text as the protect side)
   - dispatch: `get_password(args.input, salt, marker)`; keep the existing `try/except` → `Error: ...` + exit 1; stdout is the bare password.
3. Remove now-dead imports (`canaries`, `identity`) wherever they linger in the password path.

## Done when

- `uv run llm-proof password <protected-from-ticket-02> --salt dev-salt` prints exactly the 24-hex password protect printed; nothing else on stdout.
- `uv run llm-proof password test.pdf --salt dev-salt` → exit 1, `Error: not a password-protected PDF`.
- A foreign protected PDF (e.g. any AES-256 PDF from another tool, or one built with PyMuPDF and a plain hex `/ID`) → exit 1, `Error: no "LLMPROOF" seed in the PDF's file ID: ...`.
- A ticket-02 file made with `--marker ACME` → exit 1 with `no "LLMPROOF" seed` under the default marker, and re-derives correctly with `--marker ACME`.
- `llm-proof password --help` no longer shows `--canaries`.

## Comments

- 2026-09-21: Done. `get_password` opens the protected file, requires `needs_pass`, reads `/ID` without authenticating, and derives the password from salt + seed. `--canaries` removed; `--marker` added.
