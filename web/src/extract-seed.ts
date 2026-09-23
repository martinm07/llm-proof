/**
 * Self-contained, client-side extraction of the llm-proof seed from a PDF's
 * file ID (`/ID`).
 *
 * Given a PDF uploaded through the browser File API, this module reads the
 * unencrypted `/ID` entry of the authoritative trailer — the classic trailer
 * dictionary, or the cross-reference stream's stream dictionary — and returns
 * the marked seed: the string `MARKER-<32 hex>` in the *decoded value* of the
 * first `/ID` element (literal- or hex-stored alike — §7.3.4). It performs no
 * cryptographic work; the bytes never leave the browser.
 *
 * It deliberately does NOT:
 *   - compute canonical content or generate a seed (a later feature),
 *   - derive the password from the seed + salt (a later feature),
 *   - scan the file for `/ID` — only the dictionary the last `startxref`
 *     points to is authoritative (object dictionaries in the wild carry their
 *     own, unrelated `/ID` keys),
 *   - follow `/Prev` chains (linearized files: the pointed-at section is
 *     complete), resolve indirect references, or parse xref entries, object
 *     streams, or stream data.
 *
 * Format references — ISO 32000-1:2008 (PDF 1.7):
 *   §7.3     Notation: §7.3.2 whitespace and comments, §7.3.4 strings,
 *            §7.3.5 delimiters and keywords, §7.3.6 numbers, §7.3.7 names
 *   §7.5.2   File structure: header, body, trailer + `startxref`, `%%EOF`
 *   §7.5.4   Cross-reference tables
 *   §7.5.7   Trailers
 *   §7.5.8   Cross-reference streams
 *   §7.6.3   Encryption: the trailer's `/ID` and the cross-reference stream's
 *            dictionary are not encrypted (only stream data is)
 *
 * Design: ADR-0006. Spec: .scratch/web-seed-extractor/spec.md.
 *
 * The seed rule mirrors the *semantics* of `src/llm_proof/seed.py::parse_seed`:
 * `parse_seed` receives PyMuPDF's rendering of `/ID`, in which a printable
 * hex-stored string is already decoded to literal form — so the rule applies
 * to the decoded value of `ID[0]`, storage form immaterial (qpdf re-saves,
 * for example, serialize `/ID` as hex strings).
 */

// ---------------------------------------------------------------------------
// Public surface
// ---------------------------------------------------------------------------

/**
 * The outcome of a seed-extraction attempt.
 *
 * - `seed`: the file's `/ID` carries the marked seed (32 lowercase hex).
 * - `no-seed`: a PDF trailer was parsed but its `/ID` carries no marked seed
 *   (foreign file, non-string or indirect first element, or a mismatched
 *   marker — the same deliberate signal `llm-proof password` emits).
 * - `not-a-pdf`: no parseable trailer / cross-reference section was found.
 */
export type SeedResult =
  | { kind: "seed"; seed: string; encrypted: boolean }
  | { kind: "no-seed"; encrypted: boolean }
  | { kind: "not-a-pdf" };

/** Default marker label (mirrors `llm_proof.seed.MARKER_DEFAULT`). */
export const MARKER_DEFAULT = "LLMPROOF";

/**
 * Extract the marked seed from a PDF.
 *
 * `input` is anything the browser File API (or tests) can hand over: a
 * `File`/`Blob` (read via `arrayBuffer()` — never `text()`, the content is
 * binary), an `ArrayBuffer`, or a raw `Uint8Array`. `marker` defaults to
 * `LLMPROOF`; it is matched case-sensitively and is never auto-detected.
 */
export async function extractSeed(
  input: File | Blob | ArrayBuffer | Uint8Array,
  marker: string = MARKER_DEFAULT,
): Promise<SeedResult> {
  const bytes = await toBytes(input);
  return parseSeedFromPdf(bytes, marker);
}

/**
 * Synchronous pure core of the extraction: parse the authoritative trailer
 * (or xref-stream dictionary) pointed at by the file's last `startxref`, and
 * apply the seed rule to its `/ID`. Unit-testable without any DOM.
 */
