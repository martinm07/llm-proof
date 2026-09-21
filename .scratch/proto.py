"""Prototype: seed-in-file-ID password derivation, end to end."""

import hashlib
import os
import re
import sys

sys.path.insert(0, "src")

import pymupdf as fitz

from llm_proof.canaries import insert_all_canaries, parse_canary_spec
from llm_proof.password import derive_password


def make_plain(path, pages=3):
    doc = fitz.open()
    for i in range(pages):
        p = doc.new_page()
        p.insert_text(
            (72, 72),
            f"Page {i + 1}. The quick brown fox jumps over the lazy dog.",
            fontsize=12,
        )
        p.insert_text(
            (72, 100), f"More text on page {i + 1} to make it realistic.", fontsize=11
        )
    doc.save(path)
    doc.close()


def protect_with_seed(input_path, output_path, salt, canary_spec_text=None):
    doc = fitz.open(input_path)
    if doc.needs_pass:
        doc.close()
        raise ValueError("already protected")
    if canary_spec_text:
        insert_all_canaries(doc, parse_canary_spec(canary_spec_text))
    seed = os.urandom(16).hex()
    password = derive_password(salt, seed)
    doc.xref_set_key(-1, "ID", f"[<{seed}><{seed}>]")
    doc.save(
        output_path,
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw=password,
        owner_pw=password,
    )
    doc.close()
    return password, seed


def read_seed(input_path):
    doc = fitz.open(input_path)
    if not doc.needs_pass:
        doc.close()
        raise ValueError("not encrypted")
    t, v = doc.xref_get_key(-1, "ID")
    doc.close()
    m = re.search(r"<([0-9A-Fa-f]{32})>", v)
    if not m:
        raise ValueError(f"no llm-proof seed in ID: {v!r}")
    return m.group(1).lower()


def get_password_protected(input_path, salt):
    seed = read_seed(input_path)
    password = derive_password(salt, seed)
    doc = fitz.open(input_path)
    ok = doc.authenticate(password)
    doc.close()
    return password, ok


plain = "/tmp/proto_plain.pdf"
prot = "/tmp/proto_protected.pdf"
make_plain(plain)

SALT = "my-user-salt"
canaries = "Leak canary alpha.\n--- page: 2\nLeak canary beta.\n"

pw, seed = protect_with_seed(plain, prot, SALT, canaries)
print("protect -> password:", pw, "seed:", seed)

# 1. Re-derive from protected file + salt only (no canaries, no original)
pw2, ok = get_password_protected(prot, SALT)
print("re-derived:", pw2, "match:", pw == pw2, "authenticates:", bool(ok))

# 2. Wrong salt -> wrong password -> auth fails (good failure mode?)
pw3, ok3 = get_password_protected(prot, "wrong-salt")
print("wrong salt ->", pw3, "authenticates:", bool(ok3))

# 3. Canaries are still in the unlocked content (leak ID intact)?
doc = fitz.open(prot)
doc.authenticate(pw)
text = "".join(p.get_text() for p in doc)
print("canary alpha present:", "Leak canary alpha" in text)
print("canary beta present:", "Leak canary beta" in text)
doc.close()

# 4. Resave round-trip: does the seed survive? (simulate a pipeline re-saving the file)
doc = fitz.open(prot)
doc.authenticate(pw)
doc.save(
    "/tmp/proto_resaved.pdf",
    encryption=fitz.PDF_ENCRYPT_AES_256,
    user_pw=pw,
    owner_pw=pw,
)
doc.close()
raw = open("/tmp/proto_resaved.pdf", "rb").read()
idx = raw.rfind(b"/ID")
print("ID after pipeline resave:", raw[idx : idx + 90].decode("latin-1"))
pw4, ok4 = get_password_protected("/tmp/proto_resaved.pdf", SALT)
print("seed survives resave -> re-derived OK:", pw == pw4, bool(ok4))

# 5. Show raw ID shape of the protected file (check for the null quirk)
raw = open(prot, "rb").read()
idx = raw.rfind(b"/ID")
print("\nRaw ID of protected file:", raw[idx : idx + 90].decode("latin-1"))
