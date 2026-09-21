"""Experiment 2: can we set the file ID?"""

import os

import pymupdf as fitz

if not os.path.exists("/tmp/plain.pdf"):
    d = fitz.open()
    d.new_page().insert_text((72, 72), "hello", fontsize=12)
    d.save("/tmp/plain.pdf")
    d.close()

doc = fitz.open("/tmp/plain.pdf")
print("pdf_trailer:", doc.pdf_trailer())
try:
    print("_getPDFfileid:", doc._getPDFfileid())
except Exception as e:
    print("_getPDFfileid error:", e)

# Any trailer-setter-ish methods?
t_api = [
    a
    for a in dir(doc)
    if "trailer" in a.lower() or "fileid" in a.lower() or "file_id" in a.lower()
]
print("trailer/fileid API:", t_api)

# Is the trailer reachable via an xref? Try a few candidate xrefs with xref_get_key.
for x in (0, doc.xref_length() - 1, -1):
    try:
        keys = doc.xref_get_keys(x)
        print(f"xref {x} keys: {keys}")
    except Exception as e:
        print(f"xref {x}: {e}")

# Try setting ID via xref_set_key on candidate xrefs
for x in (0, doc.xref_length() - 1):
    try:
        doc.xref_set_key(x, "ID", "[<DEADBEEFDEADBEEFDEADBEEFDEADBEEF>(x)>")
        print(f"set_key on xref {x}: OK")
    except Exception as e:
        print(f"set_key on xref {x}: {e}")

doc.save("/tmp/tryset.pdf")
doc.close()
raw = open("/tmp/tryset.pdf", "rb").read()
idx = raw.rfind(b"/ID")
print(
    "\nID after set attempts:",
    raw[idx : idx + 80].decode("latin-1") if idx >= 0 else "none",
)