export function parseSeedFromPdf(
  bytes: Uint8Array,
  marker: string,
): SeedResult {
  // §7.5.2: a PDF file begins with a header line of the form %PDF-<version>.
  if (!hasPdfHeader(bytes)) return { kind: "not-a-pdf" };

  // §7.5.2: the file ends with `startxref <offset>` — the offset of the last
  // cross-reference section — followed by `%%EOF`. Real-world files may carry
  // several `startxref` occurrences (linearization writes one per section),
  // so collect every occurrence in a bounded tail scan and try them
  // last-occurrence-first; the first whose offset is structurally validated
  // wins.
  const candidates = candidateStartXrefOffsets(bytes);
  for (let i = candidates.length - 1; i >= 0; i--) {
    const trailer = readTrailerAt(bytes, candidates[i]);
    if (trailer !== null) return resultFromTrailer(trailer, marker);
  }
  return { kind: "not-a-pdf" };
}

function toBytes(
  input: File | Blob | ArrayBuffer | Uint8Array,
): Promise<Uint8Array> | Uint8Array {
  if (input instanceof Uint8Array) return input;
  if (input instanceof ArrayBuffer) return new Uint8Array(input);
  // File extends Blob; both expose arrayBuffer() for binary-safe reads.
  return input.arrayBuffer().then((buf) => new Uint8Array(buf));
}

// ---------------------------------------------------------------------------
// Candidate `startxref` offsets
// ---------------------------------------------------------------------------

/** Tail window scanned for `startxref` occurrences (the keyword sits just before `%%EOF`). */
const TAIL_SCAN_BYTES = 10 * 1024;
const STARTXREF = [0x73, 0x74, 0x61, 0x72, 0x74, 0x78, 0x72, 0x65, 0x66]; // "startxref"

/**
 * Bounded scan of the file tail collecting every `startxref` occurrence in
 * file order. Each occurrence must sit at a token boundary and be followed
 * (across whitespace, §7.3.2) by a decimal integer (§7.5.2) that lies within
 * the file; occurrences that fail either test are dropped, and the caller
 * additionally validates the structure at each surviving offset.
 */
function candidateStartXrefOffsets(bytes: Uint8Array): number[] {
  const n = bytes.length;
  const start = Math.max(0, n - TAIL_SCAN_BYTES);
  const out: number[] = [];
  for (let p = start; p + STARTXREF.length <= n; p++) {
    if (!bytesMatch(bytes, p, STARTXREF)) continue;
    // A stream payload can contain the byte sequence "startxref"; the
    // keyword only occurs at top level, i.e. after whitespace.
    if (p > start && !isWs(bytes[p - 1])) continue;
    const off = readDecimalIntegerAfterWs(bytes, p + STARTXREF.length);
    if (off !== null && off < n) out.push(off);
  }
  return out;
}

function bytesMatch(
  bytes: Uint8Array,
  at: number,
  needle: readonly number[],
): boolean {
  for (let i = 0; i < needle.length; i++) {
    if (bytes[at + i] !== needle[i]) return false;
  }
  return true;
}

/**
 * Read the non-negative decimal integer after the current position, allowing
 * the whitespace (incl. `\r\n`) and comments of §7.3.2 between tokens. The
 * integer must terminate at a token boundary (whitespace, a `%` comment
 * marker, or end of file — the `%%EOF` that follows `startxref`).
 */
function readDecimalIntegerAfterWs(
  bytes: Uint8Array,
  p: number,
): number | null {
  p = skipWsAndComments(bytes, p);
  const n = bytes.length;
  if (p >= n || !isDigit(bytes[p])) return null;
  let value = 0;
  let count = 0;
  while (p < n && isDigit(bytes[p])) {
    value = value * 10 + (bytes[p] - 0x30);
    if (value > 0x7fffffff) return null; // hostile file: refuse to overflow
    p++;
    count++;
  }
  if (count === 0) return null;
  if (p < n && !isWs(bytes[p]) && bytes[p] !== 0x25) return null;
  return value;
}

// ---------------------------------------------------------------------------
// The authoritative trailer: one dictionary, structurally validated
// ---------------------------------------------------------------------------

/** What a successful read of the authoritative section yields. */
type TrailerInfo = {
  /** The parsed `/ID` value (array/string/…), or null when absent. */
  id: PdfValue | null;
  /** Presence of an `/Encrypt` key — the value is never resolved. */
  encrypted: boolean;
};

