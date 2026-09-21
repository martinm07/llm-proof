"""Experiment 4: seed flow on an xref-stream PDF (PDF 1.5, modern producer style)."""

import re
import struct
import zlib

import pymupdf as fitz


def build_xref_stream_pdf(path):
    """Minimal PDF 1.5 whose xref table is a cross-reference stream."""
    header = b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n"
    body = []
    offsets = {}
    data = bytearray()

    def add_obj(num, payload):
        nonlocal data
        offsets[num] = len(data) + len(header)
        data += payload

    add_obj(1, b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    add_obj(2, b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    add_obj(
        3, b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
    )
    add_obj(5, b"")  # placeholder, filled below

    # Xref stream entries for objects 0..5, W = [1, 4, 2]
    entries = bytearray()
    entries += b"\x01\x00\x00\x00\x00\x00\x00"  # obj 0: free head
    for n in (1, 2, 3):
        entries += b"\x01" + struct.pack(">I", offsets[n]) + b"\x00\x00"
    entries += b"\x00\x00\x00\x00\x00\x00\xff\xff"  # obj 4: free
    # obj 5 offset filled after we know its position:
    off5 = offsets[5]
    entries += b"\x01" + struct.pack(">I", off5) + b"\x00\x00"

    stream_data = zlib.compress(bytes(entries))
    xref_obj = (
        b"5 0 obj\n<< /Type /XRef /Size 6 /W [1 4 2] /Root 1 0 R "
        b"/ID [<0123456789ABCDEF0123456789ABCDEF><FEDCBA9876543210FEDCBA9876543210]> "
        b"/Filter /FlateDecode /Length " + str(len(stream_data)).encode() + b" >>\n"
        b"stream\n" + stream_data + b"\nendstream\nendobj\n"
    )
    # Rewrite obj 5 payload (offset was recorded before, size changes only after offset start)
    out = bytearray(header + bytes(data))
    out[off5:] = xref_obj
    out += b"startxref\n" + str(off5).encode() + b"\n%%EOF\n"

    with open(path, "wb") as f:
        f.write(bytes(out))


p = ".scratch/xref_stream.pdf"
build_xref_stream_pdf(p)

raw = open(p, "rb").read()
print(repr(raw))
print("has classic trailer keyword:", b"trailer" in raw)
print("has XRef stream:", b"/Type /XRef" in raw)

doc = fitz.open(p)
print("pages:", len(doc), "| error:", doc.pdf_catalog() and "catalog ok")
print("ID (xref -1):", doc.xref_get_key(-1, "ID"))

seed = "deadbeefdeadbeefdeadbeefdeadbeef"
doc.xref_set_key(-1, "ID", f"[<{seed}><{seed}>]")
print("ID after set:", doc.xref_get_key(-1, "ID"))

doc.save(
    "/tmp/xref_stream_enc.pdf",
    encryption=fitz.PDF_ENCRYPT_AES_256,
    user_pw="pw123",
    owner_pw="pw123",
)
doc.close()

raw = open("/tmp/xref_stream_enc.pdf", "rb").read()
idx = raw.rfind(b"trailer")
print("\nencrypted output has classic trailer:", idx >= 0)
if idx >= 0:
    print(raw[idx : idx + 160].decode("latin-1"))
i2 = raw.rfind(b"/ID")
print(
    "ID in encrypted output:",
    raw[i2 : i2 + 90].decode("latin-1") if i2 >= 0 else "none",
)

doc = fitz.open("/tmp/xref_stream_enc.pdf")
print("\nneeds_pass:", doc.needs_pass)
print("seed read without pw:", doc.xref_get_key(-1, "ID"))
doc.close()
