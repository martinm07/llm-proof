"""Experiment: can we control/read the PDF file ID in PyMuPDF 1.28.2?"""

import pymupdf as fitz

print("PyMuPDF version:", fitz.version)

# 1. What ID-related API surface exists on Document?
id_api = [
    a
    for a in dir(fitz.Document)
    if "id" in a.lower() or "trailer" in a.lower() or "xref" in a.lower()
]
print("\nDocument API with id/trailer/xref:", id_api)

# 2. Make a plain PDF, look at its raw trailer
doc = fitz.open()
page = doc.new_page()
page.insert_text((72, 72), "hello", fontsize=12)
doc.save("/tmp/plain.pdf")
doc.close()

raw = open("/tmp/plain.pdf", "rb").read()
idx = raw.rfind(b"trailer")
print(
    "\nPlain trailer region:",
    raw[idx : idx + 200].decode("latin-1")
    if idx >= 0
    else "NO 'trailer' keyword (xref stream?)",
)

# 3. Encrypt it, then inspect the raw trailer of the encrypted file
doc = fitz.open("/tmp/plain.pdf")
doc.save(
    "/tmp/enc.pdf",
    encryption=fitz.PDF_ENCRYPT_AES_256,
    user_pw="userpass",
    owner_pw="ownerpass",
)
doc.close()

raw = open("/tmp/enc.pdf", "rb").read()
idx = raw.rfind(b"trailer")
print(
    "\nEncrypted trailer region:",
    raw[idx : idx + 300].decode("latin-1")
    if idx >= 0
    else "NO 'trailer' keyword (xref stream?)",
)

# 4. Can we read the file ID without the password?
doc = fitz.open("/tmp/enc.pdf")
print("\nneeds_pass:", doc.needs_pass, "is_encrypted:", doc.is_encrypted)
for attr in ("trailer", "file_id", "id", "xref_trailer"):
    if hasattr(doc, attr):
        print(f"doc.{attr} =", getattr(doc, attr))
doc.close()

# 5. Does re-saving (incremental / full) change the ID?
raw_before = open("/tmp/enc.pdf", "rb").read()
doc = fitz.open("/tmp/enc.pdf")
doc.authenticate("userpass")
doc.save(
    "/tmp/resaved.pdf",
    encryption=fitz.PDF_ENCRYPT_AES_256,
    user_pw="userpass",
    owner_pw="ownerpass",
)
doc.close()
raw_after = open("/tmp/resaved.pdf", "rb").read()
idx_b = raw_before.rfind(b"/ID")
idx_a = raw_after.rfind(b"/ID")
print(
    "\nID before resave:",
    raw_before[idx_b : idx_b + 80].decode("latin-1") if idx_b >= 0 else "none",
)
print(
    "ID after resave: ",
    raw_after[idx_a : idx_a + 80].decode("latin-1") if idx_a >= 0 else "none",
)