/**
 * Read the section the given `startxref` offset points to. Exactly one
 * dictionary is parsed — the classic trailer dictionary, or the
 * cross-reference stream's stream dictionary (§7.5.8: that dictionary is
 * plain text even in an encrypted file, §7.6.3; only the stream data is
 * compressed/encrypted, and it is never parsed).
 */
function readTrailerAt(bytes: Uint8Array, off: number): TrailerInfo | null {
  return readClassicTrailer(bytes, off) ?? readXrefStreamDict(bytes, off);
}

/** Forward bound for locating a classic table's `trailer` keyword after the table. */
const TRAILER_SCAN_LIMIT = 4 * 1024 * 1024;

/**
 * Classic cross-reference table (§7.5.4): the offset must point at the
 * `xref` keyword. The table's trailer (§7.5.7) follows the entry
 * subsections; the entries themselves are never parsed — the first whole-word
 * `trailer` keyword after the table introduces exactly one dictionary, which
 * is then parsed.
 */
function readClassicTrailer(
  bytes: Uint8Array,
  off: number,
): TrailerInfo | null {
  const afterKw = matchKeyword(bytes, off, "xref");
  if (afterKw === null) return null;
  const t = findKeyword(bytes, afterKw, "trailer", off + TRAILER_SCAN_LIMIT);
  if (t === null) return null;
  const dictStart = skipWsAndComments(bytes, t + "trailer".length);
  const dict = parseDictAt(bytes, dictStart);
  if (dict === null || !dictIsTrailer(dict)) return null;
  return { id: dict.id, encrypted: dict.encrypted };
}

/**
 * Cross-reference stream (§7.5.8): the offset must point at the stream
 * object header `N G obj`, followed by the stream dictionary and then the
 * `stream` keyword (§7.3.5). The dictionary is parsed; the stream data that
 * follows the keyword is never touched.
 */
function readXrefStreamDict(
  bytes: Uint8Array,
  off: number,
): TrailerInfo | null {
  const objNo = readIntegerAt(bytes, off);
  if (objNo === null) return null;
  let p = skipWsAndComments(bytes, objNo.end);
  const gen = readIntegerAt(bytes, p);
  if (gen === null) return null;
  p = skipWsAndComments(bytes, gen.end);
  const afterObj = matchKeyword(bytes, p, "obj");
  if (afterObj === null) return null;
  const dictStart = skipWsAndComments(bytes, afterObj);
  const dict = parseDictAt(bytes, dictStart);
  if (dict === null) return null;
  const afterDict = skipWsAndComments(bytes, dict.end);
  if (matchKeyword(bytes, afterDict, "stream") === null) return null;
  if (!dictIsTrailer(dict)) return null;
  return { id: dict.id, encrypted: dict.encrypted };
}

/**
 * A dictionary is accepted as the authoritative trailer (or xref-stream
 * dictionary) when it parses and contains at least one of the keys such a
 * section must carry: `/ID`, `/Root`, `/Size`, `/Encrypt`. This rejects
 * random object dictionaries that a corrupt `startxref` might point at.
 */
function dictIsTrailer(d: ParsedDict): boolean {
  return d.hasId || d.hasRoot || d.hasSize || d.encrypted;
}

function resultFromTrailer(trailer: TrailerInfo, marker: string): SeedResult {
  const seed = seedFromId(trailer.id, marker);
  if (seed !== null)
    return { kind: "seed", seed, encrypted: trailer.encrypted };
  return { kind: "no-seed", encrypted: trailer.encrypted };
}

// ---------------------------------------------------------------------------
// The seed rule (mirrors llm_proof.seed.parse_seed)
// ---------------------------------------------------------------------------

/**
 * The first element of `/ID` must be a **string** — literal or hex-stored;
 * §7.3.4 gives both the same byte value, and re-savers (notably qpdf)
 * serialize `/ID` as hex strings, so the storage form is immaterial — whose
 * decoded text is `<marker>-` + exactly 32 hex characters (case-insensitive;
 * returned lowercase). An indirect reference, a name, a number, or any other
 * shape means the file carries no seed. The second element is never
 * consulted.
 */
