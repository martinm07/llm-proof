# 01 — Seed module and marker config

Status: done
Blocked by: none

Read `../spec.md` first — this ticket implements spec §5 for `seed.py` and `config.py` and decision 11 (renaming).

## Scope

- Create `src/llm_proof/seed.py`; delete `src/llm_proof/identity.py`.
- Extend `src/llm_proof/config.py` with marker resolution.

## Steps

1. Move `extract_canonical_content` from `identity.py` to `seed.py` **unchanged** (including its helpers `extract_words` and `get_freetext_annotations`).
2. Add to `seed.py` per spec §5:
   - `MARKER_DEFAULT = "LLMPROOF"` and `MARKER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")`
   - `derive_seed(canonical_content: str) -> str` — `hashlib.sha256(canonical_content.encode("utf-8")).digest()[:16].hex()` (32 lowercase hex chars; the old `derive_identity`'s full-64-hex behaviour is retired, not renamed)
   - `validate_marker(marker: str) -> None` — `ValueError` with the user-friendly message from spec §5 (interpolate the offending value)
   - `seed_literal(marker: str, seed: str) -> str` — `f"({marker}-{seed})"`
   - `parse_seed(id_value: str, marker: str) -> str | None` — exactly the three-step parse in spec §5 (literal/hex first-element detection, prefix check, 32-hex case-insensitive check, lowercase return)
3. In `config.py`:
   - factor `load_config(path: str) -> dict` out of `load_salt_from_file` (returns `{}` on missing/unparseable file); `get_salt` keeps its exact behaviour and precedence
   - add `get_marker(flag_value: str | None = None) -> str`: flag > `marker` config key > `MARKER_DEFAULT`, then `validate_marker` on the resolved value
4. No other files are touched in this ticket. Do not wire `protect.py`/`password_cmd.py`/`cli.py` yet (tickets 02/03).

## Done when

- `python -c "from llm_proof.seed import derive_seed, parse_seed, validate_marker, seed_literal, extract_canonical_content, MARKER_DEFAULT"` succeeds; `identity.py` is gone.
- `parse_seed('[(LLMPROOF-f66fbc1333121d9b50ed64a4e8cc04a8)<8FF36D3E506326F95BCD86C9D7FEA758>]', 'LLMPROOF')` returns `'f66fbc1333121d9b50ed64a4e8cc04a8'`; the same input with marker `ACME`, a hex-first ID, or a 31/33-char tail returns `None`.
- `get_salt` behaviour is unchanged (grep the diff).

Note: the test suite is red after this ticket until 02/03 repoint imports — that is expected; ticket 04 fixes it.

## Comments

- 2026-09-21: Done. `src/llm_proof/seed.py` created (derive_seed, validate_marker, seed_literal, parse_seed, extract_canonical_content); marker config in `config.py` (flag > config `marker` > default); `identity.py` deleted.
