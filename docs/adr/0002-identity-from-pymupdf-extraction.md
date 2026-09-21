# Document identity is defined by PyMuPDF's text extraction

Canonical content is whatever PyMuPDF's per-page word extraction yields: reading order, whitespace-normalised, excluding words inside FreeText annotation rects. The derived password must re-derive identically across machines and time, so PyMuPDF is pinned exactly (`==` in `pyproject.toml`), and bumping the pin is a breaking change: protected documents created under one pin will no longer re-derive under another.

## Considered options

- Hashing the raw PDF bytes: rejected — annotations change the file's bytes even though the document's identity must not change.
- A custom extraction implementation: rejected — it would be a moving target; PyMuPDF's extraction is the stable, testable reference.

## Consequences

- The derived password is the first 24 lowercase hex characters of `sha256(salt ‖ canonical_content)` (96 bits), set as both the user and the owner password — deliberately shorter than the full digest.