function seedFromId(id: PdfValue | null, marker: string): string | null {
  if (id === null) return null;
  if (id.type !== "array" || id.items.length === 0) return null;
  const first = id.items[0];
  if (first.type !== "string") return null;
  const prefix = marker + "-";
  if (!first.text.startsWith(prefix)) return null;
  const rest = first.text.slice(prefix.length);
  if (!/^[0-9a-fA-F]{32}$/.test(rest)) return null;
  return rest.toLowerCase();
}

// ---------------------------------------------------------------------------
// Scoped tokenizer (ISO 32000-1:2008 §7.3)
//
// Only what the result needs survives: the `/ID` value and the presence of
// the `/Encrypt` key. Everything else is parsed (so its extent can be found)
// and then discarded.
// ---------------------------------------------------------------------------

type PdfValue =
  | { type: "string"; text: string } // literal or hex; text is decoded (Latin-1)
  | { type: "array"; items: PdfValue[] }
  | { type: "dict" } // nested dictionaries are never retained
  | { type: "other" }; // names, numbers, references, keywords

/** A parsed top-level dictionary (the trailer or xref-stream dictionary). */
type ParsedDict = {
  /** The parsed `/ID` value, when present. */
  id: PdfValue | null;
  hasId: boolean;
  /** Presence of `/Encrypt` — the value is never resolved. */
  encrypted: boolean;
  hasRoot: boolean;
  hasSize: boolean;
  /** Position just past the closing `>>`. */
  end: number;
};

/**
 * Parse the dictionary at `p` (which must start with `<<`, §7.3.5). Keys are
 * names (§7.3.7); values are parsed in full but retained only for `/ID`.
 * Returns null on any structural malformation.
 */
function parseDictAt(bytes: Uint8Array, p: number): ParsedDict | null {
  if (!isDictOpen(bytes, p)) return null;
  const d: ParsedDict = {
    id: null,
    hasId: false,
    encrypted: false,
    hasRoot: false,
    hasSize: false,
    end: 0,
  };
  let q = p + 2;
  for (;;) {
    q = skipWsAndComments(bytes, q);
    if (q >= bytes.length) return null;
    if (isDictClose(bytes, q)) {
      d.end = q + 2;
      return d;
    }
    if (bytes[q] !== 0x2f) return null; // a key must be a name (§7.3.7)
    const key = readName(bytes, q);
    if (key === null) return null;
    q = key.end;
    const value = parseValue(bytes, q);
    if (value === null) return null;
    q = value.end;
    switch (key.value) {
      case "ID":
        d.hasId = true;
        d.id = value.value;
        break;
      case "Encrypt":
        d.encrypted = true;
        break;
      case "Root":
        d.hasRoot = true;
        break;
      case "Size":
        d.hasSize = true;
        break;
      default:
        break;
    }
  }
}

/**
 * Parse the value starting at `p` (after skipping whitespace/comments) and
 * return it with its extent. Handles every §7.3 token shape so that the next
 * value's position is found exactly: dictionaries, arrays, literal and hex
 * strings, names, numbers, `N G R` references (§7.5.7.1), and bare keywords.
 */
