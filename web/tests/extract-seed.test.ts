import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  MARKER_DEFAULT,
  extractSeed,
  parseSeedFromPdf,
  type SeedResult,
} from "../src/extract-seed";

/**
 * Expected seed of the generated seed-bearing fixtures. Recorded when the
 * fixtures were generated (.scratch/web-seed-extractor/generate-fixtures.py —
 * derived from the canonical content of the small fixed plain input PDF);
 * all three seed-bearing fixtures share this value by construction. The
 * committed fixture bytes are the test input — never regenerate them.
 */
const SEED = "60b5686d3deee190e0494bd9c76fb7a5";

const FIXTURES = new URL("./fixtures/", import.meta.url);
const fixture = (name: string): Uint8Array<ArrayBuffer> =>
  new Uint8Array(readFileSync(fileURLToPath(new URL(name, FIXTURES))));

/** The synchronous core, with the spec'd required marker defaulting to the public default. */
const core = (bytes: Uint8Array, marker: string = MARKER_DEFAULT): SeedResult =>
  parseSeedFromPdf(bytes, marker);

// ---------------------------------------------------------------------------
// Fixture cases (spec §4 matrix — 14 files)
// ---------------------------------------------------------------------------

const fixtureCases: Array<[string, SeedResult]> = [
  ["enc-classic-hex-same.pdf", { kind: "no-seed", encrypted: true }],
  ["enc-classic-hex-pair.pdf", { kind: "no-seed", encrypted: true }],
  ["enc-linearized-classic.pdf", { kind: "no-seed", encrypted: true }],
  ["enc-linearized-classic-pair.pdf", { kind: "no-seed", encrypted: true }],
  ["enc-classic-hex-multiline.pdf", { kind: "no-seed", encrypted: true }],
  ["enc-xrefstream-hex.pdf", { kind: "no-seed", encrypted: true }],
  ["plain-classic-obj-id-1.pdf", { kind: "no-seed", encrypted: false }],
  ["plain-classic-obj-id-2.pdf", { kind: "no-seed", encrypted: false }],
  ["plain-classic-id-traps.pdf", { kind: "no-seed", encrypted: false }],
  ["plain-linearized-xrefstream.pdf", { kind: "no-seed", encrypted: false }],
  [
    "protected-classic-llmproof.pdf",
    { kind: "seed", seed: SEED, encrypted: true },
  ],
  [
    "plain-xrefstream-llmproof.pdf",
    { kind: "seed", seed: SEED, encrypted: false },
  ],
  [
    "test1.pdf",
    { kind: "seed", seed: "1e867d12bd4ccd4f7fece7b4cb4670b1", encrypted: true },
  ],
  [
    "test2.pdf",
    { kind: "seed", seed: "1e867d12bd4ccd4f7fece7b4cb4670b1", encrypted: true },
  ],
  [
    "test3.pdf",
    {
      kind: "seed",
      seed: "1e867d12bd4ccd4f7fece7b4cb4670b1",
      encrypted: false,
    },
  ],
  [
    "test4.pdf",
    { kind: "seed", seed: "1e867d12bd4ccd4f7fece7b4cb4670b1", encrypted: true },
  ],
];

describe("fixture files", () => {
  for (const [name, expected] of fixtureCases) {
    it(name, async () => {
      expect(await extractSeed(fixture(name))).toEqual(expected);
    });
  }

  it("protected-classic-acme.pdf (default marker → no-seed; ACME → seed)", async () => {
    const bytes = fixture("protected-classic-acme.pdf");
    expect(await extractSeed(bytes)).toEqual({
      kind: "no-seed",
      encrypted: true,
    });
    expect(await extractSeed(bytes, "ACME")).toEqual({
      kind: "seed",
      seed: SEED,
      encrypted: true,
    });
  });

  it("garbage.bin → not-a-pdf", async () => {
    expect(await extractSeed(fixture("garbage.bin"))).toEqual({
      kind: "not-a-pdf",
    });
  });
});

