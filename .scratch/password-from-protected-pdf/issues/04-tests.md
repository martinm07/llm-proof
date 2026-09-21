# 04 — Test suite for the seed scheme

Status: done
Blocked by: 02, 03

Implements spec §5 (`tests/test_core.py`) — the full test list is there; this ticket makes the suite green and regression-proof.

## Scope

- `tests/test_core.py` only.

## Steps

1. Repoint imports: `from llm_proof.seed import extract_canonical_content` (and `derive_seed`, `parse_seed`, `validate_marker` as needed); drop `llm_proof.identity` everywhere.
2. Keep unchanged (imports aside): `test_canary_spec_parsing`, `test_canary_placement_directive`, `test_free_text_annotation_exclusion`, `test_canary_insertion`.
3. Implement/replace per spec §5, items 1–9:
   - `test_protect_creates_encrypted_pdf`
   - `test_password_re_derivation_from_protected_file` (no canary argument; `authenticate(password) != 0`)
   - `test_determinism` (twice → same password; ID literal == expected `LLMPROOF-` + truncated sha256 of canonical content, read back via `xref_get_key(-1, "ID")`)
   - `test_canary_independence` (two different canary specs + none → identical passwords; canaries extractable after unlock)
   - `test_password_rejects_unencrypted`
   - `test_password_rejects_foreign_protected` (PyMuPDF-built, plain hex `/ID`, AES-256)
   - `test_custom_marker` (`marker="ACME"`; raw bytes contain `b"(ACME-"`; default-marker lookup fails with `no "LLMPROOF" seed`)
   - `test_marker_validation` (`(bad`, `a b`, `-dash`, and an empty string all rejected with the charset message)
   - `test_seed_shape` (32 lowercase hex)
4. Build every PDF with the PyMuPDF API — **never** hand-write PDF bytes (spec §7). Use `tmp_path` fixtures; do not write manual fixtures to `/tmp`.

## Done when

- `.venv/bin/python -m pytest tests/ -v` — all green.
- No test references the old flow (no `--canaries`/`canaries_file` in `get_password` calls, no `llm_proof.identity` imports): `grep -rn "derive_identity\|canaries_file" tests/ src/` returns nothing (protect's legitimate `canaries_file` parameter is the only allowed hit in `src/`).

## Comments

- 2026-09-21: Done. 15/15 green, including the xref-stream-input regression test (`test_protect_xref_stream_input`, using the repo's PDF 1.7 `test.pdf` fixture).
