# 04 — Fixtures and tests

Status: done
Blocked by: 01

Read `../spec.md` first — this ticket implements spec §5 (fixtures + test file) and the §8 definition of done.

## Scope

- `.scratch/web-seed-extractor/generate-fixtures.py` — one-off generator for the 4 generated fixtures. Run once and never re-run: the committed bytes and the hardcoded expected seed in the test file are the test input.
- `web/tests/extract-seed.test.ts` — 14 fixture cases + core unit tests + Blob/File async paths.

## Steps

1. Generate (via `.venv/bin/python` from the repo root):
   - `protected-classic-llmproof.pdf` — the repo's own `llm-proof protect` (fixed salt, default marker) on a small fixed plain PDF.
   - `protected-classic-acme.pdf` — same input, `--marker ACME`; same seed.
   - `plain-xrefstream-llmproof.pdf` — root `test.pdf` byte-patched: `/ID [(LLMPROOF-<seed>)(LLMPROOF-<seed>)]` inserted into the xref-stream dictionary (plain text; `/Length` covers stream data only); the 7-digit `startxref` value stays valid because the insertion sits inside the dictionary, after the object start — verify, don't assume.
   - `garbage.bin` — fixed non-PDF bytes.
2. Record the expected seed in the test file (one value, shared by all three seed-bearing fixtures).
3. Fixture cases: 14 files, asserting `kind`, exact `seed` where applicable, and `encrypted` per the §4 matrix. `protected-classic-acme.pdf` is asserted with the default marker (`no-seed`) and with `ACME` (`seed`).
4. Core unit tests on `parseSeedFromPdf` (synthetic in-memory PDFs): literal-string escape decoding (octal, backslash-EOL continuation, nested parens), name `#`-escape (`/I#44` ≡ `/ID`), hex-string first element → `no-seed`, multi-line arrays, indirect `/ID` → `no-seed`, startxref fallback (corrupt last `startxref` → earlier one wins), not-a-pdf shapes.
5. Async paths: `extractSeed(new Blob([bytes]))` and `extractSeed(new File([bytes], …))` (Node 24 globals).
6. DoD sanity (spec §8): a Node one-liner over `protected-classic-llmproof.pdf` → `{ kind: "seed", … }`.

## Done when

- `cd web && npm test` green (all 14 fixture cases + core unit tests); `npm run typecheck` clean; `git status` shows only `web/`, `docs/adr/0006-*`, `CONTEXT.md`, `.scratch/web-seed-extractor/`.

## Comments

- 2026-09-22: Done — 4 generated fixtures + 10 user-procured files = 14 fixture cases, plus 26 synthetic core/async tests (40 total), all green. DoD sanity (spec §8): Node one-liner `extractSeed(new Blob([readFileSync(protected-classic-llmproof.pdf)]))` → `{ "kind": "seed", "seed": "60b5…b7a5", "encrypted": true }`.
- 2026-09-22: Test-input fix — the escaped-`)` unit test originally fed `(LLMPROOF-<seed>\)` with no unescaped closing paren (an unbalanced string → candidate rejected → `not-a-pdf`); the input was corrected to `(LLMPROOF-<seed>\))` so the escaped paren is decoded content before the real closer, matching the test's stated intent (`no-seed`: 33 chars after the marker).