// ---------------------------------------------------------------------------
// Async input paths (browser upload simulation — Node 24 has Blob and File)
// ---------------------------------------------------------------------------

describe("async input paths", () => {
  const bytes = fixture("protected-classic-llmproof.pdf");
  const expected: SeedResult = { kind: "seed", seed: SEED, encrypted: true };

  it("Blob", async () => {
    expect(await extractSeed(new Blob([bytes]))).toEqual(expected);
  });

  it("File", async () => {
    expect(await extractSeed(new File([bytes], "doc.pdf"))).toEqual(expected);
  });

  it("ArrayBuffer (and the synchronous core over a Uint8Array)", async () => {
    const buf = new ArrayBuffer(bytes.length);
    new Uint8Array(buf).set(bytes);
    expect(await extractSeed(buf)).toEqual(expected);
    expect(core(bytes)).toEqual(expected);
  });
});

// ---------------------------------------------------------------------------
// Synchronous core over synthetic in-memory PDFs
//
// Helpers build minimal classic / xref-stream PDFs. The xref *entries* are
// filler — the parser never parses them — so only the structural shape the
// locator validates (keyword positions, the dictionary, `stream`) matters.
// ---------------------------------------------------------------------------

const ascii = (s: string): Uint8Array<ArrayBuffer> =>
  Uint8Array.from([...s], (c) => c.charCodeAt(0) & 0xff);

/** ASCII text as a PDF hex string — the form qpdf re-saves `/ID` in. */
const hexString = (s: string): string =>
  `<${[...s].map((c) => c.charCodeAt(0).toString(16).padStart(2, "0")).join("")}>`;

function classicPdf(trailerBody: string): Uint8Array {
  const header = "%PDF-1.4\n";
  const body = "1 0 obj\n<< /Type /Catalog >>\nendobj\n";
  const table = "xref\n0 2\n0000000000 65535 f \n0000000009 00000 n \n";
  const tableOffset = header.length + body.length;
  const tail = `startxref\n${tableOffset}\n%%EOF\n`;
  return ascii(`${header}${body}${table}trailer\n${trailerBody}\n${tail}`);
}

/** Like classicPdf, but with a second (last) `startxref` pointing at a bogus offset. */
function classicPdfWithCorruptTail(
  trailerBody: string,
  corruptOffset: number,
): Uint8Array {
  const header = "%PDF-1.4\n";
  const body = "1 0 obj\n<< /Type /Catalog >>\nendobj\n";
  const table = "xref\n0 2\n0000000000 65535 f \n0000000009 00000 n \n";
  const tableOffset = header.length + body.length;
  const tail = `startxref\n${tableOffset}\nstartxref\n${corruptOffset}\n%%EOF\n`;
  return ascii(`${header}${body}${table}trailer\n${trailerBody}\n${tail}`);
}

function xrefStreamPdf(idEntry: string): Uint8Array {
  const header = "%PDF-1.4\n";
  const objStart = header.length;
  const obj = `42 0 obj\n<< /Type /XRef /Size 2 ${idEntry}>>\nstream\nxx\nendstream\nendobj\n`;
  const tail = `startxref\n${objStart}\n%%EOF\n`;
  return ascii(`${header}${obj}${tail}`);
}