function parseValue(
  bytes: Uint8Array,
  p: number,
): { value: PdfValue; end: number } | null {
  const n = bytes.length;
  p = skipWsAndComments(bytes, p);
  if (p >= n) return null;
  const b = bytes[p];

  if (isDictOpen(bytes, p)) {
    const d = parseDictAt(bytes, p);
    if (d === null) return null;
    return { value: { type: "dict" }, end: d.end };
  }

  if (b === 0x5b) {
    // '[' — array (§7.3.2)
    const items: PdfValue[] = [];
    let q = p + 1;
    for (;;) {
      q = skipWsAndComments(bytes, q);
      if (q >= n) return null;
      if (bytes[q] === 0x5d)
        return { value: { type: "array", items }, end: q + 1 }; // ']'
      const item = parseValue(bytes, q);
      if (item === null) return null;
      items.push(item.value);
      q = item.end;
    }
  }

  if (b === 0x28) {
    const s = readLiteralString(bytes, p);
    if (s === null) return null;
    return { value: { type: "string", text: s.text }, end: s.end };
  }

  if (b === 0x3c) {
    const s = readHexString(bytes, p);
    if (s === null) return null;
    return { value: { type: "string", text: s.text }, end: s.end };
  }

  if (b === 0x2f) {
    const nm = readName(bytes, p);
    if (nm === null) return null;
    return { value: { type: "other" }, end: nm.end };
  }

  if (b === 0x29 || b === 0x3e || b === 0x5d) {
    // A stray closing delimiter where a value was expected: skip it rather
    // than failing the whole candidate (tolerant of minor malformation).
    return { value: { type: "other" }, end: p + 1 };
  }

  if (isDigit(b) || b === 0x2e || b === 0x2b || b === 0x2d) {
    // Number (§7.3.6); possibly the head of a `N G R` reference (§7.5.7.1).
    const num = readNumber(bytes, p);
    if (num === null) return null;
    if (num.integer !== null) {
      const q = skipWsAndComments(bytes, num.end);
      if (q < n && isDigit(bytes[q])) {
        const gen = readIntegerAt(bytes, q);
        if (gen !== null) {
          const r = skipWsAndComments(bytes, gen.end);
          if (matchKeyword(bytes, r, "R") !== null) {
            // Reference: never resolved (an indirect /ID is a no-seed signal).
            return { value: { type: "other" }, end: r + 1 };
          }
        }
      }
    }
    return { value: { type: "other" }, end: num.end };
  }

  // Bare keyword (§7.3.5): consume to the next whitespace or delimiter.
  let q = p + 1;
  while (q < n && !isWs(bytes[q]) && !isDelimiter(bytes[q])) q++;
  return { value: { type: "other" }, end: q };
}

// ---------------------------------------------------------------------------
// Token readers
// ---------------------------------------------------------------------------

/** §7.3.2: the six whitespace characters (NUL, TAB, LF, FF, CR, SPACE). */
function isWs(b: number): boolean {
  return (
    b === 0x00 ||
    b === 0x09 ||
    b === 0x0a ||
    b === 0x0c ||
    b === 0x0d ||
    b === 0x20
  );
}

function isDigit(b: number): boolean {
  return b >= 0x30 && b <= 0x39;
}

/** §7.3.2: the eight delimiter characters. */
function isDelimiter(b: number): boolean {
  return (
    b === 0x28 ||
    b === 0x29 ||
    b === 0x3c ||
    b === 0x3e ||
    b === 0x5b ||
    b === 0x5d ||
    b === 0x7b ||
    b === 0x7d ||
    b === 0x2f
  );
}

/**
 * Advance past whitespace and `%` comments (a comment runs to the end of the
 * line, §7.3.2).
 */
function skipWsAndComments(bytes: Uint8Array, p: number): number {
  const n = bytes.length;
  let i = p;
  while (i < n) {
    const b = bytes[i];
    if (isWs(b)) {
      i++;
      continue;
    }
    if (b === 0x25) {
      while (i < n) {
        const c = bytes[i];
        if (c === 0x0a || c === 0x0d) break;
        i++;
      }
      continue;
    }
    break;
  }
  return i;
}

/** `true` at a position opening `<<` / closing `>>` (§7.3.5). */
function isDictOpen(bytes: Uint8Array, p: number): boolean {
  return p + 1 < bytes.length && bytes[p] === 0x3c && bytes[p + 1] === 0x3c;
}

function isDictClose(bytes: Uint8Array, p: number): boolean {
  return p + 1 < bytes.length && bytes[p] === 0x3e && bytes[p + 1] === 0x3e;
}

/**
 * Match `word` as a whole word at `p`: the bytes must equal `word` and the
 * following byte (if any) must not continue the word. Returns the position
 * just past the word, or null.
 */
function matchKeyword(
  bytes: Uint8Array,
  p: number,
  word: string,
): number | null {
  if (p + word.length > bytes.length) return null;
  for (let i = 0; i < word.length; i++) {
    if (bytes[p + i] !== word.charCodeAt(i)) return null;
  }
  const q = p + word.length;
  if (q < bytes.length && isWordChar(bytes[q])) return null;
  return q;
}

function isWordChar(b: number): boolean {
  return (
    (b >= 0x30 && b <= 0x39) ||
    (b >= 0x41 && b <= 0x5a) ||
    (b >= 0x61 && b <= 0x7a)
  );
}

/**
 * Forward, bounded scan for the first whole-word occurrence of `word` from
 * `from`, requiring a whitespace boundary before it (so it is a keyword at
 * top level, not a fragment of some other token).
 */
