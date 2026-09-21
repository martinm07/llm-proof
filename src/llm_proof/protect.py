"""PDF protection: password-protect, carry the seed in the file ID, insert canaries."""

import os

import pymupdf as fitz

from .seed import MARKER_DEFAULT, derive_seed, extract_canonical_content, seed_literal


def protect_pdf(
    input_path: str,
    output_path: str,
    salt: str,
    canaries_file: str | None = None,
    marker: str = MARKER_DEFAULT,
) -> tuple[str, int, str]:
    """Protect a PDF: derive the seed from canonical content, carry it in the
    file ID, insert canaries, and apply the password.

    Canaries never contribute to the password; the seed is computed from the
    plain document before canary insertion.

    Returns (output_path, inserted_count, password).
    """
    from .canaries import insert_all_canaries, parse_canary_spec
    from .password import derive_password

    doc = fitz.open(input_path)

    # Check if document is already encrypted
    if doc.needs_pass:
        doc.close()
        raise ValueError("Input PDF is already password-protected.")

    tmp_path: str | None = None
    try:
        # Canonical content and seed before canary insertion: canaries never
        # contribute to the password
        canonical = extract_canonical_content(doc)
        seed = derive_seed(canonical)
        password = derive_password(salt, seed)

        # Carry the marked seed in the file ID. Both elements are the same
        # literal (the verified-safe write; a literal must never sit at ID[1])
        literal = seed_literal(marker, seed)
        id_value = f"[{literal}{literal}]"
        doc.xref_set_key(-1, "ID", id_value)  # pyright: ignore[reportUnknownArgumentType]
        # PyMuPDF silently drops the ID when the trailer is a cross-reference
        # stream: a plain save normalises to a classic xref table, where the
        # write succeeds. Verify by read-back and do that round-trip if needed.
        _type, stored = doc.xref_get_key(-1, "ID")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if not stored.startswith(f"[{literal}"):
            tmp_path = output_path + ".tmp"
            doc.save(tmp_path)
            new_doc = fitz.open(tmp_path)
            doc.close()
            doc = new_doc
            doc.xref_set_key(-1, "ID", id_value)  # pyright: ignore[reportUnknownArgumentType]
            _type, stored = doc.xref_get_key(-1, "ID")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            if not stored.startswith(f"[{literal}"):
                raise ValueError("could not write the seed into the PDF's file ID")

        # Insert canaries
        inserted = 0
        if canaries_file:
            with open(canaries_file, "r") as f:
                spec_text = f.read()

            canaries = parse_canary_spec(spec_text)
            inserted = insert_all_canaries(doc, canaries)

        # Save with password protection
        doc.save(
            output_path,
            encryption=fitz.PDF_ENCRYPT_AES_256,  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownArgumentType]
            user_pw=password,
            owner_pw=password,
        )

        return output_path, inserted, password

    finally:
        doc.close()
        if tmp_path is not None and os.path.exists(tmp_path):
            os.remove(tmp_path)
