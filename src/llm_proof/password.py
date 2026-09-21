"""Password derivation from seed and salt."""

import hashlib


def derive_password(salt: str, seed: str) -> str:
    """Derive the PDF password from salt and per-document seed.

    Returns a 24-character lowercase hex string.
    """
    salt_bytes = salt.encode("utf-8")
    seed_bytes = seed.encode("utf-8")
    digest = hashlib.sha256(salt_bytes + seed_bytes).hexdigest()
    return digest[:24]
