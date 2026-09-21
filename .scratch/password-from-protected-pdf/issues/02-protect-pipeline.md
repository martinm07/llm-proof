# 02 — Protect pipeline: seed before canaries, marked /ID

Status: done
Blocked by: 01

Implements spec §5 (`protect.py` + `cli.py` protect side) and decisions 4–6, 9.

## Scope

- `src/llm_proof/protect.py`
- `src/llm_proof/cli.py` — `protect` subparser and its dispatch branch only (the `password` region belongs to ticket 03)

## Steps

1. Repoint `protect.py` imports to `llm_proof.seed` (`extract_canonical_content`, `derive_seed`, `seed_literal`, `MARKER_DEFAULT`).
2. Reorder `protect_pdf` per spec §5: open → `needs_pass` guard → **canonical (before canaries)** → `seed = derive_seed(canonical)` → `password = derive_password(salt, seed)` → `doc.xref_set_key(-1, "ID", f"[{seed_literal(marker, seed)}{seed_literal(marker, seed)}]")` → insert canaries (existing logic) → save AES-256 (`user_pw == owner_pw`, keep the existing `# pyright: ignore` comment).
   - **Do not** put a literal at `/ID[1]` and **do not** mix hex-first/literal-second — the both-literal write is the only verified-safe form (spec §4).
3. `protect_pdf` gains a `marker: str = MARKER_DEFAULT` parameter (position it after `canaries_file`).
4. `cli.py`: add `--marker` to the `protect` subparser (help text per spec §5); resolve the marker **after** salt resolution with its own `try/except ValueError` → `Error: ...` on stderr, exit 1 (spec §5 snippet); pass `marker=marker` into `protect_pdf`.
5. `protect` print behaviour is unchanged: `Protected: ...`, `Canaries inserted: N` (when > 0), `Password used: <24hex>`.

## Done when

- Manual: `.venv/bin/python -m llm_proof.protect`-equivalent via the CLI — `uv run llm-proof protect test.pdf --canaries canaries.txt --salt dev-salt -o /tmp/p.pdf` succeeds; the raw bytes of `/tmp/p.pdf` contain `(LLMPROOF-` followed by 32 hex; running the same command again yields the **identical** `Password used:` line; a run with `--marker ACME` yields `(ACME-` in the file and the same password as the unmarked-marker run (same salt, same document).
- Re-saving the protected file (open with password, save) keeps `Password used:` re-derivable — check by reopening and confirming `xref_get_key(-1, "ID")` still starts with the literal.

## Comments

- 2026-09-21: Done. `protect_pdf` carries the marked seed in `/ID` and verifies by read-back; when the trailer is a cross-reference stream (PyMuPDF silently drops `xref_set_key(-1, "ID", ...)` there) it round-trips through a plain save, reopens, sets the ID, re-verifies, then does the single final encrypted save.
