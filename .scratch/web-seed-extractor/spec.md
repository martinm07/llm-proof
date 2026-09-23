# Spec: browser-side seed extraction from the file ID

Status: ready-for-agent
Design: agreed 2026-09-22 — see ADR-0006 (accepted); ADR-0005 (in force: on-disk form of the seed)

## 1. Goal

A client-side TypeScript module that, given a PDF uploaded through the browser File API, extracts the **seed** carried in the file's unencrypted **file ID** — reading `/ID` only. No canonical-content computation, no seed generation, no password derivation (those are a later feature and will have a later spec).

User story:

```ts
const file = /* <input type="file"> */;
const result = await extractSeed(file); // marker defaults to LLMPROOF
// { kind: "seed", seed: "f66fbc1333121d9b50ed64a4e8cc04a8", encrypted: true }
```

Acceptance:

- A protected document produced by `llm-proof protect` yields its seed (32 lowercase hex) under its marker, with no password.
- A foreign/encrypted-but-not-llm-proof PDF yields `no-seed` (distinct from `not-a-pdf`), with `encrypted: true`.
- An unencrypted file with no marked seed yields `no-seed`, `encrypted: false`.
- Garbage / non-PDF input yields `not-a-pdf`.
- Nothing leaves the browser: the module reads bytes via `File.arrayBuffer()` and computes nothing cryptographic.

## 2. Current state (what you are adding)

- A new top-level `web/` package, isolated from the Python project (`pyproject.toml`, `uv.lock`, `.github/` untouched).
- `web/src/extract-seed.ts` — the single self-contained module (all code lives here).
- `web/tests/extract-seed.test.ts` + `web/tests/fixtures/` — vitest suite over committed fixture PDFs (10 real-world files already in place, §4; 4 more generated, §5).
- `package.json` / `tsconfig.json` — editor and test wiring only; no build output, no runtime dependencies.

## 3. Design decisions (agreed — do not revisit)

1. **API** (the whole public surface):

   ```ts
   type SeedResult =
     | { kind: "seed"; seed: string; encrypted: boolean } // seed: 32 lowercase hex
     | { kind: "no-seed"; encrypted: boolean } // PDF parsed; no marked seed in /ID (or no /ID)
     | { kind: "not-a-pdf" }; // no parseable trailer / xref section

   const MARKER_DEFAULT: string; // "LLMPROOF"
   function extractSeed(
     input: File | Blob | ArrayBuffer | Uint8Array,
     marker?: string, // defaults to MARKER_DEFAULT; case-sensitive
   ): Promise<SeedResult>;
   ```

   `extractSeed` is a thin async wrapper over a synchronous pure core `parseSeedFromPdf(bytes: Uint8Array, marker: string): SeedResult` (unit-testable without DOM).

