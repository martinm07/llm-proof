# 03 — Seed rule and API

Status: done
Blocked by: 02

Read `../spec.md` first — this ticket implements spec decision 1 (API), decision 2 (marker semantics), decision 3 (seed rule mirroring `src/llm_proof/seed.py::parse_seed`), and decision 6 (`encrypted`).

## Scope

- `web/src/extract-seed.ts`: `SeedResult`, `MARKER_DEFAULT`, `extractSeed` (async wrapper), `seedFromId`.

## Steps

1. `SeedResult` union exactly as spec §3.1; `seed` is 32 lowercase hex.
2. `extractSeed(input: File | Blob | ArrayBuffer | Uint8Array, marker?: string)`: File/Blob via `arrayBuffer()` (never `text()` — the content is binary); ArrayBuffer/Uint8Array pass through; thin async wrapper over the synchronous pure core `parseSeedFromPdf` (unit-testable without DOM).
3. `seedFromId`: the first element of `/ID` must be a **literal string** of `<marker>-` + exactly 32 hex characters (case-insensitive, returned lowercase). A hex first element, an indirect reference, or any other shape → `no-seed`. The second element is never consulted.
4. `encrypted` = the parsed dictionary contains an `/Encrypt` key (value never resolved).
5. Marker: optional, default `LLMPROOF`, case-sensitive, no auto-detection; a mismatched marker is a `no-seed` result, not an error (mirrors the CLI).

## Done when

- `npm run typecheck` clean; semantics mirror `parse_seed` (covered by ticket 04's tests).

## Comments

- 2026-09-22: Done — `SeedResult` union, `MARKER_DEFAULT`, async `extractSeed` (File/Blob via `arrayBuffer()`, never `text()`), and the seed rule mirroring `parse_seed`: literal-string first element of `<marker>-` + exactly 32 hex (case-insensitive → lowercase); hex/indirect/other first element → `no-seed`; second element never consulted; `encrypted` from `/Encrypt` key presence only.
- 2026-09-23: Semantic fix — `seedFromId` now accepts hex-stored `ID[0]` (the rule matches the _decoded value_; `parse_seed` sees PyMuPDF's rendering, which decodes print`able hex strings, so the Python CLI always accepted hex-stored seeds). qpdf re-saves serialize `/ID` as hex strings, which exposed the gap on the new`test1.pdf`–`test4.pdf` fixtures. Spec §3.3/§4/§6, ADR-0006, and the value model (`literal` flag dropped) updated; a synthetic qpdf-form test pins it.
