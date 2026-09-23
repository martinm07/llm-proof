---
status: accepted
---

# Browser-side seed extraction uses a self-contained minimal trailer parser

The web side of llm-proof must read the marked **seed** from a protected document uploaded through the browser File API — client-side, with no server round-trip and no password. The seed lives in the file's unencrypted **file ID** (`/ID`), which sits in exactly one place: the trailer dictionary of a classic cross-reference table, or the stream dictionary of a cross-reference stream (ISO 32000-1:2008 §7.5.7, §7.5.8).

Extraction is therefore implemented as a self-contained TypeScript module (`web/src/extract-seed.ts`, zero runtime dependencies) that locates the section the file's **last `startxref`** points to and parses only that one dictionary — never scanning the file for `/ID`, never following `/Prev` chains, never resolving indirect references.

## Considered options

- **pdf.js**: rejected — a heavyweight dependency (≈1 MB of core plus worker plumbing) whose robustness targets structures that cannot carry `/ID` (object streams, content, fonts); its `/ID` access is a by-product of a full parse. A full parser would also silently tolerate exactly the malformations we want to report as `not-a-pdf`.
- **Regex / byte scan for `/ID`**: rejected — empirically unsafe. The fixture set includes real-world files carrying fifty-plus `/ID` keys in _object_ dictionaries (image and page objects, mostly indirect references) plus `/IDS` substring traps; only a structural parse of the authoritative dictionary avoids them.
- **Server-side extraction (PyMuPDF)**: rejected — the point of the web flow is that the file never leaves the user's machine.

## Consequences

- Zero runtime dependencies; the module is a single file a host page can embed or build, and a later client-side password derivation (`sha256(salt ‖ seed)`) can build on it without touching PDF parsing.
- The parser is scoped by design: it parses one dictionary (names with `#xx` escapes, literal strings with the full escape set, hex strings, arrays, nested dictionaries, indirect references) and nothing else. Documented limitations: an indirect `/ID` (`/ID 12 0 R`) is reported as no-seed (seeds are always direct strings, never indirect references, ADR-0005), and a trailer that omits `/ID` or `/Encrypt` by `/Prev`-inheritance is not chased (writers repeat both; every fixture confirms).
- The seed rule matches on the **decoded value** of `ID[0]`, not its serialization: re-savers (notably qpdf) serialize `/ID` as hex strings, and the Python reference accepts those — PyMuPDF decodes a printable hex string before `parse_seed` sees it — so the web reader must too (verified against qpdf re-saves of `llm-proof protect` output).
- Real-world traps are pinned by committed fixtures (`web/tests/fixtures/`), including encrypted linearized files whose last `startxref` points at the _first_ section, and an encrypted xref-stream file proving the xref-stream dictionary stays unencrypted (verified against the fixture; §7.5.8 states it).
- "Fully robust" is defined against that fixture set plus the spec's layout rules for the two trailer shapes — not against the full PDF object model.