function findKeyword(
  bytes: Uint8Array,
  from: number,
  word: string,
  limit: number,
): number | null {
  const n = Math.min(bytes.length, limit);
  for (let p = Math.max(from, 1); p + word.length <= n; p++) {
    if (!isWs(bytes[p - 1])) continue;
    if (matchKeyword(bytes, p, word) !== null) return p;
  }
  return null;
}

/** Read a non-negative decimal integer starting exactly at `p` (§7.3.6). */
function readIntegerAt(
  bytes: Uint8Array,
  p: number,
): { value: number; end: number } | null {
  const n = bytes.length;
  if (p >= n || !isDigit(bytes[p])) return null;
  let value = 0;
  let i = p;
  while (i < n && isDigit(bytes[i])) {
    value = value * 10 + (bytes[i] - 0x30);
    if (value > 0x7fffffff) return null;
    i++;
  }
  return { value, end: i };
}

/**
 * Read the number starting at `p` (§7.3.6): an integer or a real.
 * `integer` is non-null only for plain, non-overflowing integers — the only
 * shape that can begin a `N G R` reference.
 */
function readNumber(
  bytes: Uint8Array,
  p: number,
): { integer: number | null; end: number } | null {
  const n = bytes.length;
  let i = p;
  if (i < n && (bytes[i] === 0x2b || bytes[i] === 0x2d)) i++; // sign
  let integer = 0;
  let overflow = false;
  let sawIntDigit = false;
  while (i < n && isDigit(bytes[i])) {
    sawIntDigit = true;
    integer = integer * 10 + (bytes[i] - 0x30);
    if (integer > 0x7fffffff) overflow = true;
    i++;
  }
  if (!sawIntDigit) {
    // No integer part: a real such as `.5` (a digit after the dot required).
    if (i < n && bytes[i] === 0x2e && i + 1 < n && isDigit(bytes[i + 1])) {
      i += 2;
      while (i < n && isDigit(bytes[i])) i++;
      return { integer: null, end: i };
    }
    return null;
  }
  let isInteger = true;
  if (i < n && bytes[i] === 0x2e) {
    i++; // consume the dot; a trailing-dot form (`123.`) is a real
    while (i < n && isDigit(bytes[i])) i++;
    isInteger = false;
  }
  return { integer: overflow || !isInteger ? null : integer, end: i };
}

/**
 * Read the name token at `p` (which must be `/`, §7.3.7). The body runs to
 * the next whitespace or delimiter; `#xx` escapes decode to their byte,
 * decoded Latin-1 (byte → character).
 */
function readName(
  bytes: Uint8Array,
  p: number,
): { value: string; end: number } | null {
  const n = bytes.length;
  if (p >= n || bytes[p] !== 0x2f) return null;
  let i = p + 1;
  let out = "";
  while (i < n) {
    const b = bytes[i];
    if (isWs(b) || isDelimiter(b)) break;
    if (b === 0x23) {
      const h1 = hexDigitValue(bytes, i + 1);
      const h2 = hexDigitValue(bytes, i + 2);
      if (h1 === null || h2 === null) return null;
      out += String.fromCharCode((h1 << 4) | h2);
      i += 3;
      continue;
    }
    out += String.fromCharCode(b);
    i++;
  }
  if (i === p + 1) return null; // an empty name (a lone '/') is malformed
  return { value: out, end: i };
}

/**
 * Read the literal string at `p` (which must be `(`, §7.3.4.2). Balanced
 * nested parentheses are content; the full escape set is decoded:
 * `\( \) \\ \n \r \t \b \f`, 1–3-digit octal (value modulo 256), and
 * backslash-EOL continuation (a CRLF is a single EOL). Bytes decode one-to-
 * one as Latin-1. Returns null on an unbalanced string.
 */