describe("core: classic trailers", () => {
  it("marked seed in a literal ID pair", () => {
    const bytes = classicPdf(
      `<< /Size 2 /Root 1 0 R /ID [(LLMPROOF-${SEED})(LLMPROOF-${SEED})] >>`,
    );
    expect(core(bytes)).toEqual({ kind: "seed", seed: SEED, encrypted: false });
  });

  it("encrypted flag from the /Encrypt key (value never resolved)", () => {
    const bytes = classicPdf(
      `<< /Size 2 /Root 1 0 R /Encrypt 3 0 R /ID [(LLMPROOF-${SEED})] >>`,
    );
    expect(core(bytes)).toEqual({ kind: "seed", seed: SEED, encrypted: true });
  });

  it("/Encrypt without /ID → no-seed, encrypted", () => {
    const bytes = classicPdf(`<< /Size 2 /Root 1 0 R /Encrypt 3 0 R >>`);
    expect(core(bytes)).toEqual({ kind: "no-seed", encrypted: true });
  });

  it("name #-escape: /I#44 is the /ID key", () => {
    const bytes = classicPdf(
      `<< /Size 2 /Root 1 0 R /I#44 [(LLMPROOF-${SEED})] >>`,
    );
    expect(core(bytes)).toEqual({ kind: "seed", seed: SEED, encrypted: false });
  });

  it("literal-string escapes decode before the marker check (octal)", () => {
    // \114 (octal) is 'L': (L\114MPROOF-…) decodes to (LLMPROOF-…).
    const bytes = classicPdf(
      `<< /Size 2 /Root 1 0 R /ID [(L\\114MPROOF-${SEED})] >>`,
    );
    expect(core(bytes)).toEqual({ kind: "seed", seed: SEED, encrypted: false });
  });

  it("literal-string backslash-EOL continuation", () => {
    // The backslash+LF inside the string is removed by the tokenizer.
    const bytes = classicPdf(
      `<< /Size 2 /Root 1 0 R /ID [(LLMPROOF\\\n-${SEED})] >>`,
    );
    expect(core(bytes)).toEqual({ kind: "seed", seed: SEED, encrypted: false });
  });

  it("nested parens are content, not delimiters", () => {
    // The string's content is "(LLMPROOF-…)" — it does not start with the marker.
    const bytes = classicPdf(
      `<< /Size 2 /Root 1 0 R /ID [((LLMPROOF-${SEED}))] >>`,
    );
    expect(core(bytes)).toEqual({ kind: "no-seed", encrypted: false });
  });

  it("an escaped ')' inside the seed string breaks the 32-hex rule", () => {
    // \\) is decoded to a content ')' after the 32 hex digits; the final ) closes the string.
    const bytes = classicPdf(
      `<< /Size 2 /Root 1 0 R /ID [(LLMPROOF-${SEED}\\))] >>`,
    );
    expect(core(bytes)).toEqual({ kind: "no-seed", encrypted: false });
  });

  it("multi-line /ID array", () => {
    const bytes = classicPdf(
      `<< /Size 2 /Root 1 0 R /ID [\n  (LLMPROOF-${SEED})\n  (LLMPROOF-${SEED})\n] >>`,
    );
    expect(core(bytes)).toEqual({ kind: "seed", seed: SEED, encrypted: false });
  });

  it("hex-string first element without the marker → no-seed", () => {
    const bytes = classicPdf(`<< /Size 2 /Root 1 0 R /ID [<${SEED}>] >>`);
    expect(core(bytes)).toEqual({ kind: "no-seed", encrypted: false });
  });

  it("hex-stored marked seed decodes before the marker check (qpdf form)", () => {
    // qpdf serializes /ID as hex strings; the decoded value still carries the seed.
    const bytes = classicPdf(
      `<< /Size 2 /Root 1 0 R /ID [${hexString(`LLMPROOF-${SEED}`)}] >>`,
    );
    expect(core(bytes)).toEqual({ kind: "seed", seed: SEED, encrypted: false });
  });

  it("odd-length hex string: final digit assumed 0 (§7.3.4.3 EXAMPLE 2)", () => {
    // The missing final digit is zero-APPENDED, not a leading zero (<901FA>
    // is 90 1F A0). 81 digits here: a spec-conformant decode ends in 0x30
    // ("0") and still carries the seed; a left-padded misread would start
    // with a control byte and yield no-seed, so this pins the convention.
    const s = "12345678901234567890123456789010"; // 32 hex chars, ends in "0"
    const even = hexString(`LLMPROOF-${s}`).slice(1, -1); // the 82-digit form
    const odd = even.slice(0, -2) + "3"; // drop the "30" pair, keep a lone "3"
    const bytes = classicPdf(`<< /Size 2 /Root 1 0 R /ID [<${odd}>] >>`);
    expect(core(bytes)).toEqual({ kind: "seed", seed: s, encrypted: false });
  });

  it("indirect /ID (reference) → no-seed, never resolved", () => {
    const bytes = classicPdf(`<< /Size 2 /Root 1 0 R /ID 3 0 R >>`);
    expect(core(bytes)).toEqual({ kind: "no-seed", encrypted: false });
  });

  it("seed hex is case-insensitive and returned lowercase", () => {
    const upper = SEED.toUpperCase();
    const bytes = classicPdf(
      `<< /Size 2 /Root 1 0 R /ID [(LLMPROOF-${upper})] >>`,
    );
    expect(core(bytes)).toEqual({ kind: "seed", seed: SEED, encrypted: false });
  });

  it("mismatched marker → no-seed (same signal as the CLI)", () => {
    const bytes = classicPdf(`<< /Size 2 /Root 1 0 R /ID [(ACME-${SEED})] >>`);
    expect(core(bytes)).toEqual({ kind: "no-seed", encrypted: false });
    expect(core(bytes, "ACME")).toEqual({
      kind: "seed",
      seed: SEED,
      encrypted: false,
    });
  });

  it("MARKER_DEFAULT is LLMPROOF", () => {
    expect(MARKER_DEFAULT).toBe("LLMPROOF");
  });
});

