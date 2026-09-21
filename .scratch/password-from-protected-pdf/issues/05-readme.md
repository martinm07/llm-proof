# 05 — README and final verification

Status: done
Blocked by: 04

Implements spec §5 (`README.md`) and spec §8 (definition of done).

## Scope

- `README.md`
- Read-only verification of the rest of the repo (grep, manual CLI runs).

## Steps

1. Rewrite the README sections per spec §5:
   - **How it works** — the seed chain (canonical content → seed → marked file ID → `sha256(salt ‖ seed)[:24]`); canaries no longer affect the password; the seed is public, the salt is the sole secret.
   - **Marker** subsection next to **Salt configuration** — `--marker`, `marker` config key, default `LLMPROOF`, charset, case-sensitivity, "held like the salt" (a file protected under one marker re-derives only under the same one).
   - **Re-deriving the password** — `llm-proof password report.protected.pdf` (no `--canaries`); a wrong salt or marker yields a password that simply won't open the file (no verification is performed); the two distinct error cases.
   - **Threat model** — the seed travels with the document in the clear; a wrong salt is undetectable until someone tries to open the file.
   - **Examples** — drop `--canaries` from the re-derive example.
   - **Limitations** — PyMuPDF pin bump is a breaking change (canonical content → seed); re-saving a protected file does not change its password.
2. Run the full spec §8 definition-of-done checklist:
   - `.venv/bin/python -m pytest tests/ -v` green
   - every manual CLI case in §8 (protect → password round-trip, unencrypted rejection, foreign-PDF rejection, bad-marker rejection, `--help` output for both subcommands)
   - `grep -rn "derive_identity" src/ tests/ README.md CONTEXT.md` — no hits
   - `grep -rn "canaries" README.md` — only legitimate mentions (canary spec, insertion, attribution); no `--canaries` in the `password` examples
   - ADR-0005 exists with `status: accepted`; ADR-0003 carries `status: superseded by ADR-0005` (verify only — already done)
   - `pyproject.toml`/`uv.lock` untouched (no new dependencies)
3. Leave the design session's scratch prototypes in place (`.scratch/proto.py`, `.scratch/id-literal.py`, `.scratch/exp-*.pdf`) — they are cited by the spec and by ADR-0005's evidence trail; delete only if the maintainer asks.

## Done when

- Every item in spec §8 is checked off and the README describes the behaviour the tests prove.

## Comments

- 2026-09-21: Done. README rewritten for the seed chain, the marker subsection, the new `password` usage (protected PDF + salt only), threat model, examples, and limitations.
