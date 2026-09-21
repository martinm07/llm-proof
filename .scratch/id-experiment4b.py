"""Experiment 4b: xref-stream PDF, UNCOMPRESSED xref data (no /Filter)."""

import struct

import pymupdf as fitz


def build(path, compress):
    header = b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n"
    data = bytearray()
    offsets = {}

    def add_obj(num, payload):
        nonlocal data
        offsets[num] = len(data) + len(header)
        data += payload

    add_obj(1, b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    add_obj(2, b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    add_obj(
        3, b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
    )
    add_obj(5, b"")

    entries = bytearray()
    entries += b"\x01\x00\x00\x00\x00\x00\x00"
    for n in (1, 2, 3):
        entries += b"\x01" + struct.pack(">I", offsets[n]) + b"\x00\x00"
    entries += b"\x00\x00\x00\x00\x00\x00\xff\xff"
    off5 = offsets[5]
    entries += b"\x01" + struct.pack(">I", off5) + b"\x00\x00"
    assert len(entries) == 42, len(entries)

    if compress:
        import zlib

        stream = zlib.compress(bytes(entries))
        filt = b"/Filter /FlateDecode "
    else:
        stream = bytes(entries)
        filt = b""

    xref_obj = (
        b"5 0 obj\n<< /Type /XRef /Size 6 /W [1 4 2] /Root 1 0 R "
        b"/ID [<0123456789ABCDEF0123456789ABCDEF><FEDCBA9876543210FEDCBA9876543210]> "
        + filt
        + b"/Length "
        + str(len(stream)).encode()
        + b" >>\n"
        b"stream\n" + stream + b"\nendstream\nendobj\n"
    )
    out = bytearray(header + bytes(data))
    out[off5:] = xref_obj
    out += b"startxref\n" + str(off5).encode() + b"\n%%EOF\n"
    with open(path, "wb") as f:
        f.write(bytes(out))
    return off5


for compress in (False, True):
    p = f".scratch/xref4b_{'fl' if compress else 'plain'}.pdf"
    off5 = build(p, compress)
    raw = open(p, "rb").read()
    print(
        f"--- compress={compress}, startxref={off5}, actual offset of '5 0 obj'={raw.find(b'5 0 obj')}"
    )
    try:
        doc = fitz.open(p)
        print("opened OK, pages:", len(doc))
        print("ID:", doc.xref_get_key(-1, "ID"))
        seed = "deadbeefdeadbeefdeadbeefdeadbeef"
        doc.xref_set_key(-1, "ID", f"[<{seed}><{seed}>]")
        print("ID after set:", doc.xref_get_key(-1, "ID"))
        enc = p.replace(".pdf", "_enc.pdf")
        doc.save(
            enc, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="pw123", owner_pw="pw123"
        )
        doc.close()
        raw2 = open(enc, "rb").read()
        i = raw2.rfind(b"/ID")
        print(
            "ID in encrypted output:",
            raw2[i : i + 90].decode("latin-1") if i >= 0 else "NONE",
        )
        print("encrypted output has classic trailer:", raw2.rfind(b"trailer") >= 0)
        d2 = fitz.open(enc)
        print(
            "needs_pass:", d2.needs_pass, "| ID without pw:", d2.xref_get_key(-1, "ID")
        )
        d2.close()
    except Exception as e:
        print("FAILED:", type(e).__name__, e)
        print("file repr:", repr(raw[:400]))