describe("core: xref-stream dictionaries", () => {
  it("marked seed in the xref-stream dictionary", () => {
    const bytes = xrefStreamPdf(`/ID [(LLMPROOF-${SEED})(LLMPROOF-${SEED})]`);
    expect(core(bytes)).toEqual({ kind: "seed", seed: SEED, encrypted: false });
  });

  it("encrypted flag from /Encrypt in the xref-stream dictionary", () => {
    const bytes = xrefStreamPdf(`/Encrypt 4 0 R /ID [(LLMPROOF-${SEED})]`);
    expect(core(bytes)).toEqual({ kind: "seed", seed: SEED, encrypted: true });
  });

  it("an object dictionary without a stream keyword is rejected", () => {
    // Same header/obj/dict shape, but `endobj` (not `stream`) follows the dict.
    const header = "%PDF-1.4\n";
    const objStart = header.length;
    const bytes = ascii(
      `${header}42 0 obj\n<< /Size 2 >>\nendobj\nstartxref\n${objStart}\n%%EOF\n`,
    );
    expect(core(bytes)).toEqual({ kind: "not-a-pdf" });
  });
});

describe("core: startxref candidates", () => {
  it("a corrupt last startxref (in range, wrong structure) falls back to the earlier one", () => {
    // Offset 9 is the body object `1 0 obj << /Type /Catalog >>` — its dict
    // parses but carries no trailer key, so the candidate is rejected.
    const bytes = classicPdfWithCorruptTail(
      `<< /Size 2 /Root 1 0 R /ID [(LLMPROOF-${SEED})] >>`,
      9,
    );
    expect(core(bytes)).toEqual({ kind: "seed", seed: SEED, encrypted: false });
  });

  it("an out-of-range last startxref is dropped, the earlier one wins", () => {
    const bytes = classicPdfWithCorruptTail(
      `<< /Size 2 /Root 1 0 R /ID [(LLMPROOF-${SEED})] >>`,
      999_999_999,
    );
    expect(core(bytes)).toEqual({ kind: "seed", seed: SEED, encrypted: false });
  });

  it("no parseable candidate at all → not-a-pdf", () => {
    const bytes = ascii("%PDF-1.4\nstartxref\n0\n%%EOF\n");
    expect(core(bytes)).toEqual({ kind: "not-a-pdf" });
  });
});

describe("core: not-a-pdf shapes", () => {
  it("non-PDF bytes", () => {
    expect(core(ascii("hello world, definitely not a pdf"))).toEqual({
      kind: "not-a-pdf",
    });
  });

  it("empty input", () => {
    expect(core(new Uint8Array(0))).toEqual({ kind: "not-a-pdf" });
  });

  it("PDF header but no startxref", () => {
    expect(core(ascii("%PDF-1.4\njust some text\n"))).toEqual({
      kind: "not-a-pdf",
    });
  });
});
