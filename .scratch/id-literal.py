"""Experiment: literal strings in the /ID trailer array.

Questions:
1. Does PyMuPDF accept [(lit)(lit)] as /ID and save it cleanly (no null artifact)?
2. What do the raw trailer bytes look like after an AES-256 save?
3. Can /ID be read back without a password?
4. Does a re-save (pipeline simulation) preserve ID[0]? What shape is the
   recomputed ID[1] (literal vs hex)?
5. How does mixing literal ID[0] with hex ID[1] behave?
"""

import hashlib
from pathlib import Path

import pymupdf as fitz

WORK = Path(__file__).parent
PW = "x" * 24
seed_hex = hashlib.sha256(b"experimental canonical content").hexdigest()[:32]
print(f"seed: {seed_hex!r}")


def fresh_pdf() -> fitz.Document:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello, experiment.", fontsize=12)
    return doc


def trail(data: bytes, label: str) -> None:
    i = data.rfind(b"startxref")
    print(f"=== {label}: raw tail ===")
    print(repr(data[max(0, i - 320) :]))


def show_id(doc: fitz.Document, label: str) -> None:
    k = doc.xref_get_key(-1, "ID")
    print(f"=== {label}: xref_get_key -> {k!r}")


def run(name: str, id_value: str) -> None:
    print(f"\n############ variant {name}: {id_value} ############")
    p1 = WORK / f"exp-{name}-1.pdf"
    p2 = WORK / f"exp-{name}-2.pdf"

    doc = fresh_pdf()
    doc.xref_set_key(-1, "ID", id_value)
    doc.save(p1, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw=PW, owner_pw=PW)
    doc.close()
    trail(p1.read_bytes(), f"{name} v1 (encrypted save)")

    d2 = fitz.open(p1)  # no password
    print(f"{name} v1: is_encrypted={d2.is_encrypted}, needs_pass={d2.needs_pass}")
    show_id(d2, f"{name} v1 no-pw read")
    assert d2.authenticate(PW), f"{name}: auth failed"
    d2.save(p2, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw=PW, owner_pw=PW)
    d2.close()
    trail(p2.read_bytes(), f"{name} v2 (resaved)")

    d3 = fitz.open(p2)
    show_id(d3, f"{name} v2 no-pw read")
    assert d3.authenticate(PW), f"{name} v2: auth failed"
    d3.close()


# A: two literals
run("A", f"[(LLMPROOF-{seed_hex})(LLMPROOF-{seed_hex})]")
# B: literal ID[0] + hex ID[1]
run("B", f"[(LLMPROOF-{seed_hex})<{seed_hex}>]")
# C: two hex (control, known clean)
run("C", f"[<{seed_hex}><{seed_hex}>]")
print("\nall variants OK")
