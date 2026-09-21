"""Experiment 3: set the file ID via trailer xref -1."""

import os

import pymupdf as fitz

if not os.path.exists("/tmp/plain.pdf"):
    d = fitz.open()
    d.new_page().insert_text((72, 72), "hello", fontsize=12)
    d.save("/tmp/plain.pdf")
    d.close()

doc = fitz.open("/tmp/plain.pdf")
print("ID before:", doc.xref_get_key(-1, "ID"))

my_id = "[<DEADBEEFDEADBEEFDEADBEEFDEADBEEF>(second)>]"
try:
    doc.xref_set_key(-1, "ID", my_id)
    print("set_key(-1, ID): OK")
except Exception as e:
    print("set_key(-1, ID) failed:", e)

print("ID after set:", doc.xref_get_key(-1, "ID"))

doc.save(
    "/tmp/setid.pdf",
    encryption=fitz.PDF_ENCRYPT_AES_256,
    user_pw="secret-pw",
    owner_pw="secret-pw",
)
doc.close()

raw = open("/tmp/setid.pdf", "rb").read()
idx = raw.rfind(b"/ID")
print(
    "\nRaw ID in saved+encrypted file:",
    raw[idx : idx + 80].decode("latin-1") if idx >= 0 else "none",
)

# Read it back WITHOUT password
doc = fitz.open("/tmp/setid.pdf")
print("needs_pass:", doc.needs_pass)
print("ID read without password:", doc.xref_get_key(-1, "ID"))
doc.close()

# And with wrong/missing authenticate - still readable?
doc = fitz.open("/tmp/setid.pdf")
print("ID with no auth:", doc.xref_get_key(-1, "ID"))
doc.close()
