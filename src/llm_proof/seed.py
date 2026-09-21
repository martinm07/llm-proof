"""Canonical content extraction, seed derivation, and marker handling."""

import hashlib
import re
from typing import Any

MARKER_DEFAULT = "LLMPROOF"
MARKER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def extract_words(page) -> list[Any]:
    """Extract words with coordinates in reading order.

    Returns list of (x0, y0, x1, y1, word, block, line, word_index) tuples.
    """
    return page.get_text("words")


def get_freetext_annotations(page) -> list[Any]:
    """Get all FreeText annotations and their rects.

    Returns list of annotation objects with 'rect' and 'type' attributes.
    """
    annotations = []
    for annot in page.annots():
        if annot.type[0] == 2:  # FreeText annotation type
            annotations.append(annot)
    return annotations


def extract_canonical_content(doc) -> str:
    """Extract canonical content from the entire document.

    Reads all pages, extracts words, excludes FreeText annotation words,
    and returns the canonical text string.
    """
    canonical_parts = []

    for page in doc:
        words = extract_words(page)
        freetext_annots = get_freetext_annotations(page)

        # Build set of word indices inside FreeText annotations
        excluded_indices = set()
        for annot in freetext_annots:
            annot_rect = annot.rect
            for i, w in enumerate(words):
                wx, wy, _, _, _, _, _, _ = w
                # Check if word center is inside annotation rect
                center_x = (wx + w[2]) / 2
                center_y = (wy + w[3]) / 2
                if (
                    annot_rect.x0 <= center_x <= annot_rect.x1
                    and annot_rect.y0 <= center_y <= annot_rect.y1
                ):
                    excluded_indices.add(i)

        # Build page text excluding excluded words
        page_text_parts = []
        for i, w in enumerate(words):
            if i not in excluded_indices:
                page_text_parts.append(w[4])

        canonical_parts.append(" ".join(page_text_parts))

    return "\n".join(canonical_parts)


def derive_seed(canonical_content: str) -> str:
    """Derive the per-document seed from canonical content.

    Returns the first 16 bytes of sha256(canonical content) as 32 lowercase
    hex characters.
    """
    return hashlib.sha256(canonical_content.encode("utf-8")).digest()[:16].hex()


def validate_marker(marker: str) -> None:
    """Raise ValueError if the marker is not a valid marker label."""
    if not MARKER_RE.match(marker):
        raise ValueError(
            f'invalid marker "{marker}": must start with a letter or digit '
            "and contain only letters, digits, dashes and underscores"
        )


def seed_literal(marker: str, seed: str) -> str:
    """Return the marked seed as a PDF literal string, e.g. (LLMPROOF-<seed>)."""
    return f"({marker}-{seed})"


def parse_seed(id_value: str, marker: str) -> str | None:
    """Extract the seed from a raw /ID value, or return None.

    id_value is the raw value string from xref_get_key(-1, "ID"), e.g.
    '[(LLMPROOF-f66f…cc04a8)<8FF36D3E…>]'. The first element must be a
    literal string starting with '<marker>-' followed by exactly 32 hex
    characters (case-insensitive); the seed is returned in lowercase. A hex
    first element (or any other shape) means the file carries no seed: None.
    """
    literal = re.match(r"\[\(([^)]*)\)", id_value)
    if literal is None:
        # Hex first element (or a malformed value): seeds are only ever
        # carried in a literal first element.
        return None
    first = literal.group(1)
    prefix = f"{marker}-"
    if not first.startswith(prefix):
        return None
    rest = first[len(prefix) :]
    if not re.fullmatch(r"[0-9a-fA-F]{32}", rest):
        return None
    return rest.lower()
