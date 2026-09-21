"""Re-derive the password for a protected PDF from its file ID and the salt."""

import pymupdf as fitz

from .password import derive_password
from .seed import MARKER_DEFAULT, parse_seed


def get_password(input_path: str, salt: str, marker: str = MARKER_DEFAULT) -> str:
    """Re-derive the password from a protected PDF and the user's salt.

    Reads the marked seed from the PDF's unencrypted file ID; no original
    document, canary spec, or authentication step is involved.
    """
    doc = fitz.open(input_path)
    try:
        if not doc.needs_pass:
            raise ValueError("not a password-protected PDF")
        _t, id_value = doc.xref_get_key(-1, "ID")
        seed = parse_seed(id_value, marker)
        if seed is None:
            raise ValueError(
                f'no "{marker}" seed in the PDF\'s file ID: '
                "the file was not created by llm-proof protect, "
                "or it was protected with a different marker"
            )
        return derive_password(salt, seed)
    finally:
        doc.close()