2. **Marker semantics mirror the CLI** (ADR-0005): optional parameter, default `LLMPROOF`, case-sensitive, no auto-detection. A mismatched marker is a `no-seed` result, not an error — the same deliberate signal as `llm-proof password`.
3. **Seed rule mirrors the semantics of `llm_proof.seed.parse_seed`**: the first element of `/ID` must be a **string** — literal- or hex-stored (both carry the same byte value, §7.3.4; `parse_seed` sees PyMuPDF's rendering, which decodes a printable hex string, so the storage form is immaterial) — whose decoded value starts with `<marker>-` followed by **exactly 32 hex characters** (case-insensitive, returned lowercase). An indirect reference or any other non-string shape → `no-seed`. The second element is never consulted.
4. **Parser scope** (ADR-0006): locate the section the file's **last `startxref`** points to; parse exactly one dictionary from it — the classic `trailer` dictionary, or the xref-stream object's stream dictionary; read `/ID` and the presence of `/Encrypt`. Never scan the file for `/ID`; never follow `/Prev`; never resolve indirect references (indirect `/ID` → `no-seed`); never parse xref entries, object streams, or stream data.
5. **Robustness rules**:
   - Bounded backward scan (last ≈10 KB) collecting every `startxref` occurrence; each occurrence yields a candidate offset (decimal integer, whitespace-tolerant).
   - Each candidate is **structurally validated**: the offset must point at the `xref` keyword (classic) or at `N G obj` + dictionary + `stream` (xref stream). Candidates are tried last-occurrence-first; the first candidate yielding a parseable dictionary wins; none → `not-a-pdf`.
   - A dictionary is accepted if it parses and contains at least one of `/ID`, `/Root`, `/Size`, `/Encrypt`.
   - Byte-level throughout (binary-safe); `%PDF-` header sanity check at offset 0.
6. **`encrypted`** = the parsed dictionary contains an `/Encrypt` key (value never resolved).
7. **File**: one module, well-commented, citing ISO 32000-1:2008 (§7.3 notation, §7.5.2 file structure, §7.5.4 xref tables, §7.5.7 trailers, §7.5.8 xref streams, §7.6.3 encryption) at each structural step.
8. **Tooling**: vitest only (dev dependency, alongside typescript). No CI (explicitly deferred). No build step.

## 4. Verified facts

All verified this session against the repo and its fixtures.

- On-disk seed form (ADR-0005, `.scratch/id-literal.py`): `/ID [(<MARKER>-<seed>)(<MARKER>-<seed>)]` — a literal in **both** elements; readable without a password on an AES-256 save; PyMuPDF preserves `/ID[0]` across re-saves. Note (verified against the generated fixtures): PyMuPDF's encrypted save keeps `ID[0]` as the marked literal but rewrites `ID[1]` as a hex string (`[(LLMPROOF-<seed>)<HEX>]`, `ID[1]` non-deterministic across saves). The extraction rule consults only `ID[0]` (mirroring `parse_seed`), so this is immaterial.
- **qpdf re-saves serialize `/ID` as hex strings** (verified on the user-procured `test1.pdf`–`test4.pdf`, qpdf variants of an `llm-proof protect` output: `/ID [<4c4c…><…>]`, where `<4c4c…>` decodes to `LLMPROOF-<seed>`). PyMuPDF decodes the value before `parse_seed` runs, so the CLI accepts these files; the web rule matches on the decoded value likewise (decision 3).
- **`/ID` is unencrypted** in the classic trailer (ISO 32000-1:2008 §7.6.3) — confirmed by the repo's `.scratch` experiments and by every fixture below reading cleanly through PyMuPDF with no password.
- **The xref-stream _dictionary_ is unencrypted even in an encrypted file** (§7.5.8): confirmed empirically by `enc-xrefstream-hex.pdf` (qpdf AES-encrypted; the dictionary at the `startxref` offset is plain text carrying `/ID` and `/Encrypt`). Only the xref stream's _stream data_ is compressed/encrypted — and it is never parsed.
- **Linearized files**: the last `startxref` points at the _first_ section (offset 216 in both linearized classic fixtures), whose trailer is complete (`/ID` + `/Encrypt` present); the main section's trailer may omit `/Encrypt` by `/Prev`-inheritance (`enc-linearized-classic.pdf`) — hence "read only the pointed-at section, never follow /Prev".
- **`/ID` keys occur in object dictionaries in the wild**: `plain-classic-obj-id-1/2.pdf` carry fifty-plus `/ID` keys in image/page objects (mostly indirect refs such as `/ID 52 0 R`); `plain-classic-id-traps.pdf` additionally carries `/IDS` names and a page-dict `/ID 34 0 R`. Only the authoritative trailer's `/ID` is meaningful.
- Fixture matrix (PyMuPDF ground truth, read with no password):

  | fixture                                | shape                                          | needs_pass | authoritative /ID                                                 | expected                            |
  | -------------------------------------- | ---------------------------------------------- | :--------: | ----------------------------------------------------------------- | ----------------------------------- |
  | `enc-classic-hex-same.pdf`             | enc, classic                                   |     1      | hex, identical pair                                               | `no-seed`                           |
  | `enc-classic-hex-pair.pdf`             | enc, classic                                   |     1      | hex, distinct pair                                                | `no-seed`                           |
  | `enc-linearized-classic.pdf`           | enc, linearized classic (2 sections)           |     1      | hex; 1st-section trailer complete                                 | `no-seed`                           |
  | `enc-linearized-classic-pair.pdf`      | enc, linearized classic (2 sections, AcroForm) |     1      | hex, distinct pair                                                | `no-seed`                           |
  | `enc-classic-hex-multiline.pdf`        | enc, classic                                   |     1      | hex, multi-line array                                             | `no-seed`                           |
  | `enc-xrefstream-hex.pdf`               | enc, **xref stream**                           |     1      | hex in plain-text dict + `/Encrypt`                               | `no-seed`                           |
  | `plain-classic-obj-id-1.pdf`           | plain, classic                                 |     0      | hex; 51× object-dict `/ID` keys                                   | `no-seed`                           |
  | `plain-classic-obj-id-2.pdf`           | plain, classic                                 |     0      | hex; same traps                                                   | `no-seed`                           |
  | `plain-classic-id-traps.pdf`           | plain, classic                                 |     0      | hex; `/IDS` + page-dict `/ID`                                     | `no-seed`                           |
  | `plain-linearized-xrefstream.pdf`      | plain, linearized **xref stream** (2 sections) |     0      | hex in 1st-section dict; nested `/DecodeParms`, `/Index`, `/Prev` | `no-seed`                           |
  | `protected-classic-llmproof.pdf` (gen) | enc, classic                                   |     1      | `(LLMPROOF-<seed>)` literal at `ID[0]` (`ID[1]` hex, §4 note)     | `seed`                              |
  | `protected-classic-acme.pdf` (gen)     | enc, classic                                   |     1      | `(ACME-<seed>)` literal at `ID[0]`                                | `seed` w/ `ACME`; `no-seed` default |
  | `plain-xrefstream-llmproof.pdf` (gen)  | plain, **xref stream**                         |     0      | `(LLMPROOF-<seed>)` literal pair                                  | `seed`                              |
  | `test1.pdf` (user)                     | enc, classic (qpdf re-save)                    |     1      | hex `ID[0]` = `LLMPROOF-<seed>` (qpdf hex form)                   | `seed`                              |
  | `test2.pdf` (user)                     | enc, linearized classic (2 sections, qpdf)     |     1      | hex in both section trailers; last `startxref` → 1st-section xref | `seed`                              |
  | `test3.pdf` (user)                     | plain, classic (qpdf decrypt)                  |     0      | hex `ID[0]` = `LLMPROOF-<seed>`                                   | `seed`                              |
  | `test4.pdf` (user)                     | enc, classic (qpdf re-encryption)              |     1      | hex `ID[0]` = `LLMPROOF-<seed>`                                   | `seed`                              |
  | `garbage.bin` (gen)                    | non-PDF                                        |     —      | —                                                                 | `not-a-pdf`                         |

## 5. Target design (per file)

### `web/package.json` (new)

`"private": true`, `"type": "module"`, scripts: `"test": "vitest run"`, `"typecheck": "tsc --noEmit"`. devDependencies only: `vitest`, `typescript`. No dependencies.

### `web/tsconfig.json` (new)

Strict; target ES2022; module/resolution settings sufficient for vitest and the editor.

### `web/src/extract-seed.ts` (new — the whole feature, ~350–500 lines with docs)

Internal structure, top to bottom, all in one file:

1. Public types + `extractSeed` (async wrapper: `File | Blob | ArrayBuffer | Uint8Array` → bytes → core).
2. Core `parseSeedFromPdf(bytes, marker)`:
   - header check (`%PDF-`);
   - `candidateOffsets()`: bounded backward scan for `startxref`, parse the following integer;
   - per candidate: `readTrailerAt(bytes, off)` → `readClassicTrailer` (find `trailer` after the `xref` keyword, parse `<<…>>`) or `readXrefStreamDict` (parse `N G obj`, parse `<<…>>`, expect `stream` after) → `{ id?: PdfValue, encrypted: boolean } | null`;
   - first non-null wins; none → `not-a-pdf`;
   - `seedFromId(idValue, marker)` — decision 3.
3. Scoped tokenizer (bytes → values): whitespace + `%` comments; names with `#xx` escapes; literal strings with the full escape set (`\( \) \\ \n \r \t \b \f`, 1–3-digit octal, backslash-EOL continuation); hex strings; arrays; nested dictionaries; numbers; `N G R` references; booleans/null — only strings, arrays, and the `/Encrypt` key survive into the result; everything else is skipped.
4. Marker + hex validation (mirrors `parse_seed`).

Spec citations inline per decision 7.

### `web/tests/extract-seed.test.ts` (new)

- One case per fixture in §4 (18 total), asserting `kind`, `seed` (exact value for the seed-bearing ones), and `encrypted`.
- Unit tests on the synchronous core: literal-string escape decoding, name `#`-escape (`/I#44` ≡ `/ID`), hex-string decoding (hex-stored marked seed → `seed`; hex without marker → `no-seed`), multi-line arrays, and startxref fallback (a corrupt last `startxref` → the earlier one wins).
- The `Blob` async path exercised via `new Blob([bytes])` (Node 24 has both `Blob` and `File`).

### `web/tests/fixtures/` (4 new files, generated once and committed)

- `protected-classic-llmproof.pdf` — generated by the repo's own `protect` (fixed salt, default marker) on a small fixed plain PDF; the expected seed is recorded in the test file.
- `protected-classic-acme.pdf` — same input, `--marker ACME`; same seed.
- `plain-xrefstream-llmproof.pdf` — root `test.pdf` byte-patched: `/ID [(LLMPROOF-<seed>)(LLMPROOF-<seed>)]` inserted into the xref-stream dictionary (plain text; `/Length` covers stream data only) and the 7-digit `startxref` value adjusted in place. Same seed value as the protected fixtures.
- `garbage.bin` — fixed non-PDF bytes.

## 6. Out of scope (explicitly rejected)

- Password derivation (`sha256(salt ‖ seed)`), Web Crypto usage, any UI/page — later feature, later spec.
- Canonical content / seed generation in the browser.
- Following `/Prev` chains; resolving indirect references; parsing xref entries, object streams, or stream data.
- Auto-detecting the marker from the file.
- _Writing_ the seed as a hex-encoded ID (ADR-0005: the carrier is a human-readable literal; `protect` always writes `(MARKER-<seed>)`). Reading matches on the decoded value, so a hex-_stored_ `ID[0]` (qpdf's re-save form) still yields its seed (decision 3).
- A build/bundling pipeline, npm publishing, CI.
- Changes to the Python project (`pyproject.toml`, `uv.lock`, `src/`, `tests/`) or to the root `test.pdf`.

## 7. Environment & pitfalls

- Node 24 + npm 11 are installed; `npm install` in `web/` needs registry access (sandbox: allow `registry.npmjs.org`).
- Python side (fixture generation only): `.venv/bin/python` (or `uv run`); `UV_CACHE_DIR=/tmp/uvcache` if uv resolution is needed; PyMuPDF is `pymupdf` (untyped; existing `# pyright: ignore[...]` pattern).
- **Do not re-run fixture generation** unless a fixture is broken — the committed bytes are the test input and the expected seeds are hardcoded in the test file.
- `plain-xrefstream-llmproof.pdf` is the one fixture made by byte-patching (per §5); every other generated fixture comes from the PyMuPDF API / the `protect` CLI.
- The root `test.pdf` is **not** copied into the fixtures: the xref-stream shape is covered by `plain-linearized-xrefstream.pdf`, `enc-xrefstream-hex.pdf`, and the generated `plain-xrefstream-llmproof.pdf`.
- Literal strings are decoded as Latin-1 byte → character (the seed payload is ASCII); never assume UTF-8 anywhere in the parser.
- `startxref` integers are decimal; whitespace (including `\r\n`) may separate the keyword, the integer, and `%%EOF`.
- Worth reading before implementing: `docs/adr/0005-*.md` + `0006-*.md`, `src/llm_proof/seed.py` (`parse_seed` — the semantics being mirrored), `CONTEXT.md`.

## 8. Definition of done

- `cd web && npm test` green: all 18 fixture cases + core unit tests pass; `npm run typecheck` clean.
- Sanity check of the async path in Node: `extractSeed(new Blob([readFileBytes("web/tests/fixtures/protected-classic-llmproof.pdf")]))` → `{ kind: "seed", … }`.
- Docs in place: ADR-0006, `CONTEXT.md` **File ID** term, this spec, provenance table below.
- Python project untouched: `git status` shows only `web/`, `docs/adr/0006-*`, `CONTEXT.md`, `.scratch/web-seed-extractor/`.

Fixture provenance (`web/tests/fixtures/`). User-procured files came from a mix of LibreOffice Writer, qpdf, and online samples; per-file tooling was not recorded, so only the verified structural shape is listed (see §4 matrix).

| fixture                           | source                                                              |
| --------------------------------- | ------------------------------------------------------------------- |
| `enc-classic-hex-same.pdf`        | user-procured (was `test2.pdf`)                                     |
| `enc-classic-hex-pair.pdf`        | user-procured (was `test3.pdf`)                                     |
| `enc-linearized-classic.pdf`      | user-procured, qpdf-linearized (was `test4.pdf`)                    |
| `enc-linearized-classic-pair.pdf` | user-procured, qpdf-linearized (was `test11.pdf`)                   |
| `enc-classic-hex-multiline.pdf`   | user-procured (was `test7.pdf`)                                     |
| `enc-xrefstream-hex.pdf`          | user-procured, qpdf-encrypted (was `test10.pdf`)                    |
| `plain-classic-obj-id-1.pdf`      | user-procured (was `test5.pdf`)                                     |
| `plain-classic-obj-id-2.pdf`      | user-procured (was `test6.pdf`)                                     |
| `plain-classic-id-traps.pdf`      | user-procured (was `test8.pdf`)                                     |
| `plain-linearized-xrefstream.pdf` | user-procured, qpdf-linearized (was `test9.pdf`)                    |
| `test1.pdf`                       | user-procured: `llm-proof protect` → qpdf (passthrough)             |
| `test2.pdf`                       | user-procured: `llm-proof protect` → qpdf `--linearize`             |
| `test3.pdf`                       | user-procured: `llm-proof protect` → qpdf decrypt                   |
| `test4.pdf`                       | user-procured: `llm-proof protect` → qpdf decrypt → qpdf re-encrypt |
| `protected-classic-llmproof.pdf`  | generated: `llm-proof protect`                                      |
| `protected-classic-acme.pdf`      | generated: `llm-proof protect --marker ACME`                        |
| `plain-xrefstream-llmproof.pdf`   | generated: byte-patch of root `test.pdf`                            |
| `garbage.bin`                     | generated: fixed bytes                                              |

## 9. Tickets

Work in number order:

- `issues/01-web-package-scaffold.md` — `web/` package.json / tsconfig / vitest wiring
- `issues/02-tokenizer-and-trailer-locator.md` — parser core (candidate scan, structural validation, tokenizer, dictionary read)
- `issues/03-seed-rule-and-api.md` — `extractSeed`, marker semantics, `SeedResult`
- `issues/04-fixtures-and-tests.md` — generation of the 4 fixtures, full vitest suite
