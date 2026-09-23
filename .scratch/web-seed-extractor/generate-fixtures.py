"""Generate the four generated fixtures under web/tests/fixtures/.

ALREADY RUN ONCE. The committed bytes are the test input and the expected seed
is hardcoded in web/tests/extract-seed.test.ts — do NOT re-run unless a
fixture is broken (re-running regenerates the protected fixtures with fresh
PyMuPDF save metadata).

Run from the repo root:

    .venv/bin/python .scratch/web-seed-extractor/generate-fixtures.py

Produces (see spec.md §5 / §8 provenance table):
  web/tests/fixtures/protected-classic-llmproof.pdf  (llm-proof protect, default marker)
  web/tests/fixtures/protected-classic-acme.pdf      (llm-proof protect --marker ACME)
  web/tests/fixtures/plain-xrefstream-llmproof.pdf   (byte-patched copy of root test.pdf)
  web/tests/fixtures/garbage.bin                     (fixed non-PDF bytes)
"""

import hashlib
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = os.path.join(ROOT, "web", "tests", "fixtures")
CLI = os.path.join(ROOT, ".venv", "bin", "llm-proof")
SALT = "fixture-salt-0001"
TEXT = "llm proof fixture"

sys.path.insert(0, os.path.join(ROOT, "src"))
import pymupdf as fitz  # pyright: ignore[reportMissingImports]
from llm_proof.seed import derive_seed, extract_canonical_content  # noqa: E402


def sha256_of(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def last_startxref_offset(data: bytes) -> int:
    """Offset the file's last `startxref` points at."""
    matches = list(re.finditer(rb"startxref\s*(\d+)", data))
    assert matches, "no startxref found"
    return int(matches[-1].group(1))


def main() -> None:
    os.makedirs(FIX, exist_ok=True)
    input_path = "/tmp/input-plain.pdf"

    # 1. Small fixed plain input PDF (created with PyMuPDF; not committed —
    #    the protected outputs are the fixtures).
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), TEXT, fontsize=12)
    doc.save(input_path)
    doc.close()

    check = fitz.open(input_path)
    canonical = extract_canonical_content(check)
    seed = derive_seed(canonical)
    check.close()
    print(f"canonical content: {canonical!r}")
    print(f"seed: {seed}")
    assert re.fullmatch(r"[0-9a-f]{32}", seed), seed

    # 2. Protected fixtures via the repo's own protect CLI (fixed salt).
    for marker, out_name in (
        ("LLMPROOF", "protected-classic-llmproof.pdf"),
        ("ACME", "protected-classic-acme.pdf"),
    ):
        out_path = os.path.join(FIX, out_name)
        subprocess.run(
            [CLI, "protect", input_path, "-o", out_path, "--salt", SALT, "--marker", marker],
            check=True,
        )
        data = open(out_path, "rb").read()
        d = fitz.open(out_path)
        try:
            assert d.needs_pass, f"{out_name}: not encrypted"
            _type, idv = d.xref_get_key(-1, "ID")  # pyright: ignore[reportUnknownVariableType]
            # PyMuPDF's encrypted save keeps ID[0] as the marked literal but
            # rewrites ID[1] as a hex string; the extraction rule consults only
            # ID[0], so that is all that needs to hold (same check as protect.py).
            assert idv.startswith(f"[({marker}-{seed})"), f"{out_name}: ID {idv!r}"
            print(f"  stored ID: {idv!r}")
        finally:
            d.close()
        # Classic xref shape: last startxref points at the `xref` keyword.
        off = last_startxref_offset(data)
        assert data[off : off + 4] == b"xref", f"{out_name}: startxref {off} not at `xref`"
        print(f"{out_name}: ok (sha256 {sha256_of(out_path)})")

    # 3. plain-xrefstream-llmproof.pdf: byte-patched copy of the root test.pdf.
    #    The xref-stream dictionary is plain text even in this (unencrypted)
    #    file; inserting /ID into the dictionary does not touch /Length (which
    #    covers stream data only) and the startxref value stays valid because
    #    the insertion sits after the object start — verify, don't assume.
    data = open(os.path.join(ROOT, "test.pdf"), "rb").read()
    assert data.startswith(b"%PDF-1.7")
    obj_off = data.index(b"493 0 obj")
    assert data[obj_off : obj_off + 24] == b"493 0 obj\n<< /Type /XRef"
    off = last_startxref_offset(data)
    assert data[off : off + 9] == b"493 0 obj", f"startxref {off} not at the xref stream object"
    # §7.5.8: the startxref of a cross-reference stream points at the object
    # header (`493 0 obj`), so the dict insertion below must stay after it.
    assert off == obj_off, f"startxref {off} != xref stream object start {obj_off}"

    literal = f"(LLMPROOF-{seed})"
    needle = b"/Info 490 0 R\n>>"
    assert data.count(needle) == 1, "xref-stream dict anchor is not unique"
    repl = b"/Info 490 0 R\n   /ID [" + literal.encode("ascii") + literal.encode("ascii") + b"]\n>>"
    patched = data.replace(needle, repl)
    assert len(patched) > len(data)

    off2 = last_startxref_offset(patched)
    assert patched[off2 : off2 + 9] == b"493 0 obj", f"patched startxref {off2} invalid"

    out3 = os.path.join(FIX, "plain-xrefstream-llmproof.pdf")
    with open(out3, "wb") as f:
        f.write(patched)
    d = fitz.open(out3)
    try:
        assert not d.needs_pass, "patched file unexpectedly encrypted"
        _type, idv = d.xref_get_key(-1, "ID")  # pyright: ignore[reportUnknownVariableType]
        assert idv.startswith(f"[(LLMPROOF-{seed})"), f"patched ID {idv!r}"
    finally:
        d.close()
    print(f"plain-xrefstream-llmproof.pdf: ok (sha256 {sha256_of(out3)})")

    # 4. garbage.bin: fixed non-PDF bytes.
    out4 = os.path.join(FIX, "garbage.bin")
    with open(out4, "wb") as f:
        f.write(b"This is not a PDF file, just some arbitrary binary bytes.\n" + bytes(i % 251 for i in range(128)))
    print(f"garbage.bin: ok (sha256 {sha256_of(out4)})")

    os.remove(input_path)
    print("done")


if __name__ == "__main__":
    main()
