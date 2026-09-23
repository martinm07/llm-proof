# 02 — Tokenizer and trailer locator

Status: done
Blocked by: 01

Read `../spec.md` first — this ticket implements the parser core of `web/src/extract-seed.ts` per spec §5 (decisions 4 and 5).

## Scope

- `web/src/extract-seed.ts`: `parseSeedFromPdf` core, bounded `startxref` candidate scan, structural validation, scoped tokenizer, single-dictionary read.
- No public API yet (ticket 03); no tests (ticket 04) — the file must typecheck.

## Steps

1. Header sanity check: `%PDF-` at offset 0 (§7.5.2).
2. `candidateStartXrefOffsets`: bounded backward scan (~10 KB) collecting every `startxref` occurrence; decimal integer, whitespace-tolerant (incl. `\r\n`), range-checked, keyword at a token boundary.
3. `readTrailerAt` per candidate (last occurrence first): classic — `xref` keyword (§7.5.4), then the first whole-word `trailer` after the table (§7.5.7), then exactly one dictionary; xref stream — `N G obj` + dictionary + `stream` keyword (§7.5.8). A dictionary is accepted only if it parses and contains at least one of `/ID`, `/Root`, `/Size`, `/Encrypt`.
4. Scoped tokenizer: whitespace + `%` comments; names with `#xx` escapes; literal strings (full escape set, 1–3-digit octal, backslash-EOL continuation, balanced nested parens, Latin-1 byte→char decoding); hex strings (odd nibble zero-padded, §7.3.4.3); arrays; nested dicts; numbers; `N G R` references; keywords. Only the `/ID` value and the `/Encrypt` key survive into the result.
5. Never: scan the file for `/ID`, follow `/Prev`, resolve indirect references, parse xref entries, object streams, or stream data.
6. ISO 32000-1:2008 citations inline at each structural step (§7.3, §7.5.2, §7.5.4, §7.5.7, §7.5.8, §7.6.3).

## Done when

- `npm run typecheck` clean; the core handles every shape in the spec §4 fixture matrix (verified by ticket 04).

## Comments

- 2026-09-22: Done — `parseSeedFromPdf` core implemented per spec §5: header check, bounded `startxref` candidate scan (last occurrence first), classic (`xref` → `trailer` → dict) and xref-stream (`N G obj` + dict + `stream`) validation, scoped tokenizer with the full literal-string escape set, single-dictionary read. Zero runtime dependencies — the hand-written parser is the whole feature.
- 2026-09-22: Fix — unescaped balanced parentheses are string **content** per §7.3.4.2; the first tokenizer pass dropped them from the decoded text (`(a(b)c)` decoded as `abc` instead of `a(b)c`).