function readLiteralString(
  bytes: Uint8Array,
  p: number,
): { text: string; end: number } | null {
  const n = bytes.length;
  if (p >= n || bytes[p] !== 0x28) return null;
  let i = p + 1;
  let depth = 1;
  let out = "";
  while (i < n) {
    const b = bytes[i];
    if (b === 0x28) {
      out += "("; // unescaped balanced parens are string content (§7.3.4.2)
      depth++;
      i++;
      continue;
    }
    if (b === 0x29) {
      depth--;
      i++;
      if (depth === 0) return { text: out, end: i };
      out += ")";
      continue;
    }
    if (b !== 0x5c) {
      out += String.fromCharCode(b);
      i++;
      continue;
    }
    // Escape: the backslash is consumed; classify the next byte.
    i++;
    if (i >= n) return null; // backslash at EOF: malformed
    const c = bytes[i];
    if (c === 0x0a) {
      i++;
      continue; // backslash + LF: line continuation
    }
    if (c === 0x0d) {
      i++;
      if (i < n && bytes[i] === 0x0a) i++; // a CRLF is one EOL
      continue;
    }
    if (c === 0x6e) {
      out += "\n";
      i++;
      continue;
    }
    if (c === 0x72) {
      out += "\r";
      i++;
      continue;
    }
    if (c === 0x74) {
      out += "\t";
      i++;
      continue;
    }
    if (c === 0x62) {
      out += "\b";
      i++;
      continue;
    }
    if (c === 0x66) {
      out += "\f";
      i++;
      continue;
    }
    if (c === 0x28) {
      out += "(";
      i++;
      continue;
    }
    if (c === 0x29) {
      out += ")";
      i++;
      continue;
    }
    if (c === 0x5c) {
      out += "\\";
      i++;
      continue;
    }
    if (c >= 0x30 && c <= 0x37) {
      let value = c - 0x30;
      let digits = 1;
      i++;
      while (digits < 3 && i < n && bytes[i] >= 0x30 && bytes[i] <= 0x37) {
        value = value * 8 + (bytes[i] - 0x30);
        digits++;
        i++;
      }
      out += String.fromCharCode(value % 256);
      continue;
    }
    out += String.fromCharCode(c); // backslash + any other character
    i++;
  }
  return null; // unbalanced: no closing ')'
}

/**
 * Read the hex string at `p` (which must be `<` and not `<<`, §7.3.4.3).
 * Whitespace inside is ignored; if the final digit is missing (an odd number
 * of digits), it is assumed to be 0 — zero-appended (§7.3.4.3 EXAMPLE 2:
 * `<901FA>` is the 3-byte string `90 1F A0`). Returns null if the string is
 * not closed.
 */
function readHexString(
  bytes: Uint8Array,
  p: number,
): { text: string; end: number } | null {
  const n = bytes.length;
  if (p >= n || bytes[p] !== 0x3c) return null;
  if (p + 1 < n && bytes[p + 1] === 0x3c) return null; // that is `<<`, not a hex string
  let i = p + 1;
  let nibbles: number[] = [];
  let closed = false;
  while (i < n) {
    const b = bytes[i];
    if (b === 0x3e) {
      i++;
      closed = true;
      break;
    }
    const v = hexDigitValue(bytes, i);
    if (v !== null) {
      nibbles.push(v);
      i++;
      continue;
    }
    if (isWs(b)) {
      i++;
      continue;
    }
    return null; // a non-hex, non-whitespace byte: malformed
  }
  if (!closed) return null;
  if (nibbles.length % 2 === 1) nibbles.push(0); // §7.3.4.3: final digit assumed 0
  let out = "";
  for (let k = 0; k < nibbles.length; k += 2) {
    out += String.fromCharCode((nibbles[k] << 4) | nibbles[k + 1]);
  }
  return { text: out, end: i };
}

function hexDigitValue(bytes: Uint8Array, i: number): number | null {
  if (i >= bytes.length) return null;
  const b = bytes[i];
  if (b >= 0x30 && b <= 0x39) return b - 0x30;
  if (b >= 0x41 && b <= 0x46) return b - 0x41 + 10; // A–F
  if (b >= 0x61 && b <= 0x66) return b - 0x61 + 10; // a–f
  return null;
}

// ---------------------------------------------------------------------------
// File header
// ---------------------------------------------------------------------------

const PDF_HEADER = [0x25, 0x50, 0x44, 0x46, 0x2d]; // "%PDF-"

function hasPdfHeader(bytes: Uint8Array): boolean {
  for (let i = 0; i < PDF_HEADER.length; i++) {
    if (i >= bytes.length || bytes[i] !== PDF_HEADER[i]) return false;
  }
  return true;
}
